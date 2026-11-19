"""Behaviour checks for the project list and its navigation inputs.

Covers the unified one-project-per-gesture rule (wheel and touch), the clamps at
either end, the photo-panel wheel, the info view, keyboard arrows and realignment
after viewport changes.

Run directly, with no Python packages installed:

    python3 tests/test_project_scroll.py

Or through pytest:

    pytest tests/test_project_scroll.py

Either way Chromium or Chrome has to be installed; the test serves the
repository itself.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cdp import BrowserSession, find_browser

ROOT = Path(__file__).resolve().parents[1]
SETTLE_MS = 600  # transition is 0.35 s; leave room for image loads too
GALLERY_X = 120  # inside the left project panel on a 1280 px viewport
GALLERY_Y = 300
PHOTO_X = 900  # inside the photo panel
PHOTO_Y = 400


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


def skip_without_browser() -> None:
    reason = "Chromium or Chrome is not installed"
    if "pytest" in sys.modules:
        import pytest

        pytest.skip(reason)
    print(f"SKIP: {reason}")
    raise SystemExit(0)


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
        # is still one gesture and moves one project.
        session.wheel(GALLERY_X, GALLERY_Y, 20, count=10, gap_ms=10)
        session.wait(SETTLE_MS)
        stream = state(session)
        assert stream["activeIndex"] == 2, (
            f"a wheel stream should step exactly one project: {stream}"
        )
        assert snapped_to(stream), f"the stream should end on row 2: {stream}"

        # Reversing the direction is a new gesture.
        session.wheel(GALLERY_X, GALLERY_Y, -100)
        session.wait(SETTLE_MS)
        back = state(session)
        assert back["activeIndex"] == 1, f"wheel up should go back one project: {back}"

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


if __name__ == "__main__":
    test_project_scroll()
