"""Synchronous VNC session wrapper around vncdotool."""

from __future__ import annotations

from io import BytesIO
import threading
import time
from typing import Any

from vncdotool import api
from vncdotool.client import VNCDoToolClient, VNCDoToolFactory


class _ClipboardClient(VNCDoToolClient):
    def copy_text(self, text: str) -> None:
        self.factory.latest_clipboard = text


class _ClipboardFactory(VNCDoToolFactory):
    protocol = _ClipboardClient
    latest_clipboard = ""
    force_caps = True


class VNCSession:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self.client: Any | None = None
        self.host: str | None = None
        self.port: int | None = None
        self.name: str | None = None
        self.width: int | None = None
        self.height: int | None = None
        self._lock = threading.RLock()
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()

    def connect(self, host: str, port: int = 5900, password: str | None = None) -> dict[str, Any]:
        if not host.strip():
            raise ValueError("host must not be empty")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        with self._lock:
            self.disconnect()
            endpoint_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
            endpoint = f"{endpoint_host}::{port}"
            _ClipboardFactory.latest_clipboard = ""
            self.client = api.connect(
                endpoint,
                password=password,
                timeout=self.timeout,
                factory_class=_ClipboardFactory,
            )
            try:
                # api.connect starts the background reactor; an initial refresh waits
                # for protocol negotiation and the server's first framebuffer update.
                self.client.refreshScreen(incremental=False)
            except Exception:
                self.disconnect()
                raise
            self.host, self.port = host, port
            raw_name = getattr(self.client.protocol, "name", "")
            self.name = raw_name.decode("utf-8", "replace") if isinstance(raw_name, bytes) else str(raw_name)
            screen = getattr(self.client.protocol, "screen", None)
            if screen is not None:
                self.width, self.height = screen.size
            return self.status()

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            client, self.client = self.client, None
            if client is not None:
                for key in tuple(self._held_keys):
                    try:
                        client.keyUp(key)
                    except Exception:
                        pass
                for button in tuple(self._held_buttons):
                    try:
                        client.mouseUp({"left": 1, "middle": 2, "right": 3}[button])
                    except Exception:
                        pass
                self._held_keys.clear()
                self._held_buttons.clear()
                client.disconnect()
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            screen = getattr(getattr(self.client, "protocol", None), "screen", None)
            if screen is not None:
                self.width, self.height = screen.size
            return {
                "connected": self.client is not None,
                "host": self.host,
                "port": self.port,
                "name": self.name,
                "width": self.width,
                "height": self.height,
            }

    def _require_client(self) -> Any:
        if self.client is None:
            raise ConnectionError("Not connected; call vnc_connect first")
        return self.client

    def screenshot(self) -> tuple[bytes, int, int]:
        with self._lock:
            client = self._require_client()
            output = BytesIO()
            client.captureScreen(output, format="PNG")
            image_data = output.getvalue()
            screen = getattr(client.protocol, "screen", None)
            if screen is not None:
                self.width, self.height = screen.size
            if not self.width or not self.height:
                raise RuntimeError("VNC client did not report screen dimensions")
            return image_data, self.width, self.height

    def _check_point(self, x: int, y: int) -> None:
        client = self._require_client()
        screen = getattr(client.protocol, "screen", None)
        if screen is not None:
            self.width, self.height = screen.size
        if self.width is not None and self.height is not None:
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise ValueError(f"coordinates must be within {self.width}x{self.height}")

    def click(self, x: int, y: int, button: str = "left", count: int = 1) -> dict[str, Any]:
        buttons = {"left": 1, "middle": 2, "right": 3}
        if button not in buttons:
            raise ValueError("button must be left, middle, or right")
        if not 1 <= count <= 3:
            raise ValueError("count must be between 1 and 3")
        with self._lock:
            self._check_point(x, y)
            client = self._require_client()
            client.mouseMove(x, y)
            for _ in range(count):
                client.mousePress(buttons[button])
            return {"clicked": button, "count": count, "x": x, "y": y}

    def move(self, x: int, y: int) -> dict[str, Any]:
        with self._lock:
            self._check_point(x, y)
            self._require_client().mouseMove(x, y)
            return {"moved": True, "x": x, "y": y}

    def drag(self, x1: int, y1: int, x2: int, y2: int, button: str = "left") -> dict[str, Any]:
        buttons = {"left": 1, "middle": 2, "right": 3}
        if button not in buttons:
            raise ValueError("button must be left, middle, or right")
        with self._lock:
            self._check_point(x1, y1)
            self._check_point(x2, y2)
            client = self._require_client()
            client.mouseMove(x1, y1)
            client.mouseDown(buttons[button])
            distance = max(abs(x2 - x1), abs(y2 - y1))
            step = max(1, (distance + 29) // 30)
            try:
                client.mouseDrag(x2, y2, step=step)
            finally:
                client.mouseUp(buttons[button])
            return {"dragged": button, "from": [x1, y1], "to": [x2, y2]}

    def scroll(self, x: int, y: int, direction: str, amount: int = 1) -> dict[str, Any]:
        buttons = {"up": 4, "down": 5, "left": 6, "right": 7}
        if direction not in buttons:
            raise ValueError("direction must be up, down, left, or right")
        if not 1 <= amount <= 20:
            raise ValueError("amount must be between 1 and 20")
        with self._lock:
            self._check_point(x, y)
            client = self._require_client()
            client.mouseMove(x, y)
            for _ in range(amount):
                client.mousePress(buttons[direction])
            return {"scrolled": direction, "amount": amount, "x": x, "y": y}

    def keypress(self, key: str) -> dict[str, Any]:
        if not key.strip():
            raise ValueError("key must not be empty")
        with self._lock:
            self._require_client().keyPress(self._normalize_key(key))
            return {"pressed": key}

    def key_down(self, key: str) -> dict[str, Any]:
        if not key.strip():
            raise ValueError("key must not be empty")
        with self._lock:
            normalized = self._normalize_key(key)
            self._require_client().keyDown(normalized)
            self._held_keys.add(normalized)
            return {"key_down": key}

    def key_up(self, key: str) -> dict[str, Any]:
        if not key.strip():
            raise ValueError("key must not be empty")
        with self._lock:
            normalized = self._normalize_key(key)
            self._require_client().keyUp(normalized)
            self._held_keys.discard(normalized)
            return {"key_up": key}

    @staticmethod
    def _normalize_key(key: str) -> str:
        parts = key.strip().replace("+", "-").split("-")
        aliases = {
            "backspace": "bsp", "escape": "esc", "return": "enter",
            "insert": "ins", "pageup": "pgup", "pagedown": "pgdn",
            "windows": "super", "win": "super",
        }
        parts = [aliases.get(part.lower(), part) for part in parts]
        if len(parts) > 1:
            return "-".join(part.lower() for part in parts)
        if len(parts[0]) == 1:
            return parts[0]
        return parts[0].lower()

    def mouse_down(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        buttons = {"left": 1, "middle": 2, "right": 3}
        if button not in buttons:
            raise ValueError("button must be left, middle, or right")
        with self._lock:
            self._check_point(x, y)
            client = self._require_client()
            client.mouseMove(x, y)
            client.mouseDown(buttons[button])
            self._held_buttons.add(button)
            return {"mouse_down": button, "x": x, "y": y}

    def mouse_up(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        buttons = {"left": 1, "middle": 2, "right": 3}
        if button not in buttons:
            raise ValueError("button must be left, middle, or right")
        with self._lock:
            self._check_point(x, y)
            client = self._require_client()
            client.mouseMove(x, y)
            client.mouseUp(buttons[button])
            self._held_buttons.discard(button)
            return {"mouse_up": button, "x": x, "y": y}

    def type_text(self, text: str, delay_ms: int = 0) -> dict[str, Any]:
        if len(text) > 100_000:
            raise ValueError("text is limited to 100,000 characters per call")
        if not 0 <= delay_ms <= 1000:
            raise ValueError("delay_ms must be between 0 and 1000")
        with self._lock:
            client = self._require_client()
            for char in text:
                if char in "\r":
                    continue
                if char == "\n":
                    client.keyPress("enter")
                elif char == "\t":
                    client.keyPress("tab")
                elif ord(char) <= 0xFF:
                    client.keyPress("minus" if char == "-" else char)
                else:
                    # Unicode keysyms per X11 convention. App locale/IME support varies.
                    client.keyEvent(0x01000000 | ord(char), down=True)
                    client.keyEvent(0x01000000 | ord(char), down=False)
                if delay_ms:
                    client.pause(delay_ms / 1000.0)
            return {"typed_characters": len(text)}

    def clipboard_set(self, text: str) -> dict[str, Any]:
        if len(text) > 100_000:
            raise ValueError("clipboard text is limited to 100,000 characters")
        try:
            text.encode("iso-8859-1")
        except UnicodeEncodeError as exc:
            raise ValueError("VNC clipboard text supports ISO-8859-1 characters only") from exc
        with self._lock:
            self._require_client().paste(text)
            return {"clipboard_characters": len(text)}

    def clipboard_get(self) -> dict[str, Any]:
        with self._lock:
            client = self._require_client()
            return {"text": client.factory.latest_clipboard}

    def wait(self, seconds: float) -> dict[str, Any]:
        if not 0 <= seconds <= 60:
            raise ValueError("seconds must be between 0 and 60")
        with self._lock:
            self._require_client()
            time.sleep(seconds)
        return {"waited_seconds": seconds}
