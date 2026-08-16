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
        msgs = (payload.get("data") or {}).get("messages") or []
        for _m in msgs:
            print(f"[MSG-DEBUG] senderType={_m.get('senderType')} content={str(_m.get('content',''))[:80]}")
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
                target=_dispatch_customer_message,
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
                if account:
                    for cm in msgs:
                        ci = cm.get("contentInfo") or {}
                        summary = ci.get("summary") or cm.get("content") or ""
                        if not isinstance(summary, str):
                            summary = json.dumps(summary, ensure_ascii=False)
                        # 订单卡/商品卡只有买家能发，直接触发
                        if summary.strip() in ("[订单]", "[商品信息]", "[商品]"):
                            import threading
                            threading.Thread(
                                target=_dispatch_customer_message,
                                args=(current_user.id, account.id, app_cid, "[订单]"),
                                daemon=True,
                            ).start()
                            break

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


# ── 序列号 / IMEI 检测 ────────────────────────────────────────────────────────

import re as _re

_SN_RE = _re.compile(r'(?<![A-Z0-9])([A-HJ-NP-Z0-9]{10}|[A-HJ-NP-Z0-9]{12})(?![A-Z0-9])')
_IMEI_RE = _re.compile(r'(?:IMEI[:\s]*)?(?<!\d)(\d(?:\s?\d){14})(?!\d)', _re.IGNORECASE)

_ORDER_GUIDE = (
    "您好！感谢您的订单 🎉\n"
    "本店采用无物流发货，请提供您的设备序列号或IMEI以便完成验机。\n\n"
    "📱 iPhone / iPad：设置 → 通用 → 关于本机，或拨打 *#06# 获取IMEI\n"
    "💻 Mac / MacBook：苹果菜单 → 关于本机 → 序列号\n"
    "🎧 AirPods / 耳机：打开充电盒，盒内盖印有序列号；或在已配对iPhone的设置 → 蓝牙 → 设备名称旁边查看\n"
    "⌚ Apple Watch：设置 → 通用 → 关于本机；或表背面印有序列号\n\n"
    "✅ 所有苹果设备序列号均可查询，发送序列号即可完成验机 😊"
)

_SN_FIND_GUIDE = (
    "您好，我是店铺客服～请您先在设备上找到【序列号】或【IMEI】发给我，我马上帮您验机 😊\n\n"
    "📱 iPhone/iPad：设置 → 通用 → 关于本机（或拨号 *#06# 直接显示IMEI）\n"
    "💻 Mac：点左上角苹果  → 关于本机\n"
    "⌚ Apple Watch：设置 → 通用 → 关于本机（或看表背）\n"
    "🎧 AirPods：开盖看充电仓盖内侧，或连iPhone后 设置→蓝牙→设备名称\n\n"
    "找到后直接发给我就可以啦～"
)


def _luhn_check(n: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(n)):
        x = int(d)
        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9
        total += x
    return total % 10 == 0


def _extract_sn_imei(text: str) -> tuple[str, str]:
    """返回 (sn, imei)，未找到则为空字符串"""
    # IMEI 优先：15 位数字，允许中间有空格（如 35 113831 0588051 → 351138310588051）
    for m in _IMEI_RE.finditer(text):
        candidate = m.group(1).replace(" ", "").replace("\u3000", "")
        prefix = m.group(0)
        if 'imei' in prefix.lower() or _luhn_check(candidate):
            return "", candidate
    # SN：必须含至少一个字母（先去空格）
    text_nospace = _re.sub(r"\s+", "", text).upper()
    for m in _SN_RE.finditer(text_nospace):
        candidate = m.group(1).replace('O', '0').replace('I', '1')
        if _re.search(r'[A-HJ-NP-Z]', candidate):
            return candidate, ""
    return "", ""


def _clear_agent_session(platform_account_id: int, app_cid: str):
    """清空该会话的 Agent 历史，避免跨轮次污染"""
    from backend.app.core.database import SessionLocal
    from backend.app.models.walle import WalleAgentSession
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(WalleAgentSession).where(
                WalleAgentSession.platform_account_id == platform_account_id,
                WalleAgentSession.app_cid == app_cid,
            )
        ).all()
        for r in rows:
            db.delete(r)
        db.commit()
    finally:
        db.close()


def _extract_buyer_id_from_app_cid(app_cid: str) -> str:
    """从 appCid 提取买家真实 XHS userId（2026-08-16 修正）。

    appCid 格式：$3$<b64段1>.<b64段2>
    - 段1 base64 解码后为 '1#2#2#' + 买家 userId（24 位十六进制，如 5f40d80e0000000001002f01）
    - 段2 是店铺信息（如 MjZkYTMwMDE1OTdmN2Ey = base64(店铺id尾段)），不是买家 id
    ⚠️ 旧实现直接取 app_cid 尾部 20 字符是错的（那是 base64）。
    """
    import base64
    import re as _re
    if not app_cid:
        return ""
    seg = app_cid.split(".")[0]
    if seg.startswith("$3$"):
        seg = seg[3:]
    if not seg:
        return ""
    try:
        decoded = base64.b64decode(seg + "=" * (-len(seg) % 4)).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    m = _re.search(r"[0-9a-f]{24}", decoded)
    if m:
        return m.group(0)
    # fallback：去掉前导非十六进制字符（'#数字#数字#' 前缀）
    return _re.sub(r"^[^0-9a-f]*", "", decoded)


