#!/usr/bin/env python3
"""Test pinned stable Firefox releases using verified, project-local downloads.

Linux x86_64 only. Requires Python 3.12+, curl, and Firefox's system libraries.
Browser profiles are disposable; downloaded browsers are cached for offline reruns.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = "https://archive.mozilla.org/pub/firefox/releases/"
VERSION_PATTERN = re.compile(r"\d+\.\d+(?:\.\d+)?\Z")


def version_key(version):
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Not a stable Firefox version: {version!r}")
    return tuple(map(int, (version.split(".") + ["0"])[:3]))


def discover_versions(index, minimum, maximum):
    candidates = re.findall(r'href="(?:[^"<>]*/)?(\d+\.\d+(?:\.\d+)?)/"', index)
    return sorted({version for version in candidates
                   if version_key(minimum) <= version_key(version) <= version_key(maximum)}, key=version_key)


def checksum_for(text, relative_path):
    for line in text.splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) == 2 and fields[1] == relative_path:
            if not re.fullmatch(r"[a-fA-F0-9]{128}", fields[0]):
                raise ValueError(f"Malformed SHA-512 for {relative_path}")
            return fields[0].lower()
    return None


def file_hash(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def tree_hash(path):
    if path.is_file():
        return file_hash(path)
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode() + b"\0")
        digest.update(file.read_bytes())
    return digest.hexdigest()


def download(url, destination, offline=False):
    if destination.exists():
        return
    if offline:
        raise FileNotFoundError(f"Not cached for offline use: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    try:
        subprocess.run([
            "curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
            "--connect-timeout", "15", "--max-time", "240", url, "--output", str(part),
        ], check=True, capture_output=True, text=True, timeout=750)
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)


class BuildUnavailable(Exception):
    """A release has no Linux x86_64 en-US artifact in Mozilla's checksums."""


def prepare_browser(version, cache, offline=False):
    directory = cache / version
    directory.mkdir(parents=True, exist_ok=True)
    checksums = directory / "SHA512SUMS"
    download(f"{ARCHIVE}{version}/SHA512SUMS", checksums, offline)
    relative = f"linux-x86_64/en-US/firefox-{version}.tar.xz"
    expected = checksum_for(checksums.read_text(), relative)
    if expected is None:
        raise BuildUnavailable(f"Mozilla publishes no {relative} artifact")
    archive = directory / f"firefox-{version}.tar.xz"
    download(f"{ARCHIVE}{version}/{relative}", archive, offline)
    if file_hash(archive, "sha512") != expected:
        raise ValueError(f"SHA-512 mismatch: {archive}; remove the corrupt cached file before retrying")
    binary = directory / "firefox" / "firefox"
    marker = directory / "extracted-sha512.txt"
    if not binary.exists() or not marker.exists() or marker.read_text().strip() != expected:
        with tempfile.TemporaryDirectory(prefix="extract-", dir=directory) as staging:
            with tarfile.open(archive) as bundle:
                bundle.extractall(staging, filter="data")
            extracted = Path(staging) / "firefox"
            if not (extracted / "firefox").is_file():
                raise ValueError("Firefox binary missing from verified archive")
            if binary.parent.exists():
                shutil.rmtree(binary.parent)
            extracted.rename(binary.parent)
        marker.write_text(expected + "\n")
    # Prevent automatic updates of cached versions, including on future reruns.
    distribution = binary.parent / "distribution"
    distribution.mkdir(exist_ok=True)
    (distribution / "policies.json").write_text(json.dumps({"policies": {"DisableAppUpdate": True}}) + "\n")
    return binary, expected


