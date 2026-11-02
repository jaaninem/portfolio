# Documentation

Overview and index of the documentation for the Janine Agbayani portfolio site.

## What this project is

A static, client-side portfolio: one scrollable column of project titles and a
photo viewer that shows one project at a time. There is no build step, no
framework and no backend. Content lives in JSON and image folders; behaviour
lives in `assets/scripts/script.js`.

## Quickstart

See the [README](../README.md) for serving the site locally. In short:

```bash
python3 -m http.server 8000
```

The page fetches `galleries/*.json` and `assets/photos/manifest.json`, so it has
to be served over HTTP.

## Documentation map

| Page | Covers |
| --- | --- |
| [architecture.md](architecture.md) | Layout, runtime flow, navigation inputs, peeks, About mode |
| [config.md](config.md) | Gallery list, gallery JSON, CSS variables, tuning constants |
| [modules/photo-pipeline.md](modules/photo-pipeline.md) | `assets/scripts/script.py`, thumbnails and the manifest |
| [decisions/0001-neighbour-thumbnail-peeks.md](decisions/0001-neighbour-thumbnail-peeks.md) | Why the arrow buttons became neighbour thumbnails |

## Conventions

- Galleries are arrays of projects in `galleries/*.json`; the list of galleries
  is `galleries/galleries.js`.
- Originals live in `assets/photos/`, generated thumbnails in `assets/thumbs/`.
- `assets/photos/manifest.json` is generated and has to be refreshed when photos
  are added.
- `docs/` describes shipped behaviour only. Future work is not documented here.
