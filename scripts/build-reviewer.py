#!/usr/bin/env python3
"""Package the original extension files without modifying their contents.

Requires Python 3.12+ and its standard library only. See README.md for reviewer
instructions. --compare verifies every unpacked file against a submitted ZIP.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZipInfo, ZIP_STORED

ROOT = Path(__file__).resolve().parent.parent


def archive_contents(path):
    with ZipFile(path) as archive:
        files = [entry for entry in archive.infolist() if not entry.is_dir()]
        names = [entry.filename for entry in files]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate filenames in {path}")
        return {entry.filename: archive.read(entry) for entry in files}


def compare_archives(rebuilt, submitted):
    actual = archive_contents(rebuilt)
    expected = archive_contents(submitted)
    if actual.keys() != expected.keys():
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        raise ValueError(f"File lists differ: missing={missing}, extra={extra}")
    changed = [name for name in actual if actual[name] != expected[name]]
    if changed:
        raise ValueError(f"File contents differ: {changed}")
    return len(actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional output ZIP path")
    parser.add_argument("--compare", type=Path, help="Submitted unsigned extension ZIP to compare against")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or newer is required")

    source = ROOT / "extension"
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    slug = re.sub(r"[^a-z0-9_-]+", "_", manifest["name"].lower()).strip("_")
    output = (args.output or ROOT / "dist" / f"{slug}-{manifest['version']}-rebuilt.zip").resolve()
    if args.compare and output == args.compare.resolve():
        parser.error("Output must be different from the submitted ZIP being compared")
    if output.is_relative_to(source.resolve()):
        parser.error("Output must be outside the extension source directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source.rglob("*") if path.is_file())
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for path in files:
            if path.is_symlink():
                raise ValueError(f"Source must contain regular files, not symlinks: {path}")
            # Fixed metadata and no compression make this packaging repeatable.
            # The file's bytes are copied directly; no code is transformed.
            entry = ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    print(f"Built: {output}")
    print(f"SHA-256: {hashlib.sha256(output.read_bytes()).hexdigest()}")
    if args.compare:
        count = compare_archives(output, args.compare)
        print(f"Verified: all {count} extension files exactly match the submitted ZIP.")


if __name__ == "__main__":
    main()
