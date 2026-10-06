"""MCP stdio server exposing screenshot-based VNC controls."""

from __future__ import annotations

import asyncio
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

from .client import VNCSession


SESSION = VNCSession(timeout=float(os.environ.get("VNC_TIMEOUT", "15")))
DEFAULT_HOST = os.environ.get("VNC_HOST")
DEFAULT_PORT = int(os.environ.get("VNC_PORT", "5900"))
PASSWORD_ENV = os.environ.get("VNC_PASSWORD_ENV", "VNC_PASSWORD")
mcp = FastMCP(
    "VNC Desktop",
    instructions=(
        "Control a remote desktop through VNC. Always call vnc_screenshot after connecting "
        "to inspect the screen; coordinates use the returned image's native pixel dimensions. "
        "Call vnc_screenshot again after actions to verify the result."
    ),
)


@mcp.tool()
async def vnc_connect(host: str = "", port: int = 0, password: str = "") -> dict:
    """Connect to a VNC desktop. Host/port may come from VNC_HOST and VNC_PORT. Password is optional."""
    target_host = host.strip() or DEFAULT_HOST
    target_port = port or DEFAULT_PORT
    if not target_host:
        raise ValueError("Provide host, or set VNC_HOST before starting the server")
    target_password = password or os.environ.get(PASSWORD_ENV) or None
    return await asyncio.to_thread(SESSION.connect, target_host, target_port, target_password)


@mcp.tool()
async def vnc_disconnect() -> dict:
    """Disconnect the current VNC session."""
    return await asyncio.to_thread(SESSION.disconnect)


@mcp.tool()
async def vnc_status() -> dict:
    """Return connection state, desktop name and screen dimensions."""
    return await asyncio.to_thread(SESSION.status)


@mcp.tool()
async def vnc_screenshot() -> list:
    """Capture the full desktop. Returns native dimensions and a PNG image for visual inspection."""
    data, width, height = await asyncio.to_thread(SESSION.screenshot)
    return [f"Screenshot: {width}x{height} pixels. Use coordinates in this native resolution.", Image(data=data, format="png")]


@mcp.tool()
async def vnc_click(x: int, y: int, button: str = "left", count: int = 1) -> dict:
    """Click at screen coordinates. button: left, middle, right; count: 1-3."""
    return await asyncio.to_thread(SESSION.click, x, y, button, count)


@mcp.tool()
async def vnc_move(x: int, y: int) -> dict:
    """Move the pointer to screen coordinates."""
    return await asyncio.to_thread(SESSION.move, x, y)


@mcp.tool()
async def vnc_drag(x1: int, y1: int, x2: int, y2: int, button: str = "left") -> dict:
    """Drag from one screen coordinate to another with a mouse button held."""
    return await asyncio.to_thread(SESSION.drag, x1, y1, x2, y2, button)


@mcp.tool()
async def vnc_scroll(x: int, y: int, direction: str, amount: int = 1) -> dict:
    """Scroll at a screen coordinate. direction: up, down, left, right; amount: 1-20."""
    return await asyncio.to_thread(SESSION.scroll, x, y, direction, amount)


@mcp.tool()
async def vnc_keypress(key: str) -> dict:
    """Press a key or chord, e.g. enter, ctrl-c, alt-tab, f5, or a."""
    return await asyncio.to_thread(SESSION.keypress, key)


@mcp.tool()
async def vnc_key_down(key: str) -> dict:
    """Hold a key down until vnc_key_up releases it."""
    return await asyncio.to_thread(SESSION.key_down, key)


@mcp.tool()
async def vnc_key_up(key: str) -> dict:
    """Release a key held with vnc_key_down."""
    return await asyncio.to_thread(SESSION.key_up, key)


@mcp.tool()
async def vnc_mouse_down(x: int, y: int, button: str = "left") -> dict:
    """Press and hold a mouse button at screen coordinates."""
    return await asyncio.to_thread(SESSION.mouse_down, x, y, button)


@mcp.tool()
async def vnc_mouse_up(x: int, y: int, button: str = "left") -> dict:
    """Release a mouse button at screen coordinates."""
    return await asyncio.to_thread(SESSION.mouse_up, x, y, button)


@mcp.tool()
async def vnc_type(text: str, delay_ms: int = 0) -> dict:
    """Type text into the focused desktop control; delay_ms optionally spaces key events."""
    return await asyncio.to_thread(SESSION.type_text, text, delay_ms)


@mcp.tool()
async def vnc_clipboard_set(text: str) -> dict:
    """Send text to the remote VNC clipboard (RFB client cut text)."""
    return await asyncio.to_thread(SESSION.clipboard_set, text)


@mcp.tool()
async def vnc_clipboard_get() -> dict:
    """Return the latest clipboard text announced by the remote VNC server."""
    return await asyncio.to_thread(SESSION.clipboard_get)


@mcp.tool()
async def vnc_wait(seconds: float = 1.0) -> dict:
    """Wait up to 60 seconds for an application to respond before taking another screenshot."""
    return await asyncio.to_thread(SESSION.wait, seconds)


def run() -> None:
    mcp.run(transport="stdio")
