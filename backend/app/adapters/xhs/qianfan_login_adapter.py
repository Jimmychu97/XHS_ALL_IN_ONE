"""千帆平台登录适配器（Playwright 自动化）
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger


class QianfanLoginAdapter:
    """千帆平台登录适配器 - 使用 Playwright 自动化"""

    def __init__(self):
        self.cookie_file = Path("data/cookies/qianfan_cookies.json")

    def create_login_session(self) -> dict[str, Any]:
        """创建登录会话，返回会话信息"""
        return {
            "session_id": "qianfan_manual_login",
            "status": "pending",
            "login_url": "https://pgy.xiaohongshu.com",
            "message": "请在浏览器中完成登录",
        }

    def check_login_status(self, session_id: str) -> dict[str, Any]:
        """检查登录状态"""
        if self.cookie_file.exists():
            with open(self.cookie_file, encoding="utf-8") as f:
                data = json.load(f)
                if data.get("cookie_dict"):
                    return {
                        "status": "confirmed",
                        "cookies": data["cookie_dict"],
                    }
        return {"status": "pending", "message": "等待登录"}

    def save_cookies(self, cookie_string: str) -> dict[str, Any]:
        """保存手动导入的 Cookie"""
        cookies = self._parse_cookie_string(cookie_string)
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump({
                "cookie_string": cookie_string,
                "cookie_dict": cookies
            }, f, ensure_ascii=False, indent=2)
        return {
            "status": "confirmed",
            "cookies": cookies,
            "message": "Cookie 保存成功"
        }

    def _parse_cookie_string(self, cookie_str: str) -> dict[str, str]:
        """解析 Cookie 字符串"""
        cookie_str = cookie_str.strip().strip('"').strip("'")
        if cookie_str.startswith("{"):
            return json.loads(cookie_str)

        cookies = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def get_user_info(self, cookies: dict[str, str]) -> dict[str, Any]:
        """获取用户信息"""
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        headers = {
            "authority": "pgy.xiaohongshu.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            resp = requests.get(
                "https://pgy.xiaohongshu.com/api/draco/distributor-square/distributors-tags",
                headers=headers,
                cookies=cookies,
                params={"types": "distribution_category"},
                timeout=10,
                verify=False,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                return {
                    "user_id": cookies.get("webId", "qianfan_user"),
                    "nickname": "千帆商家账号",
                    "avatar": "",
                    "platform": "qianfan",
                }
        except Exception as e:
            logger.error(f"获取千帆用户信息失败: {e}")

        return {
            "user_id": cookies.get("webId", "qianfan_user"),
            "nickname": "千帆商家账号",
            "avatar": "",
            "platform": "qianfan",
        }


def get_qianfan_login_adapter() -> QianfanLoginAdapter:
    """依赖注入：获取千帆登录适配器"""
    return QianfanLoginAdapter()
