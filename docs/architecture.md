# Architecture

## Overview

The site is a single page with two panels inside `.container`:

- `#gallery-container`, a narrow left panel listing project titles and the gallery names, with an About button.
- `#main-display`, a white photo panel showing one slide at a time.

All behaviour is in `assets/scripts/script.js`. There is no framework, bundler or server-side code. Gallery data and the photo manifest are fetched at runtime.

## File map

| Path | Role |
| --- | --- |
| `index.html` | Page markup, About copy, peek strips, script includes |
| `assets/css/styles.css` | Layout, typography, transitions, responsive rules |
| `assets/scripts/script.js` | Data loading, rendering, navigation, peeks, About mode |
| `galleries/galleries.js` | `GALLERIES` list shown in the top bar |
| `galleries/main.json` | Projects, captions and image paths |
| `assets/photos/` | Full-size photos, one folder per project |
| `assets/photos/manifest.json` | Generated list of every available photo |
| `assets/thumbs/` | Generated 300 px thumbnails mirroring `assets/photos/` |
| `assets/scripts/script.py` | Manifest and thumbnail generator |
| `assets/fonts/` | Web fonts (Silka Mono is used by the interface) |

## Runtime flow

1. `index.html` loads `galleries/galleries.js`, which defines `GALLERIES`, then `assets/scripts/script.js`.
2. On `DOMContentLoaded`, the script fetches the first gallery file and `assets/photos/manifest.json` in parallel. A failed manifest request is treated as an empty list.
3. `expandProjectImages()` expands `*` and `?` patterns against the manifest. A literal path is kept as-is; a bare basename is resolved when exactly one manifest entry matches it.
4. `initGallery()` renders one project row per project, builds the gallery name buttons, measures the rendered title height (`readProjectHeight`) and stores it as the scroll step.
5. Selecting a project translates `#project-gallery` by `project_index * projectHeight` over `0.35s` and calls `updateProject()`.
6. `updateProject()` restores that project's remembered image index, marks the active title and calls `updateImage()`.
7. `updateImage()` paints the slide: the prefetched original when it is ready, otherwise the thumbnail preview. It then refreshes the counter, the neighbour peeks and the per-image listeners, and schedules the neighbour prefetch.

Listeners that belong to a project or to a single image are attached through an `AbortController` and aborted on the next render, so they never stack up.

## Layout

### Desktop

`body` is a centring flex container; `.container` fills the viewport and lays the two panels out in a row.

- `#gallery-container` is `25vw` wide (`--gallery-container-width`), has a soft right shadow and `resize: horizontal`, so the divider can be dragged.
- `#main-display` takes the remaining width, has a white background, `7% 5%` padding and hides overflow.
- `#image-container` is absolutely inset to match that padding and centres its content. `#featured-image` scales with `max-width` and `max-height` at 100%, keeping its own aspect ratio.
- The counter sits at the bottom-right of the panel; the photo description sits under the image container.

### Mobile (max-width: 768px)

- `.container` becomes `column-reverse`: the gallery panel moves to the bottom with `25dvh` height, the photo panel fills the rest.
- `#gallery-nav` moves to the bottom of the gallery panel and fades upward.
- Title text is scaled by `--gallery-mobile-font-scale` (0.7), and the row height `--project-title-height` is derived from the font size, so the scroll step follows automatically.
- Safe-area insets are applied to the counter, the Back button and the gallery navigation for iOS home-indicator and notch spacing.

The sidebar width and the mobile panel height are CSS variables, documented in [config.md](config.md).

## Project list and scrolling

- The project list is translated with `transform: translateY(...)`; it never uses native scrolling, so the selected title can be snapped to the cursor line.
- `readProjectHeight()` reads the used height of a rendered `.project-title` instead of the raw `var()`/`calc()` value, because custom properties do not resolve to pixels in `getComputedStyle`.
- The wheel moves the list in steps of `projectHeight * 0.15` and snaps to the nearest project. The position is clamped with half a row of extra space at each end.
- Keyboard `ArrowUp` and `ArrowDown` change project.
- On touch, a vertical swipe anywhere on the gallery panel changes exactly one project (30 px minimum, dominant vertical movement). A 10 px movement threshold separates a tap on a title from a swipe.
- The gallery-name row (`#gallery-buttons`) scrolls horizontally on its own; its touch events are excluded from the project swipe handler.

## Photo viewer

- Each project remembers its own image index in `imageIndices`.
- The slide count is the number of images plus one when the project defines `end-text`. The counter reads `current / total` and follows the visible slide: the prefetched original when it is ready, otherwise the thumbnail preview. The selected index is stored immediately, so switching projects during a load keeps the choice.
- The featured photo uses the original file under `assets/photos/`.
- When the target original is not ready, the 300 px thumbnail under `assets/thumbs/` is painted immediately at the exact box size of the original. The original loads off-screen and silently replaces the source when it decodes. The preview is sized with the image's computed `max-width` and `max-height`, so portrait and landscape frames keep the same box before and after the upgrade.
- After a slide has been visible for 300 ms, the previous and next originals are prefetched with low priority. Up to six loaded originals are kept in memory as an in-document cache. A prefetched original is painted directly, with no preview frame. Rapid navigation clears the prefetch timer and cancels the pending original, so skipped slides are not downloaded.
- Image-level navigation, all clamped at the ends:
  - wheel on the photo panel, with a 100 px accumulated threshold;
  - horizontal touch swipe, 50 px threshold;
  - `ArrowLeft` and `ArrowRight`;
  - clicking any neighbour peek, which jumps straight to that slide.
