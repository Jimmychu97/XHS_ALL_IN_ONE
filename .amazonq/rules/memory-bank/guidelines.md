# XHS_ALL_IN_ONE — Development Guidelines

## Backend Python Patterns

### API Route Structure
Every FastAPI router follows this exact pattern:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/resource", tags=["resource"])

@router.get("/items")
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Model).where(Model.user_id == current_user.id)).all()
    return paginated([{...} for item in items], page, page_size)
```

### Ownership Enforcement (universal pattern)
Every resource access checks `user_id` ownership. Cross-user access returns 404, not 403:
```python
item = db.get(Model, item_id)
if not item or item.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Not found")
```

### SDK Return Convention (apis/ layer)
All SDK methods return a 3-tuple `(success: bool, msg: str, res_json: dict | None)`:
```python
def get_note_info(self, url: str, cookies_str: str) -> tuple[bool, str, dict | None]:
    res_json = None
    try:
        # ... make request ...
        res_json = response.json()
        success, msg = res_json["success"], res_json["msg"]
    except Exception as e:
        success = False
        msg = _log_api_error(e)
    return success, msg, res_json
```
- Always initialize `res_json = None` before the try block
- Use `_log_api_error(e)` for exception logging (calls `logger.exception`)
- Never raise exceptions from SDK methods — always return `(False, str(e), None)`

### Pagination Response
Always use the `paginated()` helper for list endpoints:
```python
from backend.app.schemas.common import paginated
return paginated([{...} for item in items], page, page_size)
# Returns: {"total": N, "page": P, "page_size": S, "items": [...]}
```

### Database Session Management
- FastAPI routes: use `Depends(get_db)` — session auto-closed
- Background tasks / scheduler / threads: use `SessionLocal()` with manual `try/finally db.close()`
- Always `db.commit()` after mutations, then `db.refresh(obj)` if you need updated fields
- Use `db.begin_nested()` + `db.rollback()` for upsert operations that may conflict

### Timestamps
All datetime fields use Shanghai timezone via `shanghai_now()`:
```python
from backend.app.core.time import shanghai_now
created_at = shanghai_now()  # naive datetime, Asia/Shanghai
```
Never use `datetime.now()` or `datetime.utcnow()` for model fields.

### Credential Encryption
All sensitive data (cookies, API keys) must be encrypted before storage:
```python
from backend.app.core.security import encrypt_text, decrypt_text
encrypted = encrypt_text(raw_cookie_string)   # store this
raw = decrypt_text(encrypted_value)           # retrieve this
```

### SQLAlchemy Query Style
Use `select()` + `db.scalars()` (SQLAlchemy 2.0 style), not `db.query()`:
```python
# Preferred
items = db.scalars(select(Model).where(Model.user_id == user_id)).all()
item = db.scalars(select(Model).where(...)).first()

# Avoid (legacy style)
items = db.query(Model).filter(Model.user_id == user_id).all()
```

### Error Handling in Routes
- SDK failures → return structured error or raise `HTTPException(status_code=502)`
- Adapter/proxy failures → `HTTPException(status_code=502, detail=str(e))`
- Not found / ownership → `HTTPException(status_code=404, detail="Not found")`
- Validation errors → `HTTPException(status_code=400, detail="...")`
- Auth failures → `HTTPException(status_code=401)` (handled by `get_current_user`)

### Background Thread Pattern (Walle)
For fire-and-forget operations triggered by incoming messages:
```python
import threading
threading.Thread(
    target=_some_function,
    args=(user_id, account_id, app_cid, message),
    daemon=True,
).start()
```
Background threads must open their own `SessionLocal()` session and close it in `finally`.

### Scheduler Jobs
APScheduler jobs are registered in `build_due_publish_scheduler()`:
- `max_instances=1, coalesce=True` on all jobs to prevent overlap
- Jobs open their own `SessionLocal()` and close in `finally`
- Failures are logged with `logger.warning()`, never re-raised

### Logging
- SDK layer: `from loguru import logger` → `logger.exception(...)` for errors
- Service/scheduler layer: `import logging; logger = logging.getLogger(__name__)`
- Debug prints in walle.py use `print(f"[TAG] ...")` format for quick tracing

---

## Frontend TypeScript Patterns

### All Types in One File
All TypeScript interfaces live in `frontend/src/types/index.ts`. Never define types inline in components. Key patterns:
```typescript
// Paginated responses always use this generic
export type Paginated<T> = { total: number; page: number; page_size: number; items: T[] };

// Optional fields use `?` not `| undefined`
export type PlatformAccount = {
  id: number;
  nickname: string;
  avatar_url?: string;   // optional
  status: "active" | "healthy" | "expired" | "risk" | "unknown" | string;
};
```

### HTTP Client
Always use the `http` axios instance from `lib/api.ts`, never raw `fetch` (except SSE):
```typescript
import { http, getAccessToken } from '../lib/api'

// Regular API calls
const res = await http.get('/walle/conversations', { params: { platform_account_id: id } })
const data = await http.post('/notes/batch-save', payload)

