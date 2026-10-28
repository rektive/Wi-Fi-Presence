#!/usr/bin/env python3
"""Native Desktop Application Entry Point for Wi-Fi Presence Radar."""

import os
import signal
import socket
import subprocess
import sys
import time
import webview

# Fix WebKitGTK / GDK Protocol Error on Hyprland & Wayland
os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
os.environ["GDK_BACKEND"] = "x11,wayland"


def wait_for_server(host: str, port: int, timeout: float = 12.0) -> bool:
    """Waits until the FastAPI ASGI server is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.2)
    return False


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    python_bin = sys.executable

    print("[DESKTOP] Starting background telemetry engine...")
    backend_proc = subprocess.Popen(
        [python_bin, "main.py"],
        cwd=root_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        preexec_fn=os.setsid,  # Creates process group for clean kill
    )

    try:
        # Wait until FastAPI + WebSocket endpoints are live
        if not wait_for_server("127.0.0.1", 8000):
            print("[ERROR] Telemetry engine failed to initialize.")
            return

        print("[DESKTOP] Launching native window...")
        window = webview.create_window(
            title="Wi-Fi RF Presence Radar",
            url="http://localhost:8000",
            width=1400,
            height=900,
            resizable=True,
            min_size=(1024, 700),
            background_color="#0b0f17",
        )

        webview.start(debug=False)

    finally:
        print("\n[DESKTOP] Shutting down background engine...")
        try:
            os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        except OSError:
            backend_proc.terminate()
        backend_proc.wait(timeout=3)


if __name__ == "__main__":
    main()
