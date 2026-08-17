# XHS_ALL_IN_ONE — Dev Notes（每次开发前必读）

---

## ⚠️ 强制规则：新增函数/方法必须更新本文件

**每次完成以下任意一项，必须立即将新增内容追加到「关键函数速查」对应章节：**

1. 在 `backend/` 任意 service / core / api 文件里新增公共函数或方法
2. 在 `frontend/src/lib/api.ts` 里新增导出函数
3. 在 `apis/` 里新增 SDK 方法
4. 新增数据库表或字段（同步更新「所有表」列表和「已知历史坑」）
5. 修改已有函数签名或行为

**格式要求：**
```
### 模块名 — 文件路径
函数名(参数)   # 一句话说明用途
```

**不更新 = 下次开发重复造轮子，自己负责。**

---

## 数据库

- **默认引擎**: SQLite，文件路径 `f:\XHS_ALL_IN_ONE\data\spider_xhs.db`
- **生产环境**: MySQL，通过 `DATABASE_TYPE=mysql` + `DATABASE_URL` 切换
- **迁移工具**: Alembic，迁移文件在 `backend/alembic/versions/`
- **注意**: 直接改模型字段后，SQLite 不会自动 ALTER TABLE，需要手动执行 SQL 或写 Alembic migration

### 已知历史坑
- `ark_products` 表旧版字段是 `server_config_id`，新版模型改为 `account_id`，已手动执行：
  ```sql
  ALTER TABLE ark_products ADD COLUMN account_id INTEGER REFERENCES platform_accounts(id);
  UPDATE ark_products SET account_id = server_config_id;
  ```
- 每次新增模型字段后，如果不跑 Alembic，需要手动 ALTER TABLE
- `walle_shop_configs` 新增列在 `database.py` 的 `_add_walle_shop_config_columns()` 里用 `ALTER TABLE` 补加，不走 Alembic

### 查看表结构
```python
import sqlite3
conn = sqlite3.connect('data/spider_xhs.db')
print([r[1] for r in conn.execute('PRAGMA table_info(表名)').fetchall()])
conn.close()
```

### 所有表（25张）
`users` / `login_sessions` / `platform_accounts` / `account_cookie_versions` /
`notes` / `note_assets` / `note_comments` / `tags` / `note_tags` / `keyword_groups` /
`ai_drafts` / `draft_assets` / `ai_generated_assets` / `model_configs` /
`publish_jobs` / `publish_assets` / `auto_tasks` /
`monitoring_targets` / `monitoring_snapshots` /
`walle_conversations` / `walle_messages` / `walle_knowledge` / `walle_keywords` / `walle_orders` / `walle_shop_configs` / `walle_agent_sessions` /
`ark_server_configs` / `ark_products` / `ark_product_skus` /
`tasks` / `notifications` / `api_logs` / `app_migrations` / `alembic_version`

---

## Token / Cookie 机制

## 稳定性加固（2026-08-16 实施）

1. **进程守护**（`main.py _Supervisor`）：cookie_watcher / ark_capture 异常退出自动重启
   （指数退避 5s→60s），停止时不再拉起；uvicorn 退出时统一 terminate。
2. **backend_token 自愈**（`backend/app/main.py _start_token_self_heal`）：后端启动即检查
   `F:\eva\backend_token.txt`，临期(<3天)/无效自动重签，不依赖用户打开页面。
3. **心跳凭证检查**（`heartbeat_scheduler.check_aux_credentials`）：每小时检查
   backend_token / eva_cookies / edith_auth / ark_cookies 新鲜度，异常写入 `notifications` 表（1小时去重）。
4. **数据库每日备份**：`data/backup/spider_xhs_YYYYMMDD_HHMMSS.db`，保留 7 天。
5. **日志轮转**：uvicorn/后端 logging 镜像到 `data/logs/backend.log`（按天轮转，保留 14 天）。
6. **Ark daemon 会话校验**（`ark_capture.py _check_session_valid`）：每次刷新后页面内
   fetch `seller/info/v2` 校验 code=0，失效打印告警提示人工登录。

### Token / Cookie 机制

