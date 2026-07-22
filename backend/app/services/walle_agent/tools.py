from __future__ import annotations

"""
XHS 客服 Agent 工具集
对应 Customer-Agent 的 tools/ 目录，按 @agent_tool 装饰器注册。

工具列表：
  search_knowledge      — 搜索 WalleKnowledge 知识库（对应 search_customer_service_knowledge）
  query_gsx             — GSX 验机查询（核心业务，Customer-Agent 无此工具）
  record_order          — 记录核销订单到 WalleOrder 表
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


# ── 2. GSX 验机查询 ───────────────────────────────────────────────────────────

class QueryGsxParams(BaseModel):
    code: str = Field(..., description="序列号（SN）或 IMEI（15位数字），由用户消息提取")
    gsx_appid: str = Field(..., description="GSX appid，来自店铺配置")
    gsx_secret: str = Field(..., description="GSX secret，来自店铺配置")
    gsx_key: str = Field(..., description="GSX 接口编码，如 10127 表示苹果机型查询")


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
    _API_URL = "https://api-srv.gkdt.com/inquiry/async"
    ts = int(time.time())
    sign_params = {
        "appid": params.gsx_appid,
        "code": params.code,
        "key": params.gsx_key,
        "style": "11",
        "time": str(ts),
    }
    sorted_str = "&".join(f"{k}={v}" for k, v in sorted(sign_params.items()) if v)
    sign = hashlib.md5(f"{sorted_str}&secret={params.gsx_secret}".encode()).hexdigest()
    sign_params["sign"] = sign

    try:
        resp = _req.get(_API_URL, params=sign_params, timeout=30)
        if resp.status_code != 200:
            return f"GSX 接口请求失败：HTTP {resp.status_code}"
        text = resp.text.strip()
        if not text.startswith(("{", "[")):
            return f"GSX 接口返回异常：{text[:100]}"
        data = resp.json()
        if data.get("code") != 200:
            return f"GSX 查询失败：{data.get('message', '未知错误')}"
        result = data.get("data", data)
        if isinstance(result, dict):
            return "\n".join(f"{k}: {v}" for k, v in result.items() if v)
        return str(result)
    except Exception as e:
        return f"GSX 查询异常：{e}"


# ── 3. 核销订单记录 ───────────────────────────────────────────────────────────

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
        "将用户提供的序列号/IMEI 和卡券号记录为核销订单。"
        "当用户同时提供了序列号（或IMEI）和卡券号时调用此工具完成核销登记。"
    ),
    param_model=RecordOrderParams,
)
def record_order(params: RecordOrderParams) -> str:
    from backend.app.core.database import SessionLocal
    from backend.app.models.walle import WalleOrder
    from backend.app.core.time import shanghai_now

    db = SessionLocal()
    try:
        order = WalleOrder(
            user_id=params.user_id or 0,
            platform_account_id=params.platform_account_id,
            app_cid=params.app_cid,
            sn_imei=params.sn_imei,
            coupon_code=params.coupon_code,
            goods_name=params.goods_name,
            status=0,
            created_at=shanghai_now(),
            updated_at=shanghai_now(),
        )
        db.add(order)
        db.commit()
        return f"核销订单已登记：序列号/IMEI={params.sn_imei}，卡券={params.coupon_code}"
    except Exception as e:
        db.rollback()
        return f"核销订单登记失败：{e}"
    finally:
        db.close()
