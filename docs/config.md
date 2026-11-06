# Configuration

All configuration lives in files, there are no environment variables and no runtime settings. This page lists what can be changed and what each value does.

## Gallery list

`galleries/galleries.js` defines the galleries shown in the top bar:

```js
const GALLERIES = [
    { name: "Main", file: "galleries/main.json" }
];
```

- `name` is the label in the top bar.
- `file` is a path relative to `index.html`.
- The first entry loads at start. Clicking a name fetches that file and renders it in place, resetting the project and image selection.

Only one gallery is currently configured.

## Gallery JSON

Each gallery file is an array of projects. `galleries/main.json` follows this shape:

```json
[
    {
        "project-title": "AXE-X",
        "year": "2026",
        "location": null,
        "end-text": "Editorial project for Valentin Meghit's diploma",
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
| `end-text` | string | no | Closing slide shown after the last image; also reachable through the `Fin` peek |
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

## Photo manifest

`assets/photos/manifest.json` is a generated, sorted JSON array of relative POSIX paths such as `"Dunes/2425_S2_Agbayani_Janine_MiseEnScene_01.jpg"`. It is read at startup and never edited by hand.

Regenerate it with:

```bash
python3 assets/scripts/script.py
```

The generator is documented in [modules/photo-pipeline.md](modules/photo-pipeline.md).

## Thumbnails

`assets/thumbs/` mirrors `assets/photos/` and holds thumbnails capped at 300 px wide with the original aspect ratio. The neighbour peek strips load them, and so does the instant preview shown while an original downloads. The preview is upscaled to the photo's box, so it looks soft until the original arrives; a prefetched original skips the preview entirely. If a thumbnail is missing, the peek falls back to the full photo once.

Thumbnails are produced by `assets/scripts/script.py` (`THUMB_WIDTH = 300`). Note that the generator's `generate_thumbnails()` call is commented out in the script's entry point, so a plain run only refreshes the manifest.

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
| `--gallery-container-about-width` | `60vw` | Gallery width target in About mode |
| `--gallery-container-about-mobile-height` | `100dvh` | Gallery height in About mode on mobile |
| `--gallery-container-about-transition` | `width 0.5s ease-in-out` | Desktop About transition |
| `--gallery-container-about-transition-mobile` | `height 0.5s ease-in-out` | Mobile About transition |
| `--gallery-elements-animation` | `fadeIn 0.5s ease` | Fade used when gallery elements appear |
| `--peek-width` | `clamp(26px, 3.2vw, 46px)` | Neighbour peek width; mobile: `clamp(20px, 6.5vw, 28px)` |
| `--peek-text-width` | `calc(var(--peek-width) * 0.78)` | Width of the `Fin` card |
| `--peek-gap` | `10px` | Space between the photo and the nearest peek; mobile: `6px` |
| `--peek-spacing` | `8px` | Space between two thumbnails in the same strip; mobile: `6px` |
| `--peek-opacity` | `0.28` | Resting opacity of the nearest peek; each further step fades more |

Changing `--project-title-font-size-base` or `--gallery-mobile-font-scale` also changes the scroll step, because `--project-title-height` derives from the title size. The JavaScript re-reads the rendered title height on resize.

## Front-end tuning constants

These are constants in `assets/scripts/script.js`, not user-facing settings:

| Constant | Value | Effect |
| --- | --- | --- |
| `scrollSpeed` | `0.15` | Wheel sensitivity for the project list |
| Project transition | `transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)` | Title list slide |
| Image wheel threshold | `100` px | Accumulated wheel distance before a slide change |
| Image swipe threshold | `50` px | Horizontal swipe distance on the photo |
| Project swipe threshold | `30` px | Vertical swipe distance on the gallery panel |
| Tap threshold | `10` px | Below this a touch is a tap, not a swipe |
| Peek edge inset (`PEEK_EDGE`) | `2` px | Minimum distance between a strip and the panel edge |
| Peek strip cap (`PEEK_MAX`) | `5` | Maximum thumbnails per side on desktop |
| Mobile peek breakpoint | `(max-width: 768px)` | Below this each strip shows exactly one thumbnail |
| `PREFETCH_DELAY` | `300` ms | Idle time before the neighbouring originals are fetched |
| `PREFETCH_LIMIT` | `6` | Loaded originals kept in the in-document prefetch cache |

`readProjectHeight()` uses `60` as a fallback before the titles are rendered; it is replaced by the measured value on the first render.

## Runtime requirements

- The site has to be served over HTTP; `fetch()` of the gallery JSON and the manifest fails when `index.html` is opened from disk.
- The paths in `galleries.js`, the gallery JSON and `assets/scripts/script.py` are all relative to the repository root.
- No build step or dependency installation is needed to view the site. The photo pipeline needs Python with Pillow.
