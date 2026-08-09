# XHS_ALL_IN_ONE — Project Structure

## Top-Level Layout

```
XHS_ALL_IN_ONE/
├── main.py                    # Unified startup entry (backend + optional frontend)
├── ark_capture.py             # Playwright capture tool — login ark and print API requests
├── cookie_watcher.py          # CDP credential keep-alive service for Qianfan workbench
├── qianfan_login.py           # Qianfan platform login helper
├── requirements.txt           # Python dependencies
├── package.json               # Root Node.js scripts (frontend proxy)
├── Dockerfile                 # Multi-stage build
├── docker-compose.yml         # Orchestration
├── config/                    # YAML configuration (layered)
│   ├── default.yaml           # Base config (always loaded)
│   └── production.yaml        # Production overrides
├── apis/                      # XHS bottom-layer SDK (reverse-engineered signing + HTTP)
├── xhs_utils/                 # Signing algorithm wrappers
├── static/                    # Core JS signing files (xhs_*.js)
├── spider/                    # Standalone spider module
├── backend/                   # FastAPI application
├── frontend/                  # React 19 SPA
├── tests/                     # Backend pytest suite
└── data/                      # Runtime data (auto-created)
    ├── spider_xhs.db           # SQLite database
    ├── ark_cookies.json        # Ark login cookies
    └── ark_profile/            # Playwright persistent browser profile
```

## apis/ — Bottom-Layer SDK

Direct XHS API wrappers with reverse-engineered request signing. **Do not modify directly** — upper layers call through `backend/app/adapters/`.

| File | Platform |
|---|---|
| `xhs_pc_apis.py` | XHS PC client (search, notes, users, login) |
| `xhs_pc_login_apis.py` | PC login flows (QR code, SMS) |
| `xhs_creator_apis.py` | Creator platform (upload, publish, works list) |
| `xhs_creator_login_apis.py` | Creator login flows |
| `xhs_pugongying_apis.py` | Pugongying KOL platform |
| `xhs_qianfan_apis.py` | Qianfan distributor platform |
| `xhs_walle_eva_apis.py` | WalleEvaAPI (customer service) + ArkAPI (seller backend) |

## xhs_utils/ — Signing Utilities

| File | Purpose |
|---|---|
| `xhs_util.py` | Core XHS PC signing (x-s, x-t headers) |
| `xhs_creator_util.py` | Creator platform signing |
| `http_util.py` | Shared HTTP request helpers |
| `cookie_util.py` | Cookie parsing and management |
| `data_util.py` | Data transformation utilities |
| `common_util.py` | Shared utilities |
| `xhs_walle_eva_util.py` | Walle/Eva signing utilities |
| `xhs_pugongying_util.py` | Pugongying signing |
| `xhs_qianfan_util.py` | Qianfan signing |

## static/ — JS Signing Cores

Reverse-engineered JavaScript files executed via PyExecJS for request signing:
- `xhs_main_260411.js`, `xhs_a1.js`, `xhs_a1_other.js` — PC client signing
- `xhs_creator_sign.js`, `xhs_creator_signature.js`, `xhs_creator_260411.js` — Creator signing
- `xhs_rap.js`, `xhs_xray.js`, `xhs_xray_pack1.js`, `xhs_xray_pack2.js` — Additional signing modules
- `xhs_websectiga_env.js` — Environment fingerprint

## backend/ — FastAPI Application

### backend/app/core/
| File | Purpose |
|---|---|
| `config.py` | Layered settings (YAML → env vars), `get_settings()` cached with `@lru_cache` |
| `database.py` | SQLAlchemy engine + session factory, `init_db()`, `get_db()` |
| `deps.py` | FastAPI dependency injection: `get_current_user()` via JWT |
| `security.py` | JWT encode/decode, Fernet encryption for cookies/API keys |
| `task_runner.py` | Background task execution wrapper |
| `time.py` | Timezone utilities |
| `platforms.py` | Platform registry helpers |

### backend/app/models/
SQLAlchemy ORM models (25 tables total):

