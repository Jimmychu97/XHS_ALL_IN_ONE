# Ark (千帆) API 开发日志

## 基础信息

- **域名**: `ark.xiaohongshu.com`
- **Auth Header**: `authorization: AT-xxx`（从 `data/ark_cookies.json` 读取）
- **签名 Headers**: `x-s`, `x-t`, `x-s-common`（由页面自身 JS 签名，通过 CDP 注入）
- **测试店铺**: 深度验机的店，seller_id: `69abc6f2926da3001597f7a2`

---

## 商品管理页面接口（商品管理 → 在售/仓库中/已售罄等）

### POST `/api/edith/product/search_item_v2`
主商品列表查询，支持分页、筛选、排序。

**Request Body:**
```json
{
  "page_no": 1,
  "page_size": 20,
  "search_order": {
    "sort_field": "create_time",
    "order": "desc"
  },
  "search_filter": {
    "card_type": 2,
    "is_channel": false
  },
  "search_item_detail_option": {
    "with_product_quality_score": true,
    "with_hot_item_award_text_info": true,
    "with_ai_publish_note_permission": true,
    "with_inventory_risk_info": true,
    "with_item_lock_info": true
  }
}
```

**`card_type` 枚举:**
| 值 | 含义 |
|---|---|
| `2` | 在售 |
| `3` | 仓库中 |
| `4` | 已售罄 |
| `5` | 审核中 |
| `6` | 已下架 |
| `10` | 违规下架 |

**Response 关键字段（`data.items[]`）:**
- `item_id` — 商品 ID
- `title` — 商品标题
- `price` — 价格范围（min/max）
- `total_stock` — 总库存
- `sales_30d` — 近 30 天销量
- `total_sales` — 累计销量
- `sku_list` — SKU 列表

---

### POST `/api/edith/product/seller_item_count`
各状态商品数量统计。

**Request Body:** `{}`

**Response:** 各 `card_type` 对应的商品数量。

---

### POST `/api/edith/product/get_common_config`
商品功能开关配置（feature flags）。

**Request Body:** `{}`

---

### POST `/api/edith/product/check_freeze`
检查店铺是否被冻结。

**Request Body:** `{}`

---

### POST `/api/edith/product/get_logistics_info`
物流方案列表。

**Request Body:** `null`

---

### POST `/api/edith/product/get_delivery_time_rule`
发货时效规则。

**Request Body:**
```json
{"paramList": [{}]}
```

---

### GET `/api/edith/product/seller_property_hosting_status`
属性托管状态，无参数。

---

### GET `/api/edith/product/stock/getout_of_inventory_item?channel=false`
缺货商品列表。

---

### POST `/api/edith/product/get_item_list_resource_card`
列表资源卡片（商品列表页附加卡片信息）。

**Request Body:**
```json
{"source": 1}
```

---

## 商品编辑/规格详情接口

### POST `/api/edith/product/publish_render`
商品编辑页核心接口，返回完整商品信息（规格、SKU、属性、物流等）。

**Request Body:**
```json
{
  "data": "{\"publishType\":2,\"sourceType\":1,\"itemId\":\"69be73d315bd7400015f6592\"}"
}
```
注意：`data` 字段是 JSON 字符串（二次序列化）。

**Response 关键字段：**

`data.product.productDetail.skuList[]` — SKU 列表：
- `skuId` — SKU ID
- `skuName` — SKU 名称
- `skuVariantInfos[]` — 规格维度，含 `variantName`（如「款式」）和 `variantValue`（如「全面验机查询」）
- `basePriceInfo.price` — 价格（分）
- `baseStockInfos[].stock` — 库存数量
- `deliveryTime.time` / `deliveryTime.type` — 发货时效
- `specImage` — 规格图片
- `barcode` — 条形码

`data.category.categoryPropertyInfo.saleProperties[]` — 销售属性定义（规格维度）：
- `propertyId`、`propertyName` — 属性 ID 和名称
- `values[]` — 可选值列表（`name` + `valueId`）

`data.product.productDetail.item.properties[]` — 商品属性（年份、是否带盒等）：
- `propertyId`、`propertyName`、`propertyValueList[]`

`data.category.categoryPropertyInfo.descProperties[]` — 描述属性（非销售规格）

---

## ArkAPI 封装方法速查

| 方法 | 接口 | 说明 |
|---|---|---|
| `get_seller_info_v2()` | GET `/api/edith/seller/info/v2` | 卖家信息 |
| `get_seller_info()` | GET `/api/edith/seller/get_seller_info` | 店铺类型枚举 |
| `get_shop_score()` | POST `/api/edith/home/get_shop_score` | 店铺评分 |
| `get_todolist()` | GET `/edith/api/seller/todolist` | 待发货/待售后数量 |
| `get_key_metric_realtime()` | POST `/edith/api/seller/home/key_metric_realtime` | 实时 GMV/点击/加购 |
| `search_items(card_type, ...)` | POST `/api/edith/product/search_item_v2` | 商品列表 |
| `get_item_count()` | POST `/api/edith/product/seller_item_count` | 各状态商品数量 |
| `get_item_detail(item_id)` | POST `/api/edith/product/publish_render` | 商品完整规格/SKU详情（价格、库存、发货时效、属性） |
| `get_common_config()` | POST `/api/edith/product/get_common_config` | 功能开关配置 |
| `get_logistics_info()` | POST `/api/edith/product/get_logistics_info` | 物流方案列表 |
| `get_delivery_time_rule()` | POST `/api/edith/product/get_delivery_time_rule` | 发货时效规则 |
| `check_freeze()` | POST `/api/edith/product/check_freeze` | 店铺是否被冻结 |
| `get_out_of_inventory_items()` | GET `/api/edith/product/stock/getout_of_inventory_item` | 缺货商品列表 |
| `get_inventory_gray_config()` | GET `/api/edith/inventory/gray_config` | 库存灰度配置 |
| `get_seller_property_hosting_status()` | GET `/api/edith/product/seller_property_hosting_status` | 属性托管状态 |
| `get_item_list_resource_card()` | POST `/api/edith/product/get_item_list_resource_card` | 列表资源卡片 |
| `get_unread_count()` | GET `/api/edith/open/message/v2/unread-count` | 未读消息数 |
| `get_important_msgs()` | GET `/api/edith/open/message/v2/important-msgs` | 重要消息列表 |
| `get_latest_group_msgs()` | POST `/api/edith/open/message/latest_group_mgs` | 最新分组消息 |

---

## 捕获方式

通过 `ark_capture.py`（Playwright CDP）在浏览器中拦截网络请求，日志保存至 `data/logs/ark_YYYYMMDD_HHMMSS.jsonl`。

```bash
python ark_capture.py
# 手动导航到目标页面，Ctrl+C 退出后 cookies 自动保存
```

已封装到 `ArkAPI`（`apis/xhs_walle_eva_apis.py`），通过 CDP 让页面自身发签名请求，无需手动维护签名。
