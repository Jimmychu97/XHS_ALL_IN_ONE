from __future__ import annotations

import asyncio
import collections
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.walle import WalleConversation, WalleMessage, WalleShopConfig, WalleKnowledge, WalleKeyword, WalleOrder
from backend.app.models import AccountCookieVersion, PlatformAccount
from backend.app.schemas.common import paginated
from backend.app.services.account_service import serialize_account, upsert_platform_account_from_login

router = APIRouter(prefix="/walle", tags=["walle"])

# ── in-memory log bus ─────────────────────────────────────────────────────────
# user_id -> deque of log dicts (max 200)
_log_store: dict[int, collections.deque] = {}
# user_id -> list of asyncio.Queue (one per SSE subscriber)
_log_subscribers: dict[int, list[asyncio.Queue]] = {}


def _append_log(user_id: int, level: str, text: str, extra: dict | None = None):
    entry = {"ts": datetime.now().strftime("%H:%M:%S"), "level": level, "text": text, **(extra or {})}
    _log_store.setdefault(user_id, collections.deque(maxlen=200)).append(entry)
    for q in _log_subscribers.get(user_id, []):
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            pass


@router.get("/logs/history")
def log_history(current_user: User = Depends(get_current_user)):
    return {"items": list(_log_store.get(current_user.id, []))}


