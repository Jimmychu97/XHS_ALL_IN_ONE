# XHS_ALL_IN_ONE — Development Guidelines

## Python Code Patterns

### SDK Return Convention (100% of apis/)
All SDK methods return a 3-tuple `(success: bool, msg: str, res_json: dict | None)`:
```python
def get_note_info(self, url: str, cookies_str: str) -> tuple[bool, str, dict]:
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
Callers always check `if not success: raise Exception(msg)` before accessing data.

### Pagination Pattern (all list endpoints)
All paginated list endpoints return a consistent shape via `paginated()` from `backend/app/schemas/common.py`:
```python
return paginated([{...} for item in items], page, page_size)
# → {"total": N, "page": P, "page_size": S, "items": [...]}
```

### Multi-tenant Ownership Enforcement (all API routers)
Every resource is scoped by `user_id`. Cross-user access returns 404 (not 403):
```python
item = db.get(Model, item_id)
if not item or item.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Not found")
```
This pattern appears in every router for every resource type.

### FastAPI Router Structure
```python
router = APIRouter(prefix="/resource", tags=["resource"])

@router.get("/")
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ...
```
- Always inject `current_user` via `Depends(get_current_user)` for auth
- Always inject `db` via `Depends(get_db)` for database access
- Use `Query(default, ge=..., le=...)` for validated query params

### Dependency Injection for Adapters (testability)
Adapters are injected via FastAPI `Depends` to enable test overrides:
```python
def get_pc_login_adapter() -> XhsPcLoginAdapter:
    return XhsPcLoginAdapter()

@router.post("/qrcode")
def create_qrcode(adapter = Depends(get_pc_login_adapter), ...):
    ...
```
Tests override with: `app.dependency_overrides[get_pc_login_adapter] = lambda: FakeAdapter()`

### SQLAlchemy Query Style
Use `select()` + `db.scalars()` (SQLAlchemy 2.0 style), not legacy `db.query()`:
```python
# Preferred
items = db.scalars(
    select(Model)
    .where(Model.user_id == current_user.id)
    .order_by(Model.created_at.desc())
).all()

# Also used in older code (acceptable)
items = db.query(Model).filter(Model.user_id == user_id).all()
```

### Upsert Pattern
For create-or-update operations, check existence first then branch:
```python
existing = db.scalars(select(Model).where(...)).first()
if existing:
    existing.field = new_value
    existing.updated_at = now
else:
    db.add(Model(...))
db.commit()
```

### Encrypted Storage
All sensitive data (cookies, API keys) uses Fernet encryption:
```python
from backend.app.services.credential_service import decrypt_text, encrypt_text
# or
from backend.app.core.security import decrypt_text, encrypt_text

encrypted = encrypt_text(raw_value)
raw = decrypt_text(encrypted_value)
```
Never store cookies or API keys in plaintext.

### Background Tasks with Threading
Long-running operations triggered by webhooks use `threading.Thread`:
```python
import threading
threading.Thread(
    target=_dispatch_customer_message,
    args=(user_id, account_id, app_cid, message),
    daemon=True,
).start()
```

### Settings Access
Always use the cached singleton:
```python
from backend.app.core.config import get_settings
settings = get_settings()  # @lru_cache — safe to call repeatedly
```

### Database Session in Background Jobs
Background jobs (scheduler, threads) must manage their own sessions:
```python
from backend.app.core.database import SessionLocal

db = SessionLocal()
try:
    # ... do work ...
    db.commit()
finally:
    db.close()
```

### Nested Transaction for Concurrent Upserts
Use `db.begin_nested()` + `db.rollback()` to handle race conditions:
```python
try:
    db.begin_nested()
    db.add(new_record)
    db.flush()
except Exception:
    db.rollback()
```

### Timezone
Always use Shanghai time for timestamps:
```python
from backend.app.core.time import shanghai_now
now = shanghai_now()
```

### Logging
Use `loguru` in SDK layer, standard `logging` in backend services:
```python
# apis/ layer
from loguru import logger
logger.exception(f'XHS PC API request failed: {error}')

# backend/ layer
import logging
logger = logging.getLogger(__name__)
logger.warning(f"Task {task.id} failed: {exc}")
```

### Error Handling in API Routes
SDK/adapter failures that are user-facing should raise `HTTPException`:
```python
try:
    result = adapter.do_something()
except RuntimeError as exc:
    raise HTTPException(status_code=502, detail=str(exc))
```

### SSE Streaming Responses
```python
from fastapi.responses import StreamingResponse

