from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.time import shanghai_now
from backend.app.models.ark import ArkProduct, ArkProductSku, ArkServerConfig
from backend.app.models.user import User
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/ark", tags=["ark"])

_CARD_TYPE_LABEL = {2: "在售", 3: "仓库中", 4: "已售罄", 5: "审核中", 6: "已下架", 10: "违规下架"}


def _parse_render_data(res: dict) -> dict:
    """publish_render 的 data 字段是二次序列化 JSON 字符串，统一解析为 dict"""
    import json as _json
    data = res.get("data")
    if isinstance(data, str):
        try:
            data = _json.loads(data)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


def _extract_sku_list(res: dict) -> list:
    data = _parse_render_data(res)
    return data.get("product", {}).get("productDetail", {}).get("skuList") or []


def _extract_render_extras(res: dict) -> dict:
    """从 publish_render 响应中提取 skuList / item.properties / saleProperties"""
    data = _parse_render_data(res)
    pd = data.get("product", {}).get("productDetail", {})
    return {
        "_sku_list": pd.get("skuList") or [],
        "_item_properties": pd.get("item", {}).get("properties") or [],
        "_sale_properties": (
            data.get("category", {})
                .get("categoryPropertyInfo", {})
                .get("saleProperties") or []
        ),
    }

def _serialize_config(c: ArkServerConfig) -> dict:
    return {
        "id": c.id,
        "server_id": c.server_id,
        "seller_id": c.seller_id,
        "seller_name": c.seller_name,
        "cookie_file": c.cookie_file,
        "profile_dir": c.profile_dir,
        "enabled": c.enabled,
        "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
        "created_at": c.created_at.isoformat(),
    }


