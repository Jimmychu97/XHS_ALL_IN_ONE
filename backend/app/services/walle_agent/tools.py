from __future__ import annotations

"""
XHS 客服 Agent 工具集
对应 Customer-Agent 的 tools/ 目录，按 @agent_tool 装饰器注册。

工具列表：
  search_knowledge      — 搜索 WalleKnowledge 知识库（对应 search_customer_service_knowledge）
  query_gsx             — GSX 验机查询（核心业务，Customer-Agent 无此工具）
  record_order          — 记录验机订单到 WalleOrder 表
"""

import hashlib
import json
import time
from typing import Optional

import requests as _req
from pydantic import BaseModel, Field

from backend.app.services.walle_agent.tool_registry import agent_tool


# ── 1. 知识库搜索 ─────────────────────────────────────────────────────────────

class SearchKnowledgeParams(BaseModel):
    query: str = Field(..., description="搜索关键词")
    platform_account_id: int = Field(..., description="店铺账号 ID")


@agent_tool(
    name="search_knowledge",
    description=(
        "搜索店铺客服知识库，查找话术、FAQ、售后政策、物流信息等。"
        "用户提任何问题时必须优先调用此工具，知识库无结果时再用自身知识兜底。"
    ),
    param_model=SearchKnowledgeParams,
)
def search_knowledge(params: SearchKnowledgeParams) -> str:
    from sqlalchemy import select, or_
    from backend.app.core.database import SessionLocal
    from backend.app.models.walle import WalleKnowledge

    db = SessionLocal()
    try:
        query = params.query.strip()
        stmt = (
            select(WalleKnowledge)
            .where(
                WalleKnowledge.platform_account_id == params.platform_account_id,
                WalleKnowledge.enabled == True,
                or_(
                    WalleKnowledge.title.contains(query),
                    WalleKnowledge.content.contains(query),
                ),
            )
            .limit(5)
        )
        items = db.scalars(stmt).all()
        if not items:
            return "知识库中未找到相关内容。"
        lines = []
        for k in items:
            lines.append(f"【{k.title}】\n{k.content}")
        return "\n\n".join(lines)
    finally:
        db.close()


# ── 2. GSX 验机查询（gsxunlocking）──────────────────────────────────────────

def normalize_sn_imei(code: str) -> str:
    """按苹果序列号/IMEI 规则校验并规范化，非法返回空字符串。

    - 先去除所有空白（支持 "35 113831 0588051" 这类带空格的 IMEI）
    - IMEI：15 位纯数字
    - 序列号（SN）：8-14 位字母数字组合（大写），且至少含 1 个字母
    """
    import re as _re
    code = _re.sub(r"\s+", "", code or "").upper()
    if not code:
        return ""
    # ⚠️ isalnum/isalpha 会把中文等非 ASCII 也判为字母数字，必须 isascii 限定
    if len(code) == 15 and code.isascii() and code.isdigit():
        return code  # IMEI
    if 8 <= len(code) <= 14 and code.isascii() and code.isalnum() and any(c.isalpha() for c in code):
        return code  # SN
    return ""


def _gsx_api_key(gsx_key: str = "") -> str:
    """gsxunlocking API 密钥：优先店铺配置，其次项目根 config.json"""
    if gsx_key:
        return gsx_key
    try:
        import json as _json
        import pathlib
        # tools.py → walle_agent → services → app → backend → 项目根
        cfg = pathlib.Path(__file__).resolve().parents[4] / "config.json"
        if cfg.exists():
            data = _json.loads(cfg.read_text("utf-8"))
            if isinstance(data, dict):
                return data.get("key") or (data.get("gsxunlocking") or {}).get("key") or ""
    except Exception:
        pass
    return ""


