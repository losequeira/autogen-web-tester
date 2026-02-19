"""
Native macOS launcher for AutoGen Web Tester.
Starts the Flask+SocketIO server in a background thread, then opens
a PyWebView window so the app runs without a browser tab.
"""

import socket
import subprocess
import sys
import threading
import time

import webview

from web_ui import app, socketio


def _find_free_port() -> int:
    """Return a random available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ensure_playwright_browsers() -> None:
    """Install Playwright's Chromium browser on first run if it's missing."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Attempt a quick launch; if it fails the browser is missing.
            browser = p.chromium.launch()
            browser.close()
    except Exception:
        print("Playwright browser not found — installing Chromium (one-time setup)…")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
        print("Playwright Chromium installed.")


def _start_server(port: int) -> None:
    """Run the Flask+SocketIO server (blocking, intended for a daemon thread)."""
    socketio.run(app, host="127.0.0.1", port=port, use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)


def main() -> None:
    port = _find_free_port()

    # Start Flask server in a daemon thread so it exits when the window closes.
    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    # Give Flask a moment to bind before PyWebView tries to connect.
    time.sleep(1.5)

    # Ensure Playwright browsers are available (non-blocking check).
    playwright_thread = threading.Thread(target=_ensure_playwright_browsers, daemon=True)
    playwright_thread.start()

    webview.create_window(
        "Web Tester",
        f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
