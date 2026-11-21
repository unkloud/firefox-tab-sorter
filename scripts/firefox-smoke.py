#!/usr/bin/env python3
"""Run the actual extension/menu in a disposable Firefox profile using Marionette.

Python standard library only; never connects to the user's Firefox profile.
"""

import argparse
import hashlib
import html
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent


def extension_digest(path):
    """Hash the exact package, or all relative filenames and bytes for a source tree."""
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    else:
        for file in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(file.relative_to(path).as_posix().encode() + b"\0")
            digest.update(file.read_bytes())
    return digest.hexdigest()


class PageHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        title = html.escape(urllib.parse.unquote(self.path.lstrip("/")))
        body = f"<!doctype html><title>{title}</title><h1>{title}</h1>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class Marionette:
    def __init__(self, connection):
        self.connection = connection
        self.stream = connection.makefile("rb")
        self.message_id = 0
        self.receive()  # Protocol handshake.

    def receive(self):
        length = b""
        while True:
            byte = self.stream.read(1)
            if not byte:
                raise ConnectionError("Firefox closed the Marionette connection")
            if byte == b":":
                break
            length += byte
        return json.loads(self.stream.read(int(length)))

    def command(self, name, parameters=None):
        self.message_id += 1
        payload = json.dumps([0, self.message_id, name, parameters or {}]).encode()
        self.connection.sendall(str(len(payload)).encode() + b":" + payload)
        kind, message_id, error, result = self.receive()
        if kind != 1 or message_id != self.message_id:
            raise RuntimeError("Unexpected Marionette reply")
        if error:
            raise RuntimeError(json.dumps(error))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firefox", default=shutil.which("firefox"))
    parser.add_argument("--extension", type=Path, default=ROOT / "extension")
    parser.add_argument("--expect-version", help="Fail if the browser runs a different version")
    parser.add_argument("--report", type=Path, help="Save a machine-readable result, including failures")
    parser.add_argument("--browser-log", type=Path, help="Retain Firefox's diagnostic log")
    args = parser.parse_args()
    if not args.firefox:
        parser.error("Firefox was not found; specify --firefox /path/to/firefox")
    result_record = {
        "ok": False,
        "expected_version": args.expect_version,
        "extension_sha256": extension_digest(args.extension.resolve()),
    }

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        marionette_port = reservation.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        with tempfile.TemporaryDirectory(prefix="firefox-tab-sorter-smoke-") as directory:
            profile = Path(directory) / "profile"
            profile.mkdir()
            preferences = {
                "marionette.port": marionette_port,
                "browser.shell.checkDefaultBrowser": False,
                "browser.startup.homepage": "about:blank",
                "browser.startup.page": 0,
                "browser.startup.homepage_override.mstone": "ignore",
                "browser.aboutwelcome.enabled": False,
                "browser.tabs.groups.enabled": True,
                "browser.tabs.splitView.enabled": True,
                "browser.newtabpage.enabled": False,
                "datareporting.policy.dataSubmissionEnabled": False,
                "toolkit.telemetry.reportingpolicy.firstRun": False,
                "extensions.update.enabled": False,
                "app.update.auto": False,
                "app.update.disabledForTesting": True,
                "browser.sessionstore.resume_from_crash": False,
                "browser.tabs.warnOnClose": False,
                "network.proxy.type": 0,
            }
            (profile / "user.js").write_text("\n".join(
                f"user_pref({json.dumps(key)}, {json.dumps(value)});"
                for key, value in preferences.items()
            ))
            with (Path(directory) / "firefox.log").open("w+") as log:
                process = subprocess.Popen([
                    args.firefox, "--headless", "--no-remote", "--profile", str(profile),
                    "--marionette", "--remote-allow-system-access", "about:blank",
                ], stdout=log, stderr=log, env={**os.environ, "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1"})
                client = None
                try:
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError(f"Firefox exited with {process.returncode}")
                        try:
                            connection = socket.create_connection(("127.0.0.1", marionette_port), timeout=1)
                            connection.settimeout(55)
                            client = Marionette(connection)
                            break
                        except (ConnectionRefusedError, TimeoutError):
                            time.sleep(0.1)
                    if client is None:
                        raise TimeoutError("Firefox did not start Marionette within 30 seconds")
                    session = client.command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
                    actual_version = session["capabilities"]["browserVersion"]
                    result_record["browser_version"] = actual_version
                    print("Firefox:", actual_version, "(disposable headless profile)", flush=True)
                    if args.expect_version and actual_version != args.expect_version:
                        raise AssertionError(f"Expected {args.expect_version}, got {actual_version}")
                    print("Installed:", client.command("Addon:Install", {
                        "path": str(args.extension.resolve()), "temporary": True,
                    }), flush=True)
                    client.command("Marionette:SetContext", {"value": "chrome"})
                    client.command("WebDriver:SetTimeouts", {"script": 50000})
                    result = client.command("WebDriver:ExecuteAsyncScript", {
                        "script": (ROOT / "scripts/firefox-smoke.js").read_text(),
                        "args": [server.server_port], "newSandbox": True,
                    })
                    print(json.dumps(result, indent=2), flush=True)
                    value = result.get("value", result)
                    result_record.update(value)
                    if not value.get("ok"):
                        raise AssertionError("Firefox smoke test failed")
                except Exception as error:
                    result_record["ok"] = False
                    result_record.setdefault("error", str(error))
                    log.flush()
                    log.seek(0)
                    print(log.read()[-10000:], flush=True)
                    raise
                finally:
                    if client:
                        client.stream.close()
                        client.connection.close()
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    if args.browser_log:
                        args.browser_log.parent.mkdir(parents=True, exist_ok=True)
                        log.flush()
                        shutil.copyfile(log.name, args.browser_log)
    finally:
        server.shutdown()
        server.server_close()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result_record, indent=2) + "\n")


if __name__ == "__main__":
    main()