def _resolve_gsx_srv(buyer_user_id: str = "", srv: str = "", spec: str = "") -> str:
    """srv 服务 ID 解析（完整流程）：
    1) 显式传入的 srv 优先
    2) 买家最新订单的规格 spec ↔ ark_product_skus.query_type 匹配 → 该 SKU 的 service_id
    3) 按订单 SKU 的 sku_id 精确匹配兜底 → 该 SKU 的 service_id
    命中 SKU 后：service_id 为数字则用之（用户配置），否则回退该 SKU 的 srv 列。"""
    if srv:
        return srv
    if not buyer_user_id:
        return ""
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        ok, msg, res = ArkAPI().get_orders_by_user(buyer_user_id)
        if not ok or not res:
            return ""
        packages = ((res.get("data") or {}).get("packages")) or []
        if not packages:
            return ""
        sku = (packages[0].get("skus") or [{}])[0]
        scsku = (sku.get("scskus") or [{}])[0]
        sku_id = scsku.get("skuId") or sku.get("skuId") or ""
        if not spec:
            spec = scsku.get("specification") or scsku.get("scskuCode") or sku.get("specification") or ""

        from backend.app.core.database import SessionLocal
        from backend.app.models.ark import ArkProductSku
        from sqlalchemy import select

        def _pick(row) -> str:
            """SKU 行 → 服务码：service_id 优先，其次 srv 列。
            非数字也返回，由 query_gsx 校验并给出配置提示。"""
            if row:
                if row.service_id:
                    return row.service_id
                if row.srv:
                    return row.srv
            return ""

        db = SessionLocal()
        try:
            # 用户流程：spec ↔ query_type 匹配
            if spec:
                row = db.scalars(
                    select(ArkProductSku).where(ArkProductSku.query_type == spec)
                ).first()
                v = _pick(row)
                if v:
                    return v
            # 兜底：按 sku_id 精确匹配
            if sku_id:
                row = db.scalars(
                    select(ArkProductSku).where(ArkProductSku.sku_id == sku_id)
                ).first()
                v = _pick(row)
                if v:
                    return v
        finally:
            db.close()
        return ""
    except Exception:
        return ""


def _clean_html(text: str) -> str:
    """清理 result 中的 HTML 标签"""
    import re as _re
    text = _re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return text.strip()


class QueryGsxParams(BaseModel):
    code: str = Field(..., description="序列号（SN）或 IMEI（15位数字），由用户消息提取")
    gsx_key: str = Field("", description="gsxunlocking API 密钥（店铺配置 gsx_key，留空自动读 config.json）")
    buyer_user_id: str = Field("", description="买家的 XHS userId，用于按订单解析服务 ID")
    srv: str = Field("", description="服务 ID（数字服务码），留空则按订单 spec↔query_type 匹配 SKU 自动解析")
    spec: str = Field("", description="订单规格（如 基础查询），用于匹配 ark_product_skus.query_type")


@agent_tool(
    name="query_gsx",
    description=(
        "调用 GSX 验机接口查询手机序列号或 IMEI 的验机报告。"
        "当用户提供序列号（字母数字组合）或 IMEI（15位数字）时调用此工具。"
        "IMEI 和序列号均可用于查询，不要告诉用户 IMEI 不能查询。"
    ),
    param_model=QueryGsxParams,
)
def query_gsx(params: QueryGsxParams) -> str:
    _API_URL = "https://www.gsxunlocking.com/api/uapi"

    code = normalize_sn_imei(params.code)
    if not code:
        return "GSX 查询失败：序列号/IMEI 格式不对（IMEI 为 15 位数字；序列号为 8-14 位字母数字组合）"

    key = _gsx_api_key(params.gsx_key)
    if not key:
        return "GSX 查询失败：未配置 API 密钥（店铺配置 gsx_key 或 config.json）"

    srv = _resolve_gsx_srv(params.buyer_user_id, params.srv, params.spec)
    if not srv:
        return "GSX 查询失败：未匹配到订单 SKU 的服务 ID，请先在「商品管理 → 规格明细」配置服务ID"
    if not srv.isdigit():
        return f"GSX 查询失败：SKU 服务ID「{srv}」不是数字服务码，请到「商品管理 → 规格明细」把服务ID改为 gsxunlocking 数字服务码（如 1010）"

    try:
        resp = _req.get(
            _API_URL,
            params={"format": "json", "key": key, "srv": srv, "imei": code},
            timeout=30,
        )
        if resp.status_code != 200:
            return f"GSX 接口请求失败：HTTP {resp.status_code}"
        text = resp.text.strip()
        try:
            data = resp.json()
        except Exception:
            return f"GSX 接口返回异常：{text[:100]}"
        if data.get("code") == 0:
            return _clean_html(str(data.get("result", "")))
        return f"GSX 查询失败：{data.get('result') or '未知错误'}"
    except Exception as e:
        return f"GSX 查询异常：{e}"


