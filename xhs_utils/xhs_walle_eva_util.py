from __future__ import annotations

import json
import pathlib
import time

# cookie_watcher.py 实时保存的文件（优先读）
_WATCHER_COOKIE_PATH = pathlib.Path("F:/eva/eva_cookies.json")
# nedb 兜底（仅本地环境）
_DB_PATH = pathlib.Path.home() / "AppData" / "Roaming" / "eva" / "db" / "autoLogin.db"
# cookie 有效期阈值（秒），超过此时间认为可能过期
_COOKIE_MAX_AGE = 3600 * 6


def get_eva_cookie_string() -> str:
    """
    获取客服工作台 cookie 字符串，优先级：
    1. cookie_watcher.py 实时维护的 eva_cookies.json（本地/云端均可用）
    2. autoLogin.db 兜底（仅本地 Windows 环境）
    """
    # 优先读 watcher 文件
    if _WATCHER_COOKIE_PATH.exists():
        data = json.loads(_WATCHER_COOKIE_PATH.read_text("utf-8"))
        updated_at = data.get("updated_at", 0)
        cookie_string = data.get("cookie_string", "")
        age = time.time() - updated_at
        if cookie_string and age < _COOKIE_MAX_AGE:
            return cookie_string

    # 兜底：从 nedb 读取（本地环境）
    if not _DB_PATH.exists():
        raise FileNotFoundError(
            "未找到有效 cookie。请确认:\n"
            "1. 客服工作台已启动并登录\n"
            "2. cookie_watcher.py 正在运行"
        )

    record = None
    for line in reversed(_DB_PATH.read_text("utf-8").splitlines()):
        line = line.strip()
        if line:
            try:
                r = json.loads(line)
                if r.get("accessToken"):
                    record = r
                    break
            except json.JSONDecodeError:
                continue

    if not record:
        raise ValueError("autoLogin.db 中没有有效 accessToken，请重新登录客服工作台")

    token = record["accessToken"]
    b_user_id = record.get("bUserId", "")
    return (
        f"walle-eva-bUserId={b_user_id}; "
        f"walle-eva-auth=undefined!!{token}; "
        f"access-token-walle.xiaohongshu.com=customer.eva.{token}"
    )


if __name__ == "__main__":
    print(get_eva_cookie_string())