def _parse_order_list(res: dict) -> list:
    """解析订单列表，兼容多种响应格式"""
    packages = []
    if not res:
        return packages
    data = res.get("data") or {}
    for key in ("orderList", "orders", "resultList", "list"):
        candidate = data.get(key) or res.get(key)
        if isinstance(candidate, list):
            packages = candidate
            break
    if not packages and isinstance(data, list):
        packages = data
    return packages


def _conv_customer_id(platform_account_id: int, app_cid: str) -> str:
    """取买家真实 XHS userId：优先从 appCid base64 解码（可靠）；
    fallback 会话表 customer_id（历史 customer_id 存的是店铺 id 的 base64，不可靠）。"""
    buyer = _extract_buyer_id_from_app_cid(app_cid)
    if buyer:
        return buyer
    from backend.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        conv = db.scalars(
            select(WalleConversation).where(
                WalleConversation.platform_account_id == platform_account_id,
                WalleConversation.app_cid == app_cid,
            )
        ).first()
        return (conv.customer_id or "") if conv else ""
    finally:
        db.close()


def _fetch_buyer_orders(platform_account_id: int, app_cid: str) -> str:
    """拉取该会话买家的订单信息，返回可读文本。
    统一走 ArkAPI.get_orders_by_user（2026-08-16 已验证可用）；
    原 edith get_buyer_packages 接口 404、CDP get_conv_order 不稳定，均已废弃。"""
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        from backend.app.services.walle_agent.tools import _ORDER_STATUS

        buyer_user_id = _conv_customer_id(platform_account_id, app_cid)
        if not buyer_user_id:
            print(f"[ORDER-FETCH] 无 buyer_user_id, app_cid={app_cid[-20:]}")
            return ""

        ok, msg, res = ArkAPI().get_orders_by_user(buyer_user_id)
        if not ok or not res:
            print(f"[ORDER-FETCH] 查询失败: {msg}")
            return ""
        packages = ((res.get("data") or {}).get("packages")) or []
        if not packages:
            print(f"[ORDER-FETCH] 无订单数据, app_cid={app_cid[-20:]}")
            return ""

        lines = []
        for pkg in packages[:3]:
            sku = (pkg.get("skus") or [{}])[0]
            scsku = (sku.get("scskus") or [{}])[0]
            name = scsku.get("skuName") or scsku.get("name") or sku.get("skuName") or sku.get("name") or ""
            spec = scsku.get("specification") or scsku.get("scskuCode") or ""
            order_sn = pkg.get("orderId") or ""
            status = _ORDER_STATUS.get(pkg.get("status", -1), "")
            amount = pkg.get("actualPaid") or ""
            lines.append(f"商品：{name} 规格：{spec} 订单号：{order_sn} 状态：{status} 实付：{amount}元")
        print(f"[ORDER-FETCH] 获取到 {len(lines)} 条订单")
        return "\n".join(lines)
    except Exception as e:
        print(f"[ORDER-FETCH] 失败: {e}")
        import traceback
        traceback.print_exc()
        return ""


