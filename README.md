# Janine Agbayani - Portfolio

Portfolio site for photographer Janine Agbayani. A scrollable list of projects sits on the left, the selected project's photos are shown in the right panel. Static HTML, CSS and JavaScript, with no build step.

## Quickstart

Serve the repository root over HTTP. The gallery data and the photo manifest are fetched at runtime, so opening `index.html` from disk does not work.

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000/.

## Content

- `galleries/galleries.js`: the list of galleries shown in the top bar.
- `galleries/main.json`: projects, captions and image paths.
- `assets/photos/`: full-size photos, one folder per project.
- `assets/thumbs/`: 300 px copies used by the neighbour peeks and the instant preview.
- `assets/scripts/script.py`: refreshes `assets/photos/manifest.json` and can generate thumbnails.

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

## Status

Client-side only, no dependencies to install. Checked in Chromium at desktop and phone viewports. The repository does not include a license file.
