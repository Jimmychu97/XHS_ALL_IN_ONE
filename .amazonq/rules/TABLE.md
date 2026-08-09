# 数据库表结构说明

数据库文件：`data/spider_xhs.db`（SQLite）

---

## 用户与认证

### `users` — 平台用户
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| username | VARCHAR(80) | 登录用户名 |
| password_hash | VARCHAR(128) | pbkdf2_sha256 哈希密码 |
| created_at | DATETIME | 注册时间 |

### `login_sessions` — XHS 登录会话（扫码/短信登录中间状态）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台，如 `xhs` |
| sub_type | VARCHAR(32) | `pc` / `creator` |
| status | VARCHAR(32) | `pending` / `confirmed` / `expired` |
| login_method | VARCHAR(32) | `qrcode` / `phone` |
| phone_mask | VARCHAR(32) | 手机号脱敏，如 `138****1234` |
| qr_id | VARCHAR(128) | 二维码 ID |
| code | VARCHAR(128) | 短信验证码 |
| qr_url | TEXT | 二维码图片 URL |
| encrypted_temp_cookies | TEXT | 临时 Cookie（Fernet 加密） |
| created_at | DATETIME | 创建时间 |

---

## 账号管理

### `platform_accounts` — 绑定的 XHS 账号
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台，如 `xhs` |
| sub_type | VARCHAR(32) | `pc` / `creator` / `qianfan` / `walle` / `ark` |
| external_user_id | VARCHAR(128) | XHS 平台的用户 ID |
| nickname | VARCHAR(128) | 昵称 |
| avatar_url | TEXT | 头像 URL |
| status | VARCHAR(32) | `healthy` / `expired` / `risk` / `unknown` |
| status_message | TEXT | 状态说明 |
| profile_json | TEXT | 账号详细信息 JSON |
| created_at | DATETIME | 绑定时间 |
| updated_at | DATETIME | 最后更新时间 |

### `account_cookie_versions` — Cookie 历史版本
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| platform_account_id | INTEGER | 关联账号 |
| encrypted_cookies | TEXT | Fernet 加密的 Cookie 字符串 |
| created_at | DATETIME | 保存时间 |

---

## 内容库

### `notes` — 采集到的小红书笔记
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 采集时使用的账号 |
| platform | VARCHAR(32) | 平台，如 `xhs` |
| note_id | VARCHAR(128) | XHS 笔记原始 ID |
| title | VARCHAR(512) | 笔记标题 |
| content | TEXT | 笔记正文 |
| author_name | VARCHAR(128) | 作者昵称 |
| raw_json | JSON | 原始接口返回数据 |
| created_at | DATETIME | 入库时间 |

### `note_assets` — 笔记附属图片/视频
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| note_id | INTEGER | 关联笔记 |
| asset_type | VARCHAR(32) | `image` / `video` |
| url | TEXT | 原始 URL（无水印） |
| local_path | TEXT | 本地下载路径 |
| sort_order | INTEGER | 排序序号 |

### `note_comments` — 笔记评论
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| note_id | INTEGER | 关联笔记 |
| comment_id | VARCHAR(128) | XHS 评论原始 ID |
| user_name | VARCHAR(128) | 评论者昵称 |
| user_id | VARCHAR(128) | 评论者 XHS ID |
| content | TEXT | 评论内容 |
| like_count | INTEGER | 点赞数 |
| parent_comment_id | VARCHAR(128) | 父评论 ID（回复时有值） |
| created_at_remote | VARCHAR(64) | XHS 平台的评论时间 |
| raw_json | JSON | 原始数据 |

### `tags` — 用户自定义标签
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| name | VARCHAR(64) | 标签名 |
| color | VARCHAR(24) | 标签颜色（十六进制） |

### `note_tags` — 笔记与标签多对多关联
| 字段 | 类型 | 说明 |
|---|---|---|
| note_id | INTEGER | 笔记 ID |
| tag_id | INTEGER | 标签 ID |

### `keyword_groups` — 关键词分组
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台 |
| name | VARCHAR(128) | 分组名称 |
| keywords | JSON | 关键词列表 `["苹果验机", "GSX查询"]` |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

## 草稿与 AI

