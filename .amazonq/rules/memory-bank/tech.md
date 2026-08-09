# XHS_ALL_IN_ONE — Technology Stack

## Runtime Requirements
- Python 3.10+
- Node.js 20+

## Backend Stack

### Core Framework
- **FastAPI** 0.100+ — async REST API framework
- **Uvicorn** — ASGI server
- **SQLAlchemy** 2.0+ — ORM with declarative models
- **Alembic** — database migrations

### Authentication & Security
- **python-jose[cryptography]** — JWT token encode/decode
- **passlib[bcrypt]** — password hashing
- **cryptography (Fernet)** — symmetric encryption for cookies and API keys

### Scheduling
- **APScheduler** — background job scheduling for auto-tasks, publish jobs, and heartbeat checks

### HTTP & Scraping
- **requests** — synchronous HTTP for SDK calls
- **aiohttp** — async HTTP
- **PyExecJS** — executes reverse-engineered JS signing files from `static/`
- **retry** — automatic retry decorator

### AI & Media
- **Pillow** 9.2+ — image processing
- **opencv-python** + **numpy** — advanced image operations
- **qrcode** — QR code generation for login flows

### Data & Config
- **pydantic** + **pydantic-settings** — settings validation and env var parsing
- **pyyaml** — YAML config file loading
- **python-dotenv** — `.env` file support
- **openpyxl** — Excel export
- **loguru** — structured logging

### Testing
- **pytest** — test runner (126 tests passing)
- **httpx** — async HTTP client for FastAPI TestClient

### Optional / External
- **playwright** — used by `ark_capture.py` for Ark seller backend login
- **websockets** — used by `cookie_watcher.py` for CDP WebSocket connection

## Frontend Stack

### Core
- **React 19** — UI framework
- **TypeScript 5.9** — strict mode enabled (`"strict": true`)
- **Vite 7** — build tool and dev server
- **React Router DOM 7** — client-side routing

### UI Components
- **Ant Design (antd) 6** — primary component library
- **@ant-design/icons 6** — icon set
- **lucide-react** — additional icons
- **recharts 3** — data visualization charts

### State & Data
- **axios 1.13** — HTTP client with JWT interceptor
- **zod 4** — runtime schema validation

### Drag & Drop
- **@dnd-kit/core**, **@dnd-kit/sortable**, **@dnd-kit/utilities** — drag-and-drop for image reordering in draft workshop

### Performance
- **keepalive-for-react** + **keepalive-for-react-router** — component keep-alive to preserve page state across navigation

### Build Config
- Target: ES2020
- Module resolution: Node
- JSX: react-jsx (no React import needed)
- Vite dev proxy: `/api` → `http://127.0.0.1:8000`
- SSE proxy: disables buffering for `text/event-stream` responses

## Database

| Mode | Driver | Connection |
|---|---|---|
| SQLite (default) | Built-in | `./data/spider_xhs.db` |
| MySQL (production) | `pymysql` | Configured via YAML or env vars |

## Development Commands

### Install
```bash
pip install -r requirements.txt
npm install                        # root (optional scripts)
cd frontend && npm install && cd ..
```

### Start (Development)
```bash
# Backend + frontend together
python main.py --with-frontend

# Backend only
python main.py

# Backend with hot reload
python main.py --reload

# Frontend only
cd frontend && npm run dev
```

### Build (Production)
```bash
cd frontend && npm run build      # outputs to frontend/dist/
```

### Docker
```bash
docker compose up -d
```

### Database Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Tests
```bash
pytest tests/
```

## Service Ports
| Service | Default Port |
|---|---|
| FastAPI backend | 8000 |
| Vite frontend dev server | 5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Qianfan workbench CDP | 9222 |

## Environment Variables / Config Keys

| Key | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-only-change-me` | JWT signing secret |
| `FERNET_KEY` | `""` (auto-generated) | Fernet encryption key for cookies |
| `DATABASE_TYPE` | `sqlite` | `sqlite` or `mysql` |
| `DATABASE_URL` | (built from components) | Full DB connection string override |
| `SCHEDULER_ENABLED` | `false` | Enable APScheduler |
| `CONFIG_FILE` | — | Path to override YAML config |
| `WALLE_EVA_DIR` | `""` | Path to Qianfan workbench install dir |

## Signing Architecture

XHS API requests require dynamic signatures computed by reverse-engineered JavaScript:
1. Python calls `PyExecJS` to execute JS files in `static/`
2. JS computes `x-s`, `x-t`, `x-s-common` headers
3. Headers injected into HTTP requests via `xhs_utils/`

This is the core technical mechanism enabling all XHS API access.
