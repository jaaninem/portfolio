# Configuration

All configuration lives in files, there are no environment variables and no runtime settings. This page lists what can be changed and what each value does.

## Gallery list

`galleries/galleries.js` defines the galleries shown in the top bar:

```js
const GALLERIES = [
    { name: "Personnal", file: "galleries/personnal.json" },
    { name: "Commercial", file: "galleries/commercial.json" }
];
```

- `name` is the label in the top bar.
- `file` is a path relative to `index.html`.
- The first entry loads at start. Clicking a name fetches that file and renders it in place, resetting the project and image selection.

Two galleries are configured: Personnal, loaded first, and Commercial.

## Gallery JSON

Each gallery file is an array of projects. `galleries/commercial.json` follows this shape:

```json
[
    {
        "project-title": "AXE-X",
        "year": "2026",
        "location": null,
        "info": "Editorial project for Valentin Meghit's diploma",
        "images": [
            { "image_path": "diplome_val_*.jpg" }
        ]
    }
]
```

| Field | Type | Required | Effect |
| --- | --- | --- | --- |
| `project-title` | string | yes | Title in the project list |
| `year` | string or `null` | no | Small label next to the title |
| `location` | string or `null` | no | Small label next to the title |
| `info` | string | no | Note shown when the project's circled `i` marker opens its information view. `\n` starts a new line and `\n\n` a new paragraph |
| `images` | array | yes | Slides of the project |
| `images[].image_path` | string | yes | Path under `assets/photos/`, or a glob |
| `images[].description` | string | no | Caption under the photo; no project uses it currently |

### Image paths

`image_path` is resolved by `expandProjectImages()` in `assets/scripts/script.js`:

- `*` matches any sequence of characters and `?` matches one character. Patterns are compared with both the full relative path and the file's basename.
- A literal path that exists in `assets/photos/manifest.json` is used unchanged.
- A literal basename without a folder is resolved when exactly one manifest entry has that basename.
- Anything else is kept as written, which normally results in a broken image.

The manifest is what makes globs and bare basenames work. If it fails to load, the front end falls back to an empty list and only literal full paths resolve.

Line breaks in a project's `info` are written as `\n` in the JSON, which the info view renders with `white-space: pre-line`: the newline is kept, the spaces around it collapse, and `\n\n` leaves a blank line. The About text is plain HTML in `index.html` and uses `<br>` for its line breaks.

## Photo manifest

`assets/photos/manifest.json` is a generated, sorted JSON array of relative POSIX paths such as `"Dunes/2425_S2_Agbayani_Janine_MiseEnScene_01.jpg"`. It is read at startup and never edited by hand.

Regenerate the manifest and the thumbnails with:

```bash
python3 assets/scripts/script.py
```

Add `--clean` to delete thumbnails whose source photo is gone. The generator is documented in [modules/photo-pipeline.md](modules/photo-pipeline.md).

## Thumbnails

`assets/thumbs/` mirrors `assets/photos/` and holds thumbnails capped at 300 px wide with the original aspect ratio. The neighbour peek strips load them, and so does the instant preview shown while an original downloads. The preview is upscaled to the photo's box, so it looks soft until the original arrives; a prefetched original skips the preview entirely. If a thumbnail is missing, the peek falls back to the full photo once.

Thumbnails are produced by `assets/scripts/script.py` (`THUMB_WIDTH = 300`). A plain run rebuilds every thumbnail whose source photo is newer than the thumbnail, so replacing a photo is enough to refresh it. `--force` rebuilds everything, `--clean` removes orphans.

## CSS variables

Defined in `:root` in `assets/css/styles.css`; the mobile overrides sit in the `@media (max-width: 768px)` block of the same file.

