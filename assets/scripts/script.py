"""Photo pipeline for the portfolio.

Walks the photo folders and produces the two generated artefacts the site reads:
``assets/photos/manifest.json`` and the mirrored thumbnails under ``assets/thumbs/``.
Run it after adding, removing or replacing photos.

The default paths are anchored to the repository root, so the script behaves the same
from any working directory.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

LOGGER = logging.getLogger("photo-pipeline")

# Repository root: <repo>/assets/scripts/script.py
REPO_ROOT = Path(__file__).resolve().parents[2]

# Configuration
PHOTO_DIR = REPO_ROOT / "assets/photos"
THUMB_DIR = REPO_ROOT / "assets/thumbs"
THUMB_WIDTH = 300  # pixels
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


@dataclass
class ThumbnailReport:
    """Outcome of one thumbnail pass."""

    created: int = 0
    refreshed: int = 0
    skipped: int = 0
    removed: int = 0
    failures: list[tuple[Path, str]] = field(default_factory=list)


def is_image(path: Path) -> bool:
    """Return True when the file extension is one the site can display."""
    return path.suffix.lower() in IMAGE_EXTENSIONS


def iter_images(photo_dir: Path) -> list[Path]:
    """Return every supported image below ``photo_dir`` as a sorted list."""
    return sorted(
        path for path in photo_dir.rglob("*") if path.is_file() and is_image(path)
    )


def thumbnail_path(photo: Path, photo_dir: Path, thumb_dir: Path) -> Path:
    """Return the thumbnail path mirroring ``photo``'s location under ``photo_dir``."""
    return thumb_dir / photo.relative_to(photo_dir)


def needs_refresh(photo: Path, thumb: Path, force: bool = False) -> bool:
    """Return True when the thumbnail is missing, stale, or forced."""
    if force or not thumb.exists():
        return True
    return photo.stat().st_mtime > thumb.stat().st_mtime


def prepare_for_save(img: Image.Image, suffix: str) -> Image.Image:
    """Return an image that the thumbnail format can hold.

    Some photos are actually PNG data with a ``.jpg`` name (RGBA with an opaque
    alpha channel), and JPEG cannot store an alpha channel. Transparent pixels are
    composited on white so the thumbnail stays readable.
    """
    if suffix.lower() not in (".jpg", ".jpeg"):
        return img
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def generate_thumbnail(photo: Path, thumb: Path, thumb_width: int) -> None:
    """Write a ``thumb_width`` wide thumbnail of ``photo`` to ``thumb``.

    The aspect ratio is preserved and smaller images are not upscaled. The original
    filename and extension are kept, so the thumbnail format matches the source.
    """
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(photo) as img:
        height = round(img.height * thumb_width / img.width)
        img.thumbnail((thumb_width, height), Image.Resampling.LANCZOS)
        prepare_for_save(img, thumb.suffix).save(thumb)


def generate_thumbnails(
    photo_dir: Path = PHOTO_DIR,
    thumb_dir: Path = THUMB_DIR,
    thumb_width: int = THUMB_WIDTH,
    force: bool = False,
) -> ThumbnailReport:
    """Build every missing or stale thumbnail and report what happened."""
    report = ThumbnailReport()
    for photo in iter_images(photo_dir):
        thumb = thumbnail_path(photo, photo_dir, thumb_dir)
        if not needs_refresh(photo, thumb, force):
            report.skipped += 1
            continue
        existed = thumb.exists()
        try:
            generate_thumbnail(photo, thumb, thumb_width)
        except Exception as exc:  # noqa: BLE001 - one corrupt file must not stop the run
            report.failures.append((photo, str(exc)))
            LOGGER.error("Failed to build %s: %s", display_path(thumb), exc)
            continue
        if existed:
            report.refreshed += 1
            LOGGER.info("Refreshed %s", display_path(thumb))
        else:
            report.created += 1
            LOGGER.info("Created %s", display_path(thumb))
    return report


def remove_orphan_thumbnails(
    photo_dir: Path = PHOTO_DIR, thumb_dir: Path = THUMB_DIR
) -> list[Path]:
    """Delete thumbnails whose source photo is gone, then prune empty folders."""
    if not thumb_dir.exists():
        return []

    expected = {photo.relative_to(photo_dir) for photo in iter_images(photo_dir)}
    orphans = []
    for thumb in sorted(path for path in thumb_dir.rglob("*") if path.is_file()):
        if thumb.relative_to(thumb_dir) in expected:
            continue
        thumb.unlink()
        orphans.append(thumb)
        LOGGER.info("Removed orphan %s", display_path(thumb))

    directories = sorted(
        (path for path in thumb_dir.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass  # not empty, keep it
    return orphans


def generate_manifest(photo_dir: Path = PHOTO_DIR) -> int:
    """Write the sorted list of photos below ``photo_dir`` and return the count.

    Paths are relative to ``photo_dir`` and use forward slashes so the browser can
    match them against the globs in the gallery JSON.
    """
    files = sorted(
        photo.relative_to(photo_dir).as_posix() for photo in iter_images(photo_dir)
    )

    manifest_path = photo_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(files, handle, indent="\t")
        handle.write("\n")
    LOGGER.info("Wrote %s (%d files)", display_path(manifest_path), len(files))
    return len(files)


def display_path(path: Path) -> str:
    """Return ``path`` relative to the repository root when possible."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser."""
    parser = argparse.ArgumentParser(
        description="Refresh the photo manifest and generate thumbnails."
    )
    parser.add_argument(
        "--photo-dir",
        type=Path,
        default=PHOTO_DIR,
        help=f"photo directory (default: {display_path(PHOTO_DIR)})",
    )
    parser.add_argument(
        "--thumb-dir",
        type=Path,
        default=THUMB_DIR,
        help=f"thumbnail directory (default: {display_path(THUMB_DIR)})",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=THUMB_WIDTH,
        help=f"maximum thumbnail width in pixels (default: {THUMB_WIDTH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild every thumbnail even when it is up to date",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="delete thumbnails whose source photo no longer exists",
    )
    jobs = parser.add_mutually_exclusive_group()
    jobs.add_argument(
        "--manifest-only",
        action="store_true",
        help="refresh the manifest without touching thumbnails",
    )
    jobs.add_argument(
        "--thumbs-only",
        action="store_true",
        help="build thumbnails without rewriting the manifest",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and return the process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.manifest_only and args.clean:
        parser.error(
            "--clean needs the thumbnail pass, it cannot be combined with --manifest-only"
        )
    if args.width < 1:
        parser.error("--width must be a positive number of pixels")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    photo_dir = Path(args.photo_dir).expanduser()
    thumb_dir = Path(args.thumb_dir).expanduser()
    if not photo_dir.is_dir():
        LOGGER.error("Photo directory not found: %s", photo_dir)
        return 1

    if not args.thumbs_only:
        generate_manifest(photo_dir)

    if args.manifest_only:
        return 0

    report = generate_thumbnails(photo_dir, thumb_dir, args.width, force=args.force)
    if args.clean:
        report.removed = len(remove_orphan_thumbnails(photo_dir, thumb_dir))

    LOGGER.info(
        "Thumbnails: %d created, %d refreshed, %d unchanged, %d removed, %d failed",
        report.created,
        report.refreshed,
        report.skipped,
        report.removed,
        len(report.failures),
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