### `ai_drafts` — 草稿工坊笔记草稿
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台 |
| title | VARCHAR(256) | 草稿标题（AI 改写后） |
| body | TEXT | 草稿正文 |
| tags | JSON | 标签列表 |
| source_note_id | INTEGER | 来源笔记 ID（从内容库深拷贝） |
| created_at | DATETIME | 创建时间 |

### `draft_assets` — 草稿关联图片素材
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| draft_id | INTEGER | 关联草稿 |
| asset_type | VARCHAR(32) | `image` / `video` |
| url | TEXT | 图片 URL |
| local_path | TEXT | 本地路径 |
| sort_order | INTEGER | 拖拽排序序号 |

### `ai_generated_assets` — AI 生成的图片资产
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| draft_id | INTEGER | 关联草稿（可为空） |
| prompt | TEXT | 生成时使用的 prompt |
| model_name | VARCHAR(128) | 使用的模型名称 |
| params | JSON | 其他生成参数 |
| file_path | TEXT | 本地文件路径 |
| created_at | DATETIME | 生成时间 |

### `model_configs` — AI 模型配置
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| name | VARCHAR(128) | 配置名称 |
| model_type | VARCHAR(32) | `text` / `image` |
| provider | VARCHAR(64) | 供应商，如 `openai` / `volcengine` |
| model_name | VARCHAR(128) | 模型名，如 `gpt-4o` / `doubao-pro` |
| base_url | TEXT | API 端点 URL |
| encrypted_api_key | TEXT | Fernet 加密的 API Key |
| is_default | BOOLEAN | 是否为默认模型 |

---

## 发布

### `publish_jobs` — 发布任务队列
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 使用的 Creator 账号 |
| source_draft_id | INTEGER | 来源草稿 ID |
| platform | VARCHAR(32) | 平台 |
| title | VARCHAR(256) | 发布标题 |
| body | TEXT | 发布正文 |
| publish_mode | VARCHAR(32) | `immediate` / `scheduled` |
| publish_options | TEXT | 可见性等发布选项 JSON |
| status | VARCHAR(32) | `pending` / `publishing` / `published` / `failed` / `cancelled` |
| scheduled_at | DATETIME | 定时发布时间 |
| external_note_id | VARCHAR(128) | 发布成功后 XHS 返回的笔记 ID |
| publish_error | TEXT | 失败原因 |
| published_at | DATETIME | 实际发布时间 |
| created_at | DATETIME | 创建时间 |

### `publish_assets` — 发布任务关联的图片/视频
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| publish_job_id | INTEGER | 关联发布任务 |
| asset_type | VARCHAR(32) | `image` / `video` |
| file_path | TEXT | 本地文件路径 |
| upload_status | VARCHAR(32) | `pending` / `uploaded` / `failed` |
| creator_media_id | VARCHAR(128) | 创作者平台返回的 media_id |
| upload_error | TEXT | 上传失败原因 |
| creator_upload_info | TEXT | 上传返回的完整信息 JSON |

---

## 自动运营

### `auto_tasks` — 自动运营任务配置
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| name | VARCHAR(128) | 任务名称 |
| keywords | JSON | 搜索关键词列表 |
| pc_account_id | INTEGER | 使用的 PC 账号 |
| creator_account_id | INTEGER | 使用的 Creator 账号 |
| ai_instruction | TEXT | AI 改写指令 |
| schedule_type | VARCHAR(32) | `daily` / `weekly` / `interval` |
| schedule_time | VARCHAR(32) | 执行时间，如 `09:00` |
| schedule_days | VARCHAR(64) | 执行星期，如 `1,3,5` |
| schedule_interval_hours | INTEGER | 间隔小时数（interval 模式） |
| status | VARCHAR(32) | `active` / `paused` |
| last_run_at | DATETIME | 上次执行时间 |
| next_run_at | DATETIME | 下次执行时间 |
| total_published | INTEGER | 累计发布数量 |
| created_at | DATETIME | 创建时间 |

---

## 竞品监控

### `monitoring_targets` — 监控目标
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台 |
| target_type | VARCHAR(32) | `keyword` / `account` / `brand` / `url` |
| name | VARCHAR(128) | 监控名称 |
| value | VARCHAR(512) | 监控值（关键词/账号ID/URL） |
| status | VARCHAR(32) | `active` / `paused` / `error` |
| config | JSON | 额外配置 |
| platform_account_id | INTEGER | 使用的账号 |
| crawl_interval_minutes | INTEGER | 爬取间隔（分钟） |
| consecutive_failures | INTEGER | 连续失败次数 |
| last_crawl_error | TEXT | 最后一次失败原因 |
| last_refreshed_at | DATETIME | 最后爬取时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `monitoring_snapshots` — 监控快照历史
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| target_id | INTEGER | 关联监控目标 |
| payload | JSON | 本次爬取结果（笔记列表等） |
| created_at | DATETIME | 快照时间 |