#### ⚠️ backend_token.txt 过期问题（2026-08-16 已修复）
- `F:\eva\backend_token.txt` 存的是平台 refresh_token（**7 天有效**），cookie_watcher 用它换 access_token 推送消息。
- **过期症状**：cookie_watcher 日志 `刷新 access_token 失败: HTTP Error 401: Unauthorized` + `push_message 跳过: 无 access_token`。
- **修复**：`POST /api/walle/accounts/save-token`（后端签发新 refresh_token 写文件）；
  前端 walle 账号管理页 `load()` 已加 `saveWalleBackendToken()` 自动续期（页面每次加载刷新 token，防止 7 天后复发）。
- **手动应急**：`python -c "import sys; sys.path.insert(0,r'F:\XHS_ALL_IN_ONE'); from backend.app.core.security import create_refresh_token; import pathlib; pathlib.Path(r'F:/eva/backend_token.txt').write_text(create_refresh_token(1), encoding='utf-8')"`

### 平台 JWT（用户登录 XHS_ALL_IN_ONE 平台）
- 登录后返回 `access_token`（15分钟）+ `refresh_token`（7天）
- `access_token` 存在前端内存变量 `accessToken`（`frontend/src/lib/api.ts`），**页面刷新后丢失**
- `refresh_token` 存在 `localStorage`，key = `spider_xhs_refresh_token`
- `cookie_watcher.py` 把 refresh_token 持久化到 `F:\eva\backend_token.txt`
- 所有后端 API 路由通过 `Depends(get_current_user)` 校验 JWT

### 获取 access_token（脚本调试用）
```python
import requests
refresh_token = open('F:/eva/backend_token.txt').read().strip()
r = requests.post('http://127.0.0.1:8000/api/auth/refresh', json={'refresh_token': refresh_token})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
```

### XHS 账号 Cookie 存储
- 所有 XHS 账号 cookie 用 **Fernet 对称加密**存储在 `account_cookie_versions` 表
- `platform_accounts.sub_type` 枚举：
  - `pc` — 小红书 PC 端
  - `creator` — 创作者平台
  - `qianfan` — 千帆分销平台
  - `walle` — 千帆客服工作台（cookie 存的是 eva_cookies.json 内容）
  - `ark` — 千帆卖家后台（cookie 存的是 ark_cookies.json **文件路径**）

### Walle / Ark 凭证文件
| 文件 | 内容 |
|---|---|
| `F:\eva\eva_cookies.json` | walle 接口凭证（AT-xxx token） |
| `F:\eva\edith_auth.json` | edith 接口凭证（a1:xxx token） |
| `F:\eva\backend_token.txt` | 平台 refresh_token（cookie_watcher.py 写入） |
| `data/ark_cookies.json` | ark playwright_cookies（ark_capture.py Ctrl+C 退出才保存） |
| `data/ark_profile/` | Playwright 持久化浏览器 profile（保留登录态） |

---

## 关键函数速查（不要重复造轮子）

### 安全 / 加解密 — `backend/app/core/security.py`
```python
from backend.app.core.security import encrypt_text, decrypt_text, hash_password, verify_password, create_access_token, create_refresh_token, decode_token

encrypt_text(raw_str)          # Fernet 加密，存 cookie/api_key 用
decrypt_text(encrypted_str)    # Fernet 解密
hash_password(password)        # pbkdf2_sha256 哈希
verify_password(pwd, hash)     # 验证密码
create_access_token(user_id)   # 生成 15min JWT
create_refresh_token(user_id)  # 生成 7day JWT
decode_token(token)            # 解码并验证 JWT，返回 payload dict
```

### 时间 — `backend/app/core/time.py`
```python
from backend.app.core.time import shanghai_now
now = shanghai_now()  # 返回上海时区的 naive datetime，所有模型时间字段都用这个
```

### 数据库 Session — `backend/app/core/database.py`
```python
# FastAPI 路由里用依赖注入
from backend.app.core.database import get_db
db: Session = Depends(get_db)

# 后台任务 / scheduler / 线程里手动管理
from backend.app.core.database import SessionLocal
db = SessionLocal()
try:
    ...
    db.commit()
finally:
    db.close()
```

### 当前用户 — `backend/app/core/deps.py`
```python
from backend.app.core.deps import get_current_user
current_user: User = Depends(get_current_user)
# 所有需要鉴权的路由都加这个依赖
```

