"""千帆平台浏览器自动登录 API"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import encrypt_text
from backend.app.models import PlatformAccount, User
from backend.app.services.account_service import upsert_platform_account_from_login
from backend.app.services.credential_service import credential_service

router = APIRouter(prefix="/xhs/qianfan", tags=["xhs-qianfan-login"])


class QianfanLoginSession(BaseModel):
    status: str
    message: str
    cookies: dict[str, str] | None = None


class BrowserLoginRequest(BaseModel):
    username: str
    password: str


# 全局变量存储登录结果
_login_result: dict[str, Any] = {}


async def _run_browser_login(user_id: int, username: str = None, password: str = None):
    """后台任务：打开浏览器等待登录"""
    global _login_result
    
    chromium_path = Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1228" / "chrome-win64" / "chrome.exe"
    
    if not chromium_path.exists():
        _login_result[user_id] = {"status": "error", "message": "浏览器未安装，请先运行: python qianfan_login.py download"}
        return
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        _login_result[user_id] = {"status": "error", "message": "playwright 未安装"}
        return
    
    try:
        _login_result[user_id] = {"status": "pending", "message": "浏览器已打开，等待登录..."}
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                executable_path=str(chromium_path),
                args=["--start-maximized"]
            )
            
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            page = await context.new_page()
            await page.goto("https://pgy.xiaohongshu.com")
            
            # 如果提供了账号密码，尝试自动填写
            if username and password:
                _login_result[user_id] = {"status": "filling", "message": "正在自动填写账号密码..."}
                
                # 等待登录页面加载
                try:
                    await page.wait_for_selector("input[placeholder*='手机']", timeout=5000)
                    
                    # 填写账号密码
                    await page.fill("input[placeholder*='手机']", username)
                    await page.fill("input[type='password']", password)
                    
                    # 点击登录按钮
                    await page.click("button[type='submit']")
                    
                    _login_result[user_id] = {"status": "waiting", "message": "请在浏览器中完成验证码/扫码..."}
                except Exception as e:
                    logger.warning(f"自动填写失败，请手动登录: {e}")
                    _login_result[user_id] = {"status": "waiting", "message": "请手动登录..."}
            else:
                _login_result[user_id] = {"status": "waiting", "message": "请在浏览器中扫码登录..."}
            
            # 等待登录成功（最长 5 分钟）
            for _ in range(300):
                await asyncio.sleep(1)
                cookies = await context.cookies()
                
                has_access_token = any(c["name"].startswith("access-token") for c in cookies)
                has_session = any(c["name"] == "solar.beaker.session.id" for c in cookies)
                
                if has_access_token or has_session:
                    cookie_dict = {c["name"]: c["value"] for c in cookies}
                    _login_result[user_id] = {
                        "status": "success",
                        "message": "登录成功",
                        "cookies": cookie_dict
                    }
                    await browser.close()
                    return
            
            _login_result[user_id] = {"status": "timeout", "message": "登录超时"}
            await browser.close()
            
    except Exception as e:
        logger.error(f"千帆登录失败: {e}")
        _login_result[user_id] = {"status": "error", "message": str(e)}


@router.post("/browser-login/start")
def start_browser_login(
    payload: BrowserLoginRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """启动浏览器登录"""
    global _login_result
    
    user_id = current_user.id
    _login_result[user_id] = {"status": "starting", "message": "正在启动浏览器..."}
    
    # 保存凭据到数据库（加密）
    try:
        # 先查找是否有千帆账号
        account = db.query(PlatformAccount).filter(
            PlatformAccount.user_id == user_id,
            PlatformAccount.platform == "xhs",
            PlatformAccount.sub_type == "qianfan",
        ).first()
        
        if account:
            credential_service.save_credentials(
                db=db,
                account_id=account.id,
                username=payload.username,
                password=payload.password,
            )
            logger.info(f"千帆账号凭据已保存: account_id={account.id}")
    except Exception as e:
        logger.warning(f"保存凭据失败: {e}")
    
    # 启动后台任务
    import threading
    thread = threading.Thread(
        target=lambda: asyncio.run(_run_browser_login(user_id, payload.username, payload.password))
    )
    thread.daemon = True
    thread.start()
    
    return {"status": "starting", "message": "浏览器正在启动..."}


@router.get("/browser-login/status", response_model=QianfanLoginSession)
def get_login_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取登录状态"""
    global _login_result
    
    user_id = current_user.id
    result = _login_result.get(user_id, {"status": "idle", "message": "未开始"})
    
    if result.get("status") == "success" and result.get("cookies"):
        # 保存到数据库
        cookies = result["cookies"]
        cookies_text = json.dumps(cookies, ensure_ascii=False, separators=(",", ":"))
        
        logger.info(f"千帆登录成功，正在保存 Cookie，键数量: {len(cookies)}")
        
        try:
            account, action = upsert_platform_account_from_login(
                db=db,
                user_id=user_id,
                platform="xhs",
                sub_type="qianfan",
                user_info={
                    "user_id": cookies.get("webId", "qianfan_user"),
                    "nickname": "千帆商家账号",
                },
                cookies_text=cookies_text,
            )
            logger.info(f"千帆账号保存成功: id={account.id}, nickname={account.nickname}")
        except Exception as e:
            logger.error(f"千帆账号保存失败: {e}")
            result = {"status": "error", "message": f"保存失败: {e}"}
            return result
        
        # 清理结果
        _login_result[user_id] = {"status": "saved", "message": f"账号已保存: {account.nickname}"}
        result = _login_result[user_id]
        result["account_id"] = account.id
    
    return result
