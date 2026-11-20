"""Unit tests for the photo pipeline in ``assets/scripts/script.py``."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from conftest import PIPELINE_PATH
from PIL import Image


def make_image(path: Path, size: tuple[int, int] = (1200, 800)) -> Path:
    """Write a small JPEG at ``path`` and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 90, 60)).save(path)
    return path


@pytest.fixture
def photos(tmp_path: Path) -> Path:
    """Photo folder holding one image per project folder plus a stray file."""
    directory = tmp_path / "photos"
    make_image(directory / "Alpha" / "alpha_01.jpg", (1200, 800))
    make_image(directory / "Beta" / "beta_01.jpg", (800, 1200))
    (directory / "notes.txt").write_text("not an image")
    return directory


def test_defaults_are_anchored_to_repository_root(pipeline):
    assert pipeline.REPO_ROOT == PIPELINE_PATH.parents[2]
    assert pipeline.PHOTO_DIR.is_absolute()
    assert pipeline.PHOTO_DIR == pipeline.REPO_ROOT / "assets/photos"
    assert pipeline.THUMB_DIR.is_absolute()


def test_generate_manifest_lists_images_as_sorted_posix_paths(pipeline, photos: Path):
    count = pipeline.generate_manifest(photos)

    manifest_path = photos / "manifest.json"
    assert count == 2
    assert json.loads(manifest_path.read_text()) == [
        "Alpha/alpha_01.jpg",
        "Beta/beta_01.jpg",
    ]
    assert manifest_path.read_text().endswith("\n")
    assert '\n\t"' in manifest_path.read_text()


def test_thumbnails_mirror_the_photo_tree_and_keep_the_aspect_ratio(
    pipeline, photos: Path, tmp_path: Path
):
    thumbs = tmp_path / "thumbs"

    report = pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)

    assert report.created == 2
    assert report.failures == []
    with Image.open(thumbs / "Alpha" / "alpha_01.jpg") as image:
        assert image.width <= 200
        assert abs(image.width / image.height - 1.5) < 0.02
    with Image.open(thumbs / "Beta" / "beta_01.jpg") as image:
        assert image.width == 200
        assert abs(image.width / image.height - 800 / 1200) < 0.02


def test_small_images_are_not_upscaled(pipeline, photos: Path, tmp_path: Path):
    make_image(photos / "Alpha" / "small.jpg", (100, 50))
    thumbs = tmp_path / "thumbs"

    pipeline.generate_thumbnails(photos, thumbs, thumb_width=300)

    with Image.open(thumbs / "Alpha" / "small.jpg") as image:
        assert image.size == (100, 50)


def test_transparent_png_named_as_jpeg_is_flattened(
    pipeline, photos: Path, tmp_path: Path
):
    """Some photos are PNG data with a .jpg name; JPEG cannot hold alpha."""
    mislabelled = photos / "Alpha" / "mislabelled.jpg"
    Image.new("RGBA", (400, 200), (10, 20, 30, 0)).save(mislabelled, format="PNG")
    thumbs = tmp_path / "thumbs"

    report = pipeline.generate_thumbnails(photos, thumbs, thumb_width=100)

    assert report.failures == []
    with Image.open(thumbs / "Alpha" / "mislabelled.jpg") as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (100, 50)


def test_fresh_thumbnails_are_skipped_and_stale_ones_refreshed(
    pipeline, photos: Path, tmp_path: Path
):
    thumbs = tmp_path / "thumbs"
    first = pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)
    assert first.created == 2

    thumb = thumbs / "Alpha" / "alpha_01.jpg"
    before = thumb.stat().st_mtime

    second = pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)
    assert (second.created, second.refreshed, second.skipped) == (0, 0, 2)
    assert thumb.stat().st_mtime == before

    photo = photos / "Alpha" / "alpha_01.jpg"
    later = time.time() + 60
    os.utime(photo, (later, later))

    third = pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)
    assert (third.created, third.refreshed, third.skipped) == (0, 1, 1)
    assert thumb.stat().st_mtime > before


