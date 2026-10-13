"""
Sift Local Desktop Runtime Harness
Launches backend FastAPI analytical server and Microsoft Edge / WebView2 in standalone app mode.
Enforces air-gapped sandboxing flags, isolated user profile, and dual-process supervision.
"""

import os
import sys
import time
import signal
import socket
import argparse
import tempfile
import subprocess
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Optional, List

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    REPO_ROOT = Path(sys._MEIPASS)
else:
    REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def is_port_in_use(host: str, port: int) -> bool:
    """Check if a TCP port is currently open and accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def probe_sift_health(url: str, timeout: float = 1.0) -> bool:
    """Probe Sift /api/health endpoint to verify active backend instance."""
    health_url = f"{url.rstrip('/')}/api/health"
    try:
        req = urllib.request.Request(
            health_url,
            headers={"Host": "127.0.0.1:8765", "User-Agent": "Sift-Desktop-Harness"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                app_name = str(data.get("app", "")).lower()
                status_val = str(data.get("status", "")).lower()
                return app_name == "sift" and status_val in ("ok", "healthy")
    except Exception:
        return False
    return False


def wait_for_backend(url: str, max_wait: float = 15.0) -> bool:
    """Poll Sift health endpoint until backend is ready or timeout occurs."""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if probe_sift_health(url, timeout=0.5):
            return True
        time.sleep(0.2)
    return False


def find_edge_browser() -> Optional[str]:
    """Discover Microsoft Edge or Chromium executable on Windows host."""
    candidates = [
        # Standard 64-bit / 32-bit Edge locations on Windows
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Local app data Edge installation
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        # Playwright bundled Chromium (pre-installed on host)
        os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-1117\chrome-win\chrome.exe"),
        # Standard Google Chrome locations
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Search wildcard playwright paths
    playwright_base = Path(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"))
    if playwright_base.is_dir():
        for match in playwright_base.glob("chromium-*/chrome-win/chrome.exe"):
            if match.is_file():
                return str(match)

    # Search PATH
    for cmd in ["msedge", "chrome", "msedge.exe", "chrome.exe"]:
        try:
            res = subprocess.run(["where", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                first_path = res.stdout.strip().splitlines()[0]
                if os.path.isfile(first_path):
                    return first_path
        except Exception:
            pass

    return None


def build_browser_args(browser_exe: str, app_url: str, profile_dir: str) -> List[str]:
    """Construct command-line arguments for standalone, air-gapped app window."""
    return [
        browser_exe,
        f"--app={app_url}",
        "--window-size=1440,900",
        f"--user-data-dir={profile_dir}",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-breakpad",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
    ]


def main():
    parser = argparse.ArgumentParser(description="Sift Commercial Audit Desktop Harness")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host to bind backend (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind backend (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Launch backend server only without browser window")
    parser.add_argument("--browser-path", default=None, help="Explicit path to browser executable")
    parser.add_argument("--profile-dir", default=None, help="Custom isolated user data directory")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)

    app_url = f"http://{args.host}:{args.port}"
    server_instance = None
    server_thread = None
    spawned_backend = False

    # 1. Check if backend is already running
    if is_port_in_use(args.host, args.port):
        if probe_sift_health(app_url):
            print(f"[HARNESS] Detected active Sift backend on {app_url}. Reusing existing instance.")
        else:
            print(f"[ERROR] Port {args.port} is in use by an unrecognized foreign service.")
            print("Please terminate the existing service or choose another port via --port.")
            sys.exit(1)
    else:
        # 2. Spawn backend in daemon thread
        print(f"[HARNESS] Starting Sift backend server on {app_url}...")
        import threading
        import uvicorn
        from backend.app import app

        server_config = uvicorn.Config(
            app=app,
            host=args.host,
            port=args.port,
            log_level="warning",
            access_log=False,
        )
        server_instance = uvicorn.Server(config=server_config)
        server_thread = threading.Thread(target=server_instance.run, daemon=True)
        server_thread.start()
        spawned_backend = True

        # Wait for backend to be healthy
        print("[HARNESS] Awaiting backend initialization...")
        if not wait_for_backend(app_url, max_wait=15.0):
            print("[ERROR] Backend server failed to start or respond to health checks within 15 seconds.")
            if server_instance:
                server_instance.should_exit = True
            sys.exit(1)
        print(f"[HARNESS] Sift backend is operational on {app_url}.")

    # Clean shutdown handler
    edge_proc: Optional[subprocess.Popen] = None

    def cleanup(signum=None, frame=None):
        print("\n[HARNESS] Terminating Sift processes...")
        if edge_proc and edge_proc.poll() is None:
            edge_proc.terminate()
        if server_instance:
            server_instance.should_exit = True
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Headless mode
    if args.no_browser:
        print(f"[HARNESS] Running in headless mode on {app_url}. Press Ctrl+C to stop.")
        try:
            while server_thread and server_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[HARNESS] Shutting down...")
            cleanup()
        return

    # Find browser
    browser_bin = args.browser_path or find_edge_browser()
    if not browser_bin:
        print("[WARNING] Edge or Chromium executable not found. Opening in system default browser.")
        import webbrowser
        webbrowser.open(app_url)
        try:
            while server_thread and server_thread.is_alive():
                time.sleep(1.0)
        except KeyboardInterrupt:
            cleanup()
        return

    # Create isolated user data directory
    if args.profile_dir:
        profile_dir = Path(args.profile_dir)
    else:
        profile_dir = Path(tempfile.gettempdir()) / "sift_desktop_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    browser_args = build_browser_args(browser_bin, app_url, str(profile_dir))
    print(f"[HARNESS] Launching standalone app window: {browser_bin}")
    edge_proc = subprocess.Popen(browser_args)

    # Wait for user to close browser window
    edge_proc.wait()
    print("[HARNESS] Desktop window closed by user. Shutting down backend...")
    cleanup()


if __name__ == "__main__":
    main()
