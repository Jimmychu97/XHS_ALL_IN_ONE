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
<<<<<<< HEAD
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
=======
| Validation | Pydantic / pydantic-settings | v2 |
| Auth | python-jose (JWT) + passlib[bcrypt] | latest |
| Encryption | cryptography (Fernet) | latest |
| Scheduler | APScheduler | latest |
| HTTP client | requests + aiohttp + httpx | latest |
| JS execution | PyExecJS | latest (runs signing JS) |
| Image processing | Pillow 9.2+, opencv-python, numpy | latest |
| QR codes | qrcode | latest |
| Config | PyYAML + python-dotenv | latest |
| Testing | pytest + httpx | latest |
| Logging | loguru | latest |
>>>>>>> 565ca0d81789bed899163a193de2ada985367970

## Frontend Stack

| Layer | Technology | Version |
|---|---|---|
<<<<<<< HEAD
| UI framework | React | 19 |
| Build tool | Vite | 7 |
| Language | TypeScript | 5.9 |
| Routing | React Router DOM | 7 |
| UI components | Ant Design (antd) | 6 |
=======
| Framework | React | 19 |
| Language | TypeScript | 5.9+ |
| Build tool | Vite | 7 |
| Routing | React Router DOM | 7 |
| UI library | Ant Design (antd) | 6 |
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
| Icons | @ant-design/icons + lucide-react | latest |
| HTTP client | Axios | 1.x |
| Charts | Recharts | 3 |
| Drag & drop | @dnd-kit/core + sortable + utilities | latest |
<<<<<<< HEAD
| Validation | Zod | 4 |
=======
| Schema validation | Zod | 4 |
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
| Keep-alive | keepalive-for-react + keepalive-for-react-router | 5 |

## Database
- Development: SQLite (`./data/spider_xhs.db`)
- Production: MySQL 8.0 (optional, uncomment in docker-compose.yml)
<<<<<<< HEAD
- Migrations auto-run at startup via `init_db()` → Alembic `upgrade head`

## Configuration System
Layered priority (lowest → highest):
1. `config/default.yaml`
2. Custom YAML via `CONFIG_FILE` env var
3. `.env` file
4. Environment variables

Key env vars: `SECRET_KEY`, `FERNET_KEY`, `DATABASE_TYPE`, `DATABASE_URL`, `SCHEDULER_ENABLED`, `CONFIG_FILE`
=======
- 25 tables, all resources isolated by `user_id`
>>>>>>> 565ca0d81789bed899163a193de2ada985367970

## Development Commands

### Install
```bash
git clone https://github.com/cv-cat/XHS_ALL_IN_ONE.git
cd XHS_ALL_IN_ONE
pip install -r requirements.txt
<<<<<<< HEAD
npm install                        # root (for asar tooling)
=======
npm install
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
cd frontend && npm install && cd ..
```

### Start (development)
```bash
# Backend only
python main.py

<<<<<<< HEAD
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
=======
# Backend with hot-reload
python main.py --reload

# Frontend only (from frontend/)
npm run dev
```

### Build frontend (production)
```bash
cd frontend && npm run build
```

### Docker
```bash
docker compose up -d
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
```

### Tests
```bash
pytest tests/
```

<<<<<<< HEAD
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
=======
### Database migrations
```bash
# Alembic auto-runs at startup via init_db()
# Manual migration generation:
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## URLs (default dev)
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

## Vite Dev Proxy
All `/api` requests from the frontend are proxied to `http://127.0.0.1:8000`. SSE (`text/event-stream`) responses have `cache-control: no-cache` and `x-accel-buffering: no` injected automatically.

## Configuration Priority
`config/default.yaml` < `CONFIG_FILE` env var < `.env` file < environment variables

Key env vars: `SECRET_KEY`, `FERNET_KEY`, `DATABASE_TYPE`, `DATABASE_URL`, `SCHEDULER_ENABLED`, `BACKEND_CORS_ORIGINS`

## Security
- JWT tokens for API auth (Bearer scheme)
- Fernet symmetric encryption for cookies and API keys at rest
- Fernet key auto-derived from `SECRET_KEY` via SHA-256 + base64 if not set explicitly
- All sensitive data (cookies, model API keys) encrypted before DB storage

## Walle CS Workbench (External Dependency)
Requires Qianfan customer service desktop app (Electron) running with remote debugging on port 9222. `cookie_watcher.py` (at `F:\eva\`) connects via CDP WebSocket to capture and persist auth tokens.
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
