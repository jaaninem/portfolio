# Architecture

## Overview

The site is a single page with two panels inside `.container`:

- `#gallery-container`, a narrow left panel listing project titles and the
  gallery names, with an About button.
- `#main-display`, a white photo panel showing one slide at a time.

All behaviour is in `assets/scripts/script.js`. There is no framework, bundler
or server-side code. Gallery data and the photo manifest are fetched at runtime.

## File map

| Path | Role |
| --- | --- |
| `index.html` | Page markup, About copy, peek buttons, script includes |
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

1. `index.html` loads `galleries/galleries.js`, which defines `GALLERIES`, then
   `assets/scripts/script.js`.
2. On `DOMContentLoaded`, the script fetches the first gallery file and
   `assets/photos/manifest.json` in parallel. A failed manifest request is
   treated as an empty list.
3. `expandProjectImages()` expands `*` and `?` patterns against the manifest. A
   literal path is kept as-is; a bare basename is resolved when exactly one
   manifest entry matches it.
4. `initGallery()` renders one project row per project, builds the gallery name
   buttons, measures the rendered title height (`readProjectHeight`) and stores
   it as the scroll step.
5. Selecting a project translates `#project-gallery` by
   `project_index * projectHeight` over `0.35s` and calls `updateProject()`.
6. `updateProject()` restores that project's remembered image index, marks the
   active title and calls `updateImage()`.
7. `updateImage()` swaps the featured photo (or the end-text slide), refreshes
   the counter and the neighbour peeks, and binds the per-image listeners.

Listeners that belong to a project or to a single image are attached through an
`AbortController` and aborted on the next render, so they never stack up.

## Layout

### Desktop

`body` is a centring flex container; `.container` fills the viewport and lays the
two panels out in a row.

- `#gallery-container` is `25vw` wide (`--gallery-container-width`), has a soft
  right shadow and `resize: horizontal`, so the divider can be dragged.
- `#main-display` takes the remaining width, has a white background, `7% 5%`
  padding and hides overflow.
- `#image-container` is absolutely inset to match that padding and centres its
  content. `#featured-image` scales with `max-width` and `max-height` at 100%,
  keeping its own aspect ratio.
- The counter sits at the bottom-right of the panel; the photo description sits
  under the image container.

### Mobile (max-width: 768px)

- `.container` becomes `column-reverse`: the gallery panel moves to the bottom
  with `25dvh` height, the photo panel fills the rest.
- `#gallery-nav` moves to the bottom of the gallery panel and fades upward.
- Title text is scaled by `--gallery-mobile-font-scale` (0.7), and the row height
  `--project-title-height` is derived from the font size, so the scroll step
  follows automatically.
- Safe-area insets are applied to the counter, the Back button and the gallery
  navigation for iOS home-indicator and notch spacing.

The sidebar width and the mobile panel height are CSS variables, documented in
[config.md](config.md).

## Project list and scrolling

- The project list is translated with `transform: translateY(...)`; it never uses
  native scrolling, so the selected title can be snapped to the cursor line.
- `readProjectHeight()` reads the used height of a rendered `.project-title`
  instead of the raw `var()`/`calc()` value, because custom properties do not
  resolve to pixels in `getComputedStyle`.
- The wheel moves the list in steps of `projectHeight * 0.15` and snaps to the
  nearest project. The position is clamped with half a row of extra space at
  each end.
- Keyboard `ArrowUp` and `ArrowDown` change project.
- On touch, a vertical swipe anywhere on the gallery panel changes exactly one
  project (30 px minimum, dominant vertical movement). A 10 px movement threshold
  separates a tap on a title from a swipe.
- The gallery-name row (`#gallery-buttons`) scrolls horizontally on its own; its
  touch events are excluded from the project swipe handler.

## Photo viewer

- Each project remembers its own image index in `imageIndices`.
- The slide count is the number of images plus one when the project defines
  `end-text`. The counter reads `current / total` and is written in the same
  step that swaps the photo and the peeks, so it never runs ahead of the photo.
  The selected index itself is stored immediately, so switching projects during
  a load keeps the choice.
