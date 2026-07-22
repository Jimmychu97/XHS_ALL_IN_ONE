from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class WalleShopConfig(Base):
    """店铺 AI 客服配置，每个千帆账号一条"""
    __tablename__ = "walle_shop_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), unique=True, index=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)        # 是否开启 AI 自动回复
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False)         # AI 回复是否自动发送（否则仅建议）
    model_config_id: Mapped[Optional[int]] = mapped_column(ForeignKey("model_configs.id"), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, default="")            # 客服人设 prompt
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组，行为指令列表
    gsx_appid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)   # GSX 验机 appid
    gsx_secret: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # GSX 验机 secret
    gsx_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)      # GSX 接口编码（如 10127）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class WalleKnowledge(Base):
    """店铺客服知识库，存储话术、FAQ、规则等"""
    __tablename__ = "walle_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # 逗号分隔
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class WalleKeyword(Base):
    """转人工关键词，命中后自动转接人工客服"""
    __tablename__ = "walle_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(100))


class WalleConversation(Base):
    """客服会话，每条对应一个买家与某店铺的会话"""
    __tablename__ = "walle_conversations"
    __table_args__ = (UniqueConstraint("platform_account_id", "app_cid", name="uq_conv_account_cid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), nullable=False, index=True)
    app_cid: Mapped[str] = mapped_column(String(256), index=True)           # edith 会话 ID
    im_chat_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)  # walle bot suggest 用
    customer_name: Mapped[str] = mapped_column(String(128), default="")
    customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    receiver_app_uid: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 买家 impaas appUid，发消息用
    status: Mapped[str] = mapped_column(String(32), default="open")         # open / replied / closed
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_msg_content: Mapped[str] = mapped_column(String(512), default="")
    last_msg_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ai_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 当前 AI 建议草稿，发送后清空
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class WalleMessage(Base):
    """会话消息，只存真实收发的消息"""
    __tablename__ = "walle_messages"
    __table_args__ = (UniqueConstraint("platform_account_id", "msg_id", name="uq_msg_account_msgid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), nullable=False, index=True)
    app_cid: Mapped[str] = mapped_column(String(256), index=True)
    msg_id: Mapped[str] = mapped_column(String(256), index=True)
    sender_type: Mapped[str] = mapped_column(String(32), default="")        # customer / csa / bot
    sender_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), default="text")   # text / image / order / ...
    content: Mapped[str] = mapped_column(Text, default="")
    msg_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)


class WalleAgentSession(Base):
    """AI 对话历史，每条对应一轮 LLM 消息，支持 token 压缩摘要"""
    __tablename__ = "walle_agent_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    app_cid: Mapped[str] = mapped_column(String(256), index=True)            # 关联会话
    role: Mapped[str] = mapped_column(String(32))                            # system / user / assistant / tool
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, index=True)


class WalleOrder(Base):
    """核销订单，记录用户提交序列号/IMEI + 卡券后的核销流程"""
    __tablename__ = "walle_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    app_cid: Mapped[str] = mapped_column(String(256), index=True)           # 关联会话
    sn_imei: Mapped[str] = mapped_column(String(100), default="")           # 序列号或 IMEI
    coupon_code: Mapped[str] = mapped_column(String(100), default="")       # 卡券号
    goods_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    goods_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # 商品 ID
    sku_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)     # SKU ID，验机配置查询用
    spec: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # 规格
    order_sn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 平台订单号
    verify_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # 验机报告原始数据
    status: Mapped[int] = mapped_column(Integer, default=0)                 # 0-待核销 1-成功 2-失败 3-已过期
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)
