"""Vertical centring of the photo against the photo index.

The featured photo must sit in the middle of the space between the top of the
photo panel and the top of the counter (`1 / 12`), not the middle of the whole
panel: that way the white band above the photo matches the band between the
photo and the index text. The neighbour peeks share the photo's centre.

The info view hides the counter, so there the photo goes back to the middle of
the panel.

Run directly:

    python3 tests/test_photo_centering.py

Or through pytest:

    pytest tests/test_photo_centering.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cdp import BrowserSession, find_browser, skip_without_browser

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 2  # px, for rounding and the settled layout
DESKTOP = (1440, 900)
PHONE = (390, 844)


def layout(session: BrowserSession) -> dict[str, Any]:
    """Photo panel, photo, counter and peek-strip geometry, in CSS pixels."""
    return session.js("""(() => {
        const rect = (element) => {
            const box = element.getBoundingClientRect();
            return { top: box.top, bottom: box.bottom, height: box.height };
        };
        const strips = [...document.querySelectorAll('.peek-strip')]
            .filter(strip => strip.children.length > 0)
            .map(strip => {
                const box = strip.getBoundingClientRect();
                return (box.top + box.bottom) / 2;
            });
        return {
            photoPanel: rect(document.getElementById('main-display')),
            photo: rect(document.getElementById('featured-image')),
            counter: rect(document.getElementById('image-counter')),
            counterVisible: !document.getElementById('photo-info')
                .classList.contains('hidden'),
            peekCentres: strips,
        };
    })()""")


def centre(box: dict[str, float]) -> float:
    """Vertical middle of a box."""
    return (box["top"] + box["bottom"]) / 2


def wait_for_photo(session: BrowserSession) -> None:
    """Block until the featured photo has painted and its fade has settled."""
    session.wait_until(
        lambda: session.js(
            "(() => { const image = document.getElementById('featured-image');"
            " return image.complete && image.naturalWidth > 0"
            " && image.getAnimations().every(a => a.playState !== 'running'); })()"
        ),
        timeout=10,
        message="the featured photo did not settle",
    )


def assert_centred_above_counter(observed: dict[str, Any], label: str) -> None:
    """The photo leaves equal space above it and between it and the counter."""
    panel = observed["photoPanel"]
    photo = observed["photo"]
    counter = observed["counter"]

    assert observed["counterVisible"], (
        f"the {label} counter should be part of the normal view: {observed}"
    )
    above = photo["top"] - panel["top"]
    below = counter["top"] - photo["bottom"]
    assert above > 0, f"the {label} photo should keep a white band above it: {observed}"
    assert abs(above - below) <= TOLERANCE, (
        f"the {label} photo should be centred between the panel top and the"
        f" counter top ({above:.1f} px above, {below:.1f} px below): {observed}"
    )
    assert photo["bottom"] <= counter["top"] + TOLERANCE, (
        f"the {label} photo should stay above the counter: {observed}"
    )


def assert_centred_in_panel(observed: dict[str, Any], label: str) -> None:
    """With the counter hidden, the photo centres in the whole panel again."""
    panel = observed["photoPanel"]
    photo = observed["photo"]

    assert not observed["counterVisible"], (
        f"the {label} counter should be hidden in the info view: {observed}"
    )
    assert abs(centre(photo) - centre(panel)) <= TOLERANCE, (
        f"the {label} photo should centre in its panel in the info view: {observed}"
    )


def assert_peeks_share_centre(observed: dict[str, Any], label: str) -> None:
    """The neighbour strips line up with the photo they belong to."""
    photo_centre = centre(observed["photo"])
    for strip_centre in observed["peekCentres"]:
        assert abs(strip_centre - photo_centre) <= TOLERANCE, (
            f"a {label} peek strip should share the photo's centre: {observed}"
        )


def check_viewport(width: int, height: int, mobile: bool, label: str) -> None:
    """Normal and info view centring at one viewport."""
    with BrowserSession(ROOT, width, height) as session:
        session.set_viewport(width, height, mobile=mobile)
        session.wait(400)
        wait_for_photo(session)

        observed = layout(session)
        assert_centred_above_counter(observed, label)
        assert_peeks_share_centre(observed, label)

        session.js("document.getElementById('about').click()")
        session.wait(800)
        observed = layout(session)
        assert_centred_in_panel(observed, label)

        assert not session.exceptions, f"the page raised errors: {session.exceptions}"


def test_photo_centering_desktop() -> None:
    if not find_browser():
        skip_without_browser()
    check_viewport(*DESKTOP, mobile=False, label="desktop")
    print("all desktop photo centring checks passed")


def test_photo_centering_phone() -> None:
    if not find_browser():
        skip_without_browser()
    check_viewport(*PHONE, mobile=True, label="phone")
    print("all phone photo centring checks passed")


if __name__ == "__main__":
    test_photo_centering_desktop()
    test_photo_centering_phone()
