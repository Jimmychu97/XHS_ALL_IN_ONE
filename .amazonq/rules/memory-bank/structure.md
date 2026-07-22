# XHS_ALL_IN_ONE — Project Structure

## Top-Level Layout

```
XHS_ALL_IN_ONE/
├── main.py                  # Unified entry point (starts backend + optional frontend)
├── config/                  # Layered YAML config (default / production)
├── apis/                    # XHS bottom-layer SDK (reverse-engineered signing + HTTP)
├── xhs_utils/               # Signing algorithm wrappers and HTTP helpers
├── static/                  # Core JS files for XHS signature computation
├── backend/                 # FastAPI application
├── frontend/                # React 19 SPA
├── spider/                  # Standalone spider utilities
├── tests/                   # Backend pytest suite (126 tests)
├── data/                    # SQLite DB + cookie files (runtime, gitignored)
├── Dockerfile               # Multi-stage build
└── docker-compose.yml       # Orchestration
```

## Backend (`backend/app/`)

```
backend/app/
├── main.py                  # FastAPI app factory (create_app), lifespan, CORS, router registration
├── core/
│   ├── config.py            # Pydantic Settings — layered YAML + env var config
│   ├── database.py          # SQLAlchemy engine, SessionLocal, init_db, Alembic auto-migrate
│   ├── deps.py              # FastAPI dependency: get_current_user (JWT → User)
│   ├── security.py          # JWT encode/decode, Fernet encrypt/decrypt
│   ├── task_runner.py       # Background task execution wrapper
│   └── time.py              # shanghai_now() — Asia/Shanghai timezone helper
├── models/                  # SQLAlchemy ORM models (25 tables)
│   ├── user.py              # users
│   ├── platform_account.py  # platform_accounts, account_cookie_versions
│   ├── note.py              # notes, note_assets, note_comments, tags, note_tags, keyword_groups
│   ├── ai.py                # ai_drafts, draft_assets, ai_generated_assets, model_configs
│   ├── publish.py           # publish_jobs, publish_assets
│   ├── auto_task.py         # auto_tasks
│   ├── monitoring.py        # monitoring_targets, monitoring_snapshots
│   ├── walle.py             # walle_conversations, walle_messages, walle_knowledge_base,
│   │                        #   walle_transfer_keywords, walle_redemption_records
│   ├── task.py              # tasks (audit log)
│   ├── notification.py      # notifications
│   └── api_log.py           # api_logs
├── api/                     # FastAPI routers
│   ├── auth.py              # /auth — register, login, refresh
│   ├── accounts.py          # /accounts — XHS account binding
│   ├── notes.py             # /notes — content library CRUD
│   ├── drafts.py            # /drafts — draft workshop
│   ├── ai.py                # /ai — rewrite, image generation
│   ├── publish.py           # /publish — job queue
│   ├── auto_tasks.py        # /auto-tasks — scheduled pipeline config
│   ├── walle.py             # /walle — customer service workbench
│   ├── notifications.py     # /notifications
│   ├── tasks.py             # /tasks — audit log
│   └── platforms/xhs/       # XHS-specific: pc, creator, crawl, analytics, monitoring, qianfan
├── services/                # Business logic
│   ├── scheduler_service.py # APScheduler: due publish jobs + auto-task pipeline
│   ├── heartbeat_scheduler.py # 2h cookie health check
│   ├── account_service.py   # Cookie management, health check
│   ├── ai_service.py        # OpenAI-compatible API calls
│   ├── credential_service.py # Fernet encrypt/decrypt for cookies & API keys
│   ├── asset_downloader.py  # Download media to local storage
│   ├── monitoring_crawl_service.py # Competitor monitoring crawl
│   ├── notification_service.py # In-app notifications
│   ├── rate_limiter.py      # Per-account rate limiting
│   └── walle_agent/         # Walle customer service agent logic
├── adapters/xhs/            # Thin wrappers bridging SDK (apis/) → service layer
└── schemas/common.py        # Shared Pydantic response schemas
```

## Frontend (`frontend/src/`)

```
frontend/src/
├── main.tsx                 # React entry, mounts providers + router
├── app/
│   ├── router.tsx           # React Router v7 route definitions
│   └── providers.tsx        # App-level providers (auth context, etc.)
├── pages/
│   ├── login/               # Login page
│   ├── platform-select/     # Platform selection landing
│   └── platforms/xhs/       # All XHS feature pages
│       ├── accounts/        # Account matrix
│       ├── notes/           # Note discovery + content library
│       ├── drafts/          # Draft workshop
│       ├── publish/         # Publishing center
│       ├── auto-tasks/      # Automated operations
│       ├── analytics/       # Data insights
│       ├── monitoring/      # Competitor monitoring
│       ├── walle/           # Customer service workbench
│       └── ...
├── components/
│   ├── layout/              # Sidebar, notification bell
│   ├── account/             # Account-related shared components
│   ├── platforms/           # Platform-specific shared components
│   └── ui/                  # Generic UI primitives
├── lib/
│   ├── api.ts               # Axios HTTP client with JWT interceptor
│   ├── platforms.ts         # Platform metadata
│   └── time.ts              # Date/time formatting helpers
├── hooks/
│   └── use-auth.ts          # Auth state hook
└── types/index.ts           # All TypeScript type definitions
```

## SDK Layer (`apis/` + `xhs_utils/`)

```
apis/
├── xhs_pc_apis.py           # PC-side: login, search, note detail, comments, user info
├── xhs_pc_login_apis.py     # PC QR code + SMS login flows
├── xhs_creator_apis.py      # Creator platform: upload, publish, list works
├── xhs_creator_login_apis.py# Creator QR code + SMS login
├── xhs_pugongying_apis.py   # 蒲公英 KOL platform
├── xhs_qianfan_apis.py      # 千帆 distribution platform
└── xhs_walle_eva_apis.py    # 千帆 customer service workbench

xhs_utils/
├── xhs_util.py              # PC-side signing (calls static/*.js via PyExecJS)
├── xhs_creator_util.py      # Creator-side signing
├── http_util.py             # Shared requests session + retry logic
├── cookie_util.py           # Cookie parsing and management
└── data_util.py             # Response data normalization
```

## Architectural Patterns

### Multi-tenant Isolation
All resources are scoped by `user_id`. Every DB query in API routes filters by the authenticated user's ID.

### Layered Architecture
```
Frontend (React) → FastAPI API routes → Services → Adapters → SDK (apis/) → XHS HTTP APIs
```
The `apis/` layer must NOT be modified directly; upper layers use `adapters/xhs/` as the integration point.

### Authentication Flow
JWT Bearer tokens (access + refresh). `get_current_user` dependency injected into all protected routes via `Depends(get_current_user)`.

### Database
- Default: SQLite at `./data/spider_xhs.db`
- Production: MySQL (switchable via config)
- Migrations: Alembic, auto-run at startup via `init_db()`
- All datetimes stored in Asia/Shanghai timezone

### Scheduler
APScheduler runs two jobs:
1. `run_due_auto_tasks` — polls auto_tasks table, executes full pipeline
2. `start_due_publish_scheduler` — polls publish_jobs for scheduled/immediate jobs

### Security
- Passwords: bcrypt via passlib
- Cookies & API keys: Fernet symmetric encryption
- JWT: python-jose with HS256
