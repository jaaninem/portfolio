"""Checks that the selection line crosses the selected project title.

The line is a fixed anchor in the gallery panel and the title list is positioned
and translated against it, so the two must agree for every project, on every
viewport, whatever the number of projects in the gallery.

Run directly:

    python3 tests/test_selection_line.py

Or through pytest:

    pytest tests/test_selection_line.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cdp import BrowserSession, find_browser, skip_without_browser

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1  # px, for rounding and the settled transition
PHONE_WIDTH = 390
PHONE_HEIGHT = 844


def state(session: BrowserSession) -> dict[str, Any]:
    """Selected title and selection line geometry, in CSS pixels."""
    return session.js("""(() => {
        const active = document.querySelector('.project-title.active');
        const line = document.getElementById('cursor-line');
        const row = active.getBoundingClientRect();
        const bar = line.getBoundingClientRect();
        return {
            title: active.textContent.trim(),
            rows: document.querySelectorAll('.project-title').length,
            rowCenter: row.top + row.height / 2,
            lineCenter: bar.top + bar.height / 2,
        };
    })()""")


def assert_selected_row_on_line(session: BrowserSession, label: str) -> dict[str, Any]:
    """The active row's centre and the line's centre must coincide."""
    current = state(session)
    delta = current["lineCenter"] - current["rowCenter"]
    assert abs(delta) <= TOLERANCE, (
        f"the {label} selection line should cross the selected title"
        f" {current['title']!r}: line at {current['lineCenter']:.1f} px,"
        f" title centre at {current['rowCenter']:.1f} px, off by {delta:.1f} px"
    )
    return current


def walk_projects(session: BrowserSession, label: str) -> None:
    """Assert the line stays on the title for every project, down and back up."""
    first = assert_selected_row_on_line(session, f"{label} first row")
    assert first["rows"] >= 2, (
        f"the {label} checks need at least two projects, got {first['rows']}"
    )

    for _ in range(first["rows"] - 1):
        session.key("ArrowDown", "ArrowDown", 40)
        session.wait(500)
        assert_selected_row_on_line(session, label)

    for _ in range(first["rows"] - 1):
        session.key("ArrowUp", "ArrowUp", 38)
        session.wait(500)
        assert_selected_row_on_line(session, label)


def test_selection_line_desktop() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT) as session:
        session.wait(400)
        walk_projects(session, "desktop")
        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all desktop selection line checks passed")


def test_selection_line_phone() -> None:
    if not find_browser():
        skip_without_browser()

    with BrowserSession(ROOT, PHONE_WIDTH, PHONE_HEIGHT) as session:
        session.set_viewport(PHONE_WIDTH, PHONE_HEIGHT, mobile=True)
        session.wait(400)
        walk_projects(session, "phone")
        assert not session.exceptions, f"the page raised errors: {session.exceptions}"

    print("all phone selection line checks passed")


if __name__ == "__main__":
    test_selection_line_desktop()
    test_selection_line_phone()
