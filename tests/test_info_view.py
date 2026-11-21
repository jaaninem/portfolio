"""Focus and layout behaviour of the project information view.

The `i` shortcut has to open the selected project's note without moving focus to
that project's marker, so pressing `Escape` does not leave a focus ring there.
Clicking the marker keeps the usual "return focus to the trigger" behaviour.

On a phone the reading panel must not take the whole screen: it keeps a fixed
share of the viewport at the bottom and leaves the selected photo visible above
it.

Run directly:

    python3 tests/test_info_view.py

Or through pytest:

    pytest tests/test_info_view.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cdp import BrowserSession, find_browser, skip_without_browser

ROOT = Path(__file__).resolve().parents[1]


def state(session: BrowserSession) -> dict[str, Any]:
    """Focused element and info-view state."""
    return session.js("""(() => {
        const active = document.activeElement;
        return {
            activeTag: active ? active.tagName : null,
            activeId: active ? active.id : '',
            activeMarker: active ? active.classList.contains('project-info-btn') : false,
            info: document.getElementById('gallery-container').classList.contains('info-active'),
            markerRings: [...document.querySelectorAll('.project-info-btn')]
                .filter(marker => marker.matches(':focus-visible')).length,
        };
    })()""")


def marker_centre(session: BrowserSession) -> dict[str, float]:
    """Centre of the selected project's `+` marker, in page coordinates."""
    return session.js("""(() => {
        const marker = document.querySelector('.project-title.active .project-info-btn');
        const rect = marker.getBoundingClientRect();
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    })()""")


def click(session: BrowserSession, x: float, y: float) -> None:
    """Press and release the left mouse button at a page coordinate."""
    for event in (
        {"type": "mouseMoved"},
        {"type": "mousePressed", "button": "left", "clickCount": 1},
        {"type": "mouseReleased", "button": "left", "clickCount": 1},
    ):
        session.call("Input.dispatchMouseEvent", {**event, "x": x, "y": y})


PHONE_WIDTH = 390
PHONE_HEIGHT = 844
INFO_PANEL_SHARE = (
    0.6  # --gallery-container-info-mobile-height, as a share of the viewport
)
TOLERANCE = 2  # px, for rounding and the settled transition


def layout(session: BrowserSession) -> dict[str, Any]:
    """Panel, photo and visible info text geometry, in CSS pixels."""
    return session.js("""(() => {
        const rect = (id) => {
            const box = document.getElementById(id).getBoundingClientRect();
            return {
                top: box.top,
                bottom: box.bottom,
                width: box.width,
                height: box.height,
            };
        };
        const content = [...document.querySelectorAll('.info-content')]
            .find(element => !element.classList.contains('hidden'));
        const contentBox = content ? content.getBoundingClientRect() : null;
        return {
            viewport: { width: window.innerWidth, height: window.innerHeight },
            panel: rect('gallery-container'),
            photoPanel: rect('main-display'),
            photo: rect('featured-image'),
            content: contentBox === null ? null : {
                top: contentBox.top,
                bottom: contentBox.bottom,
                clientHeight: content.clientHeight,
                scrollHeight: content.scrollHeight,
                text: content.textContent.trim().length,
            },
        };
    })()""")


def assert_split_keeps_photo_visible(observed: dict[str, Any], label: str) -> None:
    """The reading panel keeps its share; the photo stays fully visible above it."""
    viewport_height = observed["viewport"]["height"]
    panel = observed["panel"]
    photo_panel = observed["photoPanel"]
    photo = observed["photo"]
    content = observed["content"]

    expected = viewport_height * INFO_PANEL_SHARE
    assert abs(panel["height"] - expected) <= TOLERANCE, (
        f"the {label} panel should keep {INFO_PANEL_SHARE:.0%} of the viewport"
        f" ({expected:.0f} px), got {panel['height']:.0f} px: {observed}"
    )
    assert abs(panel["bottom"] - viewport_height) <= TOLERANCE, (
        f"the {label} panel should stay anchored to the bottom: {observed}"
    )
    assert photo_panel["height"] > 0, (
        f"the photo panel should keep the remaining height: {observed}"
    )
    assert photo_panel["bottom"] <= panel["top"] + TOLERANCE, (
        f"the photo panel should sit above the {label} panel: {observed}"
    )
    assert photo["width"] > 0 and photo["height"] > 0, (
        f"the photo should stay visible above the {label} panel: {observed}"
    )
    assert photo["top"] >= photo_panel["top"] - TOLERANCE, (
        f"the photo should not overflow the top of its panel: {observed}"
    )
    assert photo["bottom"] <= photo_panel["bottom"] + TOLERANCE, (
        f"the photo should not overflow the bottom of its panel: {observed}"
    )
    assert content is not None and content["text"] > 0, (
        f"the {label} view should show its text: {observed}"
    )
    assert content["top"] >= panel["top"] - TOLERANCE, (
        f"the {label} text should start inside its panel: {observed}"
    )
    assert content["bottom"] <= panel["bottom"] + TOLERANCE, (
        f"the {label} text should stay inside its panel: {observed}"
    )