### 分页响应 — `backend/app/schemas/common.py`
```python
from backend.app.schemas.common import paginated
return paginated([{...} for item in items], page, page_size)
# 返回 {"total": N, "page": P, "page_size": S, "items": [...]}
```

### 账号服务 — `backend/app/services/account_service.py`
```python
from backend.app.services.account_service import (
    upsert_platform_account_from_login,  # 创建或更新 platform_account + cookie_version
    serialize_account,                    # PlatformAccount → dict（含 profile）
    decode_cookie_text,                   # cookie 字符串/JSON → dict
    cookie_header_from_text,              # cookie 字符串/JSON → "k=v; k=v" header 格式
    enrich_user_info_with_xhs_self_profile,  # 用 XHS 自身接口补全 user_info
    account_profile_from_user_info,       # 从 user_info 提取 profile dict
)

# 绑定账号标准写法
account, action = upsert_platform_account_from_login(
    db=db, user_id=current_user.id, platform="xhs",
    sub_type="pc", user_info=user_info, cookies_text=cookie_string,
)
db.commit()
return serialize_account(account, action)
```

### 通知服务 — `backend/app/services/notification_service.py`
```python
from backend.app.services.notification_service import (
    notify_task_failed,       # 任务失败通知
    notify_task_exhausted,    # 任务重试耗尽通知
    notify_account_expired,   # 账号过期通知
    notify_publish_failed,    # 发布失败通知
    notify_target_paused,     # 监控暂停通知
)
notify_account_expired(db, user_id=1, account_name="xxx", account_id=1)
```

### AI 服务 — `backend/app/services/ai_service.py`
```python
from backend.app.services.ai_service import OpenAICompatibleTextClient, OpenAICompatibleImageClient

text_client = OpenAICompatibleTextClient()
text_client.rewrite_note(model_config=cfg, api_key=key, title=t, body=b, instruction=i)
text_client.generate_note(model_config=cfg, api_key=key, topic=t, reference=r, instruction=i)
text_client.generate_titles(model_config=cfg, api_key=key, title=t, body=b, count=5)
text_client.generate_tags(model_config=cfg, api_key=key, title=t, body=b, count=10)
text_client.polish_text(model_config=cfg, api_key=key, text=t, instruction=i)

img_client = OpenAICompatibleImageClient()
img_client.generate_image(model_config=cfg, api_key=key, prompt=p, reference_images=[url])
img_client.describe_image(model_config=cfg, api_key=key, image_url=url, instruction=i)
```

### XHS SDK 调用 — `apis/`（通过 adapters 层调用，不直接在路由里 import）
```python
# 正确方式：通过 adapters
from backend.app.adapters.xhs.pc_api_adapter import XhsPcApiAdapter
from backend.app.adapters.xhs.pc_login_adapter import XhsPcLoginAdapter
from backend.app.adapters.xhs.creator_login_adapter import XhsCreatorLoginAdapter

# Ark / Walle SDK（直接调用，无 adapter 层）
from apis.xhs_walle_eva_apis import ArkAPI, WalleEvaAPI
api = ArkAPI(cookie_file="data/ark_cookies.json")  # cookie_file 空字符串时自动 fallback
success, msg, res = api.search_items(card_type=2, page_no=1, page_size=50)
```

### 前端 HTTP 客户端 — `frontend/src/lib/api.ts`
```typescript
import { http } from '../lib/api'           // axios 实例，自动带 JWT header
import { fetchAccounts, getAccessToken } from '../lib/api'

// 所有 API 调用走 http，不要直接用 fetch（除非 SSE）
const res = await http.get('/ark/products', { params: { account_id: 1 } })

// SSE 需要用 fetch 并手动带 token
const token = getAccessToken()
const resp = await fetch('/api/walle/logs/stream?token=' + token)
```

---

## 账号 sub_type 与商品管理（已改动）

- `walle-page.tsx` 里「商品管理」tab：`<ProductsTab acceptSubTypes={["ark", "walle"]} />`
- 后端 `ark.py` 的 `_get_ark_account`：接受 `sub_type in ("ark", "walle")`
- `_cookie_file_for`：walle 账号返回 `""`，`ArkAPI` 自动 fallback 到 `data/ark_cookies.json`
- **账号矩阵只保留 PC 账号**，Creator/千帆/千帆客服/千帆卖家各自独立管理

