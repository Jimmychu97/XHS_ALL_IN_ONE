from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Spider_XHS product platform.")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host.")
    parser.add_argument("--port", type=int, default=8000, help="Backend port.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn reload.")
    parser.add_argument("--with-frontend", action="store_true", default=True, help="Also start the frontend Vite dev server.")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend dev server port.")
    return parser.parse_args(argv)


def resolve_npm_executable() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise FileNotFoundError("npm was not found on PATH; install Node.js or start the frontend manually.")
    return npm


def build_frontend_command(port: int, npm_executable: Optional[str] = None) -> list[str]:
    npm = npm_executable or resolve_npm_executable()
    return [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]


def start_frontend(port: int) -> Optional[subprocess.Popen]:
    frontend_dir = ROOT / "frontend"
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        print("frontend/package.json not found; skipping frontend startup.")
        return None

    command = build_frontend_command(port)
    print(f"Starting frontend at http://127.0.0.1:{port}")
    return subprocess.Popen(command, cwd=str(frontend_dir))


def start_cookie_watcher() -> Optional[subprocess.Popen]:
    try:
        from backend.app.core.config import get_settings
        eva_dir = get_settings().walle_eva_dir
    except Exception:
        eva_dir = ""

    # Prefer project-internal copy, fall back to eva_dir
    project_watcher = ROOT / "cookie_watcher.py"
    if project_watcher.exists():
        watcher = project_watcher
    elif eva_dir:
        watcher = Path(eva_dir) / "cookie_watcher.py"
    else:
        watcher = Path(r"F:\eva\cookie_watcher.py")

    if not watcher.exists():
        return None

    cmd = [sys.executable, str(watcher)]
    if eva_dir:
        cmd += ["--eva-dir", eva_dir]
    print(f"Starting cookie_watcher.py from {watcher}")
    return subprocess.Popen(cmd)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    # Resolve host/port: CLI args take precedence, then YAML/env config defaults
    host = args.host
    port = args.port
    try:
        from backend.app.core.config import get_settings
        settings = get_settings()
        # Use config values only when CLI args are at their defaults
        if host == "127.0.0.1" and settings.server_host:
            host = settings.server_host
        if port == 8000 and settings.server_port:
            port = settings.server_port
    except Exception:
        pass

    frontend_process = start_frontend(args.frontend_port) if args.with_frontend else None
    watcher_process = start_cookie_watcher()

    print(f"Starting backend at http://{host}:{port}")
    try:
        import uvicorn
        uvicorn.run("backend.app.main:app", host=host, port=port, reload=args.reload)
    finally:
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
        if watcher_process and watcher_process.poll() is None:
            watcher_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
