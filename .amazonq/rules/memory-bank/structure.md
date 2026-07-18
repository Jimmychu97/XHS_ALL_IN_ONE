# XHS_ALL_IN_ONE — Project Structure

## Top-Level Layout

```
XHS_ALL_IN_ONE/
├── main.py                     # Unified entry point (starts backend + optional frontend)
├── config/                     # Layered YAML configuration
│   ├── default.yaml            # Base config (always loaded)
│   └── production.yaml         # Production overrides
├── apis/                       # XHS reverse-engineered SDK (DO NOT modify directly)
├── xhs_utils/                  # Signature algorithm helpers used by apis/
├── static/                     # Core JS files for XHS signing (loaded by PyExecJS)
├── backend/                    # FastAPI application
├── frontend/                   # React 19 SPA
├── tests/                      # Pytest test suite
├── spider/                     # Standalone spider utility
├── data/                       # Runtime data (SQLite DB, cookies)
├── Dockerfile                  # Multi-stage build
└── docker-compose.yml          # Orchestration
```

## apis/ — XHS SDK Layer
Direct reverse-engineered HTTP clients. **Never modified by application code** — consumed only through `backend/app/adapters/xhs/`.

| File | Responsibility |
|---|---|
| `xhs_pc_apis.py` | PC-side: search, note detail, user info, comments, recommendations |
| `xhs_pc_login_apis.py` | PC QR code and SMS login |
| `xhs_creator_apis.py` | Creator platform: upload images/video, list works |
| `xhs_creator_login_apis.py` | Creator QR code and SMS login |
| `xhs_pugongying_apis.py` | Pugongying (KOL) platform APIs |
| `xhs_qianfan_apis.py` | Qianfan (distributor) platform APIs |

## xhs_utils/ — Signing Utilities
Wraps PyExecJS calls into the JS signing files in `static/`.

| File | Responsibility |
|---|---|
| `xhs_util.py` | PC-side request signing |
| `xhs_creator_util.py` | Creator-side request signing |
| `http_util.py` | Shared HTTP helpers |
| `cookie_util.py` | Cookie parsing and management |
| `common_util.py` | Shared utilities |
| `data_util.py` | Data transformation helpers |

## backend/app/ — FastAPI Application

### core/
| File | Responsibility |
|---|---|
| `config.py` | `Settings` (pydantic-settings); layered YAML → env var → `.env` loading; `get_settings()` cached with `@lru_cache` |
| `database.py` | SQLAlchemy engine, `SessionLocal`, `init_db()` (runs Alembic migrations on startup), `get_db()` dependency |
| `deps.py` | FastAPI dependency injection (current user, DB session) |
| `security.py` | JWT creation/verification, Fernet encryption for cookies/API keys |
| `platforms.py` | Platform registry helpers |
| `task_runner.py` | Background task execution wrapper |
| `time.py` | Timezone utilities (Asia/Shanghai) |

### models/
SQLAlchemy ORM models (20+ tables). Key models:

| Model | Table | Notes |
|---|---|---|
| `User` | `users` | Auth, owns notes/drafts/jobs |
| `PlatformAccount` | `platform_accounts` | XHS PC or Creator account binding |
| `Note` | `notes` | Collected XHS notes with assets |
| `AiDraft` | `ai_drafts` | Draft content for editing/publishing |
| `PublishJob` | `publish_jobs` | Publish queue with status tracking |
| `AutoTask` | `auto_tasks` | Scheduled automation pipeline config |
| `MonitoringTarget` | `monitoring_targets` | Competitor monitoring entries |
| `Task` | `tasks` | General task audit log |
| `Notification` | `notifications` | In-app notification records |
| `ModelConfig` | `model_configs` | OpenAI-compatible API endpoint config |

### api/
FastAPI routers, all mounted under `/api` prefix.

- `auth.py` — JWT login/register
- `accounts.py` — Platform account CRUD
- `notes.py` — Content library CRUD
- `drafts.py` — Draft workshop CRUD
- `publish.py` — Publish job management
- `auto_tasks.py` — Automation task CRUD
- `ai.py` — AI rewrite/image endpoints
- `model_configs.py` — AI model configuration
- `notifications.py` — Notification read/list
- `tasks.py` — Task audit log
- `tags.py`, `keyword_groups.py` — Taxonomy management
- `files.py` — Media file serving
- `login_sessions.py` — XHS login session management
- `account_credentials_api.py` — Credential management
- `platforms/xhs/` — XHS-specific routes: `pc.py`, `creator.py`, `crawl.py`, `analytics.py`, `monitoring.py`, `qianfan.py`, `qianfan_login_api.py`

### services/
Business logic layer, called by API routers.

| Service | Responsibility |
|---|---|
| `scheduler_service.py` | APScheduler-based publish job scheduler; runs due auto-tasks |
| `heartbeat_scheduler.py` | 1-hour interval cookie health check for all accounts |
| `account_service.py` | Account binding, cookie refresh, health check logic |
| `ai_service.py` | OpenAI-compatible API calls for rewrite and image generation |
| `asset_downloader.py` | Downloads note images/videos to local storage |
| `credential_service.py` | Fernet encrypt/decrypt for cookies and API keys |
| `monitoring_crawl_service.py` | Crawls monitoring targets on schedule |
| `notification_service.py` | Creates and delivers in-app notifications |
| `platform_service.py` | Platform-agnostic account operations |
| `rate_limiter.py` | Per-account request rate limiting |
| `task_service.py` | Task record creation and status updates |
| `image_util.py` | Image processing (Pillow + OpenCV) |

### adapters/xhs/
Thin adapter layer that translates between the raw `apis/` SDK and the backend service layer. This is the only code that should import from `apis/`.

## frontend/src/ — React SPA

```
src/
├── app/
│   ├── router.tsx          # React Router v7 route definitions
│   └── providers.tsx       # Global context providers
├── components/
│   ├── layout/             # Sidebar, notification bell, shell
│   ├── account/            # Account binding components
│   ├── platforms/          # Platform-specific shared components
│   └── ui/                 # Generic UI primitives
├── pages/
│   ├── login/              # Auth pages
│   ├── platforms/xhs/      # All XHS feature pages (discovery, library, drafts, publish, etc.)
│   ├── models/             # Model configuration page
│   ├── settings/           # Settings page
│   └── tasks/              # Task center page
├── lib/
│   ├── api.ts              # Axios HTTP client with JWT interceptor
│   ├── platforms.ts        # Platform metadata helpers
│   └── time.ts             # Date/time formatting
├── hooks/
│   └── use-auth.ts         # Auth state hook
└── types/
    └── index.ts            # All TypeScript type definitions
```

## Configuration Priority (lowest → highest)
1. `config/default.yaml`
2. File at path in `CONFIG_FILE` env var
3. `.env` file
4. Environment variables

## Database
- Development: SQLite at `./data/spider_xhs.db`
- Production: MySQL (configured via env vars or YAML)
- Migrations: Alembic, auto-applied on `init_db()` at startup
- Custom `app_migrations` table for idempotent data-level migrations

## Key Architectural Patterns
- **Adapter boundary**: `apis/` ← `adapters/xhs/` ← `services/` ← `api/` (strict layering)
- **Dependency injection**: `get_db()` and `get_current_user()` via FastAPI `Depends()`
- **Lifespan management**: Scheduler and heartbeat started/stopped in FastAPI `lifespan` context manager
- **Encrypted secrets**: All cookies and API keys encrypted with Fernet before DB storage
- **SPA fallback**: In production/Docker, backend serves `index.html` for all non-API, non-file 404s
