from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent

EVA_CDP_PORT = 9222


def resolve_eva_dir() -> str:
    """解析 EVA（千帆客服工作台）安装目录：EVA_DIR 环境变量 > 配置文件 walle.eva_dir > F:\\eva"""
    env = os.environ.get("EVA_DIR", "").strip()
    if env:
        return env
    try:
        from backend.app.core.config import get_eva_dir as _cfg_eva
        d = _cfg_eva()
        if d:
            return d
    except Exception:
        pass
    return r"F:\eva"


def find_eva_executable(eva_dir: str) -> Optional[Path]:
    """在 EVA 目录下查找客服工作台可执行文件（优先 千帆客服工作台.exe，回退任意非卸载 exe）"""
    d = Path(eva_dir)
    if not d.is_dir():
        return None
    for name in ("千帆客服工作台.exe", "eva.exe", "Eva.exe"):
        p = d / name
        if p.exists():
            return p
    for p in sorted(d.glob("*.exe")):
        if "uninstall" not in p.name.lower():
            return p
    return None


def cdp_reachable(port: int = EVA_CDP_PORT) -> bool:
    """检测 127.0.0.1:9222 CDP 调试端口是否可达（即客服工作台是否已在运行）"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def start_eva_app(eva_dir: str) -> Optional[subprocess.Popen]:
    """自动拉起千帆客服工作台（若 CDP 9222 尚不可达且目录下能找到可执行文件）"""
    if cdp_reachable():
        print(f"[eva] 客服工作台已在运行（CDP 127.0.0.1:{EVA_CDP_PORT} 可达），跳过启动")
        return None
    exe = find_eva_executable(eva_dir)
    if exe is None:
        print(f"[eva] 未在 {eva_dir} 找到客服工作台可执行文件，跳过自动启动")
        return None
    print(f"[eva] 自动启动客服工作台: {exe}")
    return subprocess.Popen([str(exe)], cwd=eva_dir)


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
    parser.add_argument("--eva-dir", default="", help="千帆客服工作台(EVA)安装目录，例如 D:/eva；默认读取 EVA_DIR 环境变量或 config/default.yaml 的 walle.eva_dir")
    parser.add_argument("--skip-eva", action="store_true", help="不自动启动千帆客服工作台(EVA)。")
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
    eva_dir = resolve_eva_dir()

    # Prefer project-internal copy, fall back to eva_dir
    project_watcher = ROOT / "cookie_watcher.py"
    if project_watcher.exists():
        watcher = project_watcher
    else:
        watcher = Path(eva_dir) / "cookie_watcher.py"

    if not watcher.exists():
        print("[watcher] 未找到 cookie_watcher.py，跳过凭证保活服务")
        return None

    cmd = [sys.executable, str(watcher), "--eva-dir", eva_dir]
    print(f"[watcher] 启动 cookie_watcher.py（EVA 目录: {eva_dir}）")
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

    # 一键启动：EVA_DIR 环境变量 / --eva-dir 参数 > YAML 配置
    eva_dir = args.eva_dir.strip() or resolve_eva_dir()
    if args.eva_dir.strip():
        os.environ["EVA_DIR"] = args.eva_dir.strip()
    print(f"[eva] EVA 安装目录: {eva_dir}")

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
    # 1) 客服工作台（EVA）若未运行则自动拉起（--skip-eva 可关闭）
    if args.skip_eva:
        print("[eva] 已通过 --skip-eva 跳过自动启动客服工作台")
    else:
        start_eva_app(eva_dir)
    # 2) 前端
    frontend_process = start_frontend(args.frontend_port) if args.with_frontend else None
    # 3) cookie_watcher / ark_capture 由守护线程监控，异常退出自动重启
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
