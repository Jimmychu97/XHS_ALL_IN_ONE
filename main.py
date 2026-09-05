from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent

EVA_CDP_PORT = 9222


def resolve_eva_dir() -> str:
    """解析 EVA（千帆客服工作台）安装目录：EVA_DIR > 配置 > 自动探测常见盘符 > F:\\eva"""
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
    try:
        from xhs_utils.eva_env import get_eva_dir as _resolver
        return str(_resolver())
    except Exception:
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
    """检测 127.0.0.1:9222 是否为真正可用的 CDP 调试端点（HTTP /json 有响应，而非仅端口被占用）"""
    import urllib.request as _ur
    try:
        resp = _ur.urlopen(f"http://127.0.0.1:{port}/json", timeout=2)
        resp.read()
        return True
    except Exception:
        return False


def start_eva_app(eva_dir: str) -> Optional[subprocess.Popen]:
    """自动拉起千帆客服工作台（若 CDP 9222 尚不可用且目录下能找到可执行文件）"""
    if cdp_reachable():
        print(f"[eva] 客服工作台 CDP 已就绪（127.0.0.1:{EVA_CDP_PORT}/json），跳过启动")
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
    parser.add_argument("--frontend-host", default="", help="Frontend dev server bind host（云服务器用 0.0.0.0）。")
    parser.add_argument("--serve-static", action="store_true",
                        help="后端直接托管构建好的前端（frontend/dist），单端口 http://<host>:<port> 访问，不启动 Vite。")
    parser.add_argument("--server", action="store_true",
                        help="云服务器模式：host/frontend 绑定 0.0.0.0，跳过 EVA/cookie_watcher，ark 不自动开有头浏览器。")
    parser.add_argument("--skip-eva", action="store_true", help="不自动启动千帆客服工作台(EVA)。")
    parser.add_argument("--skip-watcher", action="store_true", help="不启动 cookie_watcher 凭证保活服务（适合无本地工作台的服务器）。")
    parser.add_argument("--skip-ark", action="store_true", help="不启动 ark_capture 后台保活服务。")
    parser.add_argument("--eva-dir", default="", help="千帆客服工作台(EVA)安装目录，例如 D:/eva；默认读取 EVA_DIR 环境变量或 config/default.yaml 的 walle.eva_dir")
    return parser.parse_args(argv)


def resolve_npm_executable() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise FileNotFoundError("npm was not found on PATH; install Node.js or start the frontend manually.")
    return npm


def build_frontend_command(port: int, host: str = "127.0.0.1", npm_executable: Optional[str] = None) -> list[str]:
    npm = npm_executable or resolve_npm_executable()
    return [npm, "run", "dev", "--", "--host", host, "--port", str(port)]


def start_frontend(port: int, host: str = "127.0.0.1") -> Optional[subprocess.Popen]:
    frontend_dir = ROOT / "frontend"
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        print("frontend/package.json not found; skipping frontend startup.")
        return None

    # 依赖未安装时 vite 会报 "'vite' 不是内部或外部命令"，提前给出提示并跳过
    if not (frontend_dir / "node_modules").exists():
        print("[frontend] frontend/node_modules 不存在，跳过 Vite dev server。")
        print("[frontend] 请先安装依赖：cd frontend && npm install；")
        print("[frontend] 或构建静态前端后用 --serve-static 由后端托管。")
        return None

    command = build_frontend_command(port, host)
    print(f"Starting frontend at http://{host}:{port}")
    return subprocess.Popen(command, cwd=str(frontend_dir), stdout=sys.stdout, stderr=sys.stderr)


def _ensure_npm() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise FileNotFoundError("npm was not found on PATH; cannot build the frontend automatically.")
    return npm


def _build_frontend() -> bool:
    """自动构建前端：npm install（如缺依赖）→ npm run build，返回 dist/index.html 是否生成。"""
    frontend_dir = ROOT / "frontend"
    if not (frontend_dir / "package.json").exists():
        return False
    try:
        npm = _ensure_npm()
        print("[frontend] 正在安装依赖并构建前端（npm install && npm run build），可能需要几分钟...")
        if not (frontend_dir / "node_modules").exists():
            subprocess.run([npm, "install"], cwd=str(frontend_dir), timeout=900)
        else:
            subprocess.run([npm, "install"], cwd=str(frontend_dir), timeout=900)
        subprocess.run([npm, "run", "build"], cwd=str(frontend_dir), timeout=900)
        return (frontend_dir / "dist" / "index.html").exists()
    except Exception as e:
        print(f"[frontend] 自动构建失败: {e}")
        return False


def start_cookie_watcher() -> Optional[subprocess.Popen]:
    eva_dir = resolve_eva_dir()

    # 依赖前置检查：EVA 目录必须存在（cookie_watcher 依赖客服工作台的 CDP 9222）
    if not Path(eva_dir).is_dir():
        print(f"[watcher] EVA 目录不存在（{eva_dir}），跳过 cookie_watcher 凭证保活服务")
        print("[watcher] 若本机安装了千帆客服工作台，请设置 EVA_DIR 环境变量或 --eva-dir 指定实际目录")
        return None

    # Prefer project-internal copy, fall back to eva_dir
    project_watcher = ROOT / "cookie_watcher.py"
    if project_watcher.exists():
        watcher = project_watcher
    else:
        watcher = Path(eva_dir) / "cookie_watcher.py"

    if not watcher.exists():
        print("[watcher] 未找到 cookie_watcher.py，跳过凭证保活服务")
        return None

    # 若 9222 端口被非 CDP 服务占用，cookie_watcher 会无限 404 重连刷屏 → 提前拦截。
    # 给工作台留 15s 启动窗口（start_eva_app 刚拉起 exe 时 CDP 需要几秒就绪）
    import time as _time
    import urllib.request as _ur
    cdp_ok = False
    for _ in range(3):
        try:
            _ur.urlopen("http://127.0.0.1:9222/json", timeout=2).read()
            cdp_ok = True
            break
        except Exception:
            _time.sleep(5)
    if not cdp_ok:
        print("[watcher] 客服工作台调试端口未就绪（127.0.0.1:9222 无有效 CDP 响应），跳过 cookie_watcher 启动")
        print("[watcher] 确认千帆客服工作台已运行且按 README 开启了远程调试端口 9222（或被其他程序占用）后重试")
        return None

    cmd = [sys.executable, str(watcher), "--eva-dir", eva_dir]
    print(f"[watcher] 启动 cookie_watcher.py（EVA 目录: {eva_dir}）")
    return subprocess.Popen(cmd)


