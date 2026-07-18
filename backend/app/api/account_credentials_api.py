"""账号凭据管理 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import PlatformAccount, User
from backend.app.services.credential_service import credential_service

router = APIRouter(prefix="/accounts", tags=["account-credentials"])


class SaveCredentialsRequest(BaseModel):
    username: str
    password: str


class AccountWithCredentials(BaseModel):
    id: int
    nickname: str | None
    sub_type: str
    has_credentials: bool
    auto_renew: bool


@router.post("/{account_id}/credentials")
def save_credentials(
    account_id: int,
    payload: SaveCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存账号密码"""
    account = db.get(PlatformAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="账号不存在")

    updated = credential_service.save_credentials(
        db=db,
        account_id=account_id,
        username=payload.username,
        password=payload.password,
    )

    return {"id": updated.id, "message": "账号密码已保存"}


@router.get("/{account_id}/credentials")
def get_credentials_status(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取账号凭据状态"""
    account = db.get(PlatformAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="账号不存在")

    has_credentials = bool(credential_service.get_credentials(account))
    auto_renew = account.profile.get("auto_renew", False) if account.profile else False

    return {
        "id": account.id,
        "has_credentials": has_credentials,
        "auto_renew": auto_renew,
    }


@router.post("/{account_id}/toggle-auto-renew")
def toggle_auto_renew(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """切换自动续命开关"""
    account = db.get(PlatformAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not account.profile:
        account.profile = {}

    current = account.profile.get("auto_renew", False)
    account.profile["auto_renew"] = not current
    db.commit()

    return {
        "id": account.id,
        "auto_renew": account.profile["auto_renew"],
    }


@router.post("/{account_id}/renew")
def renew_account_cookie(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发 Cookie 续命"""
    account = db.get(PlatformAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not credential_service.get_credentials(account):
        raise HTTPException(status_code=400, detail="未保存账号密码")

    # 异步执行续命
    import asyncio
    result = asyncio.run(credential_service.renew_cookie(account))

    if result["success"]:
        # 更新数据库
        import json
        from backend.app.services.account_service import upsert_platform_account_from_login

        cookies = result["cookies"]
        cookies_text = json.dumps(cookies, ensure_ascii=False, separators=(",", ":"))

        upsert_platform_account_from_login(
            db=db,
            user_id=account.user_id,
            platform=account.platform,
            sub_type=account.sub_type,
            user_info={"user_id": account.external_user_id, "nickname": account.nickname},
            cookies_text=cookies_text,
        )

        return {"success": True, "message": "Cookie 续命成功"}
    else:
        raise HTTPException(status_code=400, detail=result["message"])
