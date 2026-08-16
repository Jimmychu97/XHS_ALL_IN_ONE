# XHS_ALL_IN_ONE — Technology Stack

## Runtime Requirements

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 20+ |
| npm | bundled with Node.js |

## Backend — Python

### Core Framework
| Package | Purpose |
|---|---|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `pydantic` / `pydantic-settings` | Data validation + settings management |
| `sqlalchemy>=2.0` | ORM (sync, declarative) |
| `alembic` | Database migrations |
| `apscheduler` | Scheduled tasks (publish jobs, auto-tasks, heartbeat) |

### Security & Auth
| Package | Purpose |
|---|---|
| `cryptography` | Fernet symmetric encryption for cookies/API keys |
| `python-jose[cryptography]` | JWT creation and verification |
| `passlib[bcrypt]` | Password hashing (pbkdf2_sha256) |

### HTTP & Scraping
| Package | Purpose |
|---|---|
| `requests` | Synchronous HTTP for XHS SDK calls |
| `aiohttp` | Async HTTP |
| `PyExecJS` | Execute JS signing files from Python |
| `playwright` | Chromium automation for Ark/Walle CDP (install separately) |

### Utilities
| Package | Purpose |
|---|---|
| `loguru` | Structured logging |
| `pyyaml` | YAML config parsing |
| `python-dotenv` | `.env` file support |
| `openpyxl` | Excel export |
| `opencv-python` / `numpy` | Image processing |
| `Pillow>=9.2` | Image utilities |
| `qrcode` | QR code generation for login |
| `retry` | Retry decorator |
| `python-multipart` | File upload support |
| `httpx` | Async HTTP client (used in tests) |
| `pytest` | Test framework |

## Frontend — TypeScript / React

### Core
| Package | Version | Purpose |
|---|---|---|
| `react` | ^19.2.3 | UI framework |
| `react-dom` | ^19.2.3 | DOM rendering |
| `react-router-dom` | ^7.10.1 | Client-side routing |
| `typescript` | ^5.9.3 | Type safety |
| `vite` | ^7.3.0 | Build tool + dev server |

### UI Components
| Package | Purpose |
|---|---|
| `antd` ^6.3.7 | Primary UI component library (Ant Design) |
| `@ant-design/icons` | Icon set |
| `lucide-react` | Additional icons |
| `recharts` | Charts for analytics dashboard |

### Functionality
| Package | Purpose |
|---|---|
| `axios` | HTTP client (wrapped in `lib/api.ts`) |
| `@dnd-kit/core` + `sortable` + `utilities` | Drag-and-drop for asset reordering |
| `zod` | Runtime schema validation |
| `keepalive-for-react` / `keepalive-for-react-router` | Page state preservation |

## Database

| Mode | Engine | Config |
|---|---|---|
| Development (default) | SQLite | `./data/spider_xhs.db` |
| Production | MySQL 8.0 | `DATABASE_TYPE=mysql` + `DATABASE_URL` |

Database migrations managed by Alembic (`backend/alembic/versions/`). Some schema changes applied via raw `ALTER TABLE` in `database.py` for SQLite compatibility.

## Configuration System

Priority (lowest → highest): `config/default.yaml` → `CONFIG_FILE` env var → `.env` → environment variables

Key config sections:
```yaml
server:    host, port, cors_origins
database:  type (sqlite/mysql), paths/credentials
security:  secret_key (JWT), fernet_key (encryption)
scheduler: enabled, interval_seconds
frontend:  serve_static, build_dir
walle:     eva_dir (path to 千帆客服 installation)
```

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt
npm install
cd frontend && npm install && cd ..

# Start (backend + frontend + cookie_watcher + ark_capture)
python main.py --with-frontend

# Backend only
python main.py

# Hot reload (backend code changes auto-apply)
python main.py --reload

# Frontend only (from frontend/)
npm run dev

# Build frontend for production
cd frontend && npm run build

# Run tests
pytest tests/

# Database migration
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Docker

```bash
# Start with Docker Compose
docker compose up -d

# With MySQL (uncomment mysql service in docker-compose.yml first)
DATABASE_TYPE=mysql docker compose up -d
```

Dockerfile uses multi-stage build. Volumes: `./data`, `./config`, `./backend/app/storage/`.

## Ports

| Service | Default Port |
|---|---|
| Backend API | 8000 |
| Frontend dev server | 5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Ark CDP debug port | 9222 |

## Signing Infrastructure

XHS API calls require request signing. Two strategies:

1. **Node.js subprocess** (`PyExecJS`): Python calls JS files in `static/` via `xhs_utils/` wrappers
   - `xhs_a1.js`, `xhs_main_260411.js` — PC signing
   - `xhs_creator_sign.js`, `xhs_creator_260411.js` — Creator signing

2. **CDP (Chrome DevTools Protocol)**: Playwright connects to running browser, lets page's own JS sign requests
   - Used for Ark (`ark_capture.py`) and Walle (`cookie_watcher.py`)
   - Ark requires Playwright: `pip install playwright && playwright install chromium`
