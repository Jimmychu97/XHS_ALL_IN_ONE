"""账号心跳监测与自动续命调度器"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.models import PlatformAccount
from backend.app.services.credential_service import credential_service


class AccountHeartbeatScheduler:
    """账号心跳监测调度器"""

    def __init__(self, interval_seconds: int = 3600):
        """
        Args:
            interval_seconds: 检测间隔，默认 1 小时
        """
        self.interval_seconds = interval_seconds
        self._running = False

    async def check_single_account(self, account: PlatformAccount, db: Session) -> dict:
        """检查单个账号并续命"""
        result = {
            "account_id": account.id,
            "nickname": account.nickname,
            "status": account.status,
            "action": "none",
        }

        # 检查是否开启自动续命
        if not account.profile or not account.profile.get("auto_renew"):
            result["action"] = "skipped"
            return result

        # 检查是否保存了凭据
        if not credential_service.get_credentials(account):
            result["action"] = "no_credentials"
            return result

        # 检查 Cookie 健康状态
        from backend.app.services.account_service import check_account_health
        
        try:
            is_healthy = await check_account_health(account)
        except Exception as e:
            logger.warning(f"检查账号健康状态失败: {account.nickname}, {e}")
            is_healthy = False

        if is_healthy:
            result["action"] = "healthy"
            logger.info(f"账号心跳正常: {account.nickname}")
            return result

        # Cookie 过期，尝试续命
        logger.info(f"账号 Cookie 已过期，尝试续命: {account.nickname}")
        
        renew_result = await credential_service.renew_cookie(account)
        
        if renew_result["success"]:
            # 更新 Cookie 到数据库
            cookies = renew_result["cookies"]
            cookies_text = json.dumps(cookies, ensure_ascii=False, separators=(",", ":"))

            from backend.app.services.account_service import upsert_platform_account_from_login
            upsert_platform_account_from_login(
                db=db,
                user_id=account.user_id,
                platform=account.platform,
                sub_type=account.sub_type,
                user_info={"user_id": account.external_user_id, "nickname": account.nickname},
                cookies_text=cookies_text,
            )

            # 更新状态为 active
            account.status = "active"
            if not account.profile:
                account.profile = {}
            account.profile["last_renew_time"] = datetime.now().isoformat()
            db.commit()

            result["action"] = "renewed"
            logger.info(f"账号续命成功: {account.nickname}")
        else:
            # 续命失败，更新状态
            account.status = "expired"
            if not account.profile:
                account.profile = {}
            account.profile["renew_error"] = renew_result.get("message", "未知错误")
            db.commit()

            result["action"] = "failed"
            result["error"] = renew_result.get("message")
            logger.warning(f"账号续命失败: {account.nickname}, 原因: {renew_result.get('message')}")

        return result

    async def run_heartbeat_check(self):
        """执行一次心跳检测"""
        logger.info("开始账号心跳检测...")

        with SessionLocal() as db:
            # 查询所有开启自动续命的账号
            accounts = db.scalars(
                select(PlatformAccount).where(
                    PlatformAccount.profile["auto_renew"].as_boolean() == True
                )
            ).all()

            logger.info(f"检测到 {len(accounts)} 个账号开启自动续命")

            results = []
            for account in accounts:
                try:
                    result = await self.check_single_account(account, db)
                    results.append(result)
                except Exception as e:
                    logger.error(f"检测账号失败: {account.nickname}, {e}")
                    results.append({
                        "account_id": account.id,
                        "nickname": account.nickname,
                        "action": "error",
                        "error": str(e),
                    })

            # 统计结果
            renewed = sum(1 for r in results if r["action"] == "renewed")
            failed = sum(1 for r in results if r["action"] == "failed")
            healthy = sum(1 for r in results if r["action"] == "healthy")

            logger.info(f"心跳检测完成: 正常={healthy}, 续命成功={renewed}, 续命失败={failed}")

        return results

    async def start(self):
        """启动心跳监测循环"""
        self._running = True
        logger.info(f"账号心跳监测已启动，间隔: {self.interval_seconds}秒")

        while self._running:
            try:
                await self.run_heartbeat_check()
            except Exception as e:
                logger.error(f"心跳检测异常: {e}")

            # 等待下一次检测
            await asyncio.sleep(self.interval_seconds)

    def stop(self):
        """停止心跳监测"""
        self._running = False
        logger.info("账号心跳监测已停止")


# 全局调度器实例
_heartbeat_scheduler: AccountHeartbeatScheduler | None = None


def start_heartbeat_scheduler(interval_seconds: int = 3600) -> AccountHeartbeatScheduler:
    """启动心跳监测调度器"""
    global _heartbeat_scheduler

    if _heartbeat_scheduler is None:
        _heartbeat_scheduler = AccountHeartbeatScheduler(interval_seconds)

    # 在后台线程运行
    import threading
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=lambda: loop.run_until_complete(_heartbeat_scheduler.start()))
    thread.daemon = True
    thread.start()

    return _heartbeat_scheduler


def stop_heartbeat_scheduler():
    """停止心跳监测调度器"""
    global _heartbeat_scheduler

    if _heartbeat_scheduler:
        _heartbeat_scheduler.stop()
        _heartbeat_scheduler = None
