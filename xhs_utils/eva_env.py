"""EVA 安装目录统一解析

所有模块（main.py / backend / apis / cookie_watcher）统一从这里取千帆客服工作台的安装目录，
切换安装目录只需修改一处，程序内所有地址自动跟随。

优先级：EVA_DIR 环境变量 > config/default.yaml(或 CONFIG_FILE) 的 walle.eva_dir
        > 自动探测常见盘符（C:/D:/E:... 下的 eva 目录，谁装了用谁） > 兜底 F:\\eva
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_EVA_DIR = Path(r"F:\eva")

# 常见的 EVA 安装目录形态（目录名/可执行文件），用于自动探测
_EVA_DIR_NAMES = ("千帆客服工作台", "eva", "Eva", "EVA", "qianfan")
_EVA_EXE_NAMES = ("千帆客服工作台.exe", "eva.exe", "Eva.exe")


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


def _looks_like_eva_dir(d: Path) -> bool:
    """目录里含有 千帆客服工作台.exe / eva.exe 或名为 eva/qianfan 的目录视为 EVA 安装目录"""
    try:
        if not d.is_dir():
            return False
        for exe in _EVA_EXE_NAMES:
            if (d / exe).exists():
                return True
        for name in _EVA_DIR_NAMES:
            sub = d / name
            if sub.is_dir() and (
                any((sub / e).exists() for e in _EVA_EXE_NAMES)
                or (sub / "resources" / "app.asar").exists()
            ):
                return True
    except Exception:
        pass
    return False


def _discover_eva_dir() -> str:
    """自动探测常见盘符下已安装的千帆客服工作台目录（未配置时的兜底）"""
    for root in _candidate_roots():
        # 直接是根目录形态：C:\eva、C:\千帆客服工作台
        for name in _EVA_DIR_NAMES:
            d = root / name
            if _looks_like_eva_dir(d):
                return str(d)
        # 根目录本身（如装在 C:\ 下的裸目录）
        if _looks_like_eva_dir(root):
            return str(root)
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