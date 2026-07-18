# XHS_ALL_IN_ONE — Project Structure

## Top-Level Layout

```
XHS_ALL_IN_ONE/
├── main.py                    # Unified startup entry (backend + optional Vite frontend)
├── requirements.txt           # Python dependencies
├── package.json               # Root-level npm scripts (workspace convenience)
├── config/
│   ├── default.yaml           # Base configuration (all settings with comments)
│   └── production.yaml        # Production overrides
├── apis/                      # XHS SDK layer — reverse-engineered signing + HTTP
├── xhs_utils/                 # Signing algorithm helpers used by apis/
├── static/                    # Signing core JS files (loaded by PyExecJS)
├── backend/                   # FastAPI application
├── frontend/                  # React 19 + Vite SPA
├── spider/                    # Standalone spider utilities
├── tests/                     # Pytest test suite
├── data/                      # SQLite database (runtime, gitignored)
├── Dockerfile                 # Multi-stage build
└── docker-compose.yml         # Orchestration
```

## apis/ — XHS SDK Layer
Do NOT modify directly. Upper layers call through `backend/app/adapters/`.

```
apis/
├── xhs_pc_apis.py             # PC platform: login, search, note detail, comments, user info
├── xhs_pc_login_apis.py       # PC QR code + SMS login flows
├── xhs_creator_apis.py        # Creator platform: upload images/video, list works
├── xhs_creator_login_apis.py  # Creator QR code + SMS login flows
├── xhs_pugongying_apis.py     # Pugongying (KOL marketplace) APIs
└── xhs_qianfan_apis.py        # Qianfan (distributor) APIs
```

## xhs_utils/ — Signing Utilities
```
xhs_utils/
├── xhs_util.py                # Core PC signing (a1, web_id, x-s, x-t)
├── xhs_creator_util.py        # Creator platform signing
├── http_util.py               # Shared HTTP session helpers
├── cookie_util.py             # Cookie parsing and management
├── common_util.py             # Shared utilities
├── data_util.py               # Data transformation helpers
├── xhs_pugongying_util.py     # Pugongying signing
└── xhs_qianfan_util.py        # Qianfan signing
```

## backend/app/ — FastAPI Application

### core/
```
core/
├── config.py      # Settings (pydantic-settings); layered: YAML < .env < env vars; @lru_cache singleton
├── database.py    # SQLAlchemy engine + session factory; init_db() creates all tables
├── deps.py        # FastAPI dependency injection (get_db, get_current_user)
├── security.py    # JWT creation/verification; Fernet encryption for cookies/API keys
├── platforms.py   # Platform registry helpers
├── task_runner.py # Background task execution wrapper
└── time.py        # Timezone-aware datetime utilities
```

### models/ — SQLAlchemy ORM (20+ tables)
Key models: User, PlatformAccount, Note, NoteAsset, AiDraft, DraftAsset, PublishJob, AutoTask, Task, Notification, MonitoringTarget, KeywordGroup, ModelConfig, LoginSession, ApiLog

### api/ — FastAPI Routers
All routers mounted at `/api` prefix.
```
api/
├── auth.py            # /auth — register, login, token refresh
├── accounts.py        # /accounts — platform account CRUD + health check
├── notes.py           # /notes — content library CRUD
├── drafts.py          # /drafts — draft workshop CRUD
├── ai.py              # /ai — AI rewrite, title polish, tag generation, image enhancement
├── publish.py         # /publish — publish jobs, scheduling
├── auto_tasks.py      # /auto-tasks — automated pipeline configuration
├── tasks.py           # /tasks — task center audit
├── notifications.py   # /notifications — bell notifications
├── model_configs.py   # /model-configs — AI model endpoint configuration
├── tags.py            # /tags — custom tag management
├── keyword_groups.py  # /keyword-groups — keyword group management
├── files.py           # /files — media file serving
├── login_sessions.py  # /login-sessions — QR/SMS login session management
└── platforms/xhs/
    ├── pc.py          # /xhs/pc — note search, detail, user info (proxies SDK)
    ├── creator.py     # /xhs/creator — upload, publish via Creator API
    ├── crawl.py       # /xhs/crawl — batch URL/search/comment crawling
    ├── analytics.py   # /xhs/analytics — dashboard, trends, top content
    ├── monitoring.py  # /xhs/monitoring — competitor monitoring
    └── qianfan.py     # /xhs/qianfan — Qianfan distributor data
```

### services/ — Business Logic
```
services/
├── scheduler_service.py      # APScheduler: due publish jobs + auto-task pipeline
├── account_service.py        # Account health check, cookie refresh
├── ai_service.py             # OpenAI-compatible API calls (rewrite, image gen)
├── platform_service.py       # Platform-agnostic publish orchestration
├── asset_downloader.py       # Download and store note assets locally
├── monitoring_crawl_service.py # Competitor monitoring crawl execution
├── notification_service.py   # Create/deliver notifications
├── task_service.py           # Task record creation and status updates
├── rate_limiter.py           # Per-account request rate limiting
└── image_util.py             # Image processing (Pillow + OpenCV)
```

### adapters/xhs/
Bridge between the raw `apis/` SDK and the FastAPI service layer. Handles cookie decryption, session injection, and response normalization.

### storage/
Runtime directory for downloaded media files and CSV/JSON exports. Not committed to git.

## frontend/src/ — React SPA

```
src/
├── app/
│   ├── router.tsx             # React Router v7 route definitions
│   └── providers.tsx          # Global providers (auth context, etc.)
├── pages/platforms/xhs/       # Feature pages (one per module)
├── components/
│   ├── layout/                # Sidebar + notification bell
│   ├── account/               # Account binding components
│   ├── platforms/             # Platform-specific shared components
│   └── ui/                    # Generic UI primitives
├── hooks/
│   └── use-auth.ts            # Authentication hook
├── lib/
│   ├── api.ts                 # Axios HTTP client with auth interceptors
│   ├── platforms.ts           # Platform metadata constants
│   └── time.ts                # Date/time formatting helpers
└── types/
    └── index.ts               # All TypeScript type definitions
```

## Configuration System
Priority (lowest → highest): `config/default.yaml` → `CONFIG_FILE` env var → `.env` file → environment variables

Key settings:
- `database.type`: `sqlite` (dev) or `mysql` (prod)
- `security.secret_key`: JWT signing key (must change in production)
- `security.fernet_key`: Cookie/API key encryption (auto-derived from secret_key if empty)
- `scheduler.enabled`: Enable background scheduler for auto-operations
- `frontend.serve_static`: Serve built frontend from backend (Docker/production mode)

## Architectural Patterns

1. **Layered SDK isolation**: `apis/` ← `adapters/xhs/` ← `services/` ← `api/` routers. Never call `apis/` directly from routers.
2. **Dependency injection**: All DB sessions and current user obtained via `Depends()` from `core/deps.py`.
3. **Settings singleton**: `get_settings()` is `@lru_cache`; YAML values injected at construction time.
4. **Lifespan management**: Scheduler started/stopped in FastAPI `lifespan` context manager.
5. **SPA fallback**: In production, non-API 404s return `index.html` for client-side routing.
6. **Fernet encryption**: All sensitive data (cookies, API keys) encrypted at rest using `cryptography.fernet`.
