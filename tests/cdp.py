"""Minimal browser harness for the front-end tests.

Serves the repository over HTTP, starts a headless Chromium/Chrome and speaks the
DevTools protocol over a WebSocket. Standard library only, so the tests need no
Python packages; Chromium or Chrome must be installed.
"""

from __future__ import annotations

import base64
import functools
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

BROWSER_NAMES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "chrome",
)


def free_port() -> int:
    """Return a currently unused localhost TCP port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def find_browser() -> str | None:
    """Path of the first installed Chromium-family browser, if any."""
    for name in BROWSER_NAMES:
        path = shutil.which(name)
        if path:
            return path
    return None


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler that does not log every request."""

    def log_message(self, *args: Any) -> None:
        pass


class DevToolsSocket:
    """Small RFC 6455 client for the DevTools protocol (text frames only)."""

    def __init__(self, url: str) -> None:
        parts = urlsplit(url)
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parts.path} HTTP/1.1\r\n"
            f"Host: {parts.hostname}:{parts.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://{parts.hostname}:{parts.port}\r\n"
            "\r\n"
        )
        self.socket.sendall(request.encode())
        self.buffer = b""
        header = self._read_until(b"\r\n\r\n")
        status = header.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise RuntimeError(
                f"DevTools refused the WebSocket: {status.decode(errors='replace')}"
            )
        self.fragments = b""

    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self.buffer:
            chunk = self.socket.recv(65536)
            if not chunk:
                raise RuntimeError(
                    "DevTools closed the connection during the handshake"
                )
            self.buffer += chunk
        head, _, self.buffer = self.buffer.partition(marker)
        return head

    def _read(self, size: int) -> bytes:
        while len(self.buffer) < size:
            chunk = self.socket.recv(65536)
            if not chunk:
                raise RuntimeError("DevTools closed the connection")
            self.buffer += chunk
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        header += mask
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def send(self, message: str) -> None:
        self._send_frame(0x1, message.encode())

    def receive(self) -> str:
        """Next complete text message, answering pings as needed."""
        while True:
            first, second = self._read(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if masked else b""
            payload = self._read(length)
            if mask:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )
            if opcode == 0x9:  # ping
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x8:
                raise RuntimeError("DevTools closed the WebSocket")
            if opcode == 0xA:  # pong
                continue
            self.fragments += payload
            if not final:
                continue
            message, self.fragments = self.fragments, b""
            return message.decode()

    def close(self) -> None:
        try:
            self.socket.close()
        except OSError:
            pass