def _check_order_status(platform_account_id: int, app_cid: str) -> tuple:
    """检查订单状态，返回 (状态码, 订单详情)。
    统一走 ArkAPI.get_orders_by_user（2026-08-16 已验证可用）；
    原 edith get_buyer_packages 接口 404、CDP get_conv_order 不稳定，均已废弃。"""
    import datetime as _dt
    def _log(msg):
        print(msg)
        try:
            with open(r"F:\XHS_ALL_IN_ONE\data\logs\order_check.log", "a", encoding="utf-8") as lf:
                lf.write(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        except: pass
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        from backend.app.services.walle_agent.tools import _ORDER_STATUS, _PENDING_SHIP

        buyer_user_id = _conv_customer_id(platform_account_id, app_cid)
        if not buyer_user_id:
            _log(f"[ORDER-CHECK] 无 buyer_user_id, app_cid={app_cid[-20:]}")
            return "none", {}

        ok, msg, res = ArkAPI().get_orders_by_user(buyer_user_id)
        _log(f"[ORDER-CHECK] ArkAPI ok={ok} msg={msg}")
        if not ok or not res:
            _log(f"[ORDER-CHECK] 查询失败: {msg}")
            return "error", {}

        packages = ((res.get("data") or {}).get("packages")) or []
        if not packages:
            _log(f"[ORDER-CHECK] 无订单数据, app_cid={app_cid[-20:]}")
            return "none", {}

        latest = packages[0]
        status_code = latest.get("status", -1)
        status_text = _ORDER_STATUS.get(status_code, f"未知状态({status_code})")
        _log(f"[ORDER-CHECK] 订单状态={status_text} (code={status_code})")

        if status_code == 998:
            return "cancelled", latest
        elif status_code in _PENDING_SHIP:
            return "pending_ship", latest
        else:
            return "other", latest
    except Exception as e:
        _log(f"[ORDER-CHECK] 异常: {e}")
        import traceback
        traceback.print_exc()
        return "error", {}


def _save_pending_order(user_id: int, platform_account_id: int, app_cid: str, order_detail: dict):
    """保存待发货订单到 walle_orders 表（order_detail 为 ArkAPI get_orders 返回的 package 结构）"""
    from backend.app.core.database import SessionLocal
    from backend.app.core.time import shanghai_now
    db = SessionLocal()
    try:
        sku = (order_detail.get("skus") or [{}])[0]
        scsku = (sku.get("scskus") or [{}])[0]
        db.add(WalleOrder(
            user_id=user_id, platform_account_id=platform_account_id,
            app_cid=app_cid, sn_imei="", coupon_code="",
            goods_name=scsku.get("skuName") or scsku.get("name") or sku.get("skuName") or sku.get("name") or "",
            spec=scsku.get("specification") or scsku.get("scskuCode") or "",
            order_sn=order_detail.get("orderId") or "",
            status=0, created_at=shanghai_now(), updated_at=shanghai_now(),
        ))
        db.commit()
    finally:
        db.close()


def _extract_sn_imei_from_image(user_id: int, img_url: str) -> str:
    """用视觉模型识别图片中的序列号/IMEI，返回规范化编码（未识别到返回空串）"""
    import base64
    import requests as _req
    from backend.app.core.database import SessionLocal
    from backend.app.models import ModelConfig
    from backend.app.services.credential_service import decrypt_text
    from backend.app.services.walle_agent.tools import normalize_sn_imei

    db = SessionLocal()
    try:
        vision_mc = db.scalars(select(ModelConfig).where(
            ModelConfig.user_id == user_id, ModelConfig.model_type == "image")).first()
        if not vision_mc:
            vision_mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id)).first()
        if not vision_mc:
            print("[IMG-OCR] 未配置视觉模型")
            return ""
        api_key = decrypt_text(vision_mc.encrypted_api_key) if vision_mc.encrypted_api_key else ""
        base_url, model_name = vision_mc.base_url or "", vision_mc.model_name or ""
    finally:
        db.close()

    if not (base_url and model_name and api_key):
        print("[IMG-OCR] 视觉模型配置不完整")
        return ""

    try:
        img_resp = _req.get(img_url, headers={
            "Referer": "https://walle.xiaohongshu.com/", "User-Agent": "Mozilla/5.0"}, timeout=10)
        img_resp.raise_for_status()
        mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
        data_uri = f"data:{mime};base64,{base64.b64encode(img_resp.content).decode()}"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是序列号识别助手。识别图片中的苹果设备序列号（SN，字母数字组合）或 IMEI（15位数字）。只输出识别到的编码本身，不要解释、不要多余内容；没识别到输出 NONE。"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": "请提取图中的序列号或IMEI。"},
                ]},
            ],
            "temperature": 0,
        }
        resp = _req.post(f"{base_url.rstrip('/')}/chat/completions",
                         headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                         json=payload, timeout=30)
        resp.raise_for_status()
        text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        code = normalize_sn_imei(text)
        if code:
            return code
        sn, imei = _extract_sn_imei(text)  # 兜底正则提取
        return sn or imei or ""
    except Exception as e:
        print(f"[IMG-OCR] 识别失败: {e}")
        return ""


def _dispatch_customer_message(user_id: int, platform_account_id: int, app_cid: str, user_message: str):
    """前置拦截：订单卡 -> 检查订单状态；含序列号/IMEI -> 检查订单后验机；其余 -> Agent"""
    stripped = user_message.strip()

    # 0. 图片消息 -> 视觉识别序列号/IMEI，识别到则写入订单并走验机流程
    if stripped.startswith("[图片]"):
        img_url = stripped.replace("[图片]", "", 1).strip()
        code = _extract_sn_imei_from_image(user_id, img_url)
        if code:
            status, _ = _check_order_status(platform_account_id, app_cid)
            if status == "cancelled":
                _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                       "您好，该订单已取消。请先下单才能查询苹果GSX报告 😊")
            elif status == "pending_ship":
                print(f"[IMG-SN] 图片识别到 {code}，进入验机流程")
                _handle_sn_imei(user_id, platform_account_id, app_cid, code)
            elif status == "other":
                # 已发货/已完成等状态：不重复查询，提示已查询过
                _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                       "您好，该订单已经查询过验机了～请问您还有什么问题需要了解吗？我可以帮您解答 😊")
            elif status == "none":
                _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                       "您好，未检测到有效订单。请先下单才能查询苹果GSX报告 😊")
            else:
                print(f"[DISPATCH] 订单查询失败 status={status}，跳过验机")
        else:
            print("[IMG-SN] 图片未识别到序列号/IMEI，转 Agent 处理")
            _auto_ai_suggest(user_id, platform_account_id, app_cid, stripped)
        return

    # 1. 订单卡 -> 检查订单状态
    if stripped in ("[订单]", "[商品信息]", "[商品]"):
        _clear_agent_session(platform_account_id, app_cid)
        status, order_detail = _check_order_status(platform_account_id, app_cid)
        if status == "cancelled":
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，该订单已取消。请先下单才能查询苹果GSX报告 😊")
        elif status == "pending_ship":
            _save_pending_order(user_id, platform_account_id, app_cid, order_detail)
            _fire_and_forget_reply(user_id, platform_account_id, app_cid, _ORDER_GUIDE)
        elif status == "none":
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，请先下单才能查询苹果GSX报告 😊")
        elif status == "other":
            # 已发货/已完成等状态：让买家说明想了解的问题
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，您的订单已发货～请问您想了解什么问题呢？我可以帮您查询验机信息、售后服务等相关问题哦 😊")
        else:
            print(f"[DISPATCH] 订单查询失败 status={status}，跳过自动回复")
        return

    # 2. 含序列号 / IMEI -> 检查订单状态后验机
    sn, imei = _extract_sn_imei(user_message)
    code = sn or imei
    if code:
        status, _ = _check_order_status(platform_account_id, app_cid)
        if status == "cancelled":
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，该订单已取消。请先下单才能查询苹果GSX报告 😊")
            return
        elif status == "pending_ship":
            # 仅待发货才调用查询 API
            _handle_sn_imei(user_id, platform_account_id, app_cid, code)
            return
        elif status == "other":
            # 已发货/已完成等状态：不重复查询，提示已查询过
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，该订单已经查询过验机了～请问您还有什么问题需要了解吗？我可以帮您解答 😊")
            return
        elif status == "none":
            _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                                   "您好，未检测到有效订单。请先下单才能查询苹果GSX报告 😊")
            return
        else:
            print(f"[DISPATCH] 订单查询失败 status={status}，跳过验机")
            return

    # 3. 普通消息 -> Agent
    # 会话首次互动：先立即回复"如何找序列号"，不让客户干等 Agent 处理
    from backend.app.core.database import SessionLocal as _SDL
    from backend.app.models.walle import WalleAgentSession as _WAS
    _db0 = _SDL()
    try:
        _first_touch = _db0.scalars(
            select(_WAS).where(
                _WAS.platform_account_id == platform_account_id,
                _WAS.app_cid == app_cid,
            ).limit(1)
        ).first() is None
    finally:
        _db0.close()
    if _first_touch:
        _fire_and_forget_reply(user_id, platform_account_id, app_cid, _SN_FIND_GUIDE)
    order_info = _fetch_buyer_orders(platform_account_id, app_cid)
    if order_info:
        enriched = f"{user_message}\n\n[当前订单信息]\n{order_info}"
    else:
        enriched = user_message
    _auto_ai_suggest(user_id, platform_account_id, app_cid, enriched)