async def generate():
    for entry in history:
        yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
    while True:
        try:
            entry = await asyncio.wait_for(q.get(), timeout=25)
            yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield "data: {\"ping\": true}\n\n"

return StreamingResponse(
    generate(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```
SSE endpoints use `token` query param for auth (EventSource can't set headers):
```python
@router.get("/logs/stream")
async def log_stream(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    payload = decode_token(token)
    ...
```

### Delete Response Shape
Successful deletes return `{"id": item_id, "status": "deleted"}`.

### Serialization Helpers
Complex models use dedicated `_serialize_*` functions rather than inline dicts:
```python
def _serialize_publish_job(job: PublishJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "published_at": job.published_at.isoformat() if job.published_at else None,
        ...
    }
```

---

## Testing Patterns

### Test Database Override
Every test that touches the DB uses `_override_database(tmp_path)` to inject an isolated SQLite DB:
```python
def _override_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", ...)
    TestingSessionLocal = sessionmaker(...)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return get_db
```
Always clean up with `app.dependency_overrides.pop(key, None)` in `finally`.

### Fake Adapter Classes
Tests use Fake* classes that implement the same interface as real adapters:
```python
class FakePcLoginAdapter:
    def create_qrcode(self):
        return {"cookies": {...}, "qr_id": "qr-123", ...}

    def check_qrcode_status(self, qr_id, code, cookies):
        return {"status": "confirmed", "cookies": {...}}
```

### Auth Helper
```python
def _register_and_get_access_token(username: str = "operator") -> str:
    response = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    return response.json()["access_token"]
```

### Ownership Tests
Every resource test verifies both owner access (200) and cross-user access (404):
```python
intruder_response = client.get(f"/api/resource/{id}", headers={"Authorization": f"Bearer {intruder_token}"})
assert intruder_response.status_code == 404

owner_response = client.get(f"/api/resource/{id}", headers={"Authorization": f"Bearer {owner_token}"})
assert owner_response.status_code == 200
```

### Frontend Source Assertions
Some tests read frontend source files directly to assert UI invariants:
```python
source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()
assert "antd" in source
assert "检查" in source
```

---

## TypeScript / Frontend Patterns

### All Types in One File
All TypeScript types are centralized in `frontend/src/types/index.ts`. No inline type definitions in component files.

### Generic Paginated Type
```typescript
export type Paginated<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};
```

### Optional Fields with `?`
API response types use `?` for fields that may be absent:
```typescript
export type PlatformAccount = {
  id: number;
  nickname: string;
  avatar_url?: string;        // optional
  status_message?: string;    // optional
  profile?: Record<string, unknown>;
};
```

### Union String Types for Status Fields
Status fields use union types with a fallback `string`:
```typescript
status: "active" | "healthy" | "expired" | "risk" | "unknown" | string;
```

### Payload vs Response Type Pairs
Every resource has separate Payload (input) and Response (output) types:
```typescript
export type ModelConfigPayload = { name: string; model_type: ModelType; ... };
export type ModelConfig = { id: number; name: string; has_api_key: boolean; ... };
```

### Intersection Types for Extensions
Extended types use intersection (`&`) rather than re-declaring fields:
```typescript
export type KeywordGroupDetail = KeywordGroup & {
  trend: { total_matches: number; ... };
};
```

### Ant Design as Primary UI Library
All UI components use Ant Design (antd). Tests assert `"antd" in source` for every page component.

### API Client Pattern
All HTTP calls go through `frontend/src/lib/api.ts` (Axios instance with JWT interceptor). Never call `fetch` directly.

---

## Architecture Rules

1. **Never call `apis/` directly from routers** — always go through `backend/app/adapters/xhs/`
2. **All resources must be `user_id`-scoped** — no shared global state between users
3. **Cookies and API keys must be Fernet-encrypted** before DB storage
4. **Scheduler jobs must use `SessionLocal()` directly** — not FastAPI's `get_db()` dependency
5. **SSE auth uses `token` query param** — not Authorization header (EventSource limitation)
6. **Delete operations cascade** — child records (assets, comments, tags) must be cleaned up
7. **Adapter factory pattern for testability** — inject adapters via `Depends()` so tests can override
8. **`from __future__ import annotations`** at top of all backend Python files
9. **`get_settings()` is `@lru_cache`** — safe to call anywhere, invalidate with `get_settings.cache_clear()`
10. **Alembic for all schema changes** — never modify DB schema outside of migration files