- Double-clicking the photo panel or pressing `f` requests fullscreen on the image; `Escape` or `f` exits. Double-clicks on a peek are ignored.
- An optional `description` on an image is written to `#photo-description`.

## Neighbour peeks

Each side of the featured photo has a strip of faint thumbnails for the neighbouring slides, implemented by `#prev-peeks` and `#next-peeks` in `index.html`. The strips sit in the panel's white gutter, so they never change the featured photo's size; how many thumbnails each one holds depends on the space available.

- `refreshPeeks()` measures the gutter on each side of the featured photo and computes a capacity:
  - `floor((gutter - 2 px - gap + spacing) / (peek width + spacing))`, capped at five per side;
  - exactly one thumbnail per side below the 768 px mobile breakpoint;
  - at least one per side, as before, even when the gap has to compress.
- `peekItems()` walks outwards from the current slide and returns up to that many slides per side:
  - left: the images before the current one;
  - right: the images after it, ending with a small `Fin` card when the project's end-text slide is within reach;
  - a side with no neighbour gets an empty strip, which is hidden and has no tab stops.
- The strips are reused between slides: `renderPeekStrip()` swaps the content of the existing buttons instead of rebuilding them, so a slide change does not flash.
- The previous strip lays out in `row-reverse`, so its first child (the nearest slide) sits against the photo's left edge. The whole strip is centred vertically.
- Thumbnails use `assets/thumbs/<image_path>`. If a thumbnail is missing, the `error` listener retries once with `assets/photos/<image_path>`.
- Each step away from the photo is fainter, through the `--peek-opacity` falloff in CSS. Hover and keyboard focus raise a thumbnail to full strength.
- Clicking any thumbnail jumps straight to that slide (`showSlide(target)`); it does not step one at a time. The counter and both strips follow the new slide.
- `peekGeometry()` is recomputed through a `ResizeObserver` on `#main-display` (viewport changes, orientation changes, sidebar drag) and when the visible source settles its box, so the capacity and positions follow the panel.
- The thumbnails the strips can show are preloaded from `assets/thumbs/`, so a strip update does not leave an empty box.
- Sizes, spacing and opacity come from CSS variables; the mobile block shrinks all of them. See [config.md](config.md).

## Navigation inputs

| Input | Where | Effect |
| --- | --- | --- |
| Wheel | Gallery panel | Previous or next project |
| Wheel | Photo panel | Previous or next slide |
| Vertical swipe | Gallery panel | One project per gesture |
| Horizontal swipe | Photo panel | Previous or next slide |
| `ArrowUp` / `ArrowDown` | Page | Previous or next project |
| `ArrowLeft` / `ArrowRight` | Page | Previous or next slide |
| Peek click | Photo panel edges | Jump to the clicked slide |
| Gallery name click | Top bar | Load another gallery file |
| Project title click | Gallery panel | Select that project |
| Double-click, `f` | Photo panel | Toggle fullscreen |
| `Escape` | Page | Leave fullscreen |

## About mode

- The About button adds `about-active` to the gallery panel and the photo panel, hides the normal-mode elements and shows `#about-text` and the Back button.
- On desktop the gallery widens (target `60vw`) and the photo panel narrows; both panels stay visible.
- On mobile the gallery expands to `100dvh` and the photo panel collapses to zero height.
- Back reverses the classes and the visibility changes. Width and height transitions are defined by CSS variables.

## Photo data and thumbnails

- `assets/photos/` holds the originals. `assets/thumbs/` mirrors the same folder structure with thumbnails no wider than 300 px.
- `assets/photos/manifest.json` is a sorted array of relative POSIX paths. The front end uses it to expand glob patterns and to resolve bare basenames.
- The neighbour peeks and the instant preview use the thumbnails; once an original is ready, the featured photo shows the original file.
- Both the manifest and the thumbnails are generated by `assets/scripts/script.py`. See [modules/photo-pipeline.md](modules/photo-pipeline.md).

## Constraints

- Classic scripts only: no modules, no bundler, no transpiler.
- The page must be served over HTTP because the gallery JSON and manifest are fetched.
- The gallery JSON is the single source for project titles, captions, years, locations and end text.
- Thumbnails and the manifest are data, not build output: adding a photo without running the script leaves the peek fallback in charge.
- Prefetching is best effort and adds roughly two originals per settled slide. It is delayed, low priority and skipped while navigating quickly.
- The photo viewer keeps state in memory only; reloading returns to the first project and the first image of each project.