def _fire_and_forget_reply(user_id: int, platform_account_id: int, app_cid: str, text: str):
    """写库 + 发送固定回复"""
    import uuid
    from backend.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        now = datetime.now()
        conv = db.scalars(
            select(WalleConversation).where(
                WalleConversation.app_cid == app_cid,
                WalleConversation.platform_account_id == platform_account_id,
            )
        ).first()
        receiver_app_uid = conv.receiver_app_uid or "" if conv else ""
        db.add(WalleMessage(
            user_id=user_id,
            platform_account_id=platform_account_id,
            app_cid=app_cid,
            msg_id=f"ai_{uuid.uuid4().hex}",
            sender_type="bot",
            sender_id="ai_agent",
            content_type="text",
            content=text,
            msg_time=now,
            raw_json={},
            created_at=now,
        ))
        if conv:
            conv.ai_suggestion = text
            conv.last_msg_content = text[:200]
            conv.last_msg_time = now
            conv.updated_at = now
        db.commit()
    finally:
        db.close()
    _append_log(user_id, "success", f"🤖 固定回复: {text[:60]}", {"app_cid": app_cid})
    ok, err = _send_via_cookie_watcher(app_cid, text, receiver_app_uid)
    level = "success" if ok else "error"
    _append_log(user_id, level, f"📤 发送{'OK' if ok else '失败: ' + err}: {text[:40]}", {"app_cid": app_cid})


# GSX 报告字段名（用于按字段换行；字段表驱动，避免把值里的冒号/URL 误切）
_GSX_FIELD_NAMES = (
    "型号信息", "型号名称", "IMEI2", "IMEI", "序列号", "设备容量", "设备颜色", "机型", "类型",
    "网络制式", "激活状态", "激活日期", "预计购买时间", "有效购买日期", "保修状态", "电话支持",
    "保修截止日期", "剩余保修天数", "是否预激活", "是否延保", "延保条件", "已注册设备",
    "是否官换机", "是否官翻机", "是否演示机", "是否资源机", "是否权益机", "是否过时产品",
    "已更换产品的序列号", "借出设备", "产品类型", "维修状态", "iCloud激活锁", "iCloud状态",
    "网络锁", "运营商", "下次激活策略ID", "美国运营商状态", "GSMA状态", "型号号码", "销售地区",
    "SIM卡", "主板代号", "芯片名称", "芯片型号", "运行内存", "处理器", "电池信息", "屏幕信息",
    "上市时间", "其他信息", "设备图片", "错误信息",
    # 基础查询短报告字段
    "型号", "IMEI/SN", "激活锁", "ID黑白状态",
    # 常见 GSX 字段（减少中文值场景的歧义）
    "生产日期", "出厂状态", "购买日期", "销售日期", "首次激活日期", "激活策略",
    "维修记录", "换机记录", "翻新状态", "监管状态", "苹果官方记录", "内部代码",
    "备注信息", "特殊状态", "专属标记", "销售记录", "采购记录", "历史记录",
)