---

## Ark 千帆卖家后台 — `backend/app/api/ark.py`
```
GET  /ark/servers                        # 列出所有 ArkServerConfig
POST /ark/servers/import-ark             # 添加/更新账号，自动尝试获取真实店铺名
DELETE /ark/servers/{config_id}          # 删除账号
POST /ark/servers/{config_id}/refresh-name  # 重新调 get_seller_info_v2() 更新店铺名（页面加载时自动调）
POST /ark/servers/{config_id}/sync       # 同步商品，body: {card_types: [2,3,4,5,6,10]}
                                         # 内部直接调 _sync_skus_with_playwright（不再启子进程）
GET  /ark/products                       # 商品列表，支持 server_config_id/card_type/keyword 筛选
GET  /ark/products/{product_id}/skus     # 商品 SKU 规格明细，优先读 ark_product_skus 表，返回 query_type/service_id
DELETE /ark/products/{product_id}        # 删除商品
```
- `_upsert_skus(db, user_id, product_id, item_id, sku_list)` — 将 skuList 写入 ark_product_skus 表（upsert）

### Ark 订单查询 / 无物流发货（2026-08-16 已抓包确认）
```
POST /api/edith/fulfillment/order/page             # 订单列表（ArkAPI.get_orders / get_orders_by_user）
POST /api/edith/fulfillment/order_delivering_api   # 无物流发货（ArkAPI.ship_no_logistics）
     body: {delivery_package_id, package_id, delivery_group:false,
            express_company_code:"selfdelivery", express_no, plan_info_id?}
POST /api/edith/fulfillment/pre_check_before_delivery  # 发货预检（浏览器会带 check_scene 参数）
POST /api/edith/fulfillment/delivery/tab/route         # 发货方式 tab（body: {order_id}）
POST /api/edith/package/logistics/companies            # 物流公司列表（body: {send_from:"001", package_id_list:[...], plan_info_id}）
```
- ⚠️ 原 `ship_no_logistics` 用的 `/fulfillment/delivery/no_logistics` 是**错误路径**（返回非 JSON），
  真实提交接口是 `/fulfillment/order_delivering_api`（2026-08-16 真实抓包确认，code 0）
- 订单状态枚举：`[4,5]=待配货/待发货 [6]=已发货 [7]=已完成 [998]=已取消`（Agent 工具 tools.py 同款映射）
- `_sync_skus_with_playwright(db, user_id, products, errors, cookie_file="")` — 异步，Playwright headless 同步 SKU，**必须看下方说明**
- `_parse_render_data(res)` — publish_render 响应的 data 字段是 JSON 字符串，统一解析为 dict
- `_extract_render_extras(res)` — 一次性提取 _sku_list + _item_properties + _sale_properties
- `ark_product_skus` 表字段：`query_type`（查询类型，款式 variantValue）、`service_id`（服务ID，同 sku_id）

### ⚠️ SKU 同步关键机制（_sync_skus_with_playwright）

`publish_render` 接口**必须**在商品列表页会话上下文下才能返回 `code=200`，否则永远返回 `code=-1`。

**正确流程（缺一不可）：**
1. 用**临时 profile**（`tempfile.TemporaryDirectory`）启动 Playwright headless，避免和 daemon 的持久化 profile 冲突
2. 注入 `ark_cookies.json` 里的 `playwright_cookies`
3. **先 goto `https://ark.xiaohongshu.com/app-item/list/shelf`** 建立会话
4. 对每个商品 goto `https://ark.xiaohongshu.com/app-item/good/edit/{item_id}`（路径参数，不是 query string）
5. 用 `page.expect_response(lambda r: "publish_render" in r.url)` 拦截页面自动触发的响应

**已踩坑：**
- `page.evaluate` 里手动 fetch publish_render → `code=-1`（绕过了页面拦截器）
- XHR 方式同样 `code=-1`
- 直接 goto 编辑页但没有先去列表页 → `code=-1`
- 编辑页 URL 是 `/app-item/good/edit/{item_id}`（路径参数），不是 `/app-system/product/edit?itemId=`
- 用持久化 profile → 和 daemon 冲突报 `TargetClosedError`