# ── 3. 订单状态查询 ──────────────────────────────────────────────────────────

# 订单状态码映射
_ORDER_STATUS = {
    1: "待付款", 2: "待发货", 4: "待发货", 5: "待发货", 21: "待发货", 26: "待发货",
    55: "待发货", 6: "已发货", 7: "已完成", 998: "已取消",
}
_PENDING_SHIP = {2, 4, 5, 21, 26, 55}


class CheckOrderStatusParams(BaseModel):
    buyer_user_id: str = Field(..., description="买家的 XHS userId，从会话消息中获取")
    platform_account_id: int = Field(..., description="店铺账号 ID")


@agent_tool(
    name="check_order_status",
    description=(
        "根据买家 userId 查询其最新订单状态。"
        "当买家发来消息时，先调用此工具确认订单状态："
        "待发货 → 提示提供序列号/IMEI；其他状态 → 引导重新下单。"
    ),
    param_model=CheckOrderStatusParams,
)
def check_order_status(params: CheckOrderStatusParams) -> str:
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        api = ArkAPI()
        ok, msg, res = api.get_orders_by_user(params.buyer_user_id)
        if not ok or not res:
            return f"查询订单失败：{msg}"
        packages = (res.get("data") or {}).get("packages") or []
        if not packages:
            return "未找到该买家的订单记录。"
        # 取最新一条
        pkg = packages[0]
        status_code = pkg.get("status", -1)
        status_text = _ORDER_STATUS.get(status_code, f"未知状态({status_code})")
        order_id = pkg.get("orderId", "")
        sku_name = ""
        skus = pkg.get("skus") or []
        if skus:
            sku_name = skus[0].get("skuSpecification") or skus[0].get("skuName", "")
        is_pending = status_code in _PENDING_SHIP
        return json.dumps({
            "order_id": order_id,
            "status_code": status_code,
            "status_text": status_text,
            "sku_name": sku_name,
            "is_pending_ship": is_pending,
            "total_orders": len(packages),
        }, ensure_ascii=False)
    except Exception as e:
        return f"查询订单异常：{e}"


# ── 4. 验机订单记录 ───────────────────────────────────────────────────────────

class RecordOrderParams(BaseModel):
    app_cid: str = Field(..., description="会话 ID")
    platform_account_id: int = Field(..., description="店铺账号 ID")
    sn_imei: str = Field(..., description="用户提供的序列号或 IMEI")
    coupon_code: str = Field(..., description="用户提供的卡券号")
    goods_name: Optional[str] = Field(default=None, description="商品名称")
    user_id: Optional[int] = Field(default=None, description="平台用户 ID")


@agent_tool(
    name="record_order",
    description=(
        "将用户提供的序列号/IMEI 和卡券号记录为验机订单。"
        "当用户同时提供了序列号（或IMEI）和卡券号时调用此工具完成订单登记。"
    ),
    param_model=RecordOrderParams,
)
def record_order(params: RecordOrderParams) -> str:
    # 按苹果序列号/IMEI 规则校验后再录入
    normalized = normalize_sn_imei(params.sn_imei)
    if not normalized:
        return f"验机订单登记失败：{params.sn_imei} 格式不对（IMEI 为 15 位数字；序列号为 8-14 位字母数字组合）"

    from backend.app.core.database import SessionLocal
    from backend.app.models.walle import WalleOrder
    from backend.app.core.time import shanghai_now

    db = SessionLocal()
    try:
        order = WalleOrder(
            user_id=params.user_id or 0,
            platform_account_id=params.platform_account_id,
            app_cid=params.app_cid,
            sn_imei=normalized,
            coupon_code=params.coupon_code,
            goods_name=params.goods_name,
            status=0,
            created_at=shanghai_now(),
            updated_at=shanghai_now(),
        )
        db.add(order)
        db.commit()
        return f"验机订单已登记：序列号/IMEI={normalized}，卡券={params.coupon_code}"
    except Exception as e:
        db.rollback()
        return f"验机订单登记失败：{e}"
    finally:
        db.close()
