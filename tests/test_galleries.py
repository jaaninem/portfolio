"""Content checks for the gallery list, the gallery JSON and the photo manifest.

These read the real repository files, so they fail when a gallery is malformed or when
photos were added or removed without running ``assets/scripts/script.py``.
"""

from __future__ import annotations

import json
import re

from conftest import ROOT

GALLERIES_JS = ROOT / "galleries/galleries.js"
MANIFEST_PATH = ROOT / "assets/photos/manifest.json"
ENTRY_PATTERN = re.compile(r'\{\s*name:\s*"([^"]+)",\s*file:\s*"([^"]+)"\s*\}')


def load_manifest() -> list[str]:
    return json.loads(MANIFEST_PATH.read_text())


def load_gallery_list() -> list[dict[str, str]]:
    """Parse the gallery entries out of galleries.js without a JavaScript runtime."""
    entries = ENTRY_PATTERN.findall(GALLERIES_JS.read_text())
    return [{"name": name, "file": file} for name, file in entries]


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Mirror of globToRegExp() in assets/scripts/script.js."""
    escaped = re.sub(r"([.+^${}()|\[\]\\])", r"\\\1", pattern)
    return re.compile("^" + escaped.replace("*", ".*").replace("?", ".") + "$")


def matches(pattern: str, available: list[str]) -> list[str]:
    """Mirror of expandProjectImages() matching: full path or basename."""
    regex = glob_to_regex(pattern)
    return [
        file
        for file in available
        if regex.match(file) or regex.match(file.rsplit("/", 1)[-1])
    ]


def test_gallery_list_has_one_entry_per_gallery():
    entries = load_gallery_list()

    assert [entry["name"] for entry in entries] == ["Personnal", "Commercial"]
    for entry in entries:
        assert (ROOT / entry["file"]).is_file(), entry["file"]


def test_every_gallery_is_a_non_empty_project_list():
    for entry in load_gallery_list():
        projects = json.loads((ROOT / entry["file"]).read_text())
        assert projects, entry["file"]
        for project in projects:
            assert project["project-title"]
            assert project["images"]


def test_every_image_path_resolves_against_the_manifest():
    available = load_manifest()
    unresolved = []
    for entry in load_gallery_list():
        projects = json.loads((ROOT / entry["file"]).read_text())
        for project in projects:
            for image in project["images"]:
                pattern = image["image_path"]
                if not matches(pattern, available):
                    unresolved.append(
                        f"{entry['file']}: {project['project-title']}: {pattern}"
                    )
    assert unresolved == []


def test_manifest_matches_the_photo_folder(pipeline):
    expected = sorted(
        photo.relative_to(pipeline.PHOTO_DIR).as_posix()
        for photo in pipeline.iter_images(pipeline.PHOTO_DIR)
    )

    assert load_manifest() == expected


def test_every_photo_has_a_thumbnail(pipeline):
    available = load_manifest()
    missing = [file for file in available if not (pipeline.THUMB_DIR / file).is_file()]

    assert missing == []


def test_no_orphan_thumbnails(pipeline):
    available = set(load_manifest())

    orphans = sorted(
        thumb.relative_to(pipeline.THUMB_DIR).as_posix()
        for thumb in pipeline.THUMB_DIR.rglob("*")
        if thumb.is_file()
        and thumb.relative_to(pipeline.THUMB_DIR).as_posix() not in available
    )

    assert orphans == []