@router.get("/logs/stream")
async def log_stream(
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    from backend.app.core.security import decode_token
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(token)
    user_id: int = payload.get("user_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _log_subscribers.setdefault(user_id, []).append(q)

    async def generate():
        try:
            # 先推历史
            for entry in _log_store.get(user_id, []):
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            while True:
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"ping\": true}\n\n"
        finally:
            subs = _log_subscribers.get(user_id, [])
            if q in subs:
                subs.remove(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_ts(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000)
    except Exception:
        return None


def _extract_text(msg_raw: dict) -> str:
    content = msg_raw.get("content") or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            return content
    if isinstance(content, dict):
        return content.get("text") or content.get("content") or json.dumps(content, ensure_ascii=False)
    return str(content) if content else ""


def _get_shop_config(platform_account_id: int, user_id: int, db: Session) -> Optional[WalleShopConfig]:
    return db.scalars(
        select(WalleShopConfig).where(
            WalleShopConfig.platform_account_id == platform_account_id,
            WalleShopConfig.user_id == user_id,
        )
    ).first()


def _resolve_account(db: Session, user_id: int, b_user_id: str = "") -> Optional[PlatformAccount]:
    """按 bUserId 匹配店铺账号，找不到则取第一个"""
    stmt = select(PlatformAccount).where(
        PlatformAccount.user_id == user_id,
        PlatformAccount.sub_type == "walle",
    )
    if b_user_id:
        account = db.scalars(stmt.where(PlatformAccount.external_user_id == b_user_id)).first()
        if account:
            return account
    return db.scalars(stmt).first()


# ── push from cookie_watcher ───────────────────────────────────────────────────

@router.post("/push-message")
def push_message(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """接收 cookie_watcher.py 实时推送的消息，写入数据库"""
    import traceback
    try:
        print(f"[PUSH-DEBUG] payload={json.dumps(payload, ensure_ascii=False)[:300]}")
        return _push_message_impl(payload, current_user, db)
    except Exception as e:
        traceback.print_exc()
        raise


def _push_message_impl(payload: dict, current_user: User, db: Session):
    data = payload.get("data") or {}
    now = datetime.now()
    b_user_id = data.get("bUserId") or ""
    account = _resolve_account(db, current_user.id, b_user_id)

    if isinstance(data.get("messages"), list):
        messages = data["messages"]
        app_cid = data.get("appCid") or data.get("app_cid") or ""
        # 从消息里提取买家 receiverAppUid（客服发出的消息里有 receiverAppUids，买家发的消息里有 senderAppUid）
        receiver_app_uid = ""
        for m in messages:
            uids = m.get("receiverAppUids") or []
            if uids:
                receiver_app_uid = uids[0]
                break
            uid = m.get("senderAppUid") or m.get("targetAppUid") or ""
            if uid and str(m.get("senderType") or "").lower() in ("customer", "1"):
                receiver_app_uid = uid
                break
        _upsert_conv(db, current_user.id, app_cid, data, account, receiver_app_uid)
        _save_messages(db, current_user.id, app_cid, messages, now, account)
        shop = account.nickname if account else ""
        has_customer_msg = False
        for m in messages:
            sender = str(m.get("senderType") or "").lower()
            content = m.get("content", "")
            label = {"customer": "👤 买家", "csa": "💬 客服", "bot": "🤖 机器人"}.get(sender, f"💬 {sender}")
            level = "info" if sender == "customer" else "success" if sender == "csa" else "warning"
            _append_log(current_user.id, level,
                        f"{label}[{shop}] {content[:80]}",
                        {"app_cid": app_cid, "sender_type": sender})
            if sender == "customer":
                has_customer_msg = True
        if has_customer_msg and account:
            customer_msgs = [m for m in messages if str(m.get("senderType") or "").lower() == "customer"]
            latest_input = "\n".join(m.get("content", "") for m in customer_msgs if m.get("content"))
            import threading
            threading.Thread(
                target=_auto_ai_suggest,
                args=(current_user.id, account.id, app_cid, latest_input),
                daemon=True,
            ).start()

    # impaas batch 格式：{"infos": {"$3$...": {"userMessageInfos": [...]}}}  
    infos = data.get("infos") or {}
    if isinstance(infos, dict):
        for app_cid, info_block in infos.items():
            if not isinstance(info_block, dict):
                continue
            msgs = info_block.get("userMessageInfos") or []
            if msgs:
                _upsert_conv(db, current_user.id, app_cid, {}, account)
                _save_messages(db, current_user.id, app_cid, msgs, now, account)

    msg_map = data.get("messageMap") or {}
    if isinstance(msg_map, dict):
        for app_cid, msgs in msg_map.items():
            if isinstance(msgs, list):
                _upsert_conv(db, current_user.id, app_cid, {}, account)
                _save_messages(db, current_user.id, app_cid, msgs, now, account)

    convs = data.get("userConversationInfos") or []
    for c in convs:
        app_cid = c.get("appCid") or c.get("app_cid") or ""
        if app_cid:
            _upsert_conv(db, current_user.id, app_cid, c, account)
    if convs:
        _append_log(current_user.id, "info", f"🔄 同步会话列表 {len(convs)} 条")

    db.commit()
    return {"ok": True}

def _send_via_cookie_watcher(app_cid: str, text: str, receiver_app_uid: str = "") -> tuple[bool, str]:
    """调 cookie_watcher 9223 端口发消息，返回 (ok, msg)"""
    import urllib.request as _ur
    try:
        body = json.dumps({"app_cid": app_cid, "text": text, "receiver_app_uid": receiver_app_uid},
                          ensure_ascii=False).encode()
        req = _ur.Request("http://127.0.0.1:9223", data=body,
                          headers={"Content-Type": "application/json"}, method="POST")
        resp = json.loads(_ur.urlopen(req, timeout=25).read())
        return resp.get("ok", False), resp.get("result", {}).get("error", "")
    except Exception as e:
        return False, str(e)


def _auto_ai_suggest(user_id: int, platform_account_id: int, app_cid: str, user_message: str):
    """
    后台线程：买家消息到达后启动完整 Agent 循环。
    对应 Customer-Agent 的 CustomerAgent.async_reply 入口。
    """
    from backend.app.core.database import SessionLocal
    from backend.app.models import ModelConfig
    from backend.app.services.credential_service import decrypt_text
    from backend.app.services.walle_agent.agent_loop import run_agent
    print(f"[AI-TRIGGER] user_id={user_id} account_id={platform_account_id} app_cid={app_cid[-20:]} msg={user_message[:30]}")

    db = SessionLocal()
    try:
        shop_cfg = _get_shop_config(platform_account_id, user_id, db)
        mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id, ModelConfig.model_type == "text")).first()
        if not mc:
            mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id)).first()
        if not mc:
            return
        api_key = decrypt_text(mc.encrypted_api_key) if mc.encrypted_api_key else ""
        vision_mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id, ModelConfig.model_type == "vision")).first()
        vision_api_key = decrypt_text(vision_mc.encrypted_api_key) if vision_mc and vision_mc.encrypted_api_key else ""
        # 在 session 关闭前提前加载所有属性，避免 DetachedInstanceError
        from sqlalchemy.orm import make_transient
        if shop_cfg:
            db.expunge(shop_cfg)
            make_transient(shop_cfg)
        db.expunge(mc)
        make_transient(mc)
        if vision_mc:
            db.expunge(vision_mc)
            make_transient(vision_mc)
    finally:
        db.close()

    try:
        suggestion = run_agent(
            platform_account_id=platform_account_id,
            app_cid=app_cid,
            user_message=user_message,
            shop_cfg=shop_cfg,
            mc=mc,
            vision_mc=vision_mc,
            api_key=api_key,
            vision_api_key=vision_api_key,
            user_id=user_id,
        )
        if not suggestion:
            print(f"[AI-DEBUG] suggestion 为空, app_cid={app_cid[-20:]}")
            return

        print(f"[AI-DEBUG] suggestion={suggestion[:80]}")

        # 写入会话 ai_suggestion 字段 + 写入消息记录
        db2 = SessionLocal()
        try:
            conv = db2.scalars(
                select(WalleConversation).where(
                    WalleConversation.app_cid == app_cid,
                    WalleConversation.platform_account_id == platform_account_id,
                )
            ).first()
            if conv:
                conv.ai_suggestion = suggestion
                now = datetime.now()
                # 写入 AI 回复消息，供会话界面展示
                import uuid
                db2.add(WalleMessage(
                    user_id=user_id,
                    platform_account_id=platform_account_id,
                    app_cid=app_cid,
                    msg_id=f"ai_{uuid.uuid4().hex}",
                    sender_type="bot",
                    sender_id="ai_agent",
                    content_type="text",
                    content=suggestion,
                    msg_time=now,
                    raw_json={},
                    created_at=now,
                ))
                conv.last_msg_content = suggestion[:200]
                conv.last_msg_time = now
                conv.updated_at = now
                db2.commit()
            receiver_app_uid = conv.receiver_app_uid or "" if conv else ""
        finally:
            db2.close()

        _append_log(user_id, "success", f"🤖 Agent回复: {suggestion[:80]}", {"app_cid": app_cid})

        ok, send_msg = _send_via_cookie_watcher(app_cid, suggestion, receiver_app_uid)
        level = "success" if ok else "error"
        _append_log(user_id, level,
                    f"📤 自动回复{'OK' if ok else '失败: ' + send_msg}: {suggestion[:60]}",
                    {"app_cid": app_cid})
    except Exception as e:
        import traceback
        traceback.print_exc()
        _append_log(user_id, "error", f"Agent 运行失败: {e}", {"app_cid": app_cid})


