"""Behaviour checks for the project list, its navigation inputs, the peeks and
gallery switching.

Covers the unified one-project-per-gesture rule (wheel and touch), the clamps at
either end, the photo-panel wheel, the info view, keyboard arrows, realignment
after viewport changes, the neighbour peeks sharing one capacity rule at every
viewport, and the opacity-only gallery switch staying visible and interactive.

Run directly, with no Python packages installed:

    python3 tests/test_project_scroll.py

Or through pytest:

    pytest tests/test_project_scroll.py

Either way Chromium or Chrome has to be installed; the test serves the
repository itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cdp import BrowserSession, find_browser, skip_without_browser

ROOT = Path(__file__).resolve().parents[1]
SETTLE_MS = 600  # transition is 0.35 s; leave room for image loads too
GALLERY_X = 120  # inside the left project panel on a 1280 px viewport
GALLERY_Y = 300
PHOTO_X = 900  # inside the photo panel
PHOTO_Y = 400

PEEK_MAX = 5  # mirrors PEEK_MAX in assets/scripts/script.js


def state(session: BrowserSession) -> dict[str, Any]:
    """Current project-list and photo-view state."""
    return session.js("""(() => {
        const gallery = document.getElementById('project-gallery');
        const active = document.querySelector('.project-title.active .project-title-text');
        return {
            transform: getComputedStyle(gallery).transform,
            active: active ? active.textContent.trim() : null,
            activeIndex: [...document.querySelectorAll('.project-title')]
                .findIndex(title => title.classList.contains('active')),
            rows: document.querySelectorAll('.project-title').length,
            rowHeight: parseFloat(getComputedStyle(document.querySelector('.project-title')).height),
            counter: document.getElementById('image-counter').textContent,
            info: document.getElementById('gallery-container').classList.contains('info-active'),
        };
    })()""")


def translate_y(transform: str | None) -> float:
    """Vertical offset of a computed `matrix(...)` transform."""
    if not transform or transform == "none":
        return 0.0
    return float(transform.split(",")[-1].rstrip(")"))


def snapped_to(current: dict[str, Any]) -> bool:
    """True when the list rests exactly on a project row."""
    return (
        abs(
            translate_y(current["transform"])
            + current["activeIndex"] * current["rowHeight"]
        )
        < 0.01
    )


def peek_state(session: BrowserSession) -> dict[str, Any]:
    """Neighbour-peek counts and geometry relative to the photo panel."""
    return session.js("""(() => {
        const panel = document.getElementById('main-display').getBoundingClientRect();
        const photo = document.getElementById('featured-image').getBoundingClientRect();
        const counter = document.getElementById('image-counter').textContent.split('/');
        const strip = (id) => {
            const element = document.getElementById(id);
            const rect = element.getBoundingClientRect();
            return {
                count: element.children.length,
                left: rect.left - panel.left,
                right: rect.right - panel.left,
            };
        };
        return {
            index: Number(counter[0].trim()) - 1,
            total: Number(counter[1].trim()),
            panelWidth: panel.width,
            photoLeft: photo.left - panel.left,
            photoRight: photo.right - panel.left,
            prev: strip('prev-peeks'),
            next: strip('next-peeks'),
            mobileLayout: window.matchMedia('(max-width: 768px)').matches,
        };
    })()""")


def assert_peeks_clear_of_photo(current: dict[str, Any]) -> None:
    """Each non-empty strip sits in the gutter, inside the panel and off the photo."""
    if current["prev"]["count"]:
        assert current["prev"]["right"] <= current["photoLeft"] + 1, (
            f"the previous strip should stay left of the photo: {current}"
        )
        assert current["prev"]["left"] >= -0.5, (
            f"the previous strip should stay inside the panel: {current}"
        )
    if current["next"]["count"]:
        assert current["next"]["left"] >= current["photoRight"] - 1, (
            f"the next strip should stay right of the photo: {current}"
        )
        assert current["next"]["right"] <= current["panelWidth"] + 0.5, (
            f"the next strip should stay inside the panel: {current}"
        )


def test_project_scroll() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        start = state(session)
        assert start["rows"] >= 2, (
            f"the tests need at least two projects, got {start['rows']}"
        )
        assert start["activeIndex"] == 0, (
            f"the first project should be selected at start: {start}"
        )
        assert translate_y(start["transform"]) == 0, (
            f"the list should start at rest: {start}"
        )
        height = start["rowHeight"]
        rows = start["rows"]

        # One wheel notch moves exactly one project and lands on a row.
        session.wheel(GALLERY_X, GALLERY_Y, 100)
        session.wait(SETTLE_MS)
        after = state(session)
        assert after["activeIndex"] == 1, (
            f"one wheel notch should advance one project: {after}"
        )
        assert snapped_to(after), f"the list should snap to row 1: {after}"

        # Below the 30 px gesture threshold nothing moves.
        session.wheel(GALLERY_X, GALLERY_Y, 20)
        session.wait(SETTLE_MS)
        nudged = state(session)
        assert nudged["activeIndex"] == 1, (
            f"a 20 px nudge should not change project: {nudged}"
        )

        # A stream of small events, as a trackpad flick and its momentum produce,
        # is still one gesture and one step. A gallery with two projects only has
        # room for a clamp check at the last row, so assert the reachable index.
        deepest = min(2, rows - 1)
        session.wheel(GALLERY_X, GALLERY_Y, 20, count=10, gap_ms=10)
        session.wait(SETTLE_MS)
        stream = state(session)
        assert stream["activeIndex"] == deepest, (
            f"a wheel stream should step exactly one project: {stream}"
        )
        assert snapped_to(stream), f"the stream should end on row {deepest}: {stream}"

        # Reversing the direction is a new gesture.
        session.wheel(GALLERY_X, GALLERY_Y, -100)
        session.wait(SETTLE_MS)
        back = state(session)
        assert back["activeIndex"] == max(deepest - 1, 0), (
            f"wheel up should go back one project: {back}"
        )

        # The first project is a hard stop: no half row of overscroll.
        session.wheel(GALLERY_X, GALLERY_Y, -100)
        session.wait(SETTLE_MS)
        top = state(session)
        assert top["activeIndex"] == 0, (
            f"wheel up at the first project should stay put: {top}"
        )
        assert translate_y(top["transform"]) == 0, (
            f"no overscroll above the first row: {top}"
        )

        # The last project is a hard stop too.
        for _ in range(rows + 2):
            session.wheel(GALLERY_X, GALLERY_Y, 100)
            session.wait(250)
        session.wait(SETTLE_MS)
        bottom = state(session)
        assert bottom["activeIndex"] == rows - 1, (
            f"the list should reach the last project: {bottom}"
        )
        assert snapped_to(bottom), (
            f"the last row should sit on the cursor line: {bottom}"
        )
        session.wheel(GALLERY_X, GALLERY_Y, 100)
        session.wait(SETTLE_MS)
        clamped = state(session)
        assert clamped["activeIndex"] == rows - 1, (
            f"wheel down at the last project should stay put: {clamped}"
        )
        assert snapped_to(clamped), f"no overscroll below the last row: {clamped}"

        # A horizontal gesture belongs to the gallery-name row, not the projects.
        session.wheel(GALLERY_X, GALLERY_Y, 0, delta_x=120)
        session.wait(SETTLE_MS)
        horizontal = state(session)
        assert horizontal["activeIndex"] == rows - 1, (
            f"a horizontal wheel should not change project: {horizontal}"
        )

        # The photo panel keeps its own wheel navigation.
        counter_before = horizontal["counter"]
        session.wheel(PHOTO_X, PHOTO_Y, 100)
        session.wait_until(
            lambda: state(session)["counter"] != counter_before,
            timeout=4,
            message=f"the photo wheel should change slide (still {counter_before})",
        )

        # While the info view is open the wheel belongs to the text.
        session.js("document.getElementById('about').click()")
        session.wait(700)
        info = state(session)
        assert info["info"] is True, f"the About view should open: {info}"
        project_before_info = info["activeIndex"]
        session.wheel(200, 450, 120, count=3, gap_ms=20)
        session.wait(SETTLE_MS)
        reading = state(session)
        assert reading["activeIndex"] == project_before_info, (
            f"wheel in the info view should not change project: {reading}"
        )
        counter_before_info = reading["counter"]
        session.wheel(PHOTO_X, PHOTO_Y, 100)
        session.wait(300)
        assert state(session)["counter"] == counter_before_info, (
            "the photo wheel should be ignored in the info view"
        )

        session.js("document.getElementById('back').click()")
        session.wait(700)
        closed = state(session)
        assert closed["info"] is False, f"Back should close the info view: {closed}"
        assert closed["activeIndex"] == project_before_info, (
            f"closing should keep the project: {closed}"
        )
        assert snapped_to(closed), f"closing should realign the list: {closed}"

        # Keyboard arrows still step one project.
        session.key("ArrowUp", "ArrowUp", 38)
        session.wait(SETTLE_MS)
        arrowed = state(session)
        assert arrowed["activeIndex"] == project_before_info - 1, (
            f"ArrowUp should go back one project: {arrowed}"
        )
        assert snapped_to(arrowed), f"ArrowUp should land on a row: {arrowed}"
        session.key("ArrowDown", "ArrowDown", 40)
        session.wait(SETTLE_MS)
        arrowed = state(session)
        assert arrowed["activeIndex"] == project_before_info, (
            f"ArrowDown should return to the project: {arrowed}"
        )

        # Crossing the mobile breakpoint re-measures the row and keeps the
        # selection aligned instead of drifting.
        session.set_viewport(500, 800)
        session.wait(700)
        narrow = state(session)
        assert narrow["rowHeight"] < height, (
            f"the mobile row should be shorter: {narrow['rowHeight']} vs {height}"
        )
        assert narrow["activeIndex"] == project_before_info, (
            f"resize should keep the project: {narrow}"
        )
        assert snapped_to(narrow), f"resize should realign the list: {narrow}"
        session.clear_viewport()
        session.wait(700)
        restored = state(session)
        assert restored["activeIndex"] == project_before_info, (
            f"restoring the viewport should keep the project: {restored}"
        )
        assert snapped_to(restored), (
            f"restoring the viewport should realign the list: {restored}"
        )

        # Touch keeps the same one-gesture rule on the mobile layout. Start from
        # the first project so a swipe up has room to move.
        session.set_viewport(500, 800)
        session.wait(700)
        session.js("document.querySelectorAll('.project-title')[0].click()")
        session.wait(SETTLE_MS)
        before_swipe = state(session)
        assert before_swipe["activeIndex"] == 0, (
            f"the first title should select the first project: {before_swipe}"
        )
        session.touch_swipe(250, 700, 0, -80)
        session.wait(SETTLE_MS)
        swiped = state(session)
        assert swiped["activeIndex"] == 1, (
            f"a swipe up should advance one project: {before_swipe['activeIndex']} -> {swiped['activeIndex']}"
        )
        assert snapped_to(swiped), f"the swipe should land on a row: {swiped}"
        session.touch_swipe(250, 700, 0, -20)
        session.wait(SETTLE_MS)
        short = state(session)
        assert short["activeIndex"] == 1, (
            f"a 20 px swipe should not change project: {short}"
        )
        session.touch_swipe(250, 620, 0, 80)
        session.wait(SETTLE_MS)
        returned = state(session)
        assert returned["activeIndex"] == 0, (
            f"a swipe down should go back one project: {returned}"
        )

        # Uncaught page errors would indicate a broken listener; collect them.
        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all project scroll checks passed")


def test_neighbour_peeks() -> None:
    """The peeks use one capacity rule at every viewport.

    The strips hold as many neighbours as the gutter can take (up to the cap),
    at least one whenever that side has a neighbour, and none at the first and
    last slides. The photo keeps its box, so a strip never crosses into it.
    """
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        # A project with five or six photos gives a middle slide two neighbours
        # on each side without long keyboard walks.
        totals = []
        project_count = session.js("document.querySelectorAll('.project-title').length")
        for index in range(project_count):
            session.js(f"document.querySelectorAll('.project-title')[{index}].click()")
            session.wait(300)
            totals.append(
                session.js(
                    "Number(document.getElementById('image-counter').textContent"
                    ".split('/')[1])"
                )
            )
        candidates = [index for index, total in enumerate(totals) if total >= 5]
        assert candidates, f"the tests need a project with five photos: {totals}"
        chosen = min(candidates, key=lambda index: totals[index])
        session.js(f"document.querySelectorAll('.project-title')[{chosen}].click()")
        session.wait(SETTLE_MS)

        # First slide: nothing before it, a strip after it.
        first = peek_state(session)
        assert first["index"] == 0, (
            f"the project should start on its first slide: {first}"
        )
        assert first["prev"]["count"] == 0, (
            f"the first slide should have no previous peek: {first}"
        )
        assert first["next"]["count"] >= 1, (
            f"the first slide should show its next neighbour: {first}"
        )

        # Walk to a middle slide.
        for _ in range(2):
            session.key("ArrowRight", "ArrowRight", 39)
            session.wait(400)
        desktop = peek_state(session)
        assert desktop["index"] == 2, f"expected the third slide: {desktop}"
        assert desktop["mobileLayout"] is False, (
            f"1280 px should use the desktop layout: {desktop}"
        )
        for side in ("prev", "next"):
            count = desktop[side]["count"]
            available = (
                desktop["index"]
                if side == "prev"
                else desktop["total"] - 1 - desktop["index"]
            )
            assert 1 <= count <= PEEK_MAX, (
                f"the desktop {side} strip should hold 1..{PEEK_MAX}: {desktop}"
            )
            assert count <= available, (
                f"the {side} strip should not repeat or invent slides: {desktop}"
            )
        assert_peeks_clear_of_photo(desktop)

        # Last slide: nothing after it.
        current = peek_state(session)
        while current["index"] < current["total"] - 1:
            session.key("ArrowRight", "ArrowRight", 39)
            session.wait(400)
            current = peek_state(session)
        last = current
        assert last["next"]["count"] == 0, (
            f"the last slide should have no next peek: {last}"
        )
        assert last["prev"]["count"] >= 1, (
            f"the last slide should show its previous neighbour: {last}"
        )

        # Back to the middle slide for the layout checks.
        while current["index"] > 2:
            session.key("ArrowLeft", "ArrowLeft", 37)
            session.wait(400)
            current = peek_state(session)
        session.wait(SETTLE_MS)

        # Tablet width: still the mobile layout, but a wide gutter. The old
        # mobile special case capped both strips at one, so this is the check
        # that the desktop rule now applies everywhere.
        session.set_viewport(768, 1024, mobile=True)
        session.wait(900)
        tablet = peek_state(session)
        assert tablet["mobileLayout"] is True, (
            f"768 px should use the mobile layout: {tablet}"
        )
        for side in ("prev", "next"):
            count = tablet[side]["count"]
            assert 2 <= count <= PEEK_MAX, (
                f"the tablet {side} strip should hold 2..{PEEK_MAX}: {tablet}"
            )
        assert_peeks_clear_of_photo(tablet)

        # Phone width: one neighbour fits on each side, and the photo is intact.
        session.set_viewport(390, 844, mobile=True)
        session.wait(900)
        phone = peek_state(session)
        assert phone["mobileLayout"] is True, (
            f"390 px should use the mobile layout: {phone}"
        )
        for side in ("prev", "next"):
            count = phone[side]["count"]
            assert 1 <= count <= PEEK_MAX, (
                f"the phone {side} strip should hold 1..{PEEK_MAX}: {phone}"
            )
        assert_peeks_clear_of_photo(phone)

        session.clear_viewport()
        session.wait(900)

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all neighbour peek checks passed")


def gallery_switch_state(session: BrowserSession) -> dict[str, Any]:
    """Project wheel and gallery-button state after a switch."""
    return session.js("""(() => {
        const wheel = document.getElementById('project-gallery');
        const style = getComputedStyle(wheel);
        const activeButton = [...document.querySelectorAll('.gallery-btn')]
            .find(button => button.classList.contains('active'));
        const activeTitle = document.querySelector('.project-title.active .project-title-text');
        return {
            opacity: Number(style.opacity),
            visibility: style.visibility,
            pointerEvents: style.pointerEvents,
            switching: wheel.classList.contains('is-switching'),
            rows: document.querySelectorAll('.project-title').length,
            active: activeTitle ? activeTitle.textContent.trim() : null,
            button: activeButton ? activeButton.textContent : null,
            counter: document.getElementById('image-counter').textContent,
            animations: wheel.getAnimations().length,
        };
    })()""")


def project_title(file: str, index: int) -> str:
    """Title of one project in a gallery file."""
    return json.loads((ROOT / file).read_text(encoding="utf-8"))[index]["project-title"]


def first_project_title(file: str) -> str:
    """Title of the first project in a gallery file."""
    return project_title(file, 0)


def test_gallery_switch() -> None:
    """The wheel switch must fade in place, never blank out, and always settle.

    iOS Safari skips opacity animations that start from a visibility-hidden
    element, and the old class-based switch could leave the rebuilt rows
    invisible. The sampler checks that the wheel stays visible for the whole
    switch and fades through intermediate opacities, then that the settled
    wheel is interactive.
    """
    if not find_browser():
        skip_without_browser()

    commercial_title = first_project_title("galleries/commercial.json")
    personal_title = first_project_title("galleries/personnal.json")

    with BrowserSession(ROOT) as session:
        start = gallery_switch_state(session)
        assert start["button"] == "Personnal", (
            f"the first gallery should be active: {start}"
        )
        assert start["active"] == personal_title, (
            f"the first gallery should start on its first project: {start}"
        )

        samples = session.js("""(async () => {
            const wheel = document.getElementById('project-gallery');
            const samples = [];
            const start = performance.now();
            document.querySelectorAll('.gallery-btn')[1].click();
            await new Promise(resolve => {
                function tick() {
                    const style = getComputedStyle(wheel);
                    samples.push({
                        t: performance.now() - start,
                        opacity: Number(style.opacity),
                        visibility: style.visibility,
                    });
                    if (performance.now() - start < 800) requestAnimationFrame(tick);
                    else resolve();
                }
                requestAnimationFrame(tick);
            });
            return samples;
        })()""")

        assert samples, "the switch should produce animation frames"
        assert all(sample["visibility"] == "visible" for sample in samples), (
            "the wheel must stay visible for the whole switch, never hidden"
        )
        assert any(0 < sample["opacity"] < 0.9 for sample in samples), (
            "the wheel should fade through intermediate opacities, not jump"
        )
        assert samples[-1]["opacity"] > 0.99, (
            f"the wheel should be fully visible when the switch ends: {samples[-1]}"
        )

        switched = gallery_switch_state(session)
        assert switched["button"] == "Commercial", (
            f"the commercial gallery should be active: {switched}"
        )
        assert switched["rows"] > 0, (
            f"the switched gallery should render rows: {switched}"
        )
        assert switched["active"] == commercial_title, (
            f"the switched gallery should show its first project: {switched}"
        )
        assert switched["visibility"] == "visible" and switched["opacity"] > 0.99, (
            f"the wheel should be fully visible after the switch: {switched}"
        )
        assert not switched["switching"] and switched["pointerEvents"] == "auto", (
            f"the wheel should accept input after the switch: {switched}"
        )

        # The new rows are real controls, not just paint.
        session.js("document.querySelectorAll('.project-title')[1].click()")
        session.wait(SETTLE_MS)
        clicked = gallery_switch_state(session)
        assert clicked["active"] != commercial_title, (
            f"a title in the switched gallery should be clickable: {clicked}"
        )

        # Two quick taps settle on the last gallery, not a mixture.
        session.js("""(() => {
            const buttons = document.querySelectorAll('.gallery-btn');
            buttons[0].click();
            buttons[1].click();
        })()""")
        session.wait(900)
        rapid = gallery_switch_state(session)
        assert rapid["button"] == "Commercial", (
            f"the last tapped gallery should win: {rapid}"
        )
        assert rapid["active"] == commercial_title, (
            f"the last gallery's rows should be shown: {rapid}"
        )
        assert rapid["opacity"] > 0.99 and rapid["visibility"] == "visible", (
            f"rapid taps must still settle the wheel visible: {rapid}"
        )

        # Switching after reading a note leaves the wheel usable too.
        session.js("document.getElementById('about').click()")
        session.wait(600)
        session.js(
            "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))"
        )
        session.wait(600)
        session.js("document.querySelectorAll('.gallery-btn')[0].click()")
        session.wait(900)
        after_info = gallery_switch_state(session)
        assert after_info["button"] == "Personnal", (
            f"the personal gallery should be active again: {after_info}"
        )
        assert after_info["active"] == personal_title, (
            f"the personal gallery should show its first project: {after_info}"
        )
        assert after_info["opacity"] > 0.99 and after_info["visibility"] == "visible", (
            f"the wheel should be usable after the info view: {after_info}"
        )

        # The same switch on the phone layout.
        session.set_viewport(390, 844, mobile=True)
        session.wait(500)
        session.js("document.querySelectorAll('.gallery-btn')[1].click()")
        session.wait(900)
        phone = gallery_switch_state(session)
        assert phone["visibility"] == "visible" and phone["opacity"] > 0.99, (
            f"the phone switch should leave the wheel visible: {phone}"
        )
        assert phone["active"] == commercial_title, (
            f"the phone switch should show the new gallery: {phone}"
        )

        # iOS can drop the first click after a swipe. A synthetic touch tap emits
        # no click at all, so the switch must come from the touchend handler.
        session.js("""(() => {
            const button = document.querySelectorAll('.gallery-btn')[0];
            const rect = button.getBoundingClientRect();
            const touch = new Touch({
                identifier: 1,
                target: button,
                clientX: rect.left + rect.width / 2,
                clientY: rect.top + rect.height / 2,
            });
            const fire = (type, touches, targetTouches, changedTouches) =>
                button.dispatchEvent(new TouchEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    touches,
                    targetTouches,
                    changedTouches,
                }));
            fire('touchstart', [touch], [touch], [touch]);
            fire('touchend', [], [], [touch]);
            return true;
        })()""")
        session.wait(900)
        touched = gallery_switch_state(session)
        assert touched["button"] == "Personnal", (
            f"a touch tap without a click should switch galleries: {touched}"
        )
        assert touched["active"] == personal_title, (
            f"the touched gallery should show its first project: {touched}"
        )
        assert touched["visibility"] == "visible" and touched["opacity"] > 0.99, (
            f"the touched gallery should be visible: {touched}"
        )

        # The reported path: swipe to the second project, swipe several photos,
        # then tap the other gallery name. iOS can drop the first click after
        # that gesture, and the old project swipe must not fire during the tap.
        session.touch_swipe(195, 720, 0, -80)
        session.wait(SETTLE_MS)
        swiped = gallery_switch_state(session)
        assert swiped["active"] == project_title("galleries/personnal.json", 1), (
            f"the project swipe should select the second project: {swiped}"
        )
        for _ in range(2):
            session.touch_swipe(195, 250, -80, 0)
            session.wait(300)
        commercial_centre = session.js("""(() => {
            const button = document.querySelectorAll('.gallery-btn')[1];
            const rect = button.getBoundingClientRect();
            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        })()""")
        session.touch_tap(commercial_centre["x"], commercial_centre["y"])
        session.wait(900)
        tapped = gallery_switch_state(session)
        assert tapped["button"] == "Commercial", (
            f"a tap after photo swipes should switch galleries: {tapped}"
        )
        assert tapped["active"] == commercial_title, (
            f"the tapped gallery should show its first project: {tapped}"
        )
        assert tapped["visibility"] == "visible" and tapped["opacity"] > 0.99, (
            f"the tapped gallery should be visible: {tapped}"
        )

        # Tapping the already-active gallery must not reinitialize its slide.
        session.key("ArrowRight", "ArrowRight", 39)
        session.wait(400)
        before_active_tap = gallery_switch_state(session)
        session.js("document.querySelectorAll('.gallery-btn')[1].click()")
        session.wait(500)
        after_active_tap = gallery_switch_state(session)
        assert after_active_tap["counter"] == before_active_tap["counter"], (
            "tapping the active gallery must not reset the current photo"
            f" ({before_active_tap['counter']} -> {after_active_tap['counter']})"
        )
        assert after_active_tap["active"] == before_active_tap["active"], (
            "tapping the active gallery must not reset the current project"
        )

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all gallery switch checks passed")


if __name__ == "__main__":
    test_project_scroll()
    test_neighbour_peeks()
    test_gallery_switch()
