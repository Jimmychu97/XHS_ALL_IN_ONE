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

## Frontend Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | React | 19 |
| Language | TypeScript | 5.9+ |
| Build tool | Vite | 7 |
| Routing | React Router DOM | 7 |
| UI library | Ant Design (antd) | 6 |
| Icons | @ant-design/icons + lucide-react | latest |
| HTTP client | Axios | 1.x |
| Charts | Recharts | 3 |
| Drag & drop | @dnd-kit/core + sortable + utilities | latest |
| Schema validation | Zod | 4 |
| Keep-alive | keepalive-for-react + keepalive-for-react-router | 5 |

## Database
- Development: SQLite (`./data/spider_xhs.db`)
- Production: MySQL 8.0 (optional, uncomment in docker-compose.yml)
- 25 tables, all resources isolated by `user_id`

## Development Commands

### Install
```bash
git clone https://github.com/cv-cat/XHS_ALL_IN_ONE.git
cd XHS_ALL_IN_ONE
pip install -r requirements.txt
npm install
cd frontend && npm install && cd ..
```

### Start (development)
```bash
# Backend + frontend together
python main.py --with-frontend

# Backend only
python main.py

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
```

### Tests
```bash
pytest tests/
```

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
