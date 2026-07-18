from __future__ import annotations

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.xhs.qianfan_adapter import QianFanAdapter
from sqlalchemy import select as sa_select
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import decrypt_text
from backend.app.models import AccountCookieVersion, ModelConfig, PlatformAccount, User
from backend.app.services.ai_service import _load_json_response

router = APIRouter(prefix="/xhs/qianfan", tags=["xhs-qianfan"])


def _get_account_cookies(account_id: int, user: User, db: Session) -> str:
    account = db.get(PlatformAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    cookie_version = db.scalars(
        sa_select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account_id)
        .order_by(AccountCookieVersion.created_at.desc(), AccountCookieVersion.id.desc())
    ).first()
    if not cookie_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account has no cookies")
    return decrypt_text(cookie_version.encrypted_cookies)


def _get_qianfan_cookies(account_id: int, user: User, db: Session) -> str:
    """优先找 qianfan 类型账号，找不到则用传入的 account_id。"""
    qianfan_account = db.scalars(
        sa_select(PlatformAccount)
        .where(
            PlatformAccount.user_id == user.id,
            PlatformAccount.platform == "xhs",
            PlatformAccount.sub_type == "qianfan",
        )
        .order_by(PlatformAccount.created_at.desc())
    ).first()
    target_id = qianfan_account.id if qianfan_account else account_id
    return _get_account_cookies(target_id, user, db)


def _get_default_text_model(db: Session, user: User) -> tuple[ModelConfig, str]:
    config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == user.id,
            ModelConfig.model_type == "text",
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未配置默认文本 AI 模型，请先在「模型配置」页面设置")
    api_key = decrypt_text(config.encrypted_api_key) if config.encrypted_api_key else ""
    return config, api_key


def _llm_chat(model_config: ModelConfig, api_key: str, messages: list[dict]) -> str:
    endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
    response = http_requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model_config.model_name, "messages": messages, "temperature": 0.7},
        timeout=60,
    )
    response.raise_for_status()
    payload = _load_json_response(response)
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("AI response missing content") from exc


# ── 分销商相关 ──────────────────────────────────────────────

@router.get("/categories")
def get_categories(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cookies_str = _get_qianfan_cookies(account_id, current_user, db)
    try:
        return {"items": QianFanAdapter().get_categories(cookies_str)}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/distributors")
def get_distributors(
    account_id: int,
    choice: str = "-1",
    page: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cookies_str = _get_qianfan_cookies(account_id, current_user, db)
    try:
        return QianFanAdapter().get_distributors(cookies_str, choice, page)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/distributors/{user_id}")
def get_distributor_detail(
    user_id: str,
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cookies_str = _get_qianfan_cookies(account_id, current_user, db)
    try:
        return QianFanAdapter().get_distributor_detail(cookies_str, user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


# ── AI 客服对话 ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt: str = (
        "你是一名专业的小红书千帆平台客服助手，负责帮助品牌方与分销商沟通合作事宜。"
        "请用专业、友好的语气回复，重点关注合作品类、佣金、带货能力等话题。"
    )
    distributor_context: dict | None = None


@router.post("/ai-customer-service/chat")
def ai_chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model_config, api_key = _get_default_text_model(db, current_user)

    system = payload.system_prompt
    if payload.distributor_context:
        ctx = payload.distributor_context
        system += (
            f"\n\n当前对话的分销商信息：昵称={ctx.get('nickname', '')}，"
            f"粉丝数={ctx.get('fans', '')}，主营品类={ctx.get('category', '')}。"
        )

    messages = [{"role": "system", "content": system}]
    for msg in payload.messages:
        messages.append({"role": msg.role, "content": msg.content})

    try:
        reply = _llm_chat(model_config, api_key, messages)
        return {"reply": reply}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


class GenerateMessageRequest(BaseModel):
    distributor_info: dict
    intent: str = "合作邀约"


@router.post("/ai-customer-service/generate-message")
def generate_message(
    payload: GenerateMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model_config, api_key = _get_default_text_model(db, current_user)
    info = payload.distributor_info
    prompt = (
        f"请为以下分销商生成一条{payload.intent}消息，语气专业友好，简洁有力，不超过200字。\n"
        f"分销商信息：昵称={info.get('nickname', '')}，粉丝数={info.get('fans', '')}，"
        f"主营品类={info.get('category', '')}，近期带货数据={info.get('sales', '')}。"
    )
    try:
        reply = _llm_chat(model_config, api_key, [
            {"role": "system", "content": "你是专业的小红书千帆平台品牌合作经理。"},
            {"role": "user", "content": prompt},
        ])
        return {"message": reply}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