---

## 千帆客服工作台（Walle）

### `walle_conversations` — 客服会话列表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| app_cid | VARCHAR(256) | 会话唯一 ID（`$3$...`） |
| im_chat_id | VARCHAR(256) | IM 聊天 ID |
| customer_name | VARCHAR(128) | 买家昵称 |
| customer_id | VARCHAR(128) | 买家 ID |
| status | VARCHAR(32) | `open` / `closed` |
| unread_count | INTEGER | 未读消息数 |
| last_msg_content | VARCHAR(512) | 最后一条消息内容 |
| last_msg_time | DATETIME | 最后消息时间 |
| ai_suggestion | TEXT | AI 建议回复内容 |
| receiver_app_uid | VARCHAR(256) | 接收方 UID |
| raw_json | JSON | 原始数据 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `walle_messages` — 会话消息记录
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| app_cid | VARCHAR(256) | 所属会话 ID |
| msg_id | VARCHAR(256) | 消息唯一 ID |
| sender_type | VARCHAR(32) | `customer`（买家）/ `csa`（客服）/ `bot`（机器人） |
| sender_id | VARCHAR(128) | 发送者 ID |
| content_type | VARCHAR(32) | `text` / `image` / `order` 等 |
| content | TEXT | 消息内容 |
| msg_time | DATETIME | 消息时间 |
| raw_json | JSON | 原始数据 |
| created_at | DATETIME | 入库时间 |

### `walle_knowledge` — 客服知识库
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| title | VARCHAR(255) | 问题标题 |
| content | TEXT | 答案内容 |
| tags | VARCHAR(255) | 分类标签 |
| enabled | BOOLEAN | 是否启用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `walle_keywords` — 转人工关键词
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| keyword | VARCHAR(100) | 触发转人工的关键词 |

### `walle_orders` — 核销记录
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| app_cid | VARCHAR(256) | 所属会话 ID |
| sn_imei | VARCHAR(100) | 序列号 / IMEI |
| coupon_code | VARCHAR(100) | 核销码 |
| goods_name | VARCHAR(255) | 商品名称 |
| goods_id | VARCHAR(100) | 商品 ID |
| sku_id | VARCHAR(100) | SKU ID |
| spec | VARCHAR(100) | 规格描述 |
| order_sn | VARCHAR(100) | 订单号 |
| verify_result | JSON | 核销结果详情 |
| status | INTEGER | 核销状态 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `walle_shop_configs` — 客服 AI 配置
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| ai_enabled | BOOLEAN | 是否开启 AI 自动回复 |
| auto_send | BOOLEAN | 是否自动发送 AI 回复 |
| model_config_id | INTEGER | 使用的文本模型配置 |
| vision_model_config_id | INTEGER | 使用的视觉模型配置 |
| system_prompt | TEXT | AI 系统提示词 |
| instructions | TEXT | 额外指令 |
| gsx_appid | VARCHAR(128) | GSX 接口 AppID |
| gsx_secret | VARCHAR(256) | GSX 接口 Secret |
| gsx_key | VARCHAR(64) | GSX 接口 Key |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `walle_agent_sessions` — AI Agent 对话上下文
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| platform_account_id | INTEGER | 关联 walle 账号 |
| app_cid | VARCHAR(256) | 所属会话 ID |
| role | VARCHAR(32) | `user` / `assistant` / `tool` |
| content | TEXT | 消息内容 |
| tool_call_id | VARCHAR(128) | 工具调用 ID |
| created_at | DATETIME | 创建时间 |

---

## 千帆卖家后台（Ark）