def _upsert_conv(db: Session, user_id: int, app_cid: str, raw: dict, account: Optional[PlatformAccount] = None,
                 receiver_app_uid: str = ""):
    if not app_cid or not account:
        return
    existing = db.scalars(
        select(WalleConversation).where(
            WalleConversation.platform_account_id == account.id,
            WalleConversation.app_cid == app_cid,
        )
    ).first()
    customer = raw.get("customerInfo") or {}
    now = datetime.now()
    if existing:
        if customer.get("nickName"):
            existing.customer_name = customer["nickName"]
        if raw.get("imChatId"):
            existing.im_chat_id = raw["imChatId"]
        if receiver_app_uid and not existing.receiver_app_uid:
            existing.receiver_app_uid = receiver_app_uid
        existing.updated_at = now
    else:
        try:
            db.begin_nested()
            db.add(WalleConversation(
                user_id=user_id,
                platform_account_id=account.id,
                app_cid=app_cid,
                im_chat_id=raw.get("imChatId") or raw.get("im_chat_id"),
                customer_name=customer.get("nickName") or "",
                customer_id=customer.get("userId"),
                receiver_app_uid=receiver_app_uid or None,
                raw_json=raw,
                created_at=now,
                updated_at=now,
            ))
            db.flush()
        except Exception:
            db.rollback()