def _format_gsx_report(result: str) -> str:
    """把 GSX 报告（一行 字段:值 拼接）按字段换行，提升可读性。

    两遍切分，且保证不丢失任何内容：
    1) 已知字段表精确切分（字段名内部子串如"已更换产品的序列号"不会误切，
       URL / "Processor Speed:" 等值内冒号也不会误切）
    2) 未知字段通用兜底：仅当字段名前是"非中文"字符（数字/ASCII/标点等值边界）才切，
       避免把中文值（如"是"）误并进下一个字段名；中文值粘连时保持原样不切错。

    无论怎么切，输出去掉空白后与原文完全一致（内容零丢失）。
    """
    import re as _re
    text = (result or "").strip()
    if not text:
        return text

    # ── 第一遍：已知字段精确切分 ──
    names = sorted(_GSX_FIELD_NAMES, key=len, reverse=True)
    pat = _re.compile("(?:" + "|".join(_re.escape(n) for n in names) + ")[:：]")
    positions = []
    i = 0
    while i < len(text):
        m = pat.match(text, i)
        if m:
            positions.append(m.start())
            i = m.end()  # 跳过整个字段名+冒号，防止字段名内的子串再次匹配
        else:
            i += 1
    lines = []
    last = 0
    for pos in positions:
        if pos > last:
            lines.append(text[last:pos].strip())
            last = pos
    lines.append(text[last:].strip())

    # ── 第二遍：未知字段通用兜底（安全规则：字段名前必须是非中文边界）──
    # 已知字段开头的行已被第一遍精确切分，值保持完整，不再二次切分
    known_prefix = _re.compile("^(?:" + "|".join(_re.escape(n) for n in names) + ")[:：]")
    url_holder: dict[str, str] = {}

    def _keep_url(m: "re.Match") -> str:
        k = f"__U{len(url_holder)}__"
        url_holder[k] = m.group(0)
        return k

    generic = _re.compile(r"(?<=[^一-鿿])([\u4e00-\u9fa5]{2,10}[:：])")
    out: list[str] = []
    for line in lines:
        if ":" not in line:
            out.append(line)
            continue
        protected = _re.sub(r"https?://\S+", _keep_url, line)
        # 行首已知字段已精确切分：从它的值部分开始通用切分，避免对已知字段名二次切分
        skip = 0
        m = known_prefix.match(protected)
        if m:
            skip = m.end()
        positions = []
        i = skip
        while i < len(protected):
            m = generic.match(protected, i)
            if m:
                positions.append(m.start())
                i = m.end()
            else:
                i += 1
        segs = []
        last = 0
        for pos in positions:
            if pos > last:
                segs.append(protected[last:pos].strip())
                last = pos
        segs.append(protected[last:].strip())
        for k, v in url_holder.items():
            segs = [s.replace(k, v) for s in segs]
        out.extend(s for s in segs if s)
    return "\n".join(out)


def _load_text_model_config(user_id: int) -> tuple:
    """加载用户文本模型配置，返回 (base_url, model_name, api_key)；未配置返回三个空串"""
    from backend.app.core.database import SessionLocal
    from backend.app.models import ModelConfig
    from backend.app.services.credential_service import decrypt_text
    db = SessionLocal()
    try:
        mc = db.scalars(select(ModelConfig).where(
            ModelConfig.user_id == user_id, ModelConfig.model_type == "text")).first()
        if not mc:
            mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id)).first()
        if not mc:
            return "", "", ""
        api_key = decrypt_text(mc.encrypted_api_key) if mc.encrypted_api_key else ""
        return (mc.base_url or ""), (mc.model_name or ""), api_key
    finally:
        db.close()


def _format_gsx_report_ai(result: str, user_id: int) -> str:
    """用 LLM 智能排版验机报告（适配任意服务/格式的报告）。

    - LLM 只做排版（每字段一行），严格指令禁止增删改内容
    - 零丢失校验：LLM 输出去空白后必须与原文一致，否则回退规则式 `_format_gsx_report`
    - LLM 调用失败/未配置模型时同样回退规则式（保证任何情况下内容完整）
    """
    import re as _re
    import requests as _req
    base_url, model_name, api_key = _load_text_model_config(user_id)
    if not (base_url and model_name and api_key):
        return _format_gsx_report(result)

    prompt = (
        "你是报告排版助手。把下面的苹果验机报告重新排版成易读格式：每个字段占一行（字段名: 值），"
        "字段之间不要空行，不要加编号。"
        "【严格规则】逐字保留所有字段名和值：不要增删改任何内容、不要补充解释、不要截断、不要丢行、"
        "不要改变字段顺序。只允许插入换行和空格。\n\n报告原文：\n" + result
    )
    try:
        resp = _req.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "你只负责排版，绝不改动报告内容。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        # 零丢失校验：去空白后必须与原文完全一致，否则回退规则式
        if out and _re.sub(r"\s+", "", out) == _re.sub(r"\s+", "", result):
            return out
        print("[FMT-AI] LLM 输出与原文不一致，回退规则式")
    except Exception as e:
        print(f"[FMT-AI] LLM 排版失败: {e}")
    return _format_gsx_report(result)