### `ark_server_configs` — 千帆卖家账号配置
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| server_id | VARCHAR(128) | 用户自定义标识（如店铺名） |
| seller_id | VARCHAR(128) | 千帆平台的 seller_id |
| seller_name | VARCHAR(255) | 店铺名称 |
| cookie_file | VARCHAR(512) | ark_cookies.json 文件路径 |
| profile_dir | VARCHAR(512) | Playwright 浏览器 profile 路径 |
| enabled | BOOLEAN | 是否启用 |
| last_sync_at | DATETIME | 最后同步商品时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `ark_products` — 千帆商品列表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| server_config_id | INTEGER | 关联卖家账号 |
| account_id | INTEGER | 关联 platform_accounts（兼容字段） |
| item_id | VARCHAR(128) | 千帆商品 ID |
| title | VARCHAR(512) | 商品标题 |
| card_type | INTEGER | 商品状态：2=在售 3=仓库中 4=已售罄 5=审核中 6=已下架 10=违规下架 |
| total_stock | INTEGER | 总库存 |
| sku_count | INTEGER | SKU 数量 |
| first_sku_id | VARCHAR(128) | 第一个 SKU ID |
| sale_qty30 | INTEGER | 近 30 天销量 |
| acc_sale_qty | INTEGER | 累计销量 |
| check_status | INTEGER | 审核状态 |
| cover_url | TEXT | 封面图 URL |
| price_min | INTEGER | 最低价（分） |
| price_max | INTEGER | 最高价（分） |
| is_auto_off_shelf | BOOLEAN | 是否自动下架 |
| raw_json | JSON | 原始接口数据（含 `_sku_list` / `_item_properties` / `_sale_properties`） |
| synced_at | DATETIME | 最后同步时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `ark_product_skus` — 千帆商品 SKU 规格明细
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| product_id | INTEGER | 关联 ark_products |
| item_id | VARCHAR(128) | 千帆商品 ID |
| sku_id | VARCHAR(128) | SKU ID |
| sku_name | VARCHAR(512) | SKU 完整名称 |
| query_type | VARCHAR(255) | **查询类型**（款式 variantValue，如「全面验机报告」「基础查询」） |
| service_id | VARCHAR(128) | **服务 ID**（同 sku_id，业务语义字段） |
| price | INTEGER | 价格（分，÷100 = 元） |
| stock | INTEGER | 库存数量 |
| delivery_time | VARCHAR(32) | 发货时效值，如 `24` |
| delivery_type | INTEGER | 发货时效类型：4=小时内 5=绝对时间 |
| spec_image | TEXT | 规格图片 URL |
| barcode | VARCHAR(128) | 条形码 |
| synced_at | DATETIME | 最后同步时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

## 系统

### `tasks` — 全量任务审计日志
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台 |
| task_type | VARCHAR(64) | 任务类型，如 `crawl` / `publish` / `auto_task` |
| status | VARCHAR(32) | `pending` / `running` / `success` / `failed` / `cancelled` |
| progress | INTEGER | 进度 0-100 |
| payload | JSON | 任务参数 |
| created_at | DATETIME | 创建时间 |
| started_at | DATETIME | 开始执行时间 |
| finished_at | DATETIME | 完成时间 |
| error_type | VARCHAR(32) | 错误类型 |
| retry_count | INTEGER | 已重试次数 |
| max_retries | INTEGER | 最大重试次数 |
| parent_task_id | INTEGER | 父任务 ID（子任务时有值） |

### `notifications` — 站内通知
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| title | VARCHAR(256) | 通知标题 |
| body | TEXT | 通知内容 |
| level | VARCHAR(16) | `info` / `warning` / `error` |
| source_task_id | INTEGER | 来源任务 ID |
| source_type | VARCHAR(32) | 来源类型，如 `account` / `publish` |
| source_id | INTEGER | 来源资源 ID |
| read | BOOLEAN | 是否已读 |
| created_at | DATETIME | 创建时间 |

### `api_logs` — API 调用日志
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| user_id | INTEGER | 所属平台用户 |
| platform | VARCHAR(32) | 平台 |
| endpoint | VARCHAR(256) | 接口路径 |
| status | VARCHAR(32) | `success` / `failed` |
| meta | JSON | 额外信息（耗时、错误等） |
| created_at | DATETIME | 调用时间 |

### `app_migrations` — 应用级数据迁移记录
| 字段 | 类型 | 说明 |
|---|---|---|
| name | VARCHAR(128) | 迁移名称（主键） |
| applied_at | DATETIME | 执行时间 |

### `alembic_version` — Alembic 迁移版本
| 字段 | 类型 | 说明 |
|---|---|---|
| version_num | VARCHAR(32) | 当前迁移版本号 |
