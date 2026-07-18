"""账号凭据管理服务 - 账号密码存储与心跳续命"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session
from pathlib import Path

from backend.app.models import PlatformAccount
from backend.app.core.security import encrypt_text, decrypt_text
from backend.app.core.database import SessionLocal


class AccountCredentialService:
    """账号凭据管理服务"""

    def __init__(self):
        self.chromium_path = Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1228" / "chrome-win64" / "chrome.exe"

    def save_credentials(
        self,
        db: Session,
        account_id: int,
        username: str,
        password: str,
    ) -> PlatformAccount:
        """保存账号密码到数据库"""
        account = db.get(PlatformAccount, account_id)
        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        # 加密存储账号密码
        credentials = json.dumps({
            "username": username,
            "password": password,
        }, ensure_ascii=False)

        # 存储到 profile 字段
        if not account.profile:
            account.profile = {}
        account.profile["credentials"] = encrypt_text(credentials)
        account.profile["auto_renew"] = True
        account.profile["last_renew_time"] = datetime.now().isoformat()

        db.commit()
        db.refresh(account)
        logger.info(f"账号凭据已保存: id={account_id}")
        return account

    def get_credentials(self, account: PlatformAccount) -> dict[str, str] | None:
        """获取解密后的账号密码"""
        if not account.profile or "credentials" not in account.profile:
            return None

        try:
            encrypted = account.profile["credentials"]
            decrypted = decrypt_text(encrypted)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"解密账号凭据失败: {e}")
            return None

    async def renew_cookie(self, account: PlatformAccount) -> dict[str, Any]:
        """使用账号密码自动续命 Cookie"""
        credentials = self.get_credentials(account)
        if not credentials:
            return {"success": False, "message": "未保存账号密码"}

        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return {"success": False, "message": "账号密码不完整"}

        logger.info(f"开始自动续命: account_id={account.id}, username={username}")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"success": False, "message": "playwright 未安装"}

        if not self.chromium_path.exists():
            return {"success": False, "message": "浏览器未安装"}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,  # 无头模式，不显示浏览器
                    executable_path=str(self.chromium_path),
                )

                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                page = await context.new_page()

                # 打开千帆登录页
                await page.goto("https://pgy.xiaohongshu.com")
                await page.wait_for_load_state("networkidle")

                # 点击账号密码登录（如果有）
                try:
                    await page.click("text=账号密码登录", timeout=3000)
                except:
                    pass

                # 检查是否有登录表单
                try:
                    # 尝试填写账号密码
                    await page.fill('input[placeholder*="账号"], input[placeholder*="用户名"], input[name="username"]', username, timeout=5000)
                    await page.fill('input[placeholder*="密码"], input[name="password"]', password, timeout=5000)
                    await page.click('button[type="submit"], button:has-text("登录")')

                    # 等待登录成功
                    await page.wait_for_url("**/pgy.xiaohongshu.com/**", timeout=30000)

                except Exception as e:
                    logger.warning(f"账号密码登录失败，可能需要扫码: {e}")
                    await browser.close()
                    return {"success": False, "message": f"自动登录失败，需要手动扫码: {str(e)}"}

                # 获取 Cookie
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies}

                await browser.close()

                if cookie_dict:
                    return {
                        "success": True,
                        "cookies": cookie_dict,
                        "message": "Cookie 续命成功"
                    }
                else:
                    return {"success": False, "message": "未获取到 Cookie"}

        except Exception as e:
            logger.error(f"Cookie 续命失败: {e}")
            return {"success": False, "message": str(e)}

    async def check_and_renew(self, db: Session):
        """检查所有需要续命的账号"""
        accounts = db.query(PlatformAccount).filter(
            PlatformAccount.profile["auto_renew"].as_boolean() == True,
            PlatformAccount.status == "expired",
        ).all()

        logger.info(f"检查到 {len(accounts)} 个账号需要续命")

        for account in accounts:
            result = await self.renew_cookie(account)
            if result["success"]:
                # 更新 Cookie
                cookies = result["cookies"]
                cookies_text = json.dumps(cookies, ensure_ascii=False, separators=(",", ":"))

                # 更新账号信息
                from backend.app.services.account_service import upsert_platform_account_from_login
                upsert_platform_account_from_login(
                    db=db,
                    user_id=account.user_id,
                    platform=account.platform,
                    sub_type=account.sub_type,
                    user_info={"user_id": account.external_user_id, "nickname": account.nickname},
                    cookies_text=cookies_text,
                )
                logger.info(f"账号续命成功: {account.nickname}")
            else:
                logger.warning(f"账号续命失败: {account.nickname}, 原因: {result['message']}")


# 单例
credential_service = AccountCredentialService()
