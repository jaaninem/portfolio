"""Focus behaviour of the project information view.

The `+` shortcut has to open the selected project's note without moving focus to
that project's marker, so pressing `Escape` does not leave a focus ring there.
Clicking the marker keeps the usual "return focus to the trigger" behaviour.

Run directly:

    python3 tests/test_info_view.py

Or through pytest:

    pytest tests/test_info_view.py
"""

from __future__ import annotations

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


def test_info_view_focus() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        # With nothing focused, the shortcut must not leave focus on the marker.
        start = state(session)
        assert start["activeTag"] == "BODY", (
            f"nothing should be focused after load: {start}"
        )

        session.key("+", "Equal", 187)
        session.wait(400)
        opened = state(session)
        assert opened["info"] is True, f"the + shortcut should open the note: {opened}"
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
        session.key("+", "Equal", 187)
        session.wait(400)
        assert state(session)["info"] is True, "the + shortcut should open the note"

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