| Variable | Default | Effect |
| --- | --- | --- |
| `--project-title-font-size-base` | `45px` | Base title size |
| `--project-title-font-size` | `var(--project-title-font-size-base)` | Title size; on mobile it is 0.7 times the base |
| `--project-title-height` | `calc(var(--project-title-font-size) * 1.3333)` | Row height and scroll step of the project list |
| `--gallery-mobile-font-scale` | `0.7` | Scale applied to gallery text on mobile |
| `--gallery-container-width` | `25vw` | Width of the left panel |
| `--gallery-container-mobile-height` | `25dvh` | Height of the gallery panel on mobile |
| `--gallery-container-info-width` | `clamp(360px, 45vw, 640px)` | Gallery width while the info view is open (desktop) |
| `--gallery-container-info-mobile-height` | `60dvh` | Gallery height in the info view on mobile; the photo panel takes the remaining `40dvh` |
| `--gallery-container-info-transition` | `width 420ms cubic-bezier(0.2, 0, 0, 1)` | Desktop info-view transition; applied only while `.panel-animating` is set |
| `--gallery-container-info-transition-mobile` | `height var(--motion-panel-duration) cubic-bezier(0.2, 0, 0, 1)` | Mobile info-view transition; applied only while `.panel-animating` is set. Uses the phone panel duration (`360ms`) |
| `--motion-ease` | `cubic-bezier(0.2, 0, 0, 1)` | Shared motion curve (fast start, long settle) |
| `--motion-panel-duration` | `420ms` (`360ms` on phones) | Gallery panel resize when the info view opens or closes |
| `--motion-out-duration` | `120ms` (`100ms` on phones) | Fade out of the content the info view replaces |
| `--motion-in-duration` | `140ms` (`120ms` on phones) | Fade in of the content the info view shows |
| `--motion-in-delay` | `260ms` (`200ms` on phones) | Wait before that fade in, so most of the resize is already done |
| `--motion-hover-duration` | `160ms` | Hover and marker transitions |
| `--info-content-measure` | `44ch` | Line length of the About and project info text |
| `--peek-width` | `clamp(26px, 3.2vw, 46px)` | Neighbour peek width; mobile: `clamp(20px, 6.5vw, 28px)` |
| `--peek-gap` | `10px` | Space between the photo and the nearest peek; mobile: `6px` |
| `--peek-spacing` | `8px` | Space between two thumbnails in the same strip; mobile: `6px` |
| `--peek-opacity` | `0.28` | Resting opacity of the nearest peek; each further step fades more |
| `--photo-index-band` | `calc(15px + 1.2rem + env(safe-area-inset-bottom))` | Space the counter occupies at the bottom of the photo panel; the photo is centred above it. Mobile derives it from the scaled counter (`1.2rem * var(--gallery-mobile-font-scale)`) |

Changing `--project-title-font-size-base` or `--gallery-mobile-font-scale` also changes the scroll step, because `--project-title-height` derives from the title size. The JavaScript re-reads the rendered title height on resize.

`prefers-reduced-motion: reduce` overrides the motion durations to `1ms` with no delay and turns off the project-list slide, so the same states appear without the travel.

## Front-end tuning constants

These are constants in `assets/scripts/script.js`, not user-facing settings:

| Constant | Value | Effect |
| --- | --- | --- |
| `WHEEL_STEP` | `30` px | Accumulated wheel distance before the project list steps (same as the swipe threshold) |
| `WHEEL_GESTURE_IDLE` | `150` ms | Quiet time that ends a wheel gesture; longer trackpad momentum stays one step |
| `WHEEL_LINE_HEIGHT` | `16` px | Pixels per line when a browser reports wheel deltas in lines |
| Project list transition | `transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)` in `styles.css` | Title list slide |
| `PANEL_SETTLE_FALLBACK` | `600` ms | Fallback for the `transitionend` that refreshes and reveals the peeks |
| `SWITCH_FADE_OUT` | `140` ms | Gallery-switch fade out (Web Animations API) |
| `SWITCH_FADE_IN` | `200` ms | Gallery-switch fade in |
| `preloadThumbnail` timeout | `400` ms | Maximum wait for the new gallery's first thumbnail before revealing the rows |
| Image wheel threshold | `100` px | Accumulated wheel distance before a slide change |
| Image swipe threshold | `50` px | Horizontal swipe distance on the photo |
| Project swipe threshold | `30` px | Vertical swipe distance on the gallery panel |
| Tap threshold | `10` px | Below this a touch is a tap, not a swipe |
| Peek edge inset (`PEEK_EDGE`) | `2` px | Minimum distance between a strip and the panel edge |
| Peek strip cap (`PEEK_MAX`) | `5` | Maximum thumbnails per side, at every viewport |
| Peek capacity | measured gutter | Thumbnails that fit beside the photo; at least one per side when a neighbour exists |
| `PREFETCH_DELAY` | `300` ms | Idle time before the neighbouring originals are fetched |
| `PREFETCH_LIMIT` | `6` | Loaded originals kept in the in-document prefetch cache |

`readProjectHeight()` uses `60` as a fallback before the titles are rendered; it is replaced by the measured value on the first render.

## Runtime requirements

- The site has to be served over HTTP; `fetch()` of the gallery JSON and the manifest fails when `index.html` is opened from disk.
- The paths in `galleries.js` and the gallery JSON are relative to the repository root. The photo pipeline anchors its own defaults to the repository root, so it can be run from any directory.
- No build step or dependency installation is needed to view the site. The photo pipeline needs Python with Pillow.
