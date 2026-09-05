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
        profile = json.loads(account.profile_json or "{}")
        if not profile.get("auto_renew"):
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
            profile = json.loads(account.profile_json or "{}")
            profile["last_renew_time"] = datetime.now().isoformat()
            account.profile_json = json.dumps(profile, ensure_ascii=False)
            db.commit()

            result["action"] = "renewed"
            logger.info(f"账号续命成功: {account.nickname}")
        else:
            # 续命失败，更新状态
            account.status = "expired"
            profile = json.loads(account.profile_json or "{}")
            profile["renew_error"] = renew_result.get("message", "未知错误")
            account.profile_json = json.dumps(profile, ensure_ascii=False)
            db.commit()

            result["action"] = "failed"
            result["error"] = renew_result.get("message")
            logger.warning(f"账号续命失败: {account.nickname}, 原因: {renew_result.get('message')}")

        return result

    def _write_notification(self, db: Session, title: str, body: str, level: str = "warning") -> None:
        """写入站内通知（同一标题 1 小时内已有则跳过，避免刷屏）"""
        from datetime import timedelta
        from backend.app.models.notification import Notification
        from backend.app.core.time import shanghai_now
        dup = db.scalars(
            select(Notification).where(
                Notification.title == title,
                Notification.created_at >= shanghai_now() - timedelta(hours=1),
            ).limit(1)
        ).first()
        if dup:
            return
        db.add(Notification(user_id=1, title=title, body=body, level=level,
                            source_type="system", created_at=shanghai_now()))
        db.commit()

    def check_aux_credentials(self) -> None:
        """检查 walle/ark/backend_token 凭证新鲜度（异常写通知）+ 数据库每日备份"""
        import pathlib
        import time as _time
        import shutil as _shutil
        from backend.app.core.config import get_eva_dir
        issues: list[tuple[str, str]] = []

        eva_dir = get_eva_dir()

        # 1) 平台后端 token（backend_token.txt）
        tf = pathlib.Path(eva_dir) / "backend_token.txt"
        if not tf.exists():
            issues.append(("平台后端 token", f"{eva_dir}/backend_token.txt 不存在"))
        else:
            from backend.app.core.security import decode_token
            try:
                payload = decode_token(tf.read_text("utf-8").strip())
                exp = payload.get("exp", 0)
                if exp - _time.time() < 3 * 86400:
                    issues.append(("平台后端 token", f"剩余有效期 < 3 天（约 {int((exp - _time.time()) / 3600)}h），将自动续期"))
            except Exception:
                issues.append(("平台后端 token", "无效或已过期，将自动续期"))

        # 2) Walle 凭证
        for f, label in (
            (pathlib.Path(eva_dir) / "eva_cookies.json", "Walle 凭证 eva_cookies"),
            (pathlib.Path(eva_dir) / "edith_auth.json", "Walle 凭证 edith_auth"),
        ):
            p = pathlib.Path(f)
            if not p.exists():
                issues.append((label, "文件不存在（请确认客服工作台在运行）"))
            else:
                age = _time.time() - p.stat().st_mtime
                if age > 7200:
                    issues.append((label, f"已 {int(age / 3600)} 小时未更新"))

        # 3) Ark cookies
        ac = pathlib.Path("data/ark_cookies.json")
        if ac.exists():
            age = _time.time() - ac.stat().st_mtime
            if age > 3600:
                issues.append(("Ark cookies", f"已 {int(age / 60)} 分钟未刷新（ark_capture daemon 是否存活？）"))

        with SessionLocal() as db:
            for title, body in issues:
                logger.warning(f"[凭证检查] {title}: {body}")
                self._write_notification(db, f"[凭证检查] {title}", body)

        # 4) 数据库每日备份（保留 7 天）
        try:
            backup_dir = pathlib.Path("data/backup")
            backup_dir.mkdir(parents=True, exist_ok=True)
            db_file = pathlib.Path("data/spider_xhs.db")
            latest = backup_dir / "latest.txt"
            need = True
            if latest.exists():
                try:
                    if _time.time() - float(latest.read_text("utf-8").strip()) < 86400:
                        need = False
                except Exception:
                    pass
            if need and db_file.exists():
                target = backup_dir / f"spider_xhs_{_time.strftime('%Y%m%d_%H%M%S')}.db"
                _shutil.copy2(db_file, target)
                latest.write_text(str(_time.time()))
                cutoff = _time.time() - 7 * 86400
                for old in backup_dir.glob("spider_xhs_*.db"):
                    if old.stat().st_mtime < cutoff:
                        old.unlink(missing_ok=True)
                logger.info(f"数据库已备份: {target.name}")
        except Exception as e:
            logger.warning(f"数据库备份失败: {e}")

    async def run_heartbeat_check(self):
        """执行一次心跳检测"""
        logger.info("开始账号心跳检测...")

        # 凭证新鲜度检查（walle/ark/backend_token）+ 数据库备份
        try:
            self.check_aux_credentials()
        except Exception as e:
            logger.error(f"辅助凭证检查失败: {e}")

        with SessionLocal() as db:
            # 查询所有账号，在 Python 层过滤 auto_renew
            all_accounts = db.scalars(select(PlatformAccount)).all()
            accounts = [
                a for a in all_accounts
                if json.loads(a.profile_json or "{}").get("auto_renew")
            ]

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