class BrowserSession:
    """A served site plus a headless browser, driven over the DevTools protocol."""

    def __init__(self, root: Path, width: int = 1280, height: int = 900) -> None:
        self.root = root
        self.width = width
        self.height = height
        browser_path = find_browser()
        if not browser_path:
            raise BrowserUnavailable("Chromium or Chrome is not installed")
        self.browser_path = browser_path
        self._profile = tempfile.mkdtemp(prefix="portfolio-browser-")
        self._server: http.server.ThreadingHTTPServer | None = None
        self._browser: subprocess.Popen[bytes] | None = None
        self._ws: DevToolsSocket | None = None
        self._message_id = 0
        self.exceptions: list[str] = []
        self._started = False

    # -- lifecycle ------------------------------------------------------

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def start(self) -> None:
        """Serve the root, launch the browser and load the page."""
        self._started = True
        handler = functools.partial(QuietHandler, directory=str(self.root))
        self._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", free_port()), handler
        )
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        site = f"http://127.0.0.1:{self._server.server_address[1]}/"

        debug_port = free_port()
        self._browser = subprocess.Popen(
            [
                self.browser_path,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--hide-scrollbars",
                "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={self._profile}",
                "--window-size=1280,900",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        page = self._wait_for_page(debug_port)
        self._ws = DevToolsSocket(page["webSocketDebuggerUrl"])
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Page.navigate", {"url": site})

        def rendered() -> bool:
            try:
                return bool(
                    self.js(
                        "document.readyState === 'complete'"
                        " && document.querySelectorAll('.project-title').length > 0"
                    )
                )
            except RuntimeError:
                return False

        self.wait_until(rendered, timeout=15, message="the project list did not render")
        self.set_viewport(self.width, self.height)
        self.wait(300)

    def _wait_for_page(self, debug_port: int) -> dict[str, Any]:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{debug_port}/json/list", timeout=0.5
                ) as response:
                    targets = json.load(response)
                page = next(
                    (target for target in targets if target["type"] == "page"), None
                )
                if page:
                    return page
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError("the browser did not expose a page target")

    def close(self) -> None:
        if self._ws:
            self._ws.close()
            self._ws = None
        if self._browser:
            self._browser.terminate()
            try:
                self._browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._browser.kill()
                self._browser.wait(timeout=5)
            self._browser = None
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._started:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._started = False

    # -- protocol -------------------------------------------------------

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one DevTools command and return its result."""
        if not self._ws:
            raise RuntimeError("the session is not running")
        self._message_id += 1
        message_id = self._message_id
        self._ws.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(self._ws.receive())
            if "method" in message:
                self._record_event(message)
                continue
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    def _record_event(self, message: dict[str, Any]) -> None:
        if message["method"] == "Runtime.exceptionThrown":
            details = message.get("params", {}).get("exceptionDetails", {})
            text = details.get("exception", {}).get("description") or details.get(
                "text", "exception"
            )
            self.exceptions.append(text)

    def js(self, expression: str) -> Any:
        """Evaluate an expression in the page and return its value."""
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            raise RuntimeError(
                f"page evaluation failed: {details.get('text')} {details.get('exception', {}).get('description', '')}"
            )
        return result["result"].get("value")

    def wait(self, milliseconds: int) -> None:
        time.sleep(milliseconds / 1000)

    def wait_until(
        self, predicate: Callable[[], Any], timeout: float = 3.0, message: str = ""
    ) -> None:
        """Poll a page predicate until it is true or the timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError(message or "condition was not met in time")

    # -- input ----------------------------------------------------------

    def wheel(
        self,
        x: float,
        y: float,
        delta_y: float,
        count: int = 1,
        gap_ms: int = 0,
        delta_x: float = 0,
    ) -> None:
        """Dispatch one or more mouse-wheel events at a page coordinate."""
        for _ in range(count):
            self.call(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": delta_x,
                    "deltaY": delta_y,
                    "modifiers": 0,
                },
            )
            if gap_ms:
                self.wait(gap_ms)

    def touch_swipe(
        self, x: float, y: float, delta_x: float, delta_y: float, steps: int = 4
    ) -> None:
        """Drag one finger from (x, y) by the given offset, then lift it."""
        self.call(
            "Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1}
        )
        self.call(
            "Input.dispatchTouchEvent",
            {
                "type": "touchStart",
                "touchPoints": [{"x": x, "y": y, "id": 1}],
            },
        )
        for step in range(1, steps + 1):
            self.call(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchMove",
                    "touchPoints": [
                        {
                            "x": x + delta_x * step / steps,
                            "y": y + delta_y * step / steps,
                            "id": 1,
                        }
                    ],
                },
            )
            self.wait(16)
        self.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        self.wait(50)  # let the page handle touchend before emulation is switched off
        self.call("Emulation.setTouchEmulationEnabled", {"enabled": False})

    def key(self, name: str, code: str, virtual_key_code: int) -> None:
        """Press and release a key."""
        for event_type in ("rawKeyDown", "keyUp"):
            self.call(
                "Input.dispatchKeyEvent",
                {
                    "type": event_type,
                    "key": name,
                    "code": code,
                    "windowsVirtualKeyCode": virtual_key_code,
                    "nativeVirtualKeyCode": virtual_key_code,
                },
            )

    # -- viewport -------------------------------------------------------

    def set_viewport(self, width: int, height: int, mobile: bool = False) -> None:
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": mobile,
            },
        )

    def clear_viewport(self) -> None:
        self.call("Emulation.clearDeviceMetricsOverride")


class BrowserUnavailable(RuntimeError):
    """No Chromium-family browser is installed."""