def test_force_rebuilds_every_thumbnail(pipeline, photos: Path, tmp_path: Path):
    thumbs = tmp_path / "thumbs"
    pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)

    report = pipeline.generate_thumbnails(photos, thumbs, thumb_width=200, force=True)

    assert (report.created, report.refreshed, report.skipped) == (0, 2, 0)


def test_remove_orphan_thumbnails_deletes_unknown_files_and_empty_folders(
    pipeline, photos: Path, tmp_path: Path
):
    thumbs = tmp_path / "thumbs"
    pipeline.generate_thumbnails(photos, thumbs, thumb_width=200)
    orphan = thumbs / "Alpha" / "alpha_02.jpg"
    make_image(orphan, (60, 40))
    dead_folder = thumbs / "Gone"
    make_image(dead_folder / "gone_01.jpg", (60, 40))

    removed = pipeline.remove_orphan_thumbnails(photos, thumbs)

    assert sorted(removed) == [orphan, dead_folder / "gone_01.jpg"]
    assert not orphan.exists()
    assert not dead_folder.exists()
    assert (thumbs / "Alpha" / "alpha_01.jpg").exists()


def test_broken_photo_is_reported_as_a_failure(pipeline, photos: Path, tmp_path: Path):
    broken = photos / "Alpha" / "broken.jpg"
    broken.write_bytes(b"not really a jpeg")

    report = pipeline.generate_thumbnails(photos, tmp_path / "thumbs", thumb_width=200)

    assert report.created == 2
    assert [path for path, _ in report.failures] == [broken]
    status = pipeline.main(
        ["--photo-dir", str(photos), "--thumb-dir", str(tmp_path / "thumbs")]
    )
    assert status == 1


def test_cli_runs_from_another_directory(
    pipeline, photos: Path, tmp_path: Path, monkeypatch
):
    thumbs = tmp_path / "thumbs"
    monkeypatch.chdir(tmp_path)
    make_image(photos / "Alpha" / "alpha_01.jpg", (1200, 800))
    for path in photos.rglob("*.jpg"):
        os.utime(path, (time.time() + 60, time.time() + 60))

    status = pipeline.main(
        [
            "--photo-dir",
            str(photos),
            "--thumb-dir",
            str(thumbs),
            "--width",
            "150",
        ]
    )

    assert status == 0
    assert (photos / "manifest.json").exists()
    with Image.open(thumbs / "Alpha" / "alpha_01.jpg") as image:
        assert image.size == (150, 100)


def test_manifest_only_leaves_thumbnails_alone(pipeline, photos: Path, tmp_path: Path):
    thumbs = tmp_path / "thumbs"

    status = pipeline.main(
        [
            "--photo-dir",
            str(photos),
            "--thumb-dir",
            str(thumbs),
            "--manifest-only",
        ]
    )

    assert status == 0
    assert (photos / "manifest.json").exists()
    assert not thumbs.exists()


def test_clean_removes_orphans_through_the_cli(pipeline, photos: Path, tmp_path: Path):
    thumbs = tmp_path / "thumbs"
    orphan = thumbs / "Alpha" / "alpha_02.jpg"
    make_image(orphan, (60, 40))

    status = pipeline.main(
        [
            "--photo-dir",
            str(photos),
            "--thumb-dir",
            str(thumbs),
            "--clean",
        ]
    )

    assert status == 0
    assert not orphan.exists()
    assert (thumbs / "Beta" / "beta_01.jpg").exists()


def test_missing_photo_directory_fails(pipeline, tmp_path: Path):
    status = pipeline.main(
        [
            "--photo-dir",
            str(tmp_path / "nope"),
            "--thumb-dir",
            str(tmp_path / "thumbs"),
        ]
    )

    assert status == 1


def test_conflicting_job_flags_are_rejected(pipeline):
    with pytest.raises(SystemExit):
        pipeline.main(["--manifest-only", "--clean"])
    with pytest.raises(SystemExit):
        pipeline.main(["--manifest-only", "--thumbs-only"])