def _analyze_gsx_report_ai(report: str, user_id: int) -> str:
    """用 LLM 分析验机报告，输出【报告分析】。

    围绕 5 点分析：① iCloud激活锁 ② 网络锁 ③ 设备信息 ④ 激活日期是否对得上 ⑤ 黑名单，
    给出几条优点 + 几条缺点/注意事项。LLM 失败/未配置时回退规则式 `_analyze_gsx_report`。"""
    import requests as _req
    base_url, model_name, api_key = _load_text_model_config(user_id)
    if not (base_url and model_name and api_key):
        return _analyze_gsx_report(report)

    prompt = (
        "你是专业的苹果设备验机分析师。请根据下面的验机报告输出【报告分析】，"
        "围绕以下 5 点逐条分析：\n"
        "1. iCloud激活锁：是否开启/有ID，对购买和使用的影响\n"
        "2. 网络锁：是否有锁/运营商锁，能否正常插卡使用\n"
        "3. 设备信息：型号、容量、颜色，是否官换机/官翻机/资源机等\n"
        "4. 激活日期：是否与设备上市时间/购买时间对得上\n"
        "5. 黑名单：ID黑白状态，是否存在风险\n\n"
        "要求：\n"
        "- 先给出 2-3 条【优点】\n"
        "- 再给出 1-2 条【缺点/注意事项】（确实没问题就说明整体成色良好）\n"
        "- 简明扼要，总共 6-10 行，像资深验机师傅的口吻，别重复报告原文\n"
        "- 只能依据报告内容，报告里没有的信息不要猜测\n\n"
        "验机报告：\n" + report
    )
    try:
        resp = _req.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "你是苹果设备验机分析师，只依据报告内容分析，不编造。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        if out:
            return out
    except Exception as e:
        print(f"[FMT-AI] 报告分析失败: {e}")
    return _analyze_gsx_report(report)


def _analyze_gsx_report(result: str) -> str:
    """根据验机报告提取重点，生成简短分析（规则式）"""
    text = (result or "").strip()
    if not text:
        return ""
    joined = text.replace("\n", " ")
    points = []

    m = _re.search(r"(?:型号|MODEL)[:：]\s*([^,\n]+?)(?=\s*(?:IMEI|SN|激活锁|ID黑白|$))", text, _re.IGNORECASE)
    if m:
        points.append(f"机型：{m.group(1).strip()[:40]}")

    if "激活锁" in joined:
        if "关闭" in joined or "无ID" in joined:
            points.append("激活锁：关闭（无ID），设备干净可放心")
        elif "开启" in joined or "有ID" in joined:
            points.append("⚠️ 激活锁：开启（有ID），未退出iCloud/查找，购机需谨慎")
        else:
            mv = _re.search(r"激活锁[:：]\s*([^\n]+)", text)
            if mv:
                points.append(f"激活锁：{mv.group(1).strip()[:30]}")

    if "白名单" in joined or "clean" in joined.lower():
        points.append("ID状态：白名单（Clean），来源干净")
    elif "黑名单" in joined or "blacklist" in joined.lower():
        points.append("⚠️ ID状态：黑名单，存在风险")

    if not points:
        lines = [l.strip() for l in text.splitlines() if l.strip()][:2]
        return "；".join(lines)
    return "；".join(points)


