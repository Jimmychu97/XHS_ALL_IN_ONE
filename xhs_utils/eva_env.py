"""EVA 安装目录统一解析

所有模块（main.py / backend / apis / cookie_watcher）统一从这里取千帆客服工作台的安装目录，
切换安装目录只需修改一处，程序内所有地址自动跟随。

优先级：EVA_DIR 环境变量 > config/default.yaml(或 CONFIG_FILE) 的 walle.eva_dir > F:\\eva
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_EVA_DIR = Path(r"F:\eva")


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


def get_eva_dir() -> Path:
    """解析 EVA（千帆客服工作台）安装目录"""
    env = os.environ.get("EVA_DIR")
    if env:
        return Path(env)
    cfg = _config_eva_dir()
    if cfg:
        return Path(cfg)
    return DEFAULT_EVA_DIR


def get_eva_path(*parts: str) -> Path:
    """返回 EVA 目录下的子路径，例如 get_eva_path('eva_cookies.json')"""
    return get_eva_dir().joinpath(*parts)


if __name__ == "__main__":
    print(get_eva_dir())