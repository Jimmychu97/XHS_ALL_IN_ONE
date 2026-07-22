# XHS_ALL_IN_ONE — Project Structure

## Top-level Layout

```
XHS_ALL_IN_ONE/
├── main.py                    # Unified entry point (starts backend + optional frontend)
├── requirements.txt           # Python dependencies
├── package.json               # Root-level Node scripts (frontend proxy)
├── config/
│   ├── default.yaml           # Default layered config (server, db, security, scheduler)
│   └── production.yaml        # Production overrides
├── apis/                      # XHS bottom-layer SDK (reverse-engineered, DO NOT modify directly)
├── xhs_utils/                 # Signing algorithm wrappers used by apis/
├── static/                    # Core JS signing files (xhs_a1.js, xhs_creator_sign.js, etc.)
├── backend/                   # FastAPI application
├── frontend/                  # React 19 SPA (Vite + TypeScript)
├── spider/                    # Standalone spider utilities
├── tests/                     # Pytest backend tests
├── data/                      # SQLite DB + cookie files (gitignored)
└── docker-compose.yml / Dockerfile
```

## Backend (`backend/app/`)

```
backend/app/
├── main.py                    # FastAPI app factory (create_app), lifespan, CORS, router registration
├── core/
│   ├── config.py              # Pydantic-settings: layered YAML → env var config
│   ├── database.py            # SQLAlchemy engine, SessionLocal, init_db, Alembic auto-migrate
│   ├── deps.py                # FastAPI dependency: get_current_user (JWT → User)
│   ├── security.py            # JWT encode/decode, Fernet encrypt/decrypt
│   ├── task_runner.py         # Background task execution helper
│   ├── platforms.py           # Platform registry helpers
│   └── time.py                # Asia/Shanghai timezone utilities
├── models/                    # SQLAlchemy ORM models (25 tables)
│   ├── user.py, platform_account.py, note.py, ai.py, publish.py
│   ├── auto_task.py, monitoring.py, task.py, notification.py
│   └── walle.py               # Walle CS workbench tables
├── api/                       # FastAPI routers (one file per resource)
│   ├── auth.py, accounts.py, notes.py, drafts.py, ai.py
│   ├── publish.py, auto_tasks.py, tags.py, notifications.py
│   ├── walle.py               # Walle REST API + SSE log stream
│   └── platforms/xhs/         # XHS-specific: pc.py, creator.py, crawl.py, analytics.py, monitoring.py, qianfan.py
├── services/                  # Business logic + schedulers
│   ├── scheduler_service.py   # APScheduler: due publish jobs + auto tasks
│   ├── heartbeat_scheduler.py # 2h cookie health check
│   ├── ai_service.py          # OpenAI-compatible LLM calls
│   ├── credential_service.py  # Fernet cookie encryption/decryption
│   ├── asset_downloader.py    # Media file download to local storage
│   ├── notification_service.py
│   └── walle_agent/           # CS Agent subsystem
│       ├── agent_loop.py      # Core agent loop (LLM → tool_calls → loop, max 5)
│       ├── tool_registry.py   # @agent_tool decorator + TOOL_REGISTRY + execute_tool
│       └── tools.py           # Registered tools: search_knowledge, query_gsx, record_order
├── adapters/xhs/              # Thin adapter layer between api/ and apis/ SDK
└── schemas/common.py          # Shared Pydantic response schemas
```

## Frontend (`frontend/src/`)

```
frontend/src/
├── main.tsx                   # React entry, router mount
├── app/
│   ├── router.tsx             # React Router v7 route definitions
│   └── providers.tsx          # Global providers (auth, theme)
├── components/
│   ├── layout/                # Sidebar, notification bell
│   ├── account/               # Account binding components
│   ├── platforms/             # Platform-specific shared components
│   └── ui/                   # Generic UI primitives
├── pages/platforms/xhs/       # Feature pages (one folder per module)
│   ├── notes/, drafts/, publish/, auto-tasks/
│   ├── analytics/, monitoring/, crawl/
│   └── walle/                 # CS workbench: walle-page.tsx, walle-logs.tsx
├── lib/
│   ├── api.ts                 # Axios HTTP client (base URL, auth header injection)
│   ├── platforms.ts           # Platform metadata
│   └── time.ts                # Date formatting helpers
├── hooks/use-auth.ts          # Auth state hook
└── types/index.ts             # All TypeScript interfaces/types
```

## SDK Layer (`apis/` + `xhs_utils/`)

```
apis/
├── xhs_pc_apis.py             # PC-side: login, search, note detail, comments, user info
├── xhs_creator_apis.py        # Creator platform: upload, published list
├── xhs_creator_login_apis.py  # Creator QR/SMS login
├── xhs_pc_login_apis.py       # PC QR/SMS login
├── xhs_pugongying_apis.py     # Pugongying KOL platform
├── xhs_qianfan_apis.py        # Qianfan distributor platform
└── xhs_walle_eva_apis.py      # Walle/Eva customer service workbench

xhs_utils/
├── xhs_util.py                # PC signing (calls static JS via PyExecJS)
├── xhs_creator_util.py        # Creator signing
├── http_util.py               # Shared HTTP session helpers
├── cookie_util.py             # Cookie parsing/formatting
└── data_util.py               # Response data normalization
```

## Key Architectural Patterns

### Layered Config
`config/default.yaml` → `CONFIG_FILE` env var → `.env` → environment variables (highest priority). Managed by Pydantic-settings in `core/config.py`.

### Database
- Default: SQLite (`./data/spider_xhs.db`); production: MySQL
- Alembic auto-migrations run at startup via `init_db()`
- All resources isolated by `user_id` (multi-tenant)
- Cookies and API keys encrypted with Fernet before storage

### Auth Flow
JWT Bearer tokens. `deps.get_current_user` decodes token → fetches `User` from DB → injected into every protected route via `Depends`.

### SDK Isolation
`apis/` must not be modified directly. Upper layers call through `backend/app/adapters/xhs/` adapters.

### Agent Loop (Walle CS)
`agent_loop.run_agent` → LLM call → parallel tool execution via `tool_registry.execute_tool` → append results → loop (max 5). Tools registered with `@agent_tool` decorator. History persisted in `WalleAgentSession` table per `app_cid`. Token overflow triggers LLM-generated summary compression.

### Scheduler
APScheduler polls every 60s for due publish jobs and auto-tasks. Heartbeat scheduler runs every 3600s for cookie health checks.