def _handle_sn_imei(user_id: int, platform_account_id: int, app_cid: str, code: str):
    """序列号/IMEI 完整处理流程：
    1) 苹果规则校验（不合法 → 直接反馈，不落库）
    2) 合法 → 先写入/补全 WalleOrder（sn_imei，status=0 待验机）
    3) 调 gsxunlocking 验机 API（srv 按订单 SKU 解析）
    4) 按查询结果更新订单状态（成功=1 / 失败=2，结果存 verify_result）
    5) 反馈客户
    """
    from backend.app.services.walle_agent.tools import normalize_sn_imei
    normalized = normalize_sn_imei(code)
    if not normalized:
        _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                               f"您提供的 {code} 格式不对，请检查：IMEI 为 15 位数字，序列号（SN）为 8-14 位字母数字组合。")
        return

    # 店铺 GSX 配置（gsx_key 为 gsxunlocking API 密钥，留空时 query_gsx 自动读 config.json）
    from backend.app.core.database import SessionLocal
    from sqlalchemy import select as _select
    db = SessionLocal()
    try:
        shop_cfg = db.scalars(
            _select(WalleShopConfig).where(
                WalleShopConfig.platform_account_id == platform_account_id,
                WalleShopConfig.user_id == user_id,
            )
        ).first()
        gsx_key = shop_cfg.gsx_key or "" if shop_cfg else ""
    finally:
        db.close()

    # 买家真实 userId（用于按订单 SKU 解析 srv 服务 ID）
    buyer_user_id = _conv_customer_id(platform_account_id, app_cid)

    # ── 2) 先写入订单表：优先补全该会话待验机记录（[订单]卡创建的），无则新建 ──
    from backend.app.core.database import SessionLocal as _SL
    from backend.app.models.walle import WalleOrder
    from backend.app.core.time import shanghai_now
    from sqlalchemy import select as _sel
    db2 = _SL()
    order_id = None
    order_spec = ""  # 订单规格（用于匹配 ark_product_skus.query_type 取服务ID）
    try:
        pending = db2.scalars(
            _sel(WalleOrder).where(
                WalleOrder.platform_account_id == platform_account_id,
                WalleOrder.app_cid == app_cid,
                WalleOrder.status == 0,
            ).order_by(WalleOrder.id.desc())
        ).first()
        if pending:
            pending.sn_imei = normalized
            pending.updated_at = shanghai_now()
            db2.commit()
            order_id = pending.id
            order_spec = pending.spec or ""
        else:
            row = WalleOrder(
                user_id=user_id,
                platform_account_id=platform_account_id,
                app_cid=app_cid,
                sn_imei=normalized,
                coupon_code="",
                status=0,
                created_at=shanghai_now(),
                updated_at=shanghai_now(),
            )
            db2.add(row)
            db2.commit()
            db2.refresh(row)
            order_id = row.id
    finally:
        db2.close()

    # ── 2.5) 查询前先反馈"正在查询"，避免买家等待无响应 ──────────────
    _query_label = "IMEI" if normalized.isdigit() else "序列号"
    _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                           f"正在查询{_query_label}：{normalized}，请稍等~")

    # ── 3) 请求查询 API（srv：spec↔query_type 匹配 SKU → service_id）───────
    from backend.app.services.walle_agent.tools import QueryGsxParams, query_gsx
    result = query_gsx(QueryGsxParams(
        code=normalized,
        gsx_key=gsx_key,
        buyer_user_id=buyer_user_id,
        spec=order_spec,
    ))
    is_success = not (result.startswith("GSX 查询失败") or result.startswith("GSX 接口"))
    if is_success:
        # 验机报告智能排版（LLM 适配任意格式，零丢失；失败回退规则式）
        result = _format_gsx_report_ai(result, user_id)

    # ── 4) 更新订单状态（成功=1 / 失败=2，结果存 verify_result）──────
    if order_id:
        db3 = _SL()
        try:
            rec = db3.get(WalleOrder, order_id)
            if rec:
                rec.status = 1 if is_success else 2
                rec.verify_result = {"ok": is_success, "result": result}
                rec.updated_at = shanghai_now()
                db3.commit()
        finally:
            db3.close()

    # ── 4.5) 验机成功 → 无物流发货（发货内容 express_no = 验机报告）───
    # 仅对待发货订单执行；已发货/已完成等订单跳过（接口本身也会拒绝）。
    shipped = False
    if is_success and buyer_user_id:
        try:
            from apis.xhs_walle_eva_apis import ArkAPI
            from backend.app.services.walle_agent.tools import _PENDING_SHIP
            api = ArkAPI()
            ok2, msg2, res2 = api.get_orders_by_user(buyer_user_id)
            if ok2 and res2:
                pkgs = ((res2.get("data") or {}).get("packages")) or []
                pkg = pkgs[0] if pkgs else {}
                if pkg.get("status") in _PENDING_SHIP:
                    pkg_id = pkg.get("packageId") or ""
                    if pkg_id:
                        # ⚠️ 发货内容（express_no）上限 200 字：完整报告放聊天消息，这里放报告前段
                        ship_content = result[:190] + ("…" if len(result) > 190 else "")
                        sok, smsg, sres = api.ship_no_logistics(
                            package_id=pkg_id,
                            express_no=ship_content,
                        )
                        shipped = sok
                        print(f"[SHIP] 无物流发货 package={pkg_id} ok={sok} msg={smsg}")
                    else:
                        print(f"[SHIP] 订单 {pkg.get('orderId')} 无 packageId，跳过发货")
                else:
                    print(f"[SHIP] 订单状态 {pkg.get('status')} 非待发货，跳过发货")
        except Exception as e:
            print(f"[SHIP] 发货异常: {e}")

    # ── 5) 反馈客户：验机报告独立一条 + 重点分析 + 五星好评感谢 ──────
    if is_success:
        head = f"✅ 验机成功（{normalized}）" + ("，订单已无物流发货" if shipped else "")
        # 1) 验机报告独立一条发送
        report_msg = f"{head}\n\n📋 验机报告：\n{result}"
        _fire_and_forget_reply(user_id, platform_account_id, app_cid, report_msg)
        # 2) 报告分析（AI 围绕激活锁/网络锁/设备信息/激活日期/黑名单 给优缺点）
        analysis = _analyze_gsx_report_ai(result, user_id)
        if analysis:
            _fire_and_forget_reply(user_id, platform_account_id, app_cid, f"📌 报告分析：\n{analysis}")
        # 3) 五星好评感谢
        _fire_and_forget_reply(user_id, platform_account_id, app_cid,
                               "如果满意请给个五星好评，感谢您的支持！有什么问题随时找我～ 😊")
        reply = report_msg  # 供 Agent 上下文记录（报告内容）
    else:
        reply = f"验机查询未成功（{normalized}）：{result}"
        _fire_and_forget_reply(user_id, platform_account_id, app_cid, reply)

    # ── 6) 写入 Agent 会话上下文（walle_agent_sessions）─────────────
    # 买家后续追问（如"激活锁什么意思？"）时，run_agent 加载的历史里要有
    # 验机查询 + 验机报告，AI 才能依据报告继续回答。
    try:
        from backend.app.services.walle_agent.agent_loop import _save_message as _save_agent_msg
        db4 = _SL()
        try:
            _save_agent_msg(db4, platform_account_id, app_cid, "user", f"验机查询：{normalized}")
            _save_agent_msg(db4, platform_account_id, app_cid, "assistant", reply)
        finally:
            db4.close()
    except Exception as e:
        print(f"[AGENT-CTX] 写入失败: {e}")


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
        vision_mc = db.scalars(select(ModelConfig).where(ModelConfig.user_id == user_id, ModelConfig.model_type == "image")).first()
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
                customer_id=customer.get("userId") or (app_cid[-20:] if len(app_cid) >= 20 else app_cid),
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