def test_info_view_mobile_layout() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT, PHONE_WIDTH, PHONE_HEIGHT) as session:
        session.set_viewport(PHONE_WIDTH, PHONE_HEIGHT, mobile=True)
        session.wait(400)

        # About keeps the photo visible above the text.
        session.js("document.getElementById('about').click()")
        session.wait(800)
        assert state(session)["info"] is True, "About should open the info view"
        assert_split_keeps_photo_visible(layout(session), "About")

        session.key("Escape", "Escape", 27)
        session.wait(700)
        assert state(session)["info"] is False, "Escape should close the info view"

        # A project note uses the same split.
        session.js("""document.querySelectorAll('.project-title')[0]
            .querySelector('.project-info-btn').click()""")
        session.wait(800)
        assert state(session)["info"] is True, "the marker should open the project note"
        assert_split_keeps_photo_visible(layout(session), "project note")

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all mobile info view layout checks passed")


def note_line_count(session: BrowserSession, text: str) -> int:
    """Render ``text`` in the project note and return its rendered line count."""
    return session.js(f"""(() => {{
        const note = document.getElementById('project-info-note');
        const previous = note.textContent;
        note.textContent = {json.dumps(text)};
        const lineHeight = parseFloat(getComputedStyle(note).lineHeight);
        const lines = Math.round(note.getBoundingClientRect().height / lineHeight);
        note.textContent = previous;
        return lines;
    }})()""")


def test_project_note_line_breaks() -> None:
    """A "\\n" in the gallery JSON must render as a line break, without indentation."""
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        session.js("""document.querySelector('.project-title.active')
            .querySelector('.project-info-btn').click()""")
        session.wait(800)

        white_space = session.js(
            "getComputedStyle(document.getElementById('project-info-note')).whiteSpace"
        )
        assert white_space == "pre-line", (
            f"the project note should honour authored newlines, got {white_space!r}"
        )

        assert note_line_count(session, "one two") == 1
        assert note_line_count(session, "one\ntwo") == 2
        assert note_line_count(session, "one\n    two") == 2, (
            "the spaces around an authored newline should collapse"
        )
        assert note_line_count(session, "one\n\ntwo") == 3, (
            "a blank line in the JSON should stay a blank line"
        )

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all project note line break checks passed")


def test_info_view_focus() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        # With nothing focused, the shortcut must not leave focus on the marker.
        start = state(session)
        assert start["activeTag"] == "BODY", (
            f"nothing should be focused after load: {start}"
        )

        session.key("i", "KeyI", 73)
        session.wait(400)
        opened = state(session)
        assert opened["info"] is True, f"the i shortcut should open the note: {opened}"
        assert opened["activeId"] == "project-info", (
            f"focus should move into the note: {opened}"
        )

        session.key("Escape", "Escape", 27)
        session.wait(700)
        closed = state(session)
        assert closed["info"] is False, f"Escape should close the note: {closed}"
        assert closed["activeTag"] == "BODY", (
            f"focus should not land on the marker: {closed}"
        )
        assert closed["activeMarker"] is False, (
            f"the marker should not be focused: {closed}"
        )
        assert closed["markerRings"] == 0, (
            f"no marker should show a focus ring: {closed}"
        )

        # The shortcut restores whatever was focused before it was pressed.
        session.js("document.getElementById('about').focus()")
        session.key("i", "KeyI", 73)
        session.wait(400)
        assert state(session)["info"] is True, "the i shortcut should open the note"

        session.key("Escape", "Escape", 27)
        session.wait(700)
        restored = state(session)
        assert restored["activeId"] == "about", (
            f"focus should return to the About button: {restored}"
        )
        assert restored["activeMarker"] is False, (
            f"the marker should not be focused: {restored}"
        )

        # The click path still returns focus to the marker it was opened from.
        centre = marker_centre(session)
        click(session, centre["x"], centre["y"])
        session.wait(500)
        clicked = state(session)
        assert clicked["info"] is True, (
            f"clicking the marker should open the note: {clicked}"
        )

        session.key("Escape", "Escape", 27)
        session.wait(700)
        returned = state(session)
        assert returned["info"] is False, f"Escape should close the note: {returned}"
        assert returned["activeMarker"] is True, (
            f"the click path should return focus to the marker: {returned}"
        )

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all info view focus checks passed")


if __name__ == "__main__":
    test_info_view_focus()
    test_project_note_line_breaks()
    test_info_view_mobile_layout()