def _save_messages(db: Session, user_id: int, app_cid: str, messages: list, now: datetime, account: Optional[PlatformAccount] = None):
    if not account:
        return
    last_content: Optional[str] = None
    last_msg_time: Optional[datetime] = None
    for m in messages:
        msg_id = str(m.get("imMessageId") or m.get("msgId") or m.get("msg_id") or "")
        if not msg_id:
            continue
        exists = db.scalars(
            select(WalleMessage).where(
                WalleMessage.platform_account_id == account.id,
                WalleMessage.msg_id == msg_id,
            )
        ).first()
        if exists:
            continue
        sender_type = str(m.get("senderType") or m.get("sender_type") or "").lower()
        content = m.get("content") or _extract_text(m)
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        msg_time = _parse_ts(m.get("createAt") or m.get("msgTime") or m.get("msg_time"))
        try:
            db.begin_nested()
            db.add(WalleMessage(
                user_id=user_id,
                platform_account_id=account.id,
                app_cid=app_cid,
                msg_id=msg_id,
                sender_type=sender_type,
                sender_id=str(m.get("senderId") or m.get("sender_id") or m.get("senderName") or ""),
                content_type=str(m.get("contentType") or m.get("content_type") or "text"),
                content=content,
                msg_time=msg_time,
                raw_json=m,
                created_at=now,
            ))
            db.flush()
            if content:
                last_content = content
                last_msg_time = msg_time
        except Exception:
            db.rollback()
            continue
    if last_content:
        conv = db.scalars(
            select(WalleConversation).where(
                WalleConversation.platform_account_id == account.id,
                WalleConversation.app_cid == app_cid,
            )
        ).first()
        if conv:
            conv.last_msg_content = last_content[:200]
            conv.last_msg_time = last_msg_time
            conv.status = "open"
            conv.updated_at = datetime.now()


# ── image proxy ─────────────────────────────────────────────────────────────

