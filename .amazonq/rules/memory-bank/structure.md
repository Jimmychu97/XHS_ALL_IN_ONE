# XHS_ALL_IN_ONE — Project Structure

## Top-Level Layout

```
XHS_ALL_IN_ONE/
├── main.py                  # Unified entry point: starts backend + frontend + cookie_watcher + ark_capture
├── ark_capture.py           # Playwright capture tool for Ark (千帆卖家) — login & API interception
├── cookie_watcher.py        # CDP credential keep-alive for Walle (千帆客服) — token refresh
├── config/                  # YAML config (default.yaml / production.yaml)
├── apis/                    # XHS bottom-layer SDK (reverse-engineered signing + HTTP)
├── xhs_utils/               # Signing algorithm wrappers used by apis/
├── static/                  # Core JS signing files (xhs_a1.js, xhs_creator_sign.js, etc.)
├── backend/                 # FastAPI application
├── frontend/                # React 19 + Vite SPA
├── tests/                   # Backend pytest tests
├── data/                    # Runtime data (auto-created): SQLite DB, cookies, logs, media
└── spider/                  # Legacy spider module
```

## Backend Structure (`backend/app/`)

```
backend/app/
├── main.py              # FastAPI app factory (create_app), lifespan, CORS, router registration
├── core/
│   ├── config.py        # Settings via pydantic-settings, reads YAML + env vars
│   ├── database.py      # SQLAlchemy engine, SessionLocal, init_db(), get_db()
│   ├── deps.py          # FastAPI dependencies: get_current_user
│   ├── security.py      # Fernet encrypt/decrypt, JWT create/decode, password hash/verify
│   ├── time.py          # shanghai_now() — all timestamps use Shanghai timezone
│   ├── platforms.py     # Platform registry helpers
│   └── task_runner.py   # Background task execution wrapper
├── models/              # SQLAlchemy ORM models (25+ tables)
├── schemas/
│   └── common.py        # paginated() helper → {total, page, page_size, items}
├── api/
│   ├── auth.py          # /api/auth — login, refresh token
│   ├── accounts.py      # /api/accounts — platform account CRUD
│   ├── notes.py         # /api/notes — content library
│   ├── drafts.py        # /api/drafts — draft workshop
│   ├── publish.py       # /api/publish — publish jobs
│   ├── walle.py         # /api/walle — 千帆客服 REST + SSE log stream
│   ├── ark.py           # /api/ark — 千帆卖家 product/SKU management
│   ├── auto_tasks.py    # /api/auto-tasks — scheduled automation
│   ├── ai.py            # /api/ai — text rewrite, image generation
│   ├── model_configs.py # /api/model-configs — AI model configuration
│   ├── notifications.py # /api/notifications — in-app alerts
│   └── platforms/xhs/   # XHS-specific: pc.py, creator.py, crawl.py, analytics.py, monitoring.py
├── services/
│   ├── account_service.py       # upsert_platform_account_from_login, serialize_account, cookie helpers
│   ├── ai_service.py            # OpenAICompatibleTextClient, OpenAICompatibleImageClient
│   ├── scheduler_service.py     # APScheduler: due publish jobs + auto-task pipeline
│   ├── heartbeat_scheduler.py   # 2-hour cookie health check scheduler
│   ├── notification_service.py  # notify_* helpers for task/account/publish events
│   ├── monitoring_crawl_service.py  # Competitor monitoring crawl logic
│   ├── task_service.py          # Task audit log management
│   ├── asset_downloader.py      # Media file download to local storage
│   ├── credential_service.py    # Credential resolution for accounts
│   ├── rate_limiter.py          # API rate limiting
│   └── walle_agent/             # AI agent for Walle customer service
└── adapters/xhs/                # XHS SDK adapter layer (wraps apis/ for backend use)
```

## Frontend Structure (`frontend/src/`)

```
frontend/src/
├── main.tsx             # React entry point
├── app/
│   ├── router.tsx       # React Router v6 route definitions
│   └── providers.tsx    # Context providers (auth, theme, etc.)
├── lib/
│   ├── api.ts           # axios instance (http) with JWT auto-header + getAccessToken()
│   ├── platforms.ts     # Platform metadata helpers
│   └── time.ts          # Time formatting utilities
├── types/
│   └── index.ts         # All TypeScript interfaces and types
├── hooks/
│   └── use-auth.ts      # Authentication hook
├── components/
│   ├── layout/          # Sidebar, notification bell, shell layout
│   ├── account/         # Account binding components
│   ├── platforms/       # Shared platform UI components
│   └── ui/              # Generic UI primitives (Ant Design wrappers)
└── pages/
    ├── login/           # Login page
    ├── platform-select/ # Platform selection
    ├── platforms/xhs/   # All XHS feature pages:
    │   ├── accounts/    # Account matrix
    │   ├── notes/       # Note discovery
    │   ├── library/     # Content library
    │   ├── drafts/      # Draft workshop
    │   ├── publish/     # Publish center
    │   ├── auto-tasks/  # Auto operations
    │   ├── analytics/   # Data insights
    │   ├── monitoring/  # Competitor monitoring
    │   ├── walle/       # 千帆客服 (walle-page.tsx, walle-logs.tsx, etc.)
    │   └── ark/         # 千帆卖家
    ├── models/          # AI model configuration
    ├── settings/        # Platform settings
    └── tasks/           # Task center
```

## SDK Layer (`apis/`)

```
apis/
├── xhs_pc_apis.py           # XHS PC: search, note detail, comments, user profile, feed
├── xhs_pc_login_apis.py     # XHS PC: QR code + SMS login
├── xhs_creator_apis.py      # Creator platform: upload, list works
├── xhs_creator_login_apis.py # Creator: QR + SMS login
├── xhs_pugongying_apis.py   # 蒲公英: KOL list, fan profile
├── xhs_qianfan_apis.py      # 千帆分销: distributor/product info
└── xhs_walle_eva_apis.py    # WalleEvaAPI + ArkAPI (CDP-based signing)
```

## Key Architectural Patterns

### Layered Architecture
```
Frontend (React) → HTTP → FastAPI Routes → Services → Adapters → SDK (apis/)
                                        ↓
                                   SQLAlchemy ORM → SQLite/MySQL
```

### Signing Strategy
- XHS PC/Creator: JS signing files in `static/` executed via Node.js subprocess through `xhs_utils/`
- Ark/Walle: CDP (Chrome DevTools Protocol) — page's own JS signs requests, captured via Playwright

### Multi-tenancy
- All resources scoped by `user_id` (platform users, not XHS accounts)
- XHS accounts stored in `platform_accounts` with `sub_type` distinguishing PC/Creator/Walle/Ark

### Credential Security
- All cookies and API keys encrypted with Fernet symmetric encryption
- JWT: `access_token` (15 min, in-memory) + `refresh_token` (7 days, localStorage)
- SSE endpoints use `?token=` query param (EventSource can't set headers)

### Startup Sequence (`main.py`)
1. `start_frontend()` — Vite dev server
2. `start_cookie_watcher()` — CDP token keep-alive for Walle
3. `start_ark_capture()` — Playwright daemon for Ark cookie refresh
4. `uvicorn` — FastAPI backend on port 8000
