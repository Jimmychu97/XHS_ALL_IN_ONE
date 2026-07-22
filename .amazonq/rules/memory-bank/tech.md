# XHS_ALL_IN_ONE — Technology Stack

## Runtime Requirements
- Python 3.10+
- Node.js 20+

## Backend Stack

| Layer | Technology | Version |
|---|---|---|
| Web framework | FastAPI | 0.100+ |
| ASGI server | Uvicorn | latest |
| ORM | SQLAlchemy | 2.0+ |
| Migrations | Alembic | latest |
| Validation | Pydantic / pydantic-settings | latest |
| Scheduler | APScheduler | latest |
| Auth | python-jose (JWT HS256) + passlib (bcrypt) | latest |
| Encryption | cryptography (Fernet) | latest |
| HTTP client | requests + aiohttp | latest |
| JS execution | PyExecJS | latest (runs XHS signing JS) |
| Image processing | Pillow + opencv-python + numpy | latest |
| Logging | loguru | latest |
| Config | PyYAML + python-dotenv | latest |
| Testing | pytest + httpx | latest |

## Frontend Stack

| Layer | Technology | Version |
|---|---|---|
| UI framework | React | 19 |
| Build tool | Vite | 7 |
| Language | TypeScript | 5.9 |
| Routing | React Router DOM | 7 |
| UI components | Ant Design (antd) | 6 |
| Icons | @ant-design/icons + lucide-react | latest |
| HTTP client | Axios | 1.x |
| Charts | Recharts | 3 |
| Drag & drop | @dnd-kit/core + sortable + utilities | latest |
| Validation | Zod | 4 |
| Keep-alive | keepalive-for-react + keepalive-for-react-router | 5 |

## Database
- Development: SQLite (`./data/spider_xhs.db`)
- Production: MySQL 8.0 (optional, uncomment in docker-compose.yml)
- Migrations auto-run at startup via `init_db()` → Alembic `upgrade head`

## Configuration System
Layered priority (lowest → highest):
1. `config/default.yaml`
2. Custom YAML via `CONFIG_FILE` env var
3. `.env` file
4. Environment variables

Key env vars: `SECRET_KEY`, `FERNET_KEY`, `DATABASE_TYPE`, `DATABASE_URL`, `SCHEDULER_ENABLED`, `CONFIG_FILE`

## Development Commands

### Install
```bash
pip install -r requirements.txt
npm install                        # root (for asar tooling)
cd frontend && npm install && cd ..
```

### Start (development)
```bash
# Backend only
python main.py

# Backend + frontend dev server
python main.py --with-frontend

# With hot reload
python main.py --with-frontend --reload
```

### Frontend standalone
```bash
cd frontend
npm run dev      # Vite dev server at http://127.0.0.1:5173
npm run build    # Production build → frontend/dist/
npm run preview  # Preview production build
```

### Tests
```bash
pytest tests/
```

### Docker
```bash
docker compose up -d              # Start app (SQLite)
docker compose down
```

### Database migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## API Endpoints
- Backend API: `http://localhost:8000/api/`
- API docs (Swagger): `http://localhost:8000/docs`
- Frontend dev: `http://localhost:5173`
- Health check: `GET /api/health`

## Vite Proxy
All `/api/*` requests from the frontend dev server are proxied to `http://127.0.0.1:8000`. SSE (`text/event-stream`) responses have `cache-control: no-cache` and `x-accel-buffering: no` injected automatically.

## XHS Signing
Signature computation is done by executing bundled JavaScript files in `static/` via PyExecJS. Key files:
- `static/xhs_a1.js` — PC-side a1 token
- `static/xhs_creator_sign.js` — Creator platform signing
- `static/xhs_rap.js` — Request signing
- `static/xhs_xray.js` — Anti-bot fingerprinting

## Storage Paths
- Media files: `backend/app/storage/media/`
- Export files: `backend/app/storage/exports/`
- Both are Docker volume-mounted for persistence

## Walle Customer Service (External Dependency)
Requires 千帆客服工作台 (Electron app) installed at `F:\eva\` with CDP remote debugging enabled on port 9222. `cookie_watcher.py` is auto-started by `main.py` if present at `F:\eva\cookie_watcher.py`.
