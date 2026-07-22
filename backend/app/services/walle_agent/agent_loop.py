from __future__ import annotations

"""
XHS 客服 Agent 核心循环
对应 Customer-Agent 的 CustomerAgent._run_agent_loop + MessageBuilder + SessionManager。

设计原则（与 Customer-Agent 保持一致）：
  - 历史消息持久化在 WalleAgentSession 表（按 app_cid 隔离）
  - system prompt = system_prompt（人设）+ instructions（行为指令）+ 工具说明
  - Agent 循环：LLM → tool_calls → 并行执行 → 回传 → 循环，最多 max_loops=5
  - token 超阈值时用 LLM 生成摘要压缩历史（对应 SessionManager.compress_history）
  - 最终回复写库 + 若 auto_send=True 则调用 send_message 发送
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

# 导入工具模块触发 @agent_tool 注册
from backend.app.services.walle_agent import tools as _tools_module  # noqa: F401
from backend.app.services.walle_agent.tool_registry import execute_tool, get_tools_schema

logger = logging.getLogger(__name__)

MAX_LOOPS = 5
# token 估算阈值：超过此字符数触发历史压缩（粗略：1 token ≈ 1.5 中文字符）
COMPRESS_CHAR_THRESHOLD = 12000
RETAIN_COUNT = 10  # 压缩后保留最近 N 条


# ── session 历史管理 ──────────────────────────────────────────────────────────

def _load_history(db: Session, platform_account_id: int, app_cid: str) -> List[Dict[str, Any]]:
    from backend.app.models.walle import WalleAgentSession
    rows = db.scalars(
        select(WalleAgentSession)
        .where(
            WalleAgentSession.platform_account_id == platform_account_id,
            WalleAgentSession.app_cid == app_cid,
        )
        .order_by(WalleAgentSession.created_at.asc())
    ).all()
    result = []
    for r in rows:
        msg: Dict[str, Any] = {"role": r.role}
        content_str = r.content or ""
        if content_str.startswith("__tool_calls__"):
            # assistant 消息带 tool_calls
            msg["content"] = ""
            try:
                msg["tool_calls"] = json.loads(content_str[len("__tool_calls__"):])
            except Exception:
                pass
        elif content_str:
            try:
                parsed = json.loads(content_str)
                msg["content"] = parsed if isinstance(parsed, (list, dict)) else content_str
            except Exception:
                msg["content"] = content_str
        else:
            msg["content"] = ""
        if r.tool_call_id:
            msg["tool_call_id"] = r.tool_call_id
        # tool 消息必须有对应的 assistant tool_calls，否则跳过
        if r.role == "tool" and (not result or result[-1].get("role") != "assistant" or not result[-1].get("tool_calls")):
            continue
        result.append(msg)
    return result


def _save_message(db: Session, platform_account_id: int, app_cid: str,
                  role: str, content: Any, tool_call_id: Optional[str] = None,
                  tool_calls: Optional[list] = None) -> None:
    from backend.app.models.walle import WalleAgentSession
    if isinstance(content, (list, dict)):
        content = json.dumps(content, ensure_ascii=False)
    # tool_calls 序列化后存入 content，用特殊前缀区分
    stored_content = str(content) if content is not None else ""
    if tool_calls:
        stored_content = "__tool_calls__" + json.dumps(tool_calls, ensure_ascii=False)
    db.add(WalleAgentSession(
        platform_account_id=platform_account_id,
        app_cid=app_cid,
        role=role,
        content=stored_content,
        tool_call_id=tool_call_id,
        created_at=datetime.now(),
    ))
    db.commit()


def _should_compress(history: List[Dict[str, Any]]) -> bool:
    total = sum(len(str(m.get("content", ""))) for m in history)
    return total > COMPRESS_CHAR_THRESHOLD


def _compress_history(db: Session, platform_account_id: int, app_cid: str,
                      history: List[Dict[str, Any]], mc, api_key: str) -> None:
    """用 LLM 生成摘要，删除旧消息，插入摘要 system 消息"""
    from backend.app.models.walle import WalleAgentSession
    import requests as _req

    old = history[:-RETAIN_COUNT]
    if not old:
        return

    dialog = "\n".join(
        f"[{m['role']}]: {str(m.get('content', ''))[:200]}"
        for m in old if m.get("content")
    )
    try:
        resp = _req.post(
            f"{mc.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": mc.model_name,
                "messages": [
                    {"role": "system", "content": "你是对话摘要助手，请简洁总结以下对话要点，保留关键信息。"},
                    {"role": "user", "content": dialog},
                ],
            },
            timeout=30,
        )
        summary = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        summary = "[历史对话摘要]"

    # 删除旧消息（保留最近 RETAIN_COUNT 条）
    all_rows = db.scalars(
        select(WalleAgentSession)
        .where(
            WalleAgentSession.platform_account_id == platform_account_id,
            WalleAgentSession.app_cid == app_cid,
        )
        .order_by(WalleAgentSession.created_at.asc())
    ).all()
    for row in all_rows[:-RETAIN_COUNT]:
        db.delete(row)

    # 插入摘要
    db.add(WalleAgentSession(
        platform_account_id=platform_account_id,
        app_cid=app_cid,
        role="system",
        content=f"[以下是之前对话的摘要]\n\n{summary}",
        created_at=datetime.now(),
    ))
    db.commit()


# ── system prompt 构建 ────────────────────────────────────────────────────────

_TOOL_GUIDE = """---
行为规则：
1. 请用中文回复客户问题
2. 知识库有相关信息时，必须优先依据知识库内容回答，不要自行编造
3. 当用户发送订单信息（包含订单号、商品名、商品ID等）时，回复结尾必须加上：案例在商品页面评论区.五年老店信誉保证,请继续提供手机序列号和商品卡券【待收货-点击商品-查看卡券-复制卡券提供给客服】以便完成核销。

