# 0001 Replace photo arrows with neighbour thumbnail peeks

- Status: accepted
- Date: 2026-11-02
- Commit: `9d9fbd1`

## Context

The photo panel used two circular arrow buttons in a full-height overlay to move
between slides. They were large and visually louder than the photographs, and
they did not show what came next.

The request was to show the neighbouring photos instead: very small, low-opacity
thumbnails at the sides of the featured photo, acting as the navigation cue.

Measurements of the existing layout showed that the required space already
exists. The featured photo is inset by the panel padding, which leaves a white
gutter of about 87 px per side at 1440x900 and about 43 px at 390x844.

## Decision

Replace the arrow buttons with one peek button per side:

- Left peek: the previous slide, always an image.
- Right peek: the next image, or a small `Fin` card when the next slide is the
  project's end-text slide.
- No peek on a side that has no neighbour.
- Thumbnails use `--peek-width`, `clamp(26px, 3.2vw, 46px)` on desktop and
  `clamp(20px, 6.5vw, 28px)` on mobile, at `0.28` opacity. Hover and keyboard
  focus raise the opacity.
- The featured photo keeps its current size; peeks sit outside its rendered box
  with a 10 px gap (6 px on mobile), clamped 2 px inside the panel.
- Peeks are placed by measuring the photo, so portrait and landscape photos both
  get a tidy gutter. The measurement runs on image load and through a
  `ResizeObserver` on the panel.
- Peeks load from `assets/thumbs/` and fall back to the original photo once if a
  thumbnail is missing.
- Clicking a peek moves one slide. Wheel, horizontal swipe and the arrow keys
  continue to work as before.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| Keep the arrow buttons | The request was to replace them; they compete with the photographs |
| Shrink the featured photo to make room for larger thumbnails | Unnecessary: the measured gutters already fit a small thumbnail, and photo size matters on a portfolio |
| Overlay the thumbnails on the photo edges | Would cover part of the image, especially on landscape photos that fill the panel width |
| Two or three peeks per side, as in the reference site | One per side is enough as a cue and keeps the panel calm; more peeks crowd narrow screens |
| Full drag-physics carousel | A much larger rewrite of the viewer; the existing wheel, swipe and keyboard inputs already cover navigation |
| No peek for the end-text slide | The closing text would only be reachable by wheel, swipe or keyboard. The `Fin` card keeps it discoverable |
| Tiny excerpt instead of `Fin` | Unreadable at roughly 40 px wide |

## Consequences

- The markup has two peek buttons and the script has `updatePeeks()`,
  `positionPeeks()` and the thumbnail fallback.
- `assets/thumbs/` becomes load bearing for the interface. Missing thumbnails
  degrade to full-size images, which is correct but heavier.
- Peek placement depends on the photo's rendered size, so it is recalculated
  whenever the image loads or the panel resizes. While a photo decodes, the
  peeks are hidden through the `is-loading` class to avoid a visible jump.
- On the end-text slide, the text block becomes the positioning reference.
- Keyboard and screen-reader users get labelled buttons (`Previous photo`,
  `Next photo`, `End of series`), and hidden peeks leave the tab order.
- The two arrow SVGs in `assets/icons/` are no longer referenced.

## Verification

Measured in headless Chromium after the change:

| Viewport | Featured photo | Peek width | Gap | Overlap |
| --- | --- | --- | --- | --- |
| 1440x900, landscape | 907 px | 46 px | 10 px | none |
| 1440x900, portrait | 602 px | 46 px | 10 px | none |
| 1280x720 | 480 px | 41 px | 10 px | none |
| 1024x768 | 516 px | 33 px | 10 px | none |
| 768x900 | 432 px | 28 px | 6 px | none |
| 390x844 | 304 px | 25 px | 6 px | none |

Also checked: the `Fin` card on the last image, the end-text slide, rapid
navigation in both directions, keyboard arrows, the About and Back round trip,
and an empty browser console.

## References

- `index.html`
- `assets/css/styles.css`
- `assets/scripts/script.js`
- `assets/scripts/script.py`
- [Architecture](../architecture.md)
- [Configuration](../config.md)