## Walle 千帆客服 新增接口 — `backend/app/api/walle.py`
```
POST /walle/accounts/auto-import   # 静默自动导入：优先 CDP 9222，fallback eva_cookies.json
                                   # 返回 {ok: bool, reason?: 'no_cookie', login_url?: str}
```
- `walle-accounts.tsx` 页面加载时自动调 `auto-import`，无需手动点「导入凭证」
- 凭证缺失时显示黄色提示 + 「打开工作台」按钮（`window.open('https://walle.xiaohongshu.com')`）

### ⚠️ Walle 已知坑与修复（2026-08-16）

1. **Agent 400 崩溃（必现）**：`agent_loop.py _load_history` 原来只要求 tool 消息"前一条是 assistant"，
   当 LLM 一次并行返回多个 tool_calls（如 search_knowledge + check_order_status）时，
   第 2 个及以后的 tool 响应被误跳过 → 历史出现孤立 tool_calls →
   DeepSeek 400 "An assistant message with 'tool_calls' must be followed by tool messages"。
   **已修复**：用 `pending_call_ids` 窗口按 `tool_call_id` 匹配；tool 消息 content 保持字符串不做 JSON 解析。
2. **买家 userId 提取错误**：appCid 尾部 20 字符是 **base64**（且是店铺 id 尾段），不是买家 id；
   `walle_conversations.customer_id` 历史数据存的也是错的。
   **已修复**：`_extract_buyer_id_from_app_cid` base64 解码 appCid 第一段（`$3$` 去掉后 split('.')[0]），
   取 24 位十六进制 userId（如 `5f40d80e0000000001002f01`）。
3. **订单检查链路统一走 ArkAPI**：`_check_order_status` / `_fetch_buyer_orders` 原走
   edith `get_buyer_packages`（接口 404）+ CDP `get_conv_order`（不稳定），已全部改为
   `ArkAPI().get_orders_by_user(buyer_user_id)`（与 Agent 工具 check_order_status 一致）。
4. **`get_orders_by_user("")` 会查全店订单**（get_orders 里空 user_id 不加过滤）→ 错认买家。
   **已修复**：空 userId 直接返回 `(False, "缺少买家 userId", None)`。
5. **观察项**：walle_agent_sessions 历史里存在同一条 user 消息 3 次落库（重复 dispatch），
   会浪费 token，暂不影响功能。
6. **IMEI 支持空格**（2026-08-16）：`_extract_sn_imei` 的 IMEI 正则改为
   `\d(?:\s?\d){14}`（15 位数字允许中间空格，如 `35 113831 0588051`），
   `normalize_sn_imei` 先去空白再校验；SN 匹配改为 lookaround 支持中文上下文。
7. **400 并发交错根因（2026-08-16 已修复）**：买家连发两条消息 → 两个 run_agent 并发，
   落库交错成 `assistant(A)→assistant(B)→tool(B)→tool(A)`。`_load_history` 现改为
   **按 tool_call_id 归属查找所属 assistant 并插入其后方**（兼容任意交错顺序）+ 兜底清洗
   （无对应 tool 响应的 tool_calls 自动移除），彻底杜绝
   "tool_calls must be followed by tool messages" 400。

### GSX 验机查询（gsxunlocking，2026-08-16 接入）

**接口**：`GET https://www.gsxunlocking.com/api/uapi`
```
参数: format=json, key=<API密钥>, srv=<数字服务码>, imei=<序列号/IMEI>
响应: {"code":0,"flag":"ok","result":"序列号: xxx\n设备型号: ..."}   # code=0 成功（清理 HTML 标签后返回）
      {"code":1,"flag":"fail","result":"Wrong IMEI or SN"}          # code!=0 失败（result 即错误信息）
```

**关键点（踩坑）**：
- ⚠️ **srv 必须是数字服务码**（如 `1014`/`1032`）。`ark_product_skus.service_id` 默认值 = sku_id（24 位十六进制，
  传过去 API 直接 HTTP 400），**需要在「商品管理 → 规格明细」把服务ID改成数字服务码**（服务ID 列可编辑）。
