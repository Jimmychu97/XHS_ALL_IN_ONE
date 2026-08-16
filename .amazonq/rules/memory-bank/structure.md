# Project Structure

## Root Directory Layout
```
XHS_ALL_IN_ONE/
├── .amazonq/rules/          # Development rules & memory bank
├── apis/                     # XHS底层SDK - Reverse-engineered API clients
├── author/                   # Author assets (logos, donation QR codes)
├── backend/                  # FastAPI backend application
├── config/                   # YAML configuration files
├── data/                     # Runtime data (Database, cookies, logs)
├── frontend/                 # React frontend application
├── spider/                   # Legacy spider module
├── static/                   # Signature algorithm JS files
├── tests/                    # Backend test suite
├── xhs_utils/                # Utility functions for XHS SDK
├── main.py                   # Unified entry point
├── ark_capture.py            # Playwright-based Ark API capture tool
├── cookie_watcher.py         # CDP credential persistence service
├── docker-compose.yml        # Docker orchestration
├── Dockerfile                # Multi-stage Docker build
├── requirements.txt          # Python dependencies
└── package.json              # Node.js dependencies for SDK
```

## Core Architectural Layers

### Layer 1: SDK Layer (`apis/` + `xhs_utils/` + `static/`)
**Purpose**: Low-level API clients with transparent signature implementation

**Key Files**:
- `xhs_pc_apis.py` - PC端接口 (search, note details, user profiles)
- `xhs_creator_apis.py` - 创作者平台接口 (upload, publish)
- `xhs_pc_login_apis.py` - PC端登录 (QR code, SMS)
- `xhs_creator_login_apis.py` - 创作者登录
- `xhs_pugongying_apis.py` - 蒲公英平台API
- `xhs_qianfan_apis.py` - 千帆分销平台API
- `xhs_walle_eva_apis.py` - 千帆客服 + 卖家后台 (WalleEvaAPI + ArkAPI)

**Signature Files** (`static/`):
- `xhs_a1.js`, `xhs_creator_sign.js` - Anti-scraping signature algorithms
- `xhs_xray.js`, `xhs_rap.js` - Request signing

**Utilities** (`xhs_utils/`):
- `xhs_util.py` - Core signature generation
- `http_util.py` - HTTP request wrapper
- `cookie_util.py` - Cookie management
- `data_util.py` - Data transformation utilities

### Layer 2: Backend Application (`backend/app/`)
**Purpose**: FastAPI-based REST API with business logic

**Subdirectories**:
- `core/` - Configuration, database, security, timezone handling
- `models/` - SQLAlchemy ORM models (25+ tables)
- `api/` - API route handlers
- `services/` - Business logic layer + scheduler
- `adapters/xhs/` - Adapter layer for XHS SDK (中转调用)
- `schemas/` - Pydantic request/response schemas

**Key Files**:
- `main.py` - FastAPI app initialization
- `core/database.py` - SQLAlchemy setup + session management
- `core/security.py` - Fernet encryption, JWT tokens, password hashing
- `core/time.py` - Shanghai timezone handling
- `core/deps.py` - Dependency injection (current user, database session)

### Layer 3: Frontend Application (`frontend/src/`)
**Purpose**: React SPA with Ant Design 6

**Subdirectories**:
- `pages/platforms/xhs/` - Feature pages (账号矩阵, 笔记发现, 内容库, etc.)
- `components/layout/` - Sidebar, notifications, app shell
- `lib/api.ts` - Axios HTTP client with JWT interceptor
- `types/` - TypeScript type definitions
- `hooks/` - Custom React hooks

**Key Pages**:
- `accounts/` - Account management (账号矩阵)
- `discover/` - Note discovery (笔记发现)
- `library/` - Content library (内容库)
- `drafts/` - Draft workshop (草稿工坊)
- `publish/` - Publishing center (发布中心)
- `auto/` - Automated operations (自动运营)
- `walle/` - Customer service dashboard (千帆客服)
- `insights/` - Data analytics (数据洞察)
- `monitoring/` - Competitor monitoring (竞品监控)

### Layer 4: Data Persistence (`data/`)
**Purpose**: Runtime data storage

**Contents**:
- `spider_xhs.db` - SQLite database (default)
- `ark_cookies.json` - Playwright cookies for Ark platform
- `ark_profile/` - Playwright persistent browser profile
- `logs/` - API request/response logs (JSONL format)
- `cookies/` - Platform-specific cookie storage

## Request Flow Architecture

