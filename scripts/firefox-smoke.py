#!/usr/bin/env python3
"""Run the actual extension/menu in a disposable Firefox profile using Marionette.

Python standard library only; never connects to the user's Firefox profile.
"""

import argparse
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
    args = parser.parse_args()
    if not args.firefox:
        parser.error("Firefox was not found; specify --firefox /path/to/firefox")

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
                    print("Firefox:", session["capabilities"]["browserVersion"], "(disposable headless profile)", flush=True)
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
                    if not value.get("ok"):
                        raise AssertionError("Firefox smoke test failed")
                except Exception:
                    log.flush()
                    log.seek(0)
                    print(log.read()[-10000:], flush=True)
                    raise
                finally:
                    if client:
                        client.connection.close()
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