- The featured photo always uses the original file under `assets/photos/`.
- Image-level navigation, all clamped at the ends:
  - wheel on the photo panel, with a 100 px accumulated threshold;
  - horizontal touch swipe, 50 px threshold;
  - `ArrowLeft` and `ArrowRight`;
  - clicking the neighbour peek on either side.
- Double-clicking the photo panel or pressing `f` requests fullscreen on the
  image; `Escape` or `f` exits. Double-clicks on a peek are ignored.
- An optional `description` on an image is written to `#photo-description`.

## Neighbour peeks

The old arrow buttons were replaced by one faint thumbnail per side, implemented
by `#prev-peek` and `#next-peek` in `index.html`.

- `updatePeeks()` decides what each peek shows:
  - left: the image before the current one, when there is one;
  - right: the next image, or a small `Fin` card when the next slide is the
    project's end-text slide;
  - no neighbour on a side means the peek is hidden and removed from the tab
    order.
- Peek images use `assets/thumbs/<image_path>`. If a thumbnail is missing, the
  `error` listener retries once with `assets/photos/<image_path>`.
- `positionPeeks()` measures the featured photo's rendered box and sets each
  peek's horizontal position outside it, using `--peek-gap`. On the end-text
  slide the text block is the reference instead. Peeks are clamped 2 px inside
  the panel so they never run off the edge.
- On a photo slide the peek content and positions are only swapped once the new
  photo is ready (`load`/`error`). The peeks of the previous photo stay visible
  while that photo is still on screen, so they never blank out during a load.
  The neighbour thumbnails are preloaded at the same moment so the swap does not
  show an empty box.
- Positions are also recomputed through a `ResizeObserver` on `#main-display`
  (viewport changes, orientation changes, sidebar drag).
- Sizes and opacity come from CSS variables; the mobile block shrinks both.
  See [config.md](config.md).

The decision record is
[decisions/0001-neighbour-thumbnail-peeks.md](decisions/0001-neighbour-thumbnail-peeks.md).

## Navigation inputs

| Input | Where | Effect |
| --- | --- | --- |
| Wheel | Gallery panel | Previous or next project |
| Wheel | Photo panel | Previous or next slide |
| Vertical swipe | Gallery panel | One project per gesture |
| Horizontal swipe | Photo panel | Previous or next slide |
| `ArrowUp` / `ArrowDown` | Page | Previous or next project |
| `ArrowLeft` / `ArrowRight` | Page | Previous or next slide |
| Peek click | Photo panel edges | Previous or next slide |
| Gallery name click | Top bar | Load another gallery file |
| Project title click | Gallery panel | Select that project |
| Double-click, `f` | Photo panel | Toggle fullscreen |
| `Escape` | Page | Leave fullscreen |

## About mode

- The About button adds `about-active` to the gallery panel and the photo panel,
  hides the normal-mode elements and shows `#about-text` and the Back button.
- On desktop the gallery widens (target `60vw`) and the photo panel narrows; both
  panels stay visible.
- On mobile the gallery expands to `100dvh` and the photo panel collapses to
  zero height.
- Back reverses the classes and the visibility changes. Width and height
  transitions are defined by CSS variables.

## Photo data and thumbnails

- `assets/photos/` holds the originals. `assets/thumbs/` mirrors the same folder
  structure with thumbnails no wider than 300 px.
- `assets/photos/manifest.json` is a sorted array of relative POSIX paths. The
  front end uses it to expand glob patterns and to resolve bare basenames.
- Only the neighbour peeks use the thumbnails today; the featured photo always
  loads the original.
- Both the manifest and the thumbnails are generated by
  `assets/scripts/script.py`. See
  [modules/photo-pipeline.md](modules/photo-pipeline.md).

## Constraints

- Classic scripts only: no modules, no bundler, no transpiler.
- The page must be served over HTTP because the gallery JSON and manifest are
  fetched.
- The gallery JSON is the single source for project titles, captions, years,
  locations and end text.
- Thumbnails and the manifest are data, not build output: adding a photo without
  running the script leaves the peek fallback in charge.
- The photo viewer keeps state in memory only; reloading returns to the first
  project and the first image of each project.