def run_version(version, args):
    started = time.monotonic()
    row = {"version": version, "status": "fail"}
    args.logs.mkdir(parents=True, exist_ok=True)
    report = args.logs / f"{version}.json"
    report.unlink(missing_ok=True)
    try:
        binary, checksum = prepare_browser(version, args.cache, args.offline)
        row["archive_sha512"] = checksum
        command = [sys.executable, str(ROOT / "scripts/firefox-smoke.py"),
                   "--firefox", str(binary), "--extension", str(args.extension),
                   "--expect-version", version, "--report", str(report),
                   "--browser-log", str(args.logs / f"{version}-browser.log")]
        # The smoke process owns a Firefox process tree. Clean up the whole group
        # if the harness hangs, rather than leaving an old browser running.
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            (args.logs / f"{version}.log").write_text(stdout + stderr)
            raise TimeoutError("Smoke test exceeded 120 seconds; its process group was stopped")
        (args.logs / f"{version}.log").write_text(stdout + stderr)
        details = json.loads(report.read_text()) if report.exists() else {}
        row.update(details)
        if process.returncode == 0 and details.get("ok") and details.get("browser_version") == version:
            row["status"] = "pass"
        else:
            row["error"] = details.get("error", f"Smoke process exited {process.returncode}; see compatibility/logs/{version}.log")
    except BuildUnavailable as error:
        row.update(status="unavailable", error=str(error))
    except Exception as error:
        row["error"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            row["error"] += ": " + (error.stderr or "")[-1000:]
    row["seconds"] = round(time.monotonic() - started, 2)
    return row


def resumable(row, previous, metadata):
    return (row.get("status") == "pass" and row.get("ok") is True and
            row.get("browser_version") == row.get("version") and
            all(previous.get(key) == metadata.get(key) for key in
                ("extension_sha256", "suite_sha256", "platform")))


def save_results(destination, metadata, versions, rows):
    ordered = [rows[version] for version in versions if version in rows]
    result = {**metadata, "requested_versions": versions, "results": ordered,
              "complete": len(ordered) == len(versions)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(".json.part")
    part.write_text(json.dumps(result, indent=2) + "\n")
    part.replace(destination)
    passed = sum(row["status"] == "pass" for row in ordered)
    failed = sum(row["status"] == "fail" for row in ordered)
    unavailable = sum(row["status"] == "unavailable" for row in ordered)
    lines = ["# Firefox compatibility results", "",
             f"{passed} passed; {failed} failed; {unavailable} builds unavailable; {len(versions) - len(ordered)} pending.", "",
             "Platform: Linux x86_64, en-US, headless; regular stable releases (including point releases).",
             "ESR, beta, developer edition, nightly, Android, Windows and macOS are outside this matrix.", "",
             f"Run started (UTC): {metadata['started_at']}",
             f"Extension SHA-256: `{metadata['extension_sha256']}`",
             f"Suite SHA-256: `{metadata['suite_sha256']}`", "",
             "Both native sorting menu commands, natural ordering, group and gap boundaries, pinned/hidden tabs,",
             "active tab and container preservation, window isolation, and repeat-sort idempotence are checked.",
             "Split-view preservation is additionally checked from Firefox 149; earlier versions explicitly skip only that feature.", "",
             "| Firefox | Result | Split views | Notes |", "| --- | --- | --- | --- |"]
    for row in ordered:
        split = "checked" if row["status"] == "pass" and not row.get("skipped") else "not available" if row["status"] == "pass" else "—"
        note = row.get("error", "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['version']} | {row['status']} | {split} | {note} |")
    lines.extend(["", "Browsers come from [Mozilla's release archive](https://archive.mozilla.org/pub/firefox/releases/)",
                  "and are checked against the release's SHA512SUMS before extraction. Browser caches and detailed logs remain local and are ignored by Git.", ""])
    destination.with_suffix(".md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "compatibility/releases.json")
    parser.add_argument("--versions", help="Comma-separated subset, e.g. 140.0,149.0,160.0.1")
    parser.add_argument("--extension", type=Path, default=ROOT / "extension")
    parser.add_argument("--cache", type=Path, default=ROOT / ".firefox-cache")
    parser.add_argument("--results", type=Path, help="Default: compatibility/results.json (subsets go under logs/)")
    parser.add_argument("--logs", type=Path, default=ROOT / "compatibility/logs")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--resume", action="store_true", help="Reuse passes only for identical extension/suite hashes")
    parser.add_argument("--offline", action="store_true", help="Require cached browsers/checksums; do not download")
    parser.add_argument("--discover", action="store_true", help="Refresh the pinned stable version list, then exit")
    parser.add_argument("--minimum", default="140.0")
    parser.add_argument("--maximum", default="160.0.1")
    args = parser.parse_args()
    if args.results is None:
        args.results = ROOT / ("compatibility/logs/subset-results.json" if args.versions else "compatibility/results.json")
    if sys.version_info < (3, 12):
        parser.error("Python 3.12+ is required for filtered archive extraction")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("This matrix downloads Linux x86_64 Firefox builds only")
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    for name in ("extension", "cache", "results", "logs", "manifest"):
        setattr(args, name, getattr(args, name).resolve())
    if args.discover:
        # A fresh index is intentional; cached browser archives remain reusable.
        with tempfile.TemporaryDirectory(prefix="firefox-release-index-") as temporary:
            index = Path(temporary) / "releases.html"
            download(ARCHIVE, index, args.offline)
            versions = discover_versions(index.read_text(), args.minimum, args.maximum)
        if not versions or args.minimum not in versions or args.maximum not in versions:
            parser.error("Release index does not contain both requested boundary versions")
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps({"source": ARCHIVE, "platform": "linux-x86_64",
            "locale": "en-US", "channel": "stable", "minimum": args.minimum,
            "maximum": args.maximum, "versions": versions}, indent=2) + "\n")
        print(f"Pinned {len(versions)} versions in {args.manifest}")
        return 0

    manifest = json.loads(args.manifest.read_text())
    versions = args.versions.split(",") if args.versions else manifest["versions"]
    versions = sorted(set(versions), key=version_key)
    if not versions:
        parser.error("No versions requested")
    if not args.extension.exists():
        parser.error("Extension not found; build the ZIP first or pass --extension extension")
    metadata = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "platform": "linux-x86_64/en-US",
        "extension_sha256": tree_hash(args.extension),
        "suite_sha256": hashlib.sha256(b"".join((ROOT / "scripts" / name).read_bytes()
            for name in ("firefox-smoke.py", "firefox-smoke.js", "firefox-matrix.py"))).hexdigest(),
    }
    previous = json.loads(args.results.read_text()) if args.resume and args.results.exists() else {}
    rows = {row["version"]: row for row in previous.get("results", [])
            if row["version"] in versions and resumable(row, previous, metadata)}
    todo = [version for version in versions if version not in rows]
    save_results(args.results, metadata, versions, rows)
    print(f"Testing {len(todo)} versions; reusing {len(rows)} matching passes; {args.jobs} concurrent browsers.", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_version, version, args): version for version in todo}
        for future in as_completed(futures):
            row = future.result()
            rows[row["version"]] = row
            save_results(args.results, metadata, versions, rows)
            print(f"[{len(rows)}/{len(versions)}] {row['version']}: {row['status']} ({row['seconds']}s)"
                  + (f" — {row['error']}" if "error" in row else ""), flush=True)
    print(f"Results: {args.results.with_suffix('.md')}", flush=True)
    return 1 if any(row["status"] != "pass" for row in rows.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
