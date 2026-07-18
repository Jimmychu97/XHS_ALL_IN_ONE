# XHS_ALL_IN_ONE — Technology Stack

## Runtime Requirements
| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 20+ |

## Backend — Python

### Framework & Server
| Package | Role |
|---|---|
| `fastapi` | Web framework, OpenAPI docs at `/docs` |
| `uvicorn` | ASGI server |
| `pydantic` / `pydantic-settings` | Data validation and settings management |

### Database
| Package | Role |
|---|---|
| `sqlalchemy>=2.0` | ORM (sync, `DeclarativeBase`) |
| `alembic` | Schema migrations (auto-applied on startup) |
| SQLite (default) | Dev/single-node; path `./data/spider_xhs.db` |
| MySQL (production) | Via `pymysql`; configured with `DATABASE_TYPE=mysql` |

### Security
| Package | Role |
|---|---|
| `python-jose[cryptography]` | JWT token creation and verification |
| `passlib[bcrypt]` | Password hashing |
| `cryptography` (Fernet) | Encrypt cookies and API keys at rest |

### Scheduling
| Package | Role |
|---|---|
| `apscheduler` | Background job scheduler for publish jobs and cookie health checks |

### HTTP / Scraping
| Package | Role |
|---|---|
| `requests` | Sync HTTP for SDK layer (`apis/`) |
| `aiohttp` | Async HTTP for backend services |
| `PyExecJS` | Executes XHS signing JS files from `static/` |
| `retry` | Decorator-based retry for flaky requests |

### Media Processing
| Package | Role |
|---|---|
| `Pillow>=9.2` | Image manipulation |
| `opencv-python` | Advanced image processing |
| `numpy` | Array operations for image work |
| `qrcode` | QR code generation for login flows |

### Utilities
| Package | Role |
|---|---|
| `loguru` | Structured logging |
| `python-dotenv` | `.env` file loading |
| `pyyaml` | YAML config parsing |
| `openpyxl` | Excel export |
| `python-multipart` | File upload support in FastAPI |

### Testing
| Package | Role |
|---|---|
| `pytest` | Test runner |
| `httpx` | Async test client for FastAPI (`TestClient`) |

## Frontend — TypeScript / React

### Core
| Package | Version | Role |
|---|---|---|
| `react` | ^19.2.3 | UI framework |
| `react-dom` | ^19.2.3 | DOM renderer |
| `typescript` | ^5.9.3 | Type safety |
| `vite` | ^7.3.0 | Build tool and dev server |

### Routing & State
| Package | Role |
|---|---|
| `react-router-dom` ^7.10.1 | Client-side routing (SPA) |
| `keepalive-for-react` / `keepalive-for-react-router` | Page state preservation across route changes |

### UI Components
| Package | Role |
|---|---|
| `antd` ^6.3.7 | Primary component library (Ant Design) |
| `@ant-design/icons` ^6.2.2 | Icon set |
| `lucide-react` ^0.562.0 | Additional icon set |
| `recharts` ^3.6.0 | Charts for analytics/dashboard |

### Drag & Drop
| Package | Role |
|---|---|
| `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` | Drag-and-drop for image asset reordering in draft editor |

### HTTP & Validation
| Package | Role |
|---|---|
| `axios` ^1.13.2 | HTTP client with JWT interceptor |
| `zod` ^4.2.1 | Runtime schema validation |

## Development Commands

### Install
```bash
pip install -r requirements.txt
npm install                        # root-level (if any)
cd frontend && npm install && cd ..
```

### Start (development)
```bash
# Backend + frontend together
python main.py --with-frontend

# Backend only
python main.py

# Frontend only
cd frontend && npm run dev

# Backend with hot reload
python main.py --reload
```

### Build (production)
```bash
cd frontend && npm run build      # outputs to frontend/dist/
```

### Docker
```bash
docker compose up -d              # starts app on port 8000
```

### Tests
```bash
pytest tests/                     # 126 tests
```

## Access Points
| URL | Purpose |
|---|---|
| `http://localhost:5173` | Frontend (dev) |
| `http://localhost:8000/docs` | FastAPI Swagger UI |
| `http://localhost:8000/api/health` | Health check endpoint |

## Vite Dev Proxy
All `/api/*` requests from the frontend dev server are proxied to `http://127.0.0.1:8000`. SSE (`text/event-stream`) responses have `cache-control: no-cache` and `x-accel-buffering: no` injected automatically.

## Configuration System
Priority (lowest → highest):
1. `config/default.yaml`
2. File at `CONFIG_FILE` env var path
3. `.env` file
4. Environment variables

Key env vars: `SECRET_KEY`, `FERNET_KEY`, `DATABASE_TYPE`, `DATABASE_URL`, `SCHEDULER_ENABLED`, `CONFIG_FILE`