- **srv 解析流程**（`tools._resolve_gsx_srv`）：
  1) 显式 srv 参数优先
  2) 买家最新订单规格 spec ↔ `ark_product_skus.query_type` 匹配 → 该 SKU 的 `service_id`
  3) 按订单 SKU 的 sku_id 精确匹配兜底
  4) 非数字服务码 → query_gsx 返回明确配置提示
- **API 密钥**：`config.json`（项目根）→ `{"gsxunlocking": {"key": "..."}}`；
  也可在 `walle_shop_configs.gsx_key` 配置（店铺级覆盖，优先级更高）。
- **苹果序列号/IMEI 规则**（`tools.normalize_sn_imei`）：IMEI = 15 位纯数字；
  序列号 = 8-14 位字母数字（大写、至少 1 个字母）。校验不通过不入库、不发请求。
- **完整流程**（`walle._handle_sn_imei`）：订单状态检查 → 苹果规则校验 →
  写入/补全 `walle_orders`（sn_imei，status=0）→ 按 spec↔query_type 取 service_id 调 gsxunlocking →
  **成功 status=1 / 失败 status=2（结果存 verify_result）** →
  **验机成功且订单待发货 → 自动无物流发货（`ship_no_logistics`，express_no=验机报告，买家可见）** →
  **回复客户（含"订单已无物流发货"）→ 写入 `walle_agent_sessions`
  （user"验机查询：SN" + assistant"验机结果..."），买家后续追问时 AI 能依据验机报告继续回答**。
- **无物流发货接口**：`POST /api/edith/fulfillment/order_delivering_api`（`ship_no_logistics`），
  express_no = 发货内容，仅对待发货订单执行；已发货/已完成自动跳过（日志 `[SHIP]`）。
  ⚠️ **express_no 上限 200 字**（报错"填写的发货内容超过200字"）：完整验机报告放聊天消息，
  发货内容取报告前 190 字 + "…"（2026-08-16 实测 945 字报告直接发会被拒）。
- **订单卡话术分流**：待发货 → `_ORDER_GUIDE`（请提供序列号/IMEI）；已发货/已完成（status=other）→
  "您的订单已发货～请问您想了解什么问题呢？"；取消/无订单 → 对应引导话术。
- **首次互动先发找序列号引导**：普通消息首次进入 Agent 前（无 walle_agent_sessions 历史时），
  先立即回复 `_SN_FIND_GUIDE`（各设备找序列号/IMEI 的方法），再做订单信息拉取 + Agent，避免客户干等；
  已有历史的后续消息不再重复发送。
- **仅待发货才调查询 API**：SN/IMEI（文字或图片识别）触达时，`_check_order_status` 返回
  pending_ship → 调 GSX 查询；已发货/已完成（other）→ 回复"该订单已经查询过验机了，有什么问题可以解答"，
  不重复调 API；取消/无订单 → 对应引导话术。
- **业务术语：没有"核销"概念**（2026-08-16 统一）：本店无物流发货，验机成功 → 自动发货 → 订单完成。
  所有客服话术 / Agent 系统提示词 / 工具描述 / 管理界面里的"核销"已改为"验机/发货/完成"，
  避免客户误以为还有核销步骤。`walle_orders.status`：0-待验机 1-成功 2-失败 3-已过期。
- **验机成功回复 = 3 条独立消息**：
  1) 验机报告（AI 智能排版，独立一条，含发货成功提示）
  2) 📌 报告分析（`_analyze_gsx_report_ai`：LLM 围绕 ①iCloud激活锁 ②网络锁 ③设备信息
     ④激活日期是否对得上 ⑤黑名单 分析，给出优点 + 缺点/注意事项；失败回退规则式 `_analyze_gsx_report`）
  3) 五星好评感谢"有什么问题随时找我"。
  失败路径保持单条错误消息。Agent 上下文记录报告内容（供追问）。
- **查询前即时反馈**：写入订单表后、调 GSX API 前，先发"正在查询序列号/IMEI：XXXXX，请稍等~"
  （IMEI 用"正在查询IMEI"标签；15 位数字判 IMEI），避免买家等待无响应。