// SSE requires fetch with manual token (EventSource can't set headers)
const token = getAccessToken()
const resp = await fetch(`/api/walle/logs/stream?token=${token}`)
```

### Component Structure
Pages follow a consistent pattern:
- State declarations at top
- `useEffect` for data loading
- Handler functions prefixed with `handle` (e.g., `handleDelete`, `handleSave`)
- Ant Design components for all UI (`antd`, `@ant-design/icons`)
- `lucide-react` for supplementary icons

### Ant Design Usage
- Use `App.useApp()` to get `message`, `modal`, `notification` inside components (avoids static function warnings)
- All tables use `antd` `Table` component
- Forms use `antd` `Form` with `Form.Item`
- Never use `message.success()` / `message.error()` directly outside `App` context

### API Key Never Exposed
Model configs return `has_api_key: boolean` instead of the actual key. The `api_key` field is write-only (send on create/update, never returned):
```typescript
export type ModelConfig = {
  id: number;
  has_api_key: boolean;  // true/false only
  // no api_key field
};
```

---

## Testing Patterns

### Test Structure
Tests use `fastapi.testclient.TestClient` with a shared `client = TestClient(app)` instance. Each test that needs a database uses `tmp_path` fixture with `_override_database(tmp_path)`:
```python
def test_something(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        # test logic
    finally:
        app.dependency_overrides.pop(db_dependency, None)
```

### Dependency Injection for Adapters
External adapters (XHS SDK, AI clients) are injected via `app.dependency_overrides`:
```python
app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
try:
    # test
finally:
    app.dependency_overrides.pop(get_pc_login_adapter, None)
```

### Fake Adapter Pattern
Fake adapters are plain classes with the same method signatures as real adapters:
```python
class FakePcLoginAdapter:
    def create_qrcode(self):
        return {"cookies": {"a1": "temp-a1"}, "qr_id": "qr-123", ...}
    
    def check_qrcode_status(self, qr_id, code, cookies):
        return {"status": "confirmed", "cookies": {...}}
```

### Auth in Tests
Helper `_register_and_get_access_token(username)` registers a user and returns the access token. All authenticated requests pass `headers={"Authorization": f"Bearer {token}"}`.

### Ownership Tests
Every resource test verifies cross-user access returns 404:
```python
intruder_response = client.get(f"/api/resource/{id}", headers={"Authorization": f"Bearer {intruder_token}"})
assert intruder_response.status_code == 404
```

---

## Architecture Conventions

### Adapter Layer (never bypass)
Never import `apis/` directly in route handlers. Always go through `backend/app/adapters/xhs/`:
```python
# Correct
from backend.app.adapters.xhs.pc_api_adapter import XhsPcApiAdapter

# Wrong — don't do this in routes
from apis.xhs_pc_apis import XHS_Apis
```
Exception: `ArkAPI` and `WalleEvaAPI` have no adapter layer — import directly from `apis/`.

### Multi-tenancy Isolation
Every database query that returns user data must filter by `user_id`. The pattern is:
```python
stmt = select(Model).where(Model.user_id == current_user.id)
```
Never return data without this filter.

### Proxy Environment Isolation
All XHS SDK calls must use `direct_xhs_request_env()` context manager to strip system proxy variables:
```python
from backend.app.adapters.xhs.request_env import direct_xhs_request_env
with direct_xhs_request_env():
    result = adapter.some_method(...)
```

### Pagination Convention
- Default `page_size=20`, max `100` for most endpoints
- Messages/comments may use `page_size=50`, max `200`
- Response always includes `total`, `page`, `page_size`, `items`

### Task Audit
Every significant operation (crawl, publish, AI rewrite, monitoring) creates a `Task` record:
```python
task = Task(
    user_id=current_user.id,
    platform="xhs",
    task_type="crawl",  # or "publish", "ai_rewrite", etc.
    status="running",
    progress=0,
    payload={...},
)
db.add(task)
db.commit()
# ... do work ...
task.status = "completed"
task.progress = 100
db.commit()
```

### SSE Endpoints
SSE endpoints use `StreamingResponse` with `media_type="text/event-stream"`. Authentication uses `?token=` query param (not Authorization header):
```python
@router.get("/stream")
async def stream(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    payload = decode_token(token)
    # ...
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### Upsert Pattern
For resources that should be created-or-updated (accounts, conversations):
```python
existing = db.scalars(select(Model).where(Model.unique_field == value)).first()
if existing:
    existing.field = new_value
    existing.updated_at = now
else:
    try:
        db.begin_nested()
        db.add(Model(...))
        db.flush()
    except Exception:
        db.rollback()
db.commit()
```

### Walle Message Dispatch Flow
When a customer message arrives via `POST /walle/push-message`:
1. Upsert conversation (`_upsert_conv`)
2. Save messages (`_save_messages`)
3. If customer message detected → spawn background thread → `_dispatch_customer_message`
4. `_dispatch_customer_message` routes: order card → check order status; SN/IMEI → GSX verify; else → AI agent

### Config Hierarchy
Settings are loaded once via `@lru_cache` on `get_settings()`. To invalidate after YAML write:
```python
from backend.app.core.config import get_settings
get_settings.cache_clear()
```