**Users & Auth:** `user.py`, `login_session.py`  
**Accounts:** `platform_account.py` (PC + Creator accounts with encrypted cookies)  
**Content:** `note.py`, `keyword_group.py`  
**AI & Drafts:** `ai.py` (drafts, assets, generated images, model configs)  
**Publishing:** `publish.py` (jobs + assets)  
**Automation:** `auto_task.py`  
**Monitoring:** `monitoring.py`  
**Walle/Customer Service:** `walle.py` (conversations, messages, knowledge base, keywords, redemptions)  
**System:** `task.py`, `notification.py`, `api_log.py`

### backend/app/api/
FastAPI routers, all mounted under `/api` prefix:

**Core:** `auth.py`, `accounts.py`, `login_sessions.py`, `notes.py`, `drafts.py`, `ai.py`, `publish.py`, `tags.py`, `notifications.py`, `tasks.py`, `model_configs.py`, `keyword_groups.py`, `files.py`, `auto_tasks.py`, `account_credentials_api.py`

**Platform-specific** (`api/platforms/xhs/`): `pc.py`, `creator.py`, `crawl.py`, `analytics.py`, `monitoring.py`, `qianfan.py`, `qianfan_login_api.py`

**External SDKs:** `walle.py` (customer service workbench), `ark.py` (seller backend)

### backend/app/adapters/xhs/
Adapter layer between FastAPI services and raw `apis/` SDK. Handles session management, error normalization, and credential injection.

### backend/app/services/
Business logic and background processing:

| File | Purpose |
|---|---|
| `scheduler_service.py` | APScheduler-based auto-task and publish scheduling |
| `heartbeat_scheduler.py` | 2-hour cookie health check scheduler |
| `account_service.py` | Account CRUD and cookie management |
| `ai_service.py` | OpenAI-compatible API calls for rewriting/image generation |
| `credential_service.py` | Fernet encrypt/decrypt for cookies and API keys |
| `asset_downloader.py` | Background media download to local storage |
| `monitoring_crawl_service.py` | Competitor monitoring crawl execution |
| `notification_service.py` | In-app notification creation |
| `platform_service.py` | Platform-level operations |
| `rate_limiter.py` | Request rate limiting |
| `task_service.py` | Task audit log management |
| `image_util.py` | Image processing utilities |
| `walle_agent/` | Walle customer service agent logic |

## frontend/ — React 19 SPA

### frontend/src/pages/platforms/xhs/
Feature pages organized by module:
- `accounts/` — Account matrix management
- `notes/` — Note discovery and content library
- `drafts/` — Draft workshop (AI rewrite)
- `publish/` — Publishing center
- `auto-tasks/` — Automated operations
- `analytics/` — Data insights dashboard
- `monitoring/` — Competitor monitoring
- `walle/` — Customer service workbench UI
- `qianfan/` — Qianfan platform UI

### frontend/src/components/
- `layout/` — Sidebar navigation + notification bell
- `account/` — Account-related shared components
- `platforms/` — Platform-specific shared components
- `ui/` — Generic UI primitives

### frontend/src/lib/
- `api.ts` — Axios HTTP client with JWT auth interceptor
- `platforms.ts` — Platform registry helpers
- `time.ts` — Timezone display utilities

### frontend/src/types/index.ts
All TypeScript type definitions for the entire frontend.

## Configuration System

Priority order (later overrides earlier):
1. `config/default.yaml`
2. File at `CONFIG_FILE` env var
3. `.env` file
4. Environment variables

Key config sections: `server`, `database` (sqlite/mysql), `security` (JWT + Fernet keys), `scheduler`, `frontend`, `walle`.

## Database

Default: SQLite at `./data/spider_xhs.db`  
Production: MySQL via `DATABASE_TYPE=mysql` + connection env vars  
Migrations: Alembic (`backend/alembic/versions/`)

## Architectural Patterns

1. **Layered SDK isolation**: `apis/` → `adapters/xhs/` → `services/` → `api/` routers. Raw SDK never called directly from routers.
2. **Multi-tenant isolation**: All resources scoped by `user_id` foreign key.
3. **Encrypted secrets**: All cookies and API keys stored with Fernet symmetric encryption.
4. **Scheduler-driven automation**: APScheduler runs auto-tasks and publish jobs; heartbeat scheduler checks cookie health every 2 hours.
5. **SSE for real-time**: In-memory log bus (`_log_store` + `_log_subscribers`) with `GET /walle/logs/stream` SSE endpoint.
6. **SPA fallback**: FastAPI serves React build in production with HTTP middleware for client-side routing.