- **报告换行（AI 智能排版）**：`_format_gsx_report_ai` 用 LLM（文本模型，temperature=0）把任意格式的
  验机报告排版成"每字段一行"；**零丢失校验**（LLM 输出去空白必须与原文一致，不一致/失败自动回退
  规则式 `_format_gsx_report`，保证任何情况下内容完整）。格式化后的报告用于回复、发货内容、verify_result。
  - 规则式兜底：字段表（`_GSX_FIELD_NAMES`，含短报告"型号/IMEI/SN/激活锁/ID黑白状态" + 常见 GSX 字段）
    精确切分 + 未知字段通用切分（非中文边界规则）。
- **图片消息识别验机**（`_extract_sn_imei_from_image`）：买家发图片（`[图片] url`）→
  调视觉模型提取 SN/IMEI →
  识别到 → `_check_order_status` + `_handle_sn_imei`（写入 walle_orders.sn_imei → 验机 → 发货 → 3 条回复）；
  未识别到 → 转 Agent 描述图片。此前图片消息 tools 被禁用，LLM 只会回复"请用文字描述"，现已不走该路径。
  - ⚠️ **视觉模型类型是 `image` 不是 `vision`**（前端 ModelType = `"text" | "image"`），
    `_auto_ai_suggest` / `_extract_sn_imei_from_image` 查 `model_type == "image"`。
  - ⚠️ `normalize_sn_imei` 必须 `isascii()` 限定：Python 的 `isalnum()/isalpha()` 把中文也算字母数字，
    OCR 返回"未识别到任何编码"会被误判成合法 SN（8-14 位）。
- 旧 GKDT API（`api-srv.gkdt.com/inquiry/async`，appid+sign）已废弃移除；
  `walle_shop_configs.gsx_appid/gsx_secret` 不再使用。

## main.py 启动顺序
```
python main.py --with-frontend
  → start_frontend()        # Vite dev server，stdout/stderr 透传
  → start_cookie_watcher()  # cookie_watcher.py
  → start_ark_capture()     # ark_capture.py --daemon（headless，每30分钟刷新 cookie）
  → uvicorn backend
```
- 首次使用 ark 必须先手动运行 `python ark_capture.py`（有头模式）完成登录
- 之后 daemon 模式自动保活

---

## 后端启动

```bash
python main.py --with-frontend   # 后端 + 前端
python main.py                   # 仅后端
python main.py --reload          # 热重载（改代码自动生效）
```

- 后端 `8000`，前端 `5173`
- **非 --reload 模式改了后端代码必须重启**

---

## ark_capture.py 调试流程（接口抓包 + 日志读取）

### 什么时候用
遇到 ark 相关接口数据拿不到、字段路径不对、SKU/规格为空等问题，先跑调试程序抓日志，再读日志定位根因。

### 第一步：启动抓包程序（有头模式）
```bash
cd f:\XHS_ALL_IN_ONE
python ark_capture.py           # 抓包模式（手动操作）
python ark_capture.py --sync-skus  # SKU 同步模式：批量抓取所有商品规格写入数据库
```
抓包模式：浏览器自动打开 `https://ark.xiaohongshu.com`，手动点击目标页面（如商品编辑页），所有 API 请求/响应实时打印到终端，同时写入日志文件。

SKU 同步模式：自动打开浏览器，对数据库里所有还没有 `_sku_list` 的商品批量调用 `publish_render`，把规格写入 `raw_json`。

**先同步商品列表（页面点「同步商品」），再跑 `--sync-skus` 抓取规格。**

