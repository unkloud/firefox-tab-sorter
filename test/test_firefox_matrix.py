"""Regression tests for discovery, download integrity, and compatibility reporting."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("firefox_matrix", ROOT / "scripts/firefox-matrix.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)


class MatrixTests(unittest.TestCase):
    def test_discovery_includes_point_releases_and_excludes_other_channels(self):
        index = """
        <a href="139.0/">old</a><a href="/pub/firefox/releases/140.0/">minimum</a>
        <a href="140.0.4/">patch</a><a href="140.0esr/">ESR</a>
        <a href="141.0b1/">beta</a><a href="141.0/">stable</a>
        <a href="160.0.1/">maximum</a><a href="161.0/">new</a>
        <a href="140.0/">duplicate</a>
        """
        self.assertEqual(matrix.discover_versions(index, "140.0", "160.0.1"),
                         ["140.0", "140.0.4", "141.0", "160.0.1"])

    def test_version_validation_prevents_paths_and_nonstable_versions(self):
        for value in ["../140.0", "140.0esr", "141.0b1", "140", "140.0.1/", "140.0.1.2"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                matrix.version_key(value)
        self.assertLess(matrix.version_key("140.0.2"), matrix.version_key("140.0.10"))

    def test_checksums_require_exact_platform_locale_and_valid_sha512(self):
        digest = "a" * 128
        relative = "linux-x86_64/en-US/firefox-140.0.tar.xz"
        text = f"{'b' * 128}  linux-x86_64/en-GB/firefox-140.0.tar.xz\n{digest}  {relative}\n"
        self.assertEqual(matrix.checksum_for(text, relative), digest)
        self.assertIsNone(matrix.checksum_for(text, "win64/en-US/firefox-140.0.zip"))
        with self.assertRaises(ValueError):
            matrix.checksum_for(f"not-a-digest  {relative}", relative)

    def test_offline_mode_cannot_silently_download_a_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.xz"
            with self.assertRaises(FileNotFoundError):
                matrix.download("https://invalid.example/", path, offline=True)
            self.assertFalse(path.exists())

    def test_corrupt_archives_are_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            version = cache / "140.0"
            version.mkdir()
            (version / "firefox-140.0.tar.xz").write_bytes(b"corrupt")
            (version / "SHA512SUMS").write_text("a" * 128 + "  linux-x86_64/en-US/firefox-140.0.tar.xz\n")
            with self.assertRaisesRegex(ValueError, "SHA-512 mismatch"):
                matrix.prepare_browser("140.0", cache, offline=True)
            self.assertFalse((version / "firefox").exists())

    def test_missing_platform_build_is_reported_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            version = cache / "140.0"
            version.mkdir()
            (version / "SHA512SUMS").write_text("")
            with self.assertRaises(matrix.BuildUnavailable):
                matrix.prepare_browser("140.0", cache, offline=True)

    def test_tar_extraction_cannot_escape_the_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            version = cache / "140.0"
            version.mkdir()
            archive = version / "firefox-140.0.tar.xz"
            with tarfile.open(archive, "w:xz") as bundle:
                entry = tarfile.TarInfo("../../escaped")
                entry.size = 4
                bundle.addfile(entry, io.BytesIO(b"nope"))
            (version / "SHA512SUMS").write_text(matrix.file_hash(archive, "sha512") +
                "  linux-x86_64/en-US/firefox-140.0.tar.xz\n")
            with self.assertRaises(tarfile.FilterError):
                matrix.prepare_browser("140.0", cache, offline=True)
            self.assertFalse((cache / "escaped").exists())

    def test_resume_requires_same_extension_suite_platform_and_actual_version(self):
        metadata = {"extension_sha256": "extension", "suite_sha256": "suite", "platform": "linux"}
        row = {"version": "140.0", "browser_version": "140.0", "status": "pass", "ok": True}
        self.assertTrue(matrix.resumable(row, metadata, metadata))
        for key in metadata:
            self.assertFalse(matrix.resumable(row, metadata, {**metadata, key: "changed"}))
        for values in [{"status": "fail"}, {"ok": False}, {"browser_version": "141.0"}]:
            self.assertFalse(matrix.resumable({**row, **values}, metadata, metadata))

    def test_partial_reports_do_not_claim_the_matrix_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "results.json"
            metadata = {"started_at": "test", "extension_sha256": "extension", "suite_sha256": "suite"}
            rows = {"141.0": {"version": "141.0", "status": "pass", "skipped": ["split views"]}}
            matrix.save_results(destination, metadata, ["140.0", "141.0"], rows)
            self.assertFalse(json.loads(destination.read_text())["complete"])
            self.assertIn("1 pending", destination.with_suffix(".md").read_text())
            rows["140.0"] = {"version": "140.0", "status": "fail", "error": "error | details\nnext"}
            matrix.save_results(destination, metadata, ["140.0", "141.0"], rows)
            result = json.loads(destination.read_text())
            self.assertTrue(result["complete"])
            self.assertEqual([row["version"] for row in result["results"]], ["140.0", "141.0"])
            self.assertIn("1 failed", destination.with_suffix(".md").read_text())

    def test_source_hash_includes_filenames_and_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "a.js"
            file.write_text("source")
            first = matrix.tree_hash(root)
            file.rename(root / "b.js")
            self.assertNotEqual(first, matrix.tree_hash(root))
            archive = root / "zip"
            archive.write_bytes(b"package")
            self.assertEqual(matrix.tree_hash(archive), hashlib.sha256(b"package").hexdigest())


if __name__ == "__main__":
    unittest.main()
