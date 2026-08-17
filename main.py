from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent


class _Supervisor:
    """子进程守护：异常退出自动重启（指数退避，上限 60s）；stop_event 触发后停止不再拉起"""

    def __init__(self, name: str, starter, stop_event: threading.Event, max_delay: int = 60):
        self.name = name
        self.starter = starter
        self.stop_event = stop_event
        self.max_delay = max_delay
        self.proc: Optional[subprocess.Popen] = None

    def _run(self) -> None:
        failures = 0
        while not self.stop_event.is_set():
            try:
                self.proc = self.starter()
            except Exception as e:
                print(f"[supervisor] {self.name} 启动失败: {e}")
                failures += 1
                if self.stop_event.wait(min(5 * failures, self.max_delay)):
                    return
                continue
            if self.proc is None:
                print(f"[supervisor] {self.name} 无可启动脚本，退出守护")
                return
            print(f"[supervisor] {self.name} 已启动 pid={self.proc.pid}")
            self.proc.wait()
            if self.stop_event.is_set():
                return
            failures += 1
            delay = min(5 * failures, self.max_delay)
            print(f"[supervisor] {self.name} 异常退出(code={self.proc.returncode})，{delay}s 后重启(第{failures}次)")
            if self.stop_event.wait(delay):
                return

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, name=f"sup-{self.name}", daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass


def _setup_rotating_log() -> None:
    """uvicorn/后端 logging 输出镜像到 data/logs/backend.log（按天轮转，保留 14 天）"""
    import logging
    from logging.handlers import TimedRotatingFileHandler
    try:
        log_dir = ROOT / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(
            log_dir / "backend.log", when="midnight", backupCount=14, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
    except Exception as e:
        print(f"[log] 日志轮转初始化失败: {e}")


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
    return subprocess.Popen(command, cwd=str(frontend_dir), stdout=sys.stdout, stderr=sys.stderr)


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


def start_ark_capture() -> Optional[subprocess.Popen]:
    ark_capture = ROOT / "ark_capture.py"
    if not ark_capture.exists():
        return None
    print("Starting ark_capture.py --daemon")
    return subprocess.Popen([sys.executable, str(ark_capture), "--daemon"])


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    _setup_rotating_log()

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

    stop_event = threading.Event()
    frontend_process = start_frontend(args.frontend_port) if args.with_frontend else None
    # cookie_watcher / ark_capture 由守护线程监控，异常退出自动重启
    watcher_sup = _Supervisor("cookie_watcher", start_cookie_watcher, stop_event)
    ark_sup = _Supervisor("ark_capture", start_ark_capture, stop_event)
    watcher_sup.start()
    ark_sup.start()

    print(f"Starting backend at http://{host}:{port}")
    try:
        import uvicorn
        uvicorn.run("backend.app.main:app", host=host, port=port, reload=args.reload)
    finally:
        stop_event.set()
        watcher_sup.stop()
        ark_sup.stop()
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