def _serialize_product(p: ArkProduct) -> dict:
    return {
        "id": p.id,
        "server_config_id": p.server_config_id,
        "item_id": p.item_id,
        "title": p.title,
        "card_type": p.card_type,
        "card_type_label": _CARD_TYPE_LABEL.get(p.card_type, str(p.card_type)),
        "total_stock": p.total_stock,
        "sku_count": p.sku_count,
        "first_sku_id": p.first_sku_id,
        "sale_qty30": p.sale_qty30,
        "acc_sale_qty": p.acc_sale_qty,
        "check_status": p.check_status,
        "cover_url": p.cover_url,
        "price_min": p.price_min,
        "price_max": p.price_max,
        "is_auto_off_shelf": p.is_auto_off_shelf,
        "synced_at": p.synced_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _get_config(db: Session, user_id: int, config_id: int) -> ArkServerConfig:
    cfg = db.get(ArkServerConfig, config_id)
    if not cfg or cfg.user_id != user_id:
        raise HTTPException(status_code=404, detail="配置不存在")
    return cfg


def _upsert_product(db: Session, user_id: int, config_id: int, item: dict) -> ArkProduct | None:
    item_id = str(item.get("item_id") or item.get("itemId") or "")
    if not item_id:
        return None

    existing = db.scalars(
        select(ArkProduct).where(
            ArkProduct.server_config_id == config_id,
            ArkProduct.item_id == item_id,
        )
    ).first()

    cover_url = ""
    imgs = item.get("image_descriptions") or item.get("imageDescriptions") or []
    if imgs and isinstance(imgs, list):
        cover_url = imgs[0].get("link") or imgs[0].get("path") or ""

    # 价格直接从 min_price/max_price 字段读（单位：分）
    price_min = item.get("min_price") or None
    price_max = item.get("max_price") or None

    sale_info = item.get("sale_qty_info") or {}
    now = shanghai_now()

    if existing:
        existing.title = item.get("item_name") or item.get("title") or item.get("name") or existing.title
        existing.card_type = item.get("card_type", existing.card_type)
        existing.total_stock = item.get("total_stock", existing.total_stock)
        existing.sku_count = item.get("sku_count", existing.sku_count)
        existing.first_sku_id = item.get("first_sku_id") or existing.first_sku_id
        existing.sale_qty30 = sale_info.get("sale_qty30", existing.sale_qty30)
        existing.acc_sale_qty = sale_info.get("acc_sale_qty", existing.acc_sale_qty)
        existing.check_status = item.get("check_status", existing.check_status)
        existing.cover_url = cover_url or existing.cover_url
        existing.price_min = price_min if price_min is not None else existing.price_min
        existing.price_max = price_max if price_max is not None else existing.price_max
        existing.is_auto_off_shelf = item.get("is_auto_off_shelf", existing.is_auto_off_shelf)
        existing.raw_json = item
        existing.synced_at = now
        existing.updated_at = now
        return existing

    p = ArkProduct(
        user_id=user_id,
        server_config_id=config_id,
        item_id=item_id,
        title=item.get("item_name") or item.get("title") or item.get("name") or "",
        card_type=item.get("card_type", 2),
        total_stock=item.get("total_stock", 0),
        sku_count=item.get("sku_count", 0),
        first_sku_id=item.get("first_sku_id"),
        sale_qty30=sale_info.get("sale_qty30", 0),
        acc_sale_qty=sale_info.get("acc_sale_qty", 0),
        check_status=item.get("check_status", 1),
        cover_url=cover_url,
        price_min=price_min,
        price_max=price_max,
        is_auto_off_shelf=item.get("is_auto_off_shelf", False),
        raw_json=item,
        synced_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(p)
    return p


def _upsert_skus(db: Session, user_id: int, product_id: int, item_id: str, sku_list: list) -> None:
    """将 skuList 写入 ark_product_skus 表"""
    now = shanghai_now()
    for sku in sku_list:
        sku_id = sku.get("skuId") or ""
        if not sku_id:
            continue
        variants = sku.get("skuVariantInfos") or []
        query_type = variants[0].get("variantValue") if variants else None
        price_info = sku.get("basePriceInfo") or {}
        stock_infos = sku.get("baseStockInfos") or []
        delivery = sku.get("deliveryTime") or {}
        spec_img = sku.get("specImage") or {}

        existing = db.scalars(
            select(ArkProductSku).where(
                ArkProductSku.product_id == product_id,
                ArkProductSku.sku_id == sku_id,
            )
        ).first()

        if existing:
            existing.sku_name = sku.get("skuName") or existing.sku_name
            existing.query_type = query_type
            existing.price = price_info.get("price")
            existing.stock = stock_infos[0].get("stock") if stock_infos else None
            existing.delivery_time = str(delivery.get("time") or "")
            existing.delivery_type = delivery.get("type")
            existing.spec_image = spec_img.get("link") or spec_img.get("path") or ""
            existing.barcode = sku.get("barcode")
            existing.synced_at = now
            existing.updated_at = now
        else:
            db.add(ArkProductSku(
                user_id=user_id,
                product_id=product_id,
                item_id=item_id,
                sku_id=sku_id,
                sku_name=sku.get("skuName") or "",
                query_type=query_type,
                service_id=sku_id,
                price=price_info.get("price"),
                stock=stock_infos[0].get("stock") if stock_infos else None,
                delivery_time=str(delivery.get("time") or ""),
                delivery_type=delivery.get("type"),
                spec_image=spec_img.get("link") or spec_img.get("path") or "",
                barcode=sku.get("barcode"),
                synced_at=now,
                created_at=now,
                updated_at=now,
            ))


# ── server configs ────────────────────────────────────────────────────────────

class ServerConfigPayload(BaseModel):
    server_id: str
    seller_name: str = ""
    cookie_file: str = ""
    profile_dir: str = ""
    enabled: bool = True


@router.post("/servers/import-ark")
def import_ark_config(
    server_id: str = Body(..., embed=True),
    cookie_file: str = Body(default="", embed=True),
    profile_dir: str = Body(default="", embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = Path(__file__).resolve().parent.parent.parent.parent
    if not cookie_file:
        cookie_file = str(base / "data" / "ark_cookies.json")
    if not profile_dir:
        profile_dir = str(base / "data" / "ark_profile")

    seller_name = server_id
    seller_id = ""
    # 首次添加时尝试获取店铺名（需要 ark 浏览器开着）
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        success, _, res = ArkAPI(cookie_file=cookie_file).get_seller_info_v2()
        if success and res:
            d = res.get("data") or {}
            seller_name = d.get("user_name") or d.get("seller_name") or server_id
            seller_id = str(d.get("seller_id") or d.get("id") or "")
    except Exception:
        pass

    existing = db.scalars(
        select(ArkServerConfig).where(
            ArkServerConfig.user_id == current_user.id,
            ArkServerConfig.server_id == server_id,
        )
    ).first()

    if existing:
        existing.cookie_file = cookie_file
        existing.profile_dir = profile_dir
        if seller_name:
            existing.seller_name = seller_name
        if seller_id:
            existing.seller_id = seller_id
        existing.enabled = True
        db.commit()
        db.refresh(existing)
        return {**_serialize_config(existing), "action": "updated"}

    cfg = ArkServerConfig(
        user_id=current_user.id,
        server_id=server_id,
        seller_id=seller_id,
        seller_name=seller_name or server_id,
        cookie_file=cookie_file,
        profile_dir=profile_dir,
        enabled=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {**_serialize_config(cfg), "action": "created"}


@router.get("/servers")
def list_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(ArkServerConfig)
        .where(ArkServerConfig.user_id == current_user.id)
        .order_by(ArkServerConfig.created_at.desc())
    ).all()
    return {"items": [_serialize_config(c) for c in items]}


@router.delete("/servers/{config_id}")
def delete_server(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_config(db, current_user.id, config_id)
    db.delete(cfg)
    db.commit()
    return {"id": config_id, "status": "deleted"}


@router.post("/servers/{config_id}/refresh-name")
def refresh_server_name(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_config(db, current_user.id, config_id)
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        success, _, res = ArkAPI(cookie_file=cfg.cookie_file or "").get_seller_info_v2()
        if success and res:
            d = res.get("data") or {}
            seller_name = d.get("user_name") or d.get("seller_name") or ""
            seller_id = str(d.get("seller_id") or d.get("id") or "")
            if seller_name:
                cfg.seller_name = seller_name
            if seller_id:
                cfg.seller_id = seller_id
            db.commit()
            db.refresh(cfg)
    except Exception:
        pass
    return _serialize_config(cfg)


# ── sync products ─────────────────────────────────────────────────────────────

async def _sync_skus_with_playwright(
    db: Session, user_id: int, products: list[tuple[int, str]], errors: list,
    cookie_file: str = "",
) -> int:
    """用 Playwright headless 调 publish_render 同步 SKU"""
    import json as _json
    import asyncio as _asyncio
    import tempfile as _tempfile
    from pathlib import Path as _Path
    from playwright.async_api import async_playwright
    from backend.app.models.ark import ArkProduct as _ArkProduct

    COOKIE_FILE = _Path(cookie_file) if cookie_file else _Path(__file__).resolve().parent.parent.parent.parent / "data" / "ark_cookies.json"

    synced = 0
    with _tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                tmp_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            if COOKIE_FILE.exists():
                try:
                    data = _json.loads(COOKIE_FILE.read_text("utf-8"))
                    pw_cookies = data.get("playwright_cookies") or []
                    if pw_cookies:
                        await context.add_cookies(pw_cookies)
                except Exception:
                    pass

            page = context.pages[0] if context.pages else await context.new_page()
            try:
                # 先去列表页建立会话，否则 publish_render 返回 code=-1
                await page.goto("https://ark.xiaohongshu.com/app-item/list/shelf", wait_until="networkidle", timeout=45000)
                if "login" in page.url:
                    errors.append("ark 未登录，请先运行 ark_capture.py 完成登录")
                    await context.close()
                    return 0
                await _asyncio.sleep(1)
            except Exception as _e:
                errors.append(f"Playwright 打开 ark 页面失败: {_e}")
                await context.close()
                return 0

            for product_id, item_id in products:
                try:
                    res = {}
                    async with page.expect_response(
                        lambda r: "publish_render" in r.url, timeout=30000
                    ) as resp_info:
                        await page.goto(
                            f"https://ark.xiaohongshu.com/app-item/good/edit/{item_id}",
                            wait_until="domcontentloaded", timeout=45000,
                        )
                    try:
                        resp_val = await resp_info.value
                        res = await resp_val.json()
                    except Exception as _e:
                        errors.append(f"item_id={item_id}: 拦截响应失败: {_e}")
                        continue
                    if res.get("code") not in (0, 200) or not res.get("success"):
                        errors.append(f"item_id={item_id}: publish_render code={res.get('code')} msg={res.get('msg','')}")
                        continue
                    extras = _extract_render_extras(res)
                    if not extras["_sku_list"]:
                        errors.append(f"item_id={item_id}: skuList 为空")
                        continue
                    p = db.get(_ArkProduct, product_id)
                    if p:
                        merged = dict(p.raw_json or {})
                        merged.update(extras)
                        p.raw_json = merged
                    _upsert_skus(db, user_id, product_id, item_id, extras["_sku_list"])
                    db.commit()
                    synced += 1
                    await _asyncio.sleep(0.3)
                except Exception as _e:
                    errors.append(f"item_id={item_id}: {_e}")

            await context.close()
    return synced


class SyncPayload(BaseModel):
    card_types: list[int] = [2, 3, 4, 5, 6, 10]


@router.post("/servers/{config_id}/sync")
def sync_products(
    config_id: int,
    payload: SyncPayload = Body(default=SyncPayload()),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_config(db, current_user.id, config_id)

    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        api = ArkAPI(cookie_file=cfg.cookie_file or "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ArkAPI 初始化失败: {e}")

    synced = 0
    errors = []
    product_ids_to_sync_sku: list[tuple[int, str]] = []  # (product_id, item_id)

    for card_type in payload.card_types:
        page_no = 1
        while True:
            try:
                success, msg, res = api.search_items(
                    page_no=page_no, page_size=50, card_type=card_type
                )
            except Exception as e:
                errors.append(f"card_type={card_type} page={page_no}: {e}")
                break

            if not success:
                errors.append(f"card_type={card_type}: {msg}")
                break

            data = (res or {}).get("data") or {}
            items = data.get("items") or []
            total = data.get("total", 0)

            for item in items:
                item["card_type"] = card_type
                p = _upsert_product(db, current_user.id, config_id, item)
                if p:
                    db.flush()
                    synced += 1
                    product_ids_to_sync_sku.append((p.id, p.item_id))

            if not items or page_no * 50 >= total:
                break
            page_no += 1

    cfg.last_sync_at = shanghai_now()
    db.commit()

    # 用 Playwright 在进程内同步 SKU（publish_render 需要浏览器签名）
    sku_synced = 0
    if product_ids_to_sync_sku:
        try:
            import asyncio as _asyncio
            sku_synced = _asyncio.run(
                _sync_skus_with_playwright(db, current_user.id, product_ids_to_sync_sku, errors, cfg.cookie_file or "")
            )
        except Exception as _e:
            errors.append(f"SKU同步失败: {_e}")

    return {"synced": synced, "sku_synced": sku_synced, "errors": errors, "last_sync_at": cfg.last_sync_at.isoformat()}


# ── products ──────────────────────────────────────────────────────────────────

@router.get("/products")
def list_products(
    server_config_id: Optional[int] = None,
    card_type: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(ArkProduct).where(ArkProduct.user_id == current_user.id)
    if server_config_id:
        stmt = stmt.where(ArkProduct.server_config_id == server_config_id)
    if card_type is not None:
        stmt = stmt.where(ArkProduct.card_type == card_type)
    if keyword:
        stmt = stmt.where(ArkProduct.title.ilike(f"%{keyword}%"))
    items = db.scalars(stmt.order_by(ArkProduct.updated_at.desc())).all()
    return paginated([_serialize_product(p) for p in items], page, page_size)


@router.get("/products/{product_id}/skus")
def get_product_skus(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.get(ArkProduct, product_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    # 优先从 ark_product_skus 表读
    db_skus = db.scalars(
        select(ArkProductSku).where(ArkProductSku.product_id == p.id)
        .order_by(ArkProductSku.id)
    ).all()
    if db_skus:
        skus = [
            {
                "sku_id": s.sku_id,
                "sku_name": s.sku_name,
                "query_type": s.query_type,
                "service_id": s.service_id,
                "srv": s.srv or "",
                "variants": [{"name": "款式", "value": s.query_type}] if s.query_type else [],
                "price": s.price,
                "stock": s.stock,
                "delivery_time": s.delivery_time,
                "delivery_type": s.delivery_type,
                "spec_image": s.spec_image or "",
                "barcode": s.barcode,
            }
            for s in db_skus
        ]
        raw = p.raw_json or {}
        return {
            "item_id": p.item_id,
            "skus": skus,
            "item_properties": [
                {"name": prop.get("propertyName"), "values": [v.get("value") for v in (prop.get("propertyValueList") or [])]}
                for prop in (raw.get("_item_properties") or [])
            ],
            "sale_properties": [
                {"name": sp.get("propertyName"), "values": [v.get("name") for v in (sp.get("values") or [])]}
                for sp in (raw.get("_sale_properties") or [])
            ],
        }

    # 没有则从 raw_json 或实时拉取
    sku_list = (p.raw_json or {}).get("_sku_list") or []

    # 没有则尝试实时拉取（需要 CDP）
    if not sku_list:
        cfg = db.get(ArkServerConfig, p.server_config_id)
        if cfg:
            try:
                from apis.xhs_walle_eva_apis import ArkAPI
                success, _, res = ArkAPI(cookie_file=cfg.cookie_file or "").get_item_detail(p.item_id)
                if success and res:
                    extras = _extract_render_extras(res)
                    if extras["_sku_list"]:
                        merged = dict(p.raw_json or {})
                        merged.update(extras)
                        p.raw_json = merged
                        db.commit()
                        sku_list = extras["_sku_list"]
            except Exception:
                pass

    if sku_list:
        _upsert_skus(db, current_user.id, p.id, p.item_id, sku_list)
        db.commit()

    raw = p.raw_json or {}
    skus = []
    for sku in sku_list:
        price_info = sku.get("basePriceInfo") or {}
        stock_infos = sku.get("baseStockInfos") or []
        delivery = sku.get("deliveryTime") or {}
        spec_img = sku.get("specImage") or {}
        skus.append({
            "sku_id": sku.get("skuId"),
            "sku_name": sku.get("skuName"),
            "query_type": variants[0].get("variantValue") if (variants := sku.get("skuVariantInfos") or []) else None,
            "service_id": sku.get("skuId") or "",
            "variants": [
                {"name": v.get("variantName"), "value": v.get("variantValue")}
                for v in (sku.get("skuVariantInfos") or [])
            ],
            "price": price_info.get("price"),
            "stock": stock_infos[0].get("stock") if stock_infos else None,
            "delivery_time": delivery.get("time"),
            "delivery_type": delivery.get("type"),
            "spec_image": spec_img.get("link") or spec_img.get("path") or "",
            "barcode": sku.get("barcode"),
        })

    # 商品属性（是否带框、题材等）
    item_properties = [
        {
            "name": prop.get("propertyName"),
            "values": [v.get("value") for v in (prop.get("propertyValueList") or [])],
        }
        for prop in (raw.get("_item_properties") or [])
    ]

    # 规格维度定义（款式可选值列表）
    sale_properties = [
        {
            "name": sp.get("propertyName"),
            "values": [v.get("name") for v in (sp.get("values") or [])],
        }
        for sp in (raw.get("_sale_properties") or [])
    ]

    return {
        "item_id": p.item_id,
        "skus": skus,
        "item_properties": item_properties,
        "sale_properties": sale_properties,
    }


@router.get("/products/{product_id}/debug-raw")
def debug_product_raw(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """调试用：返回 publish_render 原始响应，用于排查 SKU 数据结构"""
    p = db.get(ArkProduct, product_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    cfg = db.get(ArkServerConfig, p.server_config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    try:
        from apis.xhs_walle_eva_apis import ArkAPI
        success, msg, res = ArkAPI(cookie_file=cfg.cookie_file or "").get_item_detail(p.item_id)
        return {"success": success, "msg": msg, "item_id": p.item_id, "raw": res, "skus_extracted": _extract_sku_list(res) if res else []}
    except Exception as e:
        return {"success": False, "msg": str(e), "item_id": p.item_id, "raw": None}


class SkuPatchPayload(BaseModel):
    query_type: Optional[str] = None
    service_id: Optional[str] = None
    srv: Optional[str] = None


@router.patch("/products/{product_id}/skus/{sku_id}")
def patch_sku(
    product_id: int,
    sku_id: str,
    payload: SkuPatchPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.get(ArkProduct, product_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    sku = db.scalars(
        select(ArkProductSku).where(
            ArkProductSku.product_id == product_id,
            ArkProductSku.sku_id == sku_id,
        )
    ).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    if payload.query_type is not None:
        sku.query_type = payload.query_type
    if payload.service_id is not None:
        sku.service_id = payload.service_id
    if payload.srv is not None:
        sku.srv = payload.srv
    sku.updated_at = shanghai_now()
    db.commit()
    return {"sku_id": sku.sku_id, "query_type": sku.query_type, "service_id": sku.service_id, "srv": sku.srv}


@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.get(ArkProduct, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    # 兼容 user_id 直接匹配，或通过 server_config 归属当前用户
    cfg = db.get(ArkServerConfig, p.server_config_id)
    if p.user_id != current_user.id and (not cfg or cfg.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="Not found")
    # 级联删除关联 SKU
    db.scalars(select(ArkProductSku).where(ArkProductSku.product_id == p.id)).all()
    for sku in db.scalars(select(ArkProductSku).where(ArkProductSku.product_id == p.id)).all():
        db.delete(sku)
    db.delete(p)
    db.commit()
    return {"id": product_id, "status": "deleted"}