def _playwright_available() -> bool:
    """检测 playwright 是否可用（ark_capture / 同步商品依赖它）"""
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def start_ark_capture(no_open_browser: bool = False) -> Optional[subprocess.Popen]:
    ark_capture = ROOT / "ark_capture.py"
    if not ark_capture.exists():
        return None
    if not _playwright_available():
        print("[ark] 未安装 playwright，跳过 ark_capture 后台保活服务")
        print("[ark] 需要时请安装：pip install playwright && playwright install chromium")
        return None
    cmd = [sys.executable, str(ark_capture), "--daemon"]
    if no_open_browser:
        cmd.append("--no-open-browser")
    print("Starting ark_capture.py --daemon" + (" (--no-open-browser)" if no_open_browser else ""))
    return subprocess.Popen(cmd)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    _setup_rotating_log()

    # 云服务器模式：默认绑定 0.0.0.0、跳过 EVA 自动拉起与 cookie_watcher
    if args.server:
        args.host = args.host if args.host != "127.0.0.1" else "0.0.0.0"
        args.skip_eva = True
        args.skip_watcher = True

    # 一键启动：EVA_DIR 环境变量 / --eva-dir 参数 > YAML 配置
    eva_dir = args.eva_dir.strip() or resolve_eva_dir()
    if args.eva_dir.strip():
        os.environ["EVA_DIR"] = args.eva_dir.strip()
    print(f"[eva] EVA 安装目录: {eva_dir}")

    # ── 前端模式决策 ──────────────────────────────────────────────
    # 1) --serve-static / 云服务器模式 → 优先后端托管 frontend/dist（单端口 8000 访问）
    # 2) 缺 dist 时尝试自动构建（npm install && npm run build）
    # 3) 构建不了但有 node_modules → Vite dev（--server 时绑定 0.0.0.0，可远程访问）
    # 4) 都没有 → API-only 模式，并给出指引
    dist_index = ROOT / "frontend" / "dist" / "index.html"
    use_static = args.serve_static or args.server
    if use_static and not dist_index.exists():
        if _build_frontend():
            print("[frontend] 前端构建完成，由后端静态托管")
        elif not (ROOT / "frontend" / "node_modules").exists():
            print("[frontend] 构建失败（npm 不可用或依赖缺失），将以 API-only 模式启动")
            print("[frontend] 之后可手动构建：cd frontend && npm install && npm run build，重启后自动托管")
        use_static = dist_index.exists()
    if use_static:
        os.environ["FRONTEND_SERVE_STATIC"] = "true"
        os.environ["FRONTEND_BUILD_DIR"] = str(ROOT / "frontend" / "dist")
        args.with_frontend = False
        print(f"[frontend] 静态前端由后端托管 http://{args.host}:{args.port}")

    # Resolve host/port: CLI args take precedence, then YAML/env config defaults
    host = args.host
    port = args.port
    frontend_host = args.frontend_host
    try:
        from backend.app.core.config import get_settings
        settings = get_settings()
        # Use config values only when CLI args are at their defaults
        if host == "127.0.0.1" and settings.server_host:
            host = settings.server_host
        if port == 8000 and settings.server_port:
            port = settings.server_port
        if not frontend_host:
            frontend_host = "0.0.0.0" if host == "0.0.0.0" else "127.0.0.1"
    except Exception:
        if not frontend_host:
            frontend_host = "127.0.0.1"

    stop_event = threading.Event()
    # 1) 客服工作台（EVA）若未运行则自动拉起（--skip-eva 可关闭 / 缺目录自动跳过）
    if args.skip_eva:
        print("[eva] 已跳过自动启动客服工作台（--skip-eva / --server）")
    else:
        start_eva_app(eva_dir)
    # 2) 前端（--serve-static 时后端托管，不启 Vite）
    frontend_process = start_frontend(args.frontend_port, frontend_host) if args.with_frontend else None
    # 3) cookie_watcher / ark_capture 由守护线程监控，异常退出自动重启
    watcher_sup = None
    ark_sup = None
    if not args.skip_watcher:
        watcher_sup = _Supervisor("cookie_watcher", start_cookie_watcher, stop_event)
        watcher_sup.start()
    if not args.skip_ark:
        ark_sup = _Supervisor("ark_capture", lambda: start_ark_capture(no_open_browser=args.server), stop_event)
        ark_sup.start()
    if args.server and (args.skip_watcher or args.skip_ark):
        print(f"[server] 云服务器模式：{('跳过 cookie_watcher ' if args.skip_watcher else '')}{('跳过 ark_capture ' if args.skip_ark else '')}")

    print(f"Starting backend at http://{host}:{port}")
    try:
        import uvicorn
        uvicorn.run("backend.app.main:app", host=host, port=port, reload=args.reload)
    finally:
        stop_event.set()
        if watcher_sup:
            watcher_sup.stop()
        if ark_sup:
            ark_sup.stop()
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