### 第二步：读取日志文件
日志目录：`f:\XHS_ALL_IN_ONE\data\logs\`
文件命名：`ark_YYYYMMDD_HHMMSS.jsonl`（每次启动新建一个）

**我（AI）的标准操作流程：**
1. `dir f:\XHS_ALL_IN_ONE\data\logs\ /O-D` — 找最新日志文件
2. `findstr "目标接口关键词" 日志文件路径` — 搜索目标接口
3. 读取 response 的 `body` 字段，分析真实数据结构

### 日志格式
每行一个 JSON，`direction` 字段区分请求/响应：
```jsonc
// 请求
{"ts": "18:20:02", "direction": "request", "method": "POST", "url": "...", "headers": {...}, "body": {...}}
// 响应
{"ts": "18:20:02", "direction": "response", "status": 200, "url": "...", "body": {...}}
```

### ⚠️ 已知坑：publish_render 的 data 字段是二次序列化字符串
`POST /api/edith/product/publish_render` 的响应结构：
```json
{"code": 200, "success": true, "data": "{\"product\":{\"productDetail\":{\"skuList\":[...]}}}"}
```
`data` 是 **JSON 字符串**，不是对象！必须先 `json.loads(res["data"])` 再取路径。
已封装为 `_extract_sku_list(res)` 函数（`backend/app/api/ark.py`）。

### 常用搜索关键词
| 要查的接口 | findstr 关键词 |
|---|---|
| 商品规格/SKU | `publish_render` |
| 商品列表 | `search_item_v2` |
| 卖家信息 | `seller/info` |
| 实时数据 | `key_metric_realtime` |

### 关键函数
```python
# backend/app/api/ark.py
_parse_render_data(res)      # publish_render 响应的 data 字段是 JSON 字符串，统一解析为 dict
_extract_sku_list(res)       # 从 publish_render 响应中提取 skuList
_extract_render_extras(res)  # 一次性提取 _sku_list + _item_properties + _sale_properties
```

### ⚠️ 已知坑：ark_capture.py 的 Ctrl+C 保存与编码问题（已修复 2026-08-16）

1. **Ctrl+C 保存失效**：`_capture_mode`/`_sync_skus_mode` 原来只 `except KeyboardInterrupt`，
   但 `asyncio.run()` 收到 Ctrl+C 时先取消主任务（抛 `asyncio.CancelledError`），
   导致"按 Ctrl+C 保存 cookies"永远不会执行。已改为 `except (KeyboardInterrupt, asyncio.CancelledError)`。
2. **stdout 重定向时 GBK 编码崩溃**：`print("➡/⬅")` 的箭头字符在 stdout 重定向到文件时
   触发 `UnicodeEncodeError`，请求/响应日志全部丢失（浏览器正常但日志为空）。
   已新增 `_fix_stdio_encoding()`：非控制台时强制 UTF-8，控制台保持原样。
3. **排查经验**：`data/ark_cookies.json` 的 `updated_at` 变化**不代表 Ctrl+C 保存成功**——
   `_save_at_token_to_file` 在捕获到带 `authorization: AT-` 的请求时就会更新 `updated_at` 和 token。
   确认保存成功要看 stdout 的 `[INFO] N 条 cookie 已保存` 或 playwright_cookies 数量变化。
4. **登录态判断**：直连调用返回 `code 902 / -13004`（登录已过期）时是**会话真的过期**，
   需要重新打开 ark_capture.py 在浏览器里登录；期间登录墙跳转（customer.xiaohongshu.com）抓到的是
   瞬时/旧 token，不要误以为已刷新。

---

## 常见报错排查

| 报错 | 原因 | 解法 |
|---|---|---|
| 405 Method Not Allowed | 路由未注册到 `main.py` 或 HTTP 方法不对 | 检查 `app.include_router` 和 `@router.post/get` |
| 404 账号不存在 | `sub_type` 不在允许列表，或 `user_id` 不匹配 | 检查 `_get_ark_account` 等函数的 sub_type 判断 |
| 500 Internal Server Error | 数据库表字段和模型不一致 | `PRAGMA table_info(表名)` 检查，手动 ALTER TABLE |
| 401 Not authenticated | access_token 丢失 | 刷新页面；脚本调试用 `backend_token.txt` 换 token |
| ark 同步无数据 | `data/ark_cookies.json` 不存在 | 运行 `ark_capture.py` 后必须 **Ctrl+C** 退出才保存 |
| ark SKU 同步 code=-1 | 没有先去列表页建立会话，或用了持久化 profile 被 daemon 占用 | `_sync_skus_with_playwright` 已修复：临时 profile + 先 goto list/shelf + expect_response 拦截 |
| antd message 静态函数警告 | 在 `App` 组件外用了 `message.xxx` | 用 `App.useApp()` 的 `message`，或在组件外层包 `<App>` |