📦 工具使用说明：

1️⃣ search_knowledge（搜索知识库）
- 用途：查话术、FAQ、售后政策、物流等一切客服问题
- 【强制规则】用户发任何文字问题，必须第一个调用此工具，知识库无结果再用自身知识兜底

2️⃣ query_gsx（GSX 验机查询）
- 用途：用户提供序列号（字母数字组合）或 IMEI（15位数字）时查询验机报告
- IMEI 和序列号均可查询，不要告诉用户 IMEI 不能查询

3️⃣ record_order（核销登记）
- 用途：用户同时提供序列号/IMEI 和卡券号时，登记核销订单
"""


def _build_system_prompt(shop_cfg) -> str:
    base = shop_cfg.system_prompt if shop_cfg else "你是小红书店铺客服，请用简洁友好的语言回复买家问题。"
    return f"{base}\n\n{_TOOL_GUIDE}"


# ── Agent 主循环 ──────────────────────────────────────────────────────────────

def run_agent(
    *,
    platform_account_id: int,
    app_cid: str,
    user_message: str,
    shop_cfg,
    mc,
    vision_mc,
    api_key: str,
    vision_api_key: str,
    user_id: int,
) -> str:
    """
    完整 Agent 循环（同步，跑在后台线程中）。

    图片/文字分流：
      - 消息含 "[图片] " 前缀 → 下载图片转 base64 → 构造多模态 content 传给同一个 mc
      - 纯文字 → 直接传文字 content
    两种情况都走同一个 Agent 循环，用同一个 mc。
    """
    import base64
    import requests as _req
    from backend.app.core.database import SessionLocal

    is_image = user_message.startswith("[图片] ")

    if is_image:
        img_url = user_message[4:].strip()
        logger.info(f"图片消息: app_cid={app_cid}")
        if vision_mc:
            # 视觉模型：下载图片转 base64 构造多模态输入
            try:
                img_resp = _req.get(
                    img_url,
                    headers={"Referer": "https://walle.xiaohongshu.com/", "User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                img_resp.raise_for_status()
                mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
                data_uri = f"data:{mime};base64,{base64.b64encode(img_resp.content).decode()}"
                user_content: Any = [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": "请识别图片中的内容，重点提取 IMEI、序列号、卡券号等编码，并回复客户。"},
                ]
                active_mc = vision_mc
                active_api_key = vision_api_key
            except Exception as e:
                logger.warning(f"图片下载失败: {e}")
                return "图片加载失败，请重新发送或直接输入序列号。"
        else:
            # 没有视觉模型，图片转文字描述给文本模型
            user_content = f"买家发送了一张图片，请识别图片内容并回复客户。图片地址：{img_url}"
            active_mc = mc
            active_api_key = api_key
        user_message_for_history = f"[图片] {img_url}"
    else:
        logger.info(f"文字消息 ({mc.model_name}): app_cid={app_cid}")
        user_content = user_message
        user_message_for_history = user_message
        active_mc = mc
        active_api_key = api_key

    db = SessionLocal()
    try:

        # 1. 加载历史
        history = _load_history(db, platform_account_id, app_cid)

        # 2. 检查是否需要压缩
        if _should_compress(history):
            logger.info(f"触发历史压缩: app_cid={app_cid}")
            _compress_history(db, platform_account_id, app_cid, history, mc, api_key)
            history = _load_history(db, platform_account_id, app_cid)

        # 3. 保存用户消息到历史（存文字描述，不存 base64）
        _save_message(db, platform_account_id, app_cid, "user", user_message_for_history)

        # 4. 构建 messages
        system_prompt = _build_system_prompt(shop_cfg)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append(msg)
        messages.append({"role": "user", "content": user_content})

        # 5. dependencies
        dependencies: Dict[str, Any] = {
            "platform_account_id": platform_account_id,
            "app_cid": app_cid,
            "user_id": user_id,
            "gsx_appid": shop_cfg.gsx_appid or "" if shop_cfg else "",
            "gsx_secret": shop_cfg.gsx_secret or "" if shop_cfg else "",
            "gsx_key": shop_cfg.gsx_key or "" if shop_cfg else "",
        }

        # 6. Agent 循环（图片消息用 active_mc，文字消息用 mc）
        tools_schema = get_tools_schema() if not is_image else []  # 图片消息不用工具
        endpoint = f"{active_mc.base_url.rstrip('/')}/chat/completions"
        import requests as _req

        loop_count = 0
        while loop_count < MAX_LOOPS:
            req_body: Dict[str, Any] = {
                "model": active_mc.model_name,
                "messages": messages,
                "temperature": 0.3,
            }
            if tools_schema:
                req_body["tools"] = tools_schema
                req_body["tool_choice"] = "auto"

            resp = _req.post(
                endpoint,
                headers={"Authorization": f"Bearer {active_api_key}", "Content-Type": "application/json"},
                json=req_body,
                timeout=60,
            )
            if not resp.ok:
                logger.error(f"LLM 400 detail: {resp.text[:500]}")
            resp.raise_for_status()
            choice = resp.json()["choices"][0]
            message = choice["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                # 无工具调用，返回最终回复
                final = (message.get("content") or "").strip()
                messages.append({"role": "assistant", "content": final})
                _save_message(db, platform_account_id, app_cid, "assistant", final)
                return final

            # 保存 assistant 消息（含 tool_calls）
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)
            _save_message(db, platform_account_id, app_cid, "assistant",
                          message.get("content") or "", tool_calls=tool_calls)

            if loop_count >= MAX_LOOPS - 1:
                # 达到上限，强制结束
                logger.warning(f"工具调用达到上限 {MAX_LOOPS}，强制结束: app_cid={app_cid}")
                messages.append({"role": "user", "content": "[已达到最大工具调用次数，请基于已有信息给出最终回复。]"})
                resp2 = _req.post(endpoint,
                                  headers={"Authorization": f"Bearer {active_api_key}", "Content-Type": "application/json"},
                                  json={"model": active_mc.model_name, "messages": messages, "temperature": 0.3},
                                  timeout=60)
                resp2.raise_for_status()
                final = (resp2.json()["choices"][0]["message"].get("content") or "").strip()
                _save_message(db, platform_account_id, app_cid, "assistant", final)
                return final

            # 执行工具调用
            tool_names = [tc["function"]["name"] for tc in tool_calls]
            logger.info(f"LLM 调用工具: {tool_names}, app_cid={app_cid}")

            for tc in tool_calls:
                result = execute_tool(tc["function"]["name"], tc["function"]["arguments"], dependencies)
                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result}
                messages.append(tool_msg)
                # 工具结果也持久化，便于历史压缩时保留上下文
                _save_message(db, platform_account_id, app_cid, "tool", result, tool_call_id=tc["id"])

            loop_count += 1

        return ""

    except Exception as e:
        logger.error(f"Agent 循环异常: app_cid={app_cid}, error={e}")
        raise
    finally:
        db.close()