@router.post("/accounts/auto-import")
def auto_import_eva(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """静默自动导入：优先 CDP，fallback 文件，都没有返回 {ok: False}"""
    from backend.app.core.config import get_settings
    eva_dir = get_settings().walle_eva_dir or r"F:\eva"
    eva_path = f"{eva_dir}/eva_cookies.json"
    import os, json as _json, urllib.request as _ur
    cookies: dict = {}
    try:
        pages = _json.loads(_ur.urlopen("http://localhost:9222/json", timeout=2).read())
        ws_url = next(
            (p["webSocketDebuggerUrl"] for p in pages
             if "walle.xiaohongshu.com" in p.get("url", "") and "login" not in p.get("url", "") and p.get("type") == "page"),
            None
        )
        if ws_url:
            import asyncio, websockets as _ws
            async def _fetch():
                async with _ws.connect(ws_url) as ws:
                    await ws.send(_json.dumps({"id": 99, "method": "Network.getCookies", "params": {}}))
                    for _ in range(30):
                        msg = _json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                        if msg.get("id") == 99:
                            return {c["name"]: c["value"] for c in msg["result"]["cookies"]}
                return {}
            raw = asyncio.run(_fetch())
            if raw.get("walle-eva-auth") or raw.get("walle-eva-bUserId"):
                keep = ["walle-eva-auth", "walle-eva-bUserId", "access-token-walle.xiaohongshu.com",
                        "acw_tc", "gid", "websectiga", "xsecappid", "webId", "a1"]
                cookies = {"cookie_string": "; ".join(f"{k}={raw[k]}" for k in keep if k in raw), "cookies": raw}
    except Exception:
        pass
    if not cookies and os.path.exists(eva_path):
        try:
            with open(eva_path, "r", encoding="utf-8") as f:
                cookies = _json.load(f)
        except Exception:
            pass
    if not cookies:
        return {"ok": False, "reason": "no_cookie", "login_url": "https://walle.xiaohongshu.com"}
    inner = cookies.get("cookies") or {}
    nickname = cookies.get("nickname") or cookies.get("csaName") or "千帆客服工作台"
    external_id = cookies.get("csaId") or cookies.get("userId") or inner.get("walle-eva-bUserId") or "walle"
    account, action = upsert_platform_account_from_login(
        db=db, user_id=current_user.id, platform="xhs", sub_type="walle",
        user_info={"external_user_id": str(external_id), "nickname": nickname, "avatar_url": ""},
        cookies_text=cookies.get("cookie_string") or _json.dumps(inner or cookies, ensure_ascii=False),
    )
    db.commit()
    db.refresh(account)
    return {"ok": True, "action": action, **serialize_account(account, action)}


@router.post("/accounts/import-eva")
def import_eva_account(
    eva_path: str = Query(default=r"F:\eva\eva_cookies.json", description="eva_cookies.json 路径"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """优先从 CDP 9222 实时抓 walle cookie，fallback 读 eva_cookies.json 文件"""
    import os, json as _json, urllib.request as _ur

    cookies: dict = {}

    # 1. 优先从 CDP 实时抓
    try:
        pages = _json.loads(_ur.urlopen("http://localhost:9222/json", timeout=2).read())
        ws_url = next(
            (p["webSocketDebuggerUrl"] for p in pages
             if "walle.xiaohongshu.com" in p.get("url", "") and "login" not in p.get("url", "") and p.get("type") == "page"),
            None
        )
        if ws_url:
            import asyncio, websockets as _ws

            async def _fetch_cookies():
                async with _ws.connect(ws_url) as ws:
                    await ws.send(_json.dumps({"id": 99, "method": "Network.getCookies", "params": {}}))
                    for _ in range(30):
                        msg = _json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                        if msg.get("id") == 99:
                            return {c["name"]: c["value"] for c in msg["result"]["cookies"]}
                return {}

            raw = asyncio.run(_fetch_cookies())
            if raw.get("walle-eva-auth") or raw.get("walle-eva-bUserId"):
                keep = ["walle-eva-auth", "walle-eva-bUserId", "access-token-walle.xiaohongshu.com",
                        "acw_tc", "gid", "websectiga", "xsecappid", "webId", "a1"]
                cookie_string = "; ".join(f"{k}={raw[k]}" for k in keep if k in raw)
                cookies = {
                    "cookie_string": cookie_string,
                    "cookies": raw,
                }
    except Exception:
        pass

    # 2. fallback：读文件
    if not cookies:
        if not os.path.exists(eva_path):
            raise HTTPException(status_code=400, detail=f"CDP 未连接且文件不存在: {eva_path}，请先启动 cookie_watcher.py")
        try:
            with open(eva_path, "r", encoding="utf-8") as f:
                cookies = _json.load(f)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    inner = cookies.get("cookies") or {}
    nickname = cookies.get("nickname") or cookies.get("csaName") or "千帆客服工作台"
    external_id = (
        cookies.get("csaId")
        or cookies.get("userId")
        or inner.get("walle-eva-bUserId")
        or "walle"
    )
    token = inner.get("walle-eva-auth") or inner.get("access-token-walle.xiaohongshu.com") or ""

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
