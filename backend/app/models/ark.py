from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class ArkServerConfig(Base):
    """千帆卖家后台账号配置（ark.xiaohongshu.com）"""
    __tablename__ = "ark_server_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    server_id: Mapped[str] = mapped_column(String(128), index=True)          # 用户自定义标识，如店铺名
    seller_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    seller_name: Mapped[str] = mapped_column(String(255), default="")
    cookie_file: Mapped[str] = mapped_column(String(512), default="")        # ark_cookies.json 路径
    profile_dir: Mapped[str] = mapped_column(String(512), default="")        # ark_profile 路径
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class ArkProductSku(Base):
    """千帆商品 SKU 规格明细，从 publish_render 同步"""
    __tablename__ = "ark_product_skus"
    __table_args__ = (UniqueConstraint("product_id", "sku_id", name="uq_ark_sku_product_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("ark_products.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    sku_id: Mapped[str] = mapped_column(String(128), index=True)             # service_id — 服务ID
    sku_name: Mapped[str] = mapped_column(String(512), default="")
    query_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)   # 查询类型（款式 variantValue）
    service_id: Mapped[str] = mapped_column(String(128), default="")         # 同 sku_id，业务语义字段
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)     # 分
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivery_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spec_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class ArkProduct(Base):
    """千帆卖家后台商品，从 search_item_v2 同步"""
    __tablename__ = "ark_products"
    __table_args__ = (UniqueConstraint("server_config_id", "item_id", name="uq_ark_product_server_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    server_config_id: Mapped[int] = mapped_column(ForeignKey("ark_server_configs.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    card_type: Mapped[int] = mapped_column(Integer, default=2)               # 2=在售 3=仓库 4=售罄 5=审核 6=下架 10=违规
    total_stock: Mapped[int] = mapped_column(Integer, default=0)
    sku_count: Mapped[int] = mapped_column(Integer, default=0)
    first_sku_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sale_qty30: Mapped[int] = mapped_column(Integer, default=0)              # 近30天销量
    acc_sale_qty: Mapped[int] = mapped_column(Integer, default=0)            # 累计销量
    check_status: Mapped[int] = mapped_column(Integer, default=1)
    cover_url: Mapped[str] = mapped_column(Text, default="")
    price_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 分
    price_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_auto_off_shelf: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)