@router.get("/img-proxy")
def img_proxy(
    url: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """用 walle cookie 代理加载小红书图片"""
    import requests as _requests
    from fastapi.responses import Response
    try:
        resp = _requests.get(
            url,
            headers={"Referer": "https://walle.xiaohongshu.com/", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── eva config ───────────────────────────────────────────────────────────────

@router.get("/eva-config")
def get_eva_config(current_user: User = Depends(get_current_user)):
    from backend.app.core.config import get_settings
    return {"eva_dir": get_settings().walle_eva_dir}


@router.put("/eva-config")
def save_eva_config(
    eva_dir: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    import yaml
    from pathlib import Path as _Path
    config_path = _Path(__file__).resolve().parent.parent.parent.parent / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("walle", {})["eva_dir"] = eva_dir
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # Invalidate settings cache so next read picks up new value
    from backend.app.core.config import get_settings
    get_settings.cache_clear()
    return {"eva_dir": eva_dir}


# ── walle accounts ───────────────────────────────────────────────────────────

@router.post("/accounts/save-token")
def save_backend_token(
    current_user: User = Depends(get_current_user),
):
    from backend.app.core.security import create_refresh_token
    import pathlib
    token = create_refresh_token(current_user.id)
    pathlib.Path("F:/eva/backend_token.txt").write_text(token, encoding="utf-8")
    return {"ok": True}


@router.post("/accounts/import-eva")
def import_eva_account(
    eva_path: str = Query(default=r"F:\eva\eva_cookies.json", description="eva_cookies.json 路径"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """读取 cookie_watcher.py 写入的 eva_cookies.json，绑定千帆客服工作台账号"""
    import os, json as _json
    if not os.path.exists(eva_path):
        raise HTTPException(status_code=400, detail=f"文件不存在: {eva_path}，请先启动 cookie_watcher.py")
    try:
        with open(eva_path, "r", encoding="utf-8") as f:
            cookies = _json.load(f)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    token = cookies.get("token") or cookies.get("AT") or ""
    inner = cookies.get("cookies") or {}
    nickname = cookies.get("nickname") or cookies.get("csaName") or "千帆客服工作台"
    external_id = (
        cookies.get("csaId")
        or cookies.get("userId")
        or inner.get("walle-eva-bUserId")
        or "walle"
    )
    if not token:
        auth_val = inner.get("walle-eva-auth") or inner.get("access-token-walle.xiaohongshu.com") or ""
        token = auth_val

    account, action = upsert_platform_account_from_login(
        db=db,
        user_id=current_user.id,
        platform="xhs",
        sub_type="walle",
        user_info={"external_user_id": str(external_id), "nickname": nickname, "avatar_url": ""},
        cookies_text=cookies.get("cookie_string") or _json.dumps(inner or cookies, ensure_ascii=False),
    )
    db.commit()
    db.refresh(account)
    return {**serialize_account(account, action), "token_preview": token[:12] + "..." if len(token) > 12 else token}


@router.get("/accounts")
def list_walle_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.scalars(
        select(PlatformAccount).where(
            PlatformAccount.user_id == current_user.id,
            PlatformAccount.platform == "xhs",
            PlatformAccount.sub_type == "walle",
        ).order_by(PlatformAccount.created_at.desc())
    ).all()
    return {"items": [serialize_account(a) for a in accounts]}


# ── shop config ───────────────────────────────────────────────────────────────

class ShopConfigPayload(BaseModel):
    ai_enabled: bool = False
    auto_send: bool = True
    model_config_id: Optional[int] = None
    system_prompt: str = ""
    instructions: Optional[str] = None
    gsx_appid: Optional[str] = None
    gsx_secret: Optional[str] = None
    gsx_key: Optional[str] = None


@router.get("/shop-configs/{platform_account_id}")
def get_shop_config(
    platform_account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_shop_config(platform_account_id, current_user.id, db)
    if not cfg:
        return {"platform_account_id": platform_account_id, "ai_enabled": False, "auto_send": False,
                "model_config_id": None, "system_prompt": "",
                "instructions": None, "gsx_appid": None, "gsx_secret": None, "gsx_key": None}
    return {"id": cfg.id, "platform_account_id": cfg.platform_account_id,
            "ai_enabled": cfg.ai_enabled, "auto_send": cfg.auto_send,
            "model_config_id": cfg.model_config_id,
            "system_prompt": cfg.system_prompt, "instructions": cfg.instructions,
            "gsx_appid": cfg.gsx_appid, "gsx_secret": cfg.gsx_secret, "gsx_key": cfg.gsx_key}


@router.put("/shop-configs/{platform_account_id}")
def upsert_shop_config(
    platform_account_id: int,
    payload: ShopConfigPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_shop_config(platform_account_id, current_user.id, db)
    if cfg:
        cfg.ai_enabled = payload.ai_enabled
        cfg.auto_send = payload.auto_send
        cfg.model_config_id = payload.model_config_id
        cfg.system_prompt = payload.system_prompt
        cfg.instructions = payload.instructions
        cfg.gsx_appid = payload.gsx_appid
        cfg.gsx_secret = payload.gsx_secret
        cfg.gsx_key = payload.gsx_key
    else:
        cfg = WalleShopConfig(
            user_id=current_user.id,
            platform_account_id=platform_account_id,
            ai_enabled=payload.ai_enabled,
            auto_send=payload.auto_send,
            model_config_id=payload.model_config_id,
            system_prompt=payload.system_prompt,
            instructions=payload.instructions,
            gsx_appid=payload.gsx_appid,
            gsx_secret=payload.gsx_secret,
            gsx_key=payload.gsx_key,
        )
        db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {"id": cfg.id, "platform_account_id": cfg.platform_account_id,
            "ai_enabled": cfg.ai_enabled, "auto_send": cfg.auto_send,
            "model_config_id": cfg.model_config_id,
            "system_prompt": cfg.system_prompt, "instructions": cfg.instructions,
            "gsx_appid": cfg.gsx_appid, "gsx_secret": cfg.gsx_secret, "gsx_key": cfg.gsx_key}


# ── sync ──────────────────────────────────────────────────────────────────────

@router.post("/sync")
def sync_messages(
    platform_account_id: int = Query(..., description="千帆账号 ID（platform_accounts.id）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拉取指定千帆账号的会话列表 + 最新消息，upsert 到数据库"""
    from apis.xhs_walle_eva_apis import WalleEvaAPI

    api = WalleEvaAPI()

    success, msg, res = api.get_conv_list()
    if not success:
        return {"success": False, "msg": msg}

    convs = res.get("data", {}).get("userConversationInfos", [])
    app_cids = []

    for c in convs:
        app_cid = c.get("appCid") or c.get("app_cid", "")
        if not app_cid:
            continue
        app_cids.append(app_cid)

        customer = c.get("customerInfo") or {}
        im_chat_id = c.get("imChatId") or c.get("im_chat_id")
        now = datetime.now()

        existing = db.scalars(
            select(WalleConversation).where(
                WalleConversation.platform_account_id == platform_account_id,
                WalleConversation.app_cid == app_cid,
            )
        ).first()

        if existing:
            existing.customer_name = customer.get("nickName") or customer.get("nick_name") or existing.customer_name
            existing.im_chat_id = im_chat_id or existing.im_chat_id
            existing.raw_json = c
            existing.updated_at = now
        else:
            db.add(WalleConversation(
                user_id=current_user.id,
                platform_account_id=platform_account_id,
                app_cid=app_cid,
                im_chat_id=im_chat_id,
                customer_name=customer.get("nickName") or customer.get("nick_name") or "",
                customer_id=customer.get("userId") or customer.get("user_id"),
                raw_json=c,
                created_at=now,
                updated_at=now,
            ))

    db.commit()

    if not app_cids:
        return {"success": True, "conversations": 0, "messages": 0}

    success, msg, res = api.get_message_list_batch(app_cids, count=20)
    if not success:
        return {"success": False, "msg": msg}

    batch_data = res.get("data") or {}
    msg_map: dict = batch_data if isinstance(batch_data, dict) else {}
    if "messageMap" in msg_map:
        msg_map = msg_map["messageMap"]

    saved = 0
    for app_cid, messages in msg_map.items():
        if not isinstance(messages, list):
            continue

        # 更新会话最后一条消息摘要
        last_msg = messages[-1] if messages else None

        for m in messages:
            msg_id = str(m.get("msgId") or m.get("msg_id") or "")
            if not msg_id:
                continue
            exists = db.scalars(
                select(WalleMessage).where(
                    WalleMessage.platform_account_id == platform_account_id,
                    WalleMessage.msg_id == msg_id,
                )
            ).first()
            if exists:
                continue
            db.add(WalleMessage(
                user_id=current_user.id,
                platform_account_id=platform_account_id,
                app_cid=app_cid,
                msg_id=msg_id,
                sender_type=str(m.get("senderType") or m.get("sender_type") or ""),
                sender_id=str(m.get("senderId") or m.get("sender_id") or ""),
                content_type=str(m.get("contentType") or m.get("content_type") or "text"),
                content=_extract_text(m),
                msg_time=_parse_ts(m.get("msgTime") or m.get("msg_time")),
                raw_json=m,
                created_at=datetime.now(),
            ))
            saved += 1

        # 更新会话摘要
        if last_msg:
            conv = db.scalars(
                select(WalleConversation).where(
                    WalleConversation.platform_account_id == platform_account_id,
                    WalleConversation.app_cid == app_cid,
                )
            ).first()
            if conv:
                conv.last_msg_content = _extract_text(last_msg)[:200]
                conv.last_msg_time = _parse_ts(last_msg.get("msgTime") or last_msg.get("msg_time"))
                conv.status = "open"

    db.commit()
    return {"success": True, "conversations": len(app_cids), "messages": saved}


# ── conversations ─────────────────────────────────────────────────────────────

@router.get("/conversations")
def list_conversations(
    platform_account_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(WalleConversation).where(WalleConversation.user_id == current_user.id)
    if platform_account_id is not None:
        stmt = stmt.where(WalleConversation.platform_account_id == platform_account_id)
    if status:
        stmt = stmt.where(WalleConversation.status == status)
    items = db.scalars(stmt.order_by(WalleConversation.updated_at.desc())).all()
    return paginated([{
        "id": c.id,
        "app_cid": c.app_cid,
        "im_chat_id": c.im_chat_id,
        "platform_account_id": c.platform_account_id,
        "customer_name": c.customer_name,
        "customer_id": c.customer_id,
        "status": c.status,
        "unread_count": c.unread_count,
        "last_msg_content": c.last_msg_content,
        "ai_suggestion": c.ai_suggestion,
        "last_msg_time": c.last_msg_time.isoformat() if c.last_msg_time else None,
        "updated_at": c.updated_at.isoformat(),
    } for c in items], page, page_size)


@router.patch("/conversations/{conversation_id}/status")
def update_conversation_status(
    conversation_id: int,
    status: str = Query(..., description="open / replied / closed"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(WalleConversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    conv.status = status
    db.commit()
    return {"id": conv.id, "status": conv.status}


# ── messages ──────────────────────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(WalleConversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    items = db.scalars(
        select(WalleMessage).where(
            WalleMessage.platform_account_id == conv.platform_account_id,
            WalleMessage.app_cid == conv.app_cid,
        ).order_by(WalleMessage.msg_time.asc())
    ).all()
    return paginated([{
        "id": m.id,
        "msg_id": m.msg_id,
        "sender_type": m.sender_type,
        "sender_id": m.sender_id,
        "content_type": m.content_type,
        "content": m.content,
        "msg_time": m.msg_time.isoformat() if m.msg_time else None,
    } for m in items], page, page_size)


# ── AI 建议回复 ────────────────────────────────────────────────────────────────


@router.post("/conversations/{conversation_id}/send")
def send_message(
    conversation_id: int,
    text: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通过 cookie_watcher 向买家发消息"""
    conv = db.get(WalleConversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    ok, msg = _send_via_cookie_watcher(conv.app_cid, text, conv.receiver_app_uid or "")
    if not ok:
        raise HTTPException(status_code=502, detail=f"发送失败: {msg}")
    return {"ok": True}


# ── AI 建议回复 ────────────────────────────────────────────────────────────────

def _img_to_data_uri(url: str) -> Optional[str]:
    import base64, requests as _req
    try:
        resp = _req.get(url, headers={"Referer": "https://walle.xiaohongshu.com/"}, timeout=10)
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        return f"data:{mime};base64,{base64.b64encode(resp.content).decode()}"
    except Exception:
        return None


@router.post("/conversations/{conversation_id}/ai-suggest")
def ai_suggest(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用视觉模型分析最近消息（含图片）生成客服建议回复"""
    from backend.app.models import ModelConfig
    from backend.app.services.credential_service import decrypt_text
    import requests as _req

    conv = db.get(WalleConversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    shop_cfg = _get_shop_config(conv.platform_account_id, current_user.id, db)
    mc_id = (shop_cfg.model_config_id if shop_cfg and shop_cfg.model_config_id
             else (db.scalars(select(ModelConfig).where(ModelConfig.user_id == current_user.id)).first() or None))
    if not mc_id:
        raise HTTPException(status_code=400, detail="请先在店铺配置中设置 AI 模型")
    model_config = db.get(ModelConfig, mc_id if isinstance(mc_id, int) else mc_id.id)
    if not model_config:
        raise HTTPException(status_code=400, detail="模型配置不存在")
    api_key = decrypt_text(model_config.encrypted_api_key) if model_config.encrypted_api_key else ""

    recent = db.scalars(
        select(WalleMessage)
        .where(WalleMessage.app_cid == conv.app_cid,
               WalleMessage.platform_account_id == conv.platform_account_id)
        .order_by(WalleMessage.msg_time.desc())
        .limit(10)
    ).all()[::-1]

    user_parts: list = []
    for m in recent:
        content = m.content or ""
        if content.startswith("[图片] "):
            img_url = content[4:].strip()
            data_uri = _img_to_data_uri(img_url)
            if data_uri:
                user_parts.append({"type": "image_url", "image_url": {"url": data_uri}})
                continue
        label = {"customer": "买家", "csa": "客服", "bot": "机器人"}.get(m.sender_type, m.sender_type)
        user_parts.append({"type": "text", "text": f"{label}: {content}"})
    user_parts.append({"type": "text", "text": "请根据以上对话内容（包括图片），给出一条简洁友好的客服回复建议。"})

    system_prompt = (shop_cfg.system_prompt if shop_cfg and shop_cfg.system_prompt
                     else "你是一个小红书店铺客服，请根据对话内容给出简洁、友好的回复建议。")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_parts},
    ]

    endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
    try:
        resp = _req.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model_config.model_name, "messages": messages},
            timeout=60,
        )
        resp.raise_for_status()
        suggestion = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 调用失败: {e}")

    conv.ai_suggestion = suggestion
    db.commit()
    return {"success": True, "suggestion": suggestion}


# ── knowledge ─────────────────────────────────────────────────────────────────

class KnowledgePayload(BaseModel):
    platform_account_id: int
    title: str
    content: str
    tags: Optional[str] = None
    enabled: bool = True


@router.get("/knowledge")
def list_knowledge(
    platform_account_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(WalleKnowledge)
        .where(WalleKnowledge.user_id == current_user.id,
               WalleKnowledge.platform_account_id == platform_account_id)
        .order_by(WalleKnowledge.created_at.desc())
    ).all()
    return paginated([{
        "id": k.id, "platform_account_id": k.platform_account_id,
        "title": k.title, "content": k.content, "tags": k.tags,
        "enabled": k.enabled,
        "created_at": k.created_at.isoformat(), "updated_at": k.updated_at.isoformat(),
    } for k in items], page, page_size)


@router.post("/knowledge")
def create_knowledge(
    payload: KnowledgePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = WalleKnowledge(
        user_id=current_user.id,
        platform_account_id=payload.platform_account_id,
        title=payload.title, content=payload.content,
        tags=payload.tags, enabled=payload.enabled,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return {"id": k.id, "title": k.title, "enabled": k.enabled}


@router.patch("/knowledge/{knowledge_id}")
def update_knowledge(
    knowledge_id: int,
    payload: KnowledgePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = db.get(WalleKnowledge, knowledge_id)
    if not k or k.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    for field in ("title", "content", "tags", "enabled"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(k, field, val)
    k.updated_at = datetime.now()
    db.commit()
    return {"id": k.id, "title": k.title, "enabled": k.enabled}


@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = db.get(WalleKnowledge, knowledge_id)
    if not k or k.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(k)
    db.commit()
    return {"id": knowledge_id, "status": "deleted"}


# ── keywords ──────────────────────────────────────────────────────────────────

class KeywordPayload(BaseModel):
    platform_account_id: int
    keyword: str


@router.get("/keywords")
def list_keywords(
    platform_account_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(WalleKeyword).where(
            WalleKeyword.user_id == current_user.id,
            WalleKeyword.platform_account_id == platform_account_id,
        )
    ).all()
    return {"items": [{"id": k.id, "platform_account_id": k.platform_account_id, "keyword": k.keyword} for k in items]}


@router.post("/keywords")
def create_keyword(
    payload: KeywordPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = WalleKeyword(user_id=current_user.id,
                     platform_account_id=payload.platform_account_id,
                     keyword=payload.keyword)
    db.add(k)
    db.commit()
    db.refresh(k)
    return {"id": k.id, "platform_account_id": k.platform_account_id, "keyword": k.keyword}


@router.delete("/keywords/{keyword_id}")
def delete_keyword(
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = db.get(WalleKeyword, keyword_id)
    if not k or k.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(k)
    db.commit()
    return {"id": keyword_id, "status": "deleted"}


# ── orders ────────────────────────────────────────────────────────────────────

@router.get("/orders")
def list_orders(
    platform_account_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(WalleOrder)
        .where(WalleOrder.user_id == current_user.id,
               WalleOrder.platform_account_id == platform_account_id)
        .order_by(WalleOrder.created_at.desc())
    ).all()
    return paginated([{
        "id": o.id, "app_cid": o.app_cid,
        "sn_imei": o.sn_imei, "coupon_code": o.coupon_code,
        "goods_name": o.goods_name, "spec": o.spec, "order_sn": o.order_sn,
        "status": o.status,
        "created_at": o.created_at.isoformat(), "updated_at": o.updated_at.isoformat(),
    } for o in items], page, page_size)
