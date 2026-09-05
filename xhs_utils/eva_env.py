"""EVA 安装目录统一解析

所有模块（main.py / backend / apis / cookie_watcher）统一从这里取千帆客服工作台的安装目录，
切换安装目录只需修改一处，程序内所有地址自动跟随。

优先级：
    1. EVA_DIR 环境变量
    2. config/default.yaml(或 CONFIG_FILE) 的 walle.eva_dir（Web 界面『设置』也会写到这里）
    3. 自动探测：常见盘符 C:/D:/E:... 下的 eva / 千帆客服工作台 等目录、
       各盘 Program Files、名字含关键字的目录（含标记文件才算）
    4. 兜底：<项目所在盘>:\\eva（服务器装在 C 盘 → C:\\eva，本机在 F 盘 → F:\\eva）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 兜底目录：跟随项目所在盘。项目在 C 盘（云服务器）→ C:\eva；在 F 盘（本机）→ F:\eva
try:
    _PROJECT_DRIVE = os.path.splitdrive(str(Path(__file__).resolve()))[0]
except Exception:
    _PROJECT_DRIVE = ""
PROJECT_DRIVE = _PROJECT_DRIVE or ("C:" if sys.platform.startswith("win") else "")
DEFAULT_EVA_DIR = Path(f"{PROJECT_DRIVE}\\eva") if PROJECT_DRIVE else Path(r"F:\eva")

# 常见的 EVA 安装目录形态（目录名/可执行文件），用于自动探测
_EVA_DIR_NAMES = ("千帆客服工作台", "千帆客服", "千帆", "eva", "Eva", "EVA", "qianfan")
_EVA_EXE_NAMES = ("千帆客服工作台.exe", "eva.exe", "Eva.exe")
# 目录名字含以下关键字也视为候选（配合标记文件双重确认，避免误判其它 Electron 应用）
_NAME_KEYWORDS = ("千帆", "客服", "工作台", "eva", "Eva", "EVA", "qianfan")


def _config_eva_dir() -> str:
    """从 config/default.yaml（或 CONFIG_FILE 指定的文件）读取 walle.eva_dir"""
    try:
        import yaml
        project_root = Path(__file__).resolve().parent.parent
        candidates = [project_root / "config" / "default.yaml"]
        config_file = os.environ.get("CONFIG_FILE")
        if config_file:
            p = Path(config_file)
            if not p.is_absolute():
                p = project_root / p
            candidates.insert(0, p)
        for cfg in candidates:
            if not cfg.exists():
                continue
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            val = (data.get("walle") or {}).get("eva_dir")
            if val:
                return str(val)
    except Exception:
        pass
    return ""


def _candidate_roots() -> list[Path]:
    """生成候选盘符/目录根：Windows 上枚举 C:~Z:，Linux 上常用目录"""
    if sys.platform.startswith("win"):
        from string import ascii_uppercase
        return [Path(f"{letter}:\\") for letter in ascii_uppercase]
    return [Path("/"), Path("/opt"), Path("/usr/local"), Path.home(), Path("/home")]


def _has_marker(d: Path) -> bool:
    """目录内出现 千帆客服工作台.exe / eva.exe 或 resources/app.asar（标准 Electron 布局）即含标记"""
    try:
        if not d.is_dir():
            return False
        for exe in _EVA_EXE_NAMES:
            if (d / exe).exists():
                return True
        if (d / "resources" / "app.asar").exists():
            return True
    except Exception:
        pass
    return False


def _looks_like_eva_dir(d: Path) -> bool:
    """d 本身含标记，或其一层的固定名子目录（d/千帆客服工作台 这种嵌套）含标记，即视为 EVA。
    只向下看一层，避免把包含 eva 目录的盘根误判为 EVA 安装目录本身。"""
    if _has_marker(d):
        return True
    try:
        for name in _EVA_DIR_NAMES:
            sub = d / name
            if _has_marker(sub):
                return True
    except Exception:
        pass
    return False


def _discover_eva_dir() -> str:
    """自动探测各盘符下已安装的千帆客服工作台目录（未配置时的兜底）"""
    for root in _candidate_roots():
        # 盘根目录本身就是 EVA（裸安装，如 C:\ 根目录直接放 exe）
        try:
            if _has_marker(root):
                return str(root)
        except Exception:
            pass
        # 常见位置：盘根 + Program Files + Program Files (x86)
        bases = [root]
        if sys.platform.startswith("win"):
            bases += [root / "Program Files", root / "Program Files (x86)"]
        for base in bases:
            if not base.is_dir():
                continue
            try:
                # 1) 固定目录名：C:\eva、C:\千帆客服工作台、Program Files\千帆客服工作台
                for name in _EVA_DIR_NAMES:
                    d = base / name
                    if _looks_like_eva_dir(d):
                        return str(d)
                # 2) 名字含关键字的目录（×××千帆×××、eva-xxx 等），含标记文件才命中
                for p in base.iterdir():
                    if not p.is_dir() or p.name.startswith("$"):
                        continue
                    if any(k in p.name for k in _NAME_KEYWORDS) and _looks_like_eva_dir(p):
                        return str(p)
            except Exception:
                pass
    return ""


def get_eva_dir() -> Path:
    """解析 EVA（千帆客服工作台）安装目录"""
    env = os.environ.get("EVA_DIR")
    if env:
        return Path(env)
    cfg = _config_eva_dir()
    if cfg:
        return Path(cfg)
    discovered = _discover_eva_dir()
    if discovered:
        return Path(discovered)
    return DEFAULT_EVA_DIR


def get_eva_path(*parts: str) -> Path:
    """返回 EVA 目录下的子路径，例如 get_eva_path('eva_cookies.json')"""
    return get_eva_dir().joinpath(*parts)


if __name__ == "__main__":
    print(get_eva_dir())