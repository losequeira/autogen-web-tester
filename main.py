"""
Native macOS launcher for AutoGen Web Tester.
Starts the Flask+SocketIO server in a background thread, then opens
a PyWebView native window so the app runs without a browser tab.
"""
import multiprocessing

# Must be called before any other code so PyWebView's spawned helper
# processes are handled correctly and don't re-run the server/window code.
multiprocessing.freeze_support()

import shutil
import socket
import subprocess
import sys
import threading
import time


_PREFERRED_PORT = 8765  # Fixed port so WebView localStorage persists across launches


def _find_free_port(preferred: int = _PREFERRED_PORT) -> int:
    """Try the preferred port first (keeps localStorage origin stable), then fall back."""
    for port in [preferred] + list(range(preferred + 1, preferred + 20)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    # Last resort: let the OS pick
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _find_python() -> str:
    """
    Return a path to a real Python interpreter.
    Inside a PyInstaller bundle sys.executable is the app binary itself,
    so we look for python3/python on PATH instead.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python3", "python"):
        path = shutil.which(name)
        if path:
            return path
    return "python3"  # last resort; will fail gracefully below


def _ensure_playwright_browsers() -> None:
    """Install Playwright's Chromium browser on first run if it's missing."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return  # already installed
    except Exception:
        pass

    python = _find_python()
    print(f"Playwright browser not found — installing Chromium (one-time setup)…")
    result = subprocess.run(
        [python, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("Playwright Chromium installed.")
    else:
        print(f"Could not auto-install Playwright browsers: {result.stderr.strip()}")
        print("Run manually: playwright install chromium")


def _start_server(port: int) -> None:
    """Run the Flask+SocketIO server. Imported here so child processes don't execute it."""
    from web_ui import app, socketio
    socketio.run(
        app,
        host="127.0.0.1",
        port=port,
        use_reloader=False,
        log_output=False,
        allow_unsafe_werkzeug=True,
    )


def main() -> None:
    import webview

    port = _find_free_port()

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    # Give Flask a moment to bind before PyWebView opens the window.
    time.sleep(1.5)

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