```
User Browser (React)
    ↓ Axios HTTP
FastAPI Backend (:8000)
    ↓ Dependency Injection
API Route Handler (backend/app/api/*.py)
    ↓ Business Logic
Service Layer (backend/app/services/*.py)
    ↓ SDK Adapter
XHS SDK Adapter (backend/app/adapters/xhs/)
    ↓ Low-level API
XHS SDK Layer (apis/*.py)
    ↓ Signature + HTTP
XHS Platform APIs
```

## Database Architecture
**Engine**: SQLite (default) / MySQL (production)  
**ORM**: SQLAlchemy 2.0+  
**Migrations**: Alembic

**Key Table Groups**:
1. **User & Auth**: `users`, `login_sessions`
2. **Account Management**: `platform_accounts`, `account_cookie_versions`
3. **Content Library**: `notes`, `note_assets`, `note_comments`, `tags`, `note_tags`
4. **Drafts & AI**: `ai_drafts`, `draft_assets`, `ai_generated_assets`, `model_configs`
5. **Publishing**: `publish_jobs`, `publish_assets`
6. **Automation**: `auto_tasks`
7. **Monitoring**: `monitoring_targets`, `monitoring_snapshots`
8. **Walle (客服)**: `walle_conversations`, `walle_messages`, `walle_knowledge`, `walle_keywords`, `walle_orders`, `walle_shop_configs`, `walle_agent_sessions`
9. **Ark (卖家)**: `ark_server_configs`, `ark_products`, `ark_product_skus`
10. **System**: `tasks`, `notifications`, `api_logs`

## Security Architecture
- **Cookie Storage**: Fernet symmetric encryption
- **API Keys**: Fernet encryption in database
- **JWT Tokens**: 
  - Access token: 15 minutes
  - Refresh token: 7 days (stored in localStorage)
- **Password Hashing**: pbkdf2_sha256

## Background Services

### 1. Cookie Watcher (`cookie_watcher.py`)
- Connects to千帆客服工作台 via CDP (port 9222)
- Monitors token refresh events in real-time
- Saves credentials to `eva_cookies.json` + `edith_auth.json` every 30 seconds

### 2. Ark Capture (`ark_capture.py`)
- Playwright-based headless browser
- Maintains persistent login state (`data/ark_profile/`)
- Captures API requests/responses for debugging
- Daemon mode: auto-refresh cookies every 30 minutes

### 3. Scheduler (`backend/app/services/scheduler_service.py`)
- APScheduler-based task scheduling
- Handles automated operations, monitoring, cookie health checks
- Configurable via `config/*.yaml`

## Configuration Management
**Layered Configuration** (priority low → high):
1. `config/default.yaml` - Default settings
2. `CONFIG_FILE` environment variable - Custom config file
3. `.env` file - Environment variables
4. Direct environment variables (highest priority)

**Key Configuration Keys**:
- `database.type` - "sqlite" or "mysql"
- `security.secret_key` - JWT signing key
- `scheduler.enabled` - Enable background tasks
- `walle_eva_dir` - Path to千帆客服工作台 installation

## Development Workflow

### Startup Sequence
```bash
python main.py --with-frontend
  ├─ start_frontend()       # Vite dev server :5173
  ├─ start_cookie_watcher() # CDP credential watcher
  ├─ start_ark_capture()    # Ark daemon (headless)
  └─ uvicorn backend        # FastAPI :8000
```

### API Development
1. Add model in `backend/app/models/`
2. Create Alembic migration (or manual ALTER TABLE for SQLite)
3. Add schema in `backend/app/schemas/`
4. Implement service logic in `backend/app/services/`
5. Create route in `backend/app/api/`
6. Register router in `backend/app/main.py`

### Frontend Development
1. Define types in `frontend/src/types/`
2. Create page component in `frontend/src/pages/platforms/xhs/`
3. Add API client function in `frontend/src/lib/api.ts`
4. Register route in app router

## Testing Strategy
- **Test Framework**: pytest
- **Test Location**: `tests/backend/`
- **Coverage**: API endpoints, services, models
- **Run Command**: `pytest tests/backend/`

## Deployment Options
1. **Development**: `python main.py --with-frontend`
2. **Docker**: `docker compose up -d`
3. **Production**: Configure MySQL + nginx reverse proxy

## File Naming Conventions
- Backend: `snake_case.py` for files, `PascalCase` for classes, `snake_case` for functions
- Frontend: `kebab-case.tsx` for files, `PascalCase` for components
- Models: `{entity}.py` (e.g., `user.py`, `note.py`)
- API routes: `{resource}.py` (e.g., `auth.py`, `accounts.py`)
- Services: `{domain}_service.py` (e.g., `account_service.py`)
