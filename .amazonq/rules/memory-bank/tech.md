# XHS_ALL_IN_ONE — Technology Stack

## Languages & Runtimes
| Layer | Language | Version |
|---|---|---|
| Backend | Python | 3.10+ |
| Frontend | TypeScript | 5.9+ |
| Signing engine | JavaScript (via PyExecJS) | Node.js 20+ |

## Backend Dependencies (requirements.txt)

### Web Framework
- `fastapi` — async REST API framework
- `uvicorn` — ASGI server
- `python-multipart` — multipart form data (file uploads)

### Database
- `sqlalchemy>=2.0` — ORM (sync engine used with thread pool)
- `alembic` — database migrations
- Supports: SQLite (dev) and MySQL via `pymysql` (prod)

### Auth & Security
- `passlib[bcrypt]` — password hashing
- `python-jose[cryptography]` — JWT tokens
- `cryptography` — Fernet symmetric encryption for cookies/API keys

### Configuration
- `pydantic` + `pydantic-settings` — settings validation and env var binding
- `python-dotenv` — `.env` file loading
- `pyyaml` — YAML config file parsing

### Scheduling
- `apscheduler` — background job scheduler (publish jobs, health checks, auto-tasks)

### HTTP & Scraping
- `requests` — sync HTTP (SDK layer)
- `aiohttp` — async HTTP
- `retry` — retry decorator for flaky network calls

### AI & Media
- `openai`-compatible HTTP calls (via `aiohttp`, no SDK dependency — any compatible endpoint)
- `Pillow>=9.2` — image processing
- `opencv-python` + `numpy` — advanced image operations
- `qrcode` — QR code generation for login flows

### Utilities
- `loguru` — structured logging
- `openpyxl` — Excel export
- `PyExecJS` — execute XHS signing JS files from Python

### Testing
- `pytest` — test runner (126 tests passing)
- `httpx` — async HTTP client for FastAPI TestClient

## Frontend Dependencies (package.json)

### Core
- `react` 19 + `react-dom` 19
- `react-router-dom` 7 — client-side routing
- `typescript` 5.9 + `vite` 7 — build tooling

### UI
- `antd` 6 — Ant Design component library
- `@ant-design/icons` 6 — icon set
- `lucide-react` — additional icon set

### Data & State
- `axios` — HTTP client with interceptors
- `zod` 4 — runtime schema validation

### Drag & Drop
- `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` — drag-and-drop for image reordering

### Charts
- `recharts` 3 — data visualization (analytics dashboard)

### Performance
- `keepalive-for-react` + `keepalive-for-react-router` — component keep-alive (preserve page state on navigation)

## Development Commands

### Start (development)
```bash
# Backend only
python main.py

# Backend + frontend (recommended)
python main.py --with-frontend

# With hot reload
python main.py --with-frontend --reload
```

### Frontend only
```bash
cd frontend
npm run dev
```

### Build frontend for production
```bash
cd frontend
npm run build
```

### Database migrations
```bash
cd backend
alembic upgrade head          # Apply all migrations
alembic revision --autogenerate -m "description"  # Generate new migration
```

### Tests
```bash
pytest tests/
```

### Docker
```bash
docker compose up -d          # Start all services
docker compose down           # Stop
docker compose logs -f        # Follow logs
```

## Runtime Ports
| Service | Default Port |
|---|---|
| Backend API | 8000 |
| Frontend dev server | 5173 |
| API docs (Swagger) | http://localhost:8000/docs |

## Database Schema
- 20+ SQLAlchemy models
- Migrations managed by Alembic in `backend/alembic/versions/`
- SQLite for local dev; MySQL for production
- Database auto-initialized on first startup via `init_db()`

## Signing Engine
XHS request signing uses reverse-engineered JavaScript loaded from `static/*.js` and executed via PyExecJS. Key files:
- `xhs_a1.js` / `xhs_a1_other.js` — PC platform a1 token
- `xhs_creator_sign.js` / `xhs_creator_signature.js` — Creator platform signing
- `xhs_rap.js`, `xhs_xray*.js` — Additional signing components

## Docker Architecture
- Multi-stage Dockerfile: Node.js build stage (frontend) + Python runtime stage
- `docker-compose.yml` orchestrates backend service with volume mounts for data persistence
- Production mode: `FRONTEND_SERVE_STATIC=true` serves built frontend from FastAPI static files
