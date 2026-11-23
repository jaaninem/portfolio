# Janine Agbayani - Portfolio

Portfolio site for photographer Janine Agbayani. A scrollable list of projects sits on the left, the selected project's photos are shown in the right panel. A circled `i` next to a project title opens that project's information in the same panel as the About text. Static HTML, CSS and JavaScript, with no build step.

## Quickstart

Serve the repository root over HTTP. The gallery data and the photo manifest are fetched at runtime, so opening `index.html` from disk does not work.

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000/.

## Content

- `galleries/galleries.js`: the list of galleries shown in the top bar.
- `galleries/personnal.json`, `galleries/commercial.json`: projects, notes and image paths.
- `assets/photos/`: full-size photos, one folder per project.
- `assets/thumbs/`: 300 px copies used by the neighbour peeks and the instant preview.
- `assets/scripts/script.py`: refreshes `assets/photos/manifest.json`, rebuilds stale thumbnails and can prune orphans.

## Project layout

```
index.html
galleries/        gallery list and project JSON
assets/css/       styles.css
assets/scripts/   script.js (front end), script.py (photo pipeline)
assets/photos/    full-size images
assets/thumbs/    generated thumbnails mirroring assets/photos
assets/fonts/     web fonts (Silka Mono is used by the interface)
assets/icons/     SVG icons (currently unused)
docs/             project documentation
```

## Documentation

- [Documentation index](docs/index.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/config.md)
- [Photo pipeline](docs/modules/photo-pipeline.md)

## Tests

Browser checks in `tests/` cover the project list (one project per wheel gesture or swipe), gallery switching, the info view's focus handling and its split on phones, and the photo's vertical centring against the counter. They are driven by headless Chromium/Chrome through a stdlib-only DevTools harness (`tests/cdp.py`). Unit tests cover the photo pipeline and check that the gallery JSON parses, that every image path resolves against the manifest, and that the manifest and thumbnails match the photo folder.

```bash
python3 tests/test_project_scroll.py
python3 tests/test_info_view.py
python3 tests/test_photo_centering.py
pytest tests/test_photo_pipeline.py tests/test_galleries.py
```

The browser scripts serve the repository themselves and need no Python packages, only Chromium or Chrome. The pipeline tests need Pillow. `pytest tests/` runs everything.

## Status

Client-side only, no dependencies to install. Checked in Chromium at desktop and phone viewports. The repository does not include a license file.
