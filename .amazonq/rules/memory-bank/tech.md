# Technology Stack

## Backend Stack

### Core Framework
- **Python**: 3.10+
- **Web Framework**: FastAPI 0.100+
- **ASGI Server**: Uvicorn
- **Process Manager**: Built-in subprocess management in `main.py`

### Database & ORM
- **Primary Database**: SQLite (default, file: `data/spider_xhs.db`)
- **Production Database**: MySQL (configurable via `DATABASE_TYPE=mysql`)
- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Connection String**: 
  - SQLite: `sqlite:///./data/spider_xhs.db`
  - MySQL: Configurable via `DATABASE_URL` environment variable

### Security & Authentication
- **Password Hashing**: passlib[bcrypt] - pbkdf2_sha256
- **JWT Tokens**: python-jose[cryptography]
  - Access Token: 15 minutes expiry
  - Refresh Token: 7 days expiry, stored in localStorage
- **Cookie Encryption**: cryptography (Fernet symmetric encryption)
- **CORS**: FastAPI built-in CORS middleware

### Validation & Serialization
- **Data Validation**: Pydantic 2.x
- **Settings Management**: pydantic-settings
- **Configuration Format**: YAML (pyyaml)

### Task Scheduling
- **Scheduler**: APScheduler
- **Job Store**: SQLAlchemy (persistent)
- **Trigger Types**: 
  - Interval trigger (hourly)
  - Cron trigger (daily/weekly)
- **Configuration**: `scheduler.enabled` in YAML config

### HTTP Client
- **Primary**: requests (synchronous)
- **Async Support**: aiohttp
- **Testing Client**: httpx

### Media Processing
- **Image Processing**: Pillow >= 9.2
- **Computer Vision**: opencv-python, numpy
- **QR Code**: qrcode

### Logging & Monitoring
- **Logging**: loguru
- **Excel Export**: openpyxl

### Testing
- **Framework**: pytest
- **Test Client**: httpx (for async API testing)

### Reverse Engineering Tools
- **JavaScript Execution**: PyExecJS
- **Browser Automation**: 
  - Playwright (for Ark platform)
  - CDP (Chrome DevTools Protocol) for千帆客服工作台

## Frontend Stack

### Core Framework
- **Runtime**: Node.js 20+
- **Framework**: React 19.2.3
- **Language**: TypeScript 5.9.3
- **Build Tool**: Vite 7.3.0

### UI Library
- **Component Library**: Ant Design 6.3.7
- **Icons**: @ant-design/icons 6.2.2
- **Additional Icons**: lucide-react 0.562.0

### Routing & State
- **Router**: react-router-dom 7.10.1
- **Route Caching**: 
  - keepalive-for-react 5.0.11
  - keepalive-for-react-router 5.0.7

### Data Visualization
- **Charts**: recharts 3.6.0

### Drag & Drop
- **DnD Library**: @dnd-kit 
  - core: 6.3.1
  - sortable: 10.0.0
  - utilities: 3.2.2

### HTTP & Validation
- **HTTP Client**: axios 1.13.2
- **Schema Validation**: zod 4.2.1

### Development Tools
- **Vite Plugin**: @vitejs/plugin-react 5.1.2
- **Type Definitions**: 
  - @types/react 19.2.14
  - @types/react-dom 19.2.3

## SDK Layer Stack

### JavaScript Dependencies (`package.json`)
- **Encryption**: crypto-js 4.2.0
- **DOM Environment**: jsdom 26.0.0

### Signature Implementation
- **Algorithm**: Custom reverse-engineered signature algorithms
- **Execution**: PyExecJS runs JavaScript signature functions
- **Key Files**:
  - `xhs_a1.js` - A1 signature generation
  - `xhs_creator_sign.js` - Creator platform signing
  - `xhs_xray.js` - X-Ray anti-scraping bypass

## Development Commands

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend only
python main.py

# Start backend with auto-reload
python main.py --reload

# Start backend with frontend
python main.py --with-frontend

# Run tests
pytest tests/backend/

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Frontend Development
```bash
# Install dependencies
cd frontend && npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### SDK Debugging
```bash
# Playwright browser automation
python ark_capture.py                # Interactive mode
python ark_capture.py --daemon       # Background mode
python ark_capture.py --sync-skus    # Batch SKU sync

# Cookie watcher for 千帆客服
python cookie_watcher.py             # Starts CDP listener
```

### Docker Deployment
```bash
# Build and start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Environment Variables

### Required
```bash
SECRET_KEY=your-jwt-secret-key          # JWT signing
```

### Optional
```bash
DATABASE_TYPE=sqlite                     # or mysql
DATABASE_URL=mysql://user:pass@host/db   # MySQL connection string
CONFIG_FILE=/path/to/config.yaml         # Custom config file
SCHEDULER_ENABLED=true                   # Enable background tasks
SERVER_HOST=0.0.0.0                      # Backend bind host
SERVER_PORT=8000                         # Backend port
```

## Configuration Files

### Backend
- `config/default.yaml` - Default settings
- `config/production.yaml` - Production overrides
- `requirements.txt` - Python dependencies
- `backend/alembic.ini` - Alembic configuration

### Frontend
- `frontend/package.json` - Node dependencies & scripts
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/vite.config.ts` - Vite build configuration
- `frontend/index.html` - HTML template

### Docker
- `Dockerfile` - Multi-stage build definition
- `docker-compose.yml` - Service orchestration
- `.dockerignore` - Exclude patterns

## Build Outputs

### Backend
- **Location**: N/A (interpreted language)
- **Entry Point**: `backend.app.main:app`
- **Port**: 8000 (configurable)

### Frontend
- **Build Command**: `npm run build`
- **Output Directory**: `frontend/dist/`
- **Assets**: Static HTML, JS, CSS bundles
- **Port**: 5173 (dev), 80 (production via nginx)

## API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: Auto-generated by FastAPI

## Version Requirements Summary

| Component | Minimum Version | Recommended |
|-----------|----------------|-------------|
| Python | 3.10 | 3.11+ |
| Node.js | 20.x | 20.x LTS |
| FastAPI | 0.100 | Latest |
| SQLAlchemy | 2.0 | 2.0+ |
| React | 19.x | 19.x |
| TypeScript | 5.9 | 5.9+ |
| Ant Design | 6.x | 6.x |
| Vite | 7.x | 7.x |

## Dependency Management
- **Python**: pip with `requirements.txt`
- **Node.js**: npm with `package-lock.json`
- **Version Locking**: Dependencies are locked for reproducibility

## Performance Considerations
- **Database**: SQLite suitable for single-user, MySQL recommended for multi-user production
- **Background Tasks**: APScheduler runs in separate thread, non-blocking
- **Browser Automation**: Playwright headless mode for minimal resource usage
- **Frontend**: Vite HMR for fast development, optimized production builds
