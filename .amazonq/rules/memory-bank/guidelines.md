# XHS_ALL_IN_ONE — Development Guidelines

## Python Code Style

### Module Header
All Python files start with `from __future__ import annotations` for forward reference support.

### Return Convention — SDK Layer (apis/)
Every SDK method returns a `(success: bool, msg: str, res_json: dict | list | None)` tuple:
```python
def get_note_info(self, url: str, cookies_str: str, proxies: dict = None):
    res_json = None
    try:
        # ... HTTP call ...
        success, msg = res_json["success"], res_json["msg"]
    except Exception as e:
        success = False
        msg = _log_api_error(e)
    return success, msg, res_json
```
- Always initialize `res_json = None` before the try block
- Use `logger.exception()` via `_log_api_error()` helper for error logging
- Never raise exceptions from SDK methods — always catch and return `(False, msg, None)`

### Pagination Pattern — Backend APIs
All list endpoints return a consistent paginated shape via `paginated()` helper:
```python
from backend.app.schemas.common import paginated
return paginated(items_list, page, page_size)
# → {"total": N, "page": P, "page_size": S, "items": [...]}
```

### FastAPI Route Patterns
```python
router = APIRouter(prefix="/walle", tags=["walle"])

@router.get("/conversations")
def list_conversations(
    platform_account_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
```
- Always inject `current_user: User = Depends(get_current_user)` for protected routes
- Always inject `db: Session = Depends(get_db)` for DB access
- Use `Query(default, ge=..., le=...)` for validated query params
- Use `Body(..., embed=True)` for single-field body params

### Multi-tenant Ownership Enforcement
Cross-user access always returns 404 (not 403) to avoid leaking resource existence:
```python
item = db.get(Model, item_id)
if not item or item.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Not found")
```
This pattern appears in every CRUD endpoint across all resources.

### SQLAlchemy Query Style
Use `select()` + `db.scalars()` (SQLAlchemy 2.0 style), not legacy `db.query()`:
```python
# Preferred
items = db.scalars(
    select(WalleConversation)
    .where(WalleConversation.user_id == current_user.id)
    .order_by(WalleConversation.updated_at.desc())
).all()

# Also used for single items
item = db.scalars(select(Model).where(...)).first()
```
Legacy `db.query()` is still present in some older service files — prefer `select()` for new code.

### Upsert Pattern
Use `db.begin_nested()` + `db.rollback()` for safe upsert on potential unique constraint violations:
```python
try:
    db.begin_nested()
    db.add(WalleConversation(...))
    db.flush()
except Exception:
    db.rollback()
```

### ORM Model Definition
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
```
- Use `Mapped[T]` + `mapped_column()` (SQLAlchemy 2.0 style)
- Always use `shanghai_now` (not `datetime.utcnow`) for datetime defaults

### Security Patterns
- Cookies and API keys: always encrypt with `encrypt_text()` / `decrypt_text()` (Fernet) before storing
- Never expose `encrypted_api_key` in API responses — use `has_api_key: bool` instead
- JWT tokens: `create_access_token()` / `create_refresh_token()` / `decode_token()`

### Background Tasks
Long-running operations always create a `Task` record for audit:
```python
task = Task(
    user_id=current_user.id,
    platform=job.platform,
    task_type="creator_publish_scheduler",
    status="running",
    progress=20,
    payload={"publish_job_id": job.id},
)
db.add(task)
db.commit()
# ... do work ...
task.status = "completed"
task.progress = 100
db.commit()
```

### Scheduler Jobs
APScheduler jobs use `max_instances=1, coalesce=True` to prevent overlapping runs:
```python
scheduler.add_job(
    job_func,
    "interval",
    seconds=interval_seconds,
    id="due_publish_runner",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

### SSE (Server-Sent Events)
SSE endpoints use `StreamingResponse` with `text/event-stream` media type:
```python
return StreamingResponse(
    generate(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```
SSE auth uses `token` query param (not Authorization header) since EventSource cannot set headers:
```python
@router.get("/logs/stream")
async def log_stream(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
```

### In-memory Pub/Sub (Log Bus)
Per-user log bus pattern using `asyncio.Queue` + `collections.deque`:
```python
_log_store: dict[int, collections.deque] = {}       # history (maxlen=200)
_log_subscribers: dict[int, list[asyncio.Queue]] = {}  # live subscribers

def _append_log(user_id: int, level: str, text: str, extra: dict | None = None):
    entry = {"ts": ..., "level": level, "text": text, **(extra or {})}
    _log_store.setdefault(user_id, collections.deque(maxlen=200)).append(entry)
    for q in _log_subscribers.get(user_id, []):
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            pass
```

---

## Testing Patterns

### Test Structure
- Use `fastapi.testclient.TestClient` for integration tests
- Override DB dependency with in-memory SQLite per test via `app.dependency_overrides`
- Always clean up overrides in `finally` blocks

### DB Override Pattern
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
    return get_db  # return key for cleanup
```

### Fake Adapter Pattern
Inject fake adapters via `app.dependency_overrides` to isolate XHS SDK calls:
```python
class FakePcLoginAdapter:
    def create_qrcode(self):
        return {"cookies": {"a1": "temp-a1"}, "qr_id": "qr-123", ...}

app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
```

### Ownership Tests
Every resource test verifies three scenarios:
1. Anonymous → 401
2. Cross-user (intruder) → 404
3. Owner → 200

### Frontend Source Tests
Some tests read frontend `.tsx` source files directly to assert UI invariants:
```python
source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()
assert "antd" in source
assert "checkingAccountIds" in source
```

---

## TypeScript / Frontend Patterns

### Type Definitions
All types are centralized in `frontend/src/types/index.ts`. No inline type definitions in components.

### Generic Paginated Type
```typescript
export type Paginated<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};
```

### Union String Types for Status Fields
Status fields use string unions with a fallback `string` for extensibility:
```typescript
status: "active" | "healthy" | "expired" | "risk" | "unknown" | string;
status: "pending" | "running" | "completed" | "failed" | "cancelled" | string;
```

### Optional Fields
Use `?` for optional fields, `| null` for explicitly nullable fields:
```typescript
scheduled_at?: string | null;
parent_comment_id?: string | null;
```

### Payload vs Response Types
Separate payload (request) and response types for every resource:
```typescript
export type ModelConfigPayload = { name: string; model_type: ModelType; ... };
export type ModelConfig = { id: number; name: string; has_api_key: boolean; ... };
```

### API Client
All HTTP calls go through `frontend/src/lib/api.ts` (Axios with JWT interceptor). Never use `fetch` directly.

### UI Component Library
Use Ant Design (antd v6) for all UI components. Do not mix with other component libraries.

---

## Architecture Rules

### SDK Isolation
- `apis/` is the bottom-layer SDK — **do not modify directly**
- Upper layers access XHS APIs only through `backend/app/adapters/xhs/`
- All adapter calls must use `direct_xhs_request_env()` context manager to strip system proxy env vars

### Datetime Handling
- Always use `shanghai_now()` from `backend.app.core.time` — never `datetime.utcnow()` or `datetime.now()`
- All datetimes stored in Asia/Shanghai timezone

### Cookie Storage
- Cookies stored as Fernet-encrypted JSON strings in `account_cookie_versions`
- Latest cookie = highest `id` (or `created_at`) in `account_cookie_versions`
- Cookie format: either JSON dict `{"a1": "...", "web_session": "..."}` or raw cookie string — both handled by `_cookies_to_string()`

### Config Layering
Never hardcode config values. Use `get_settings()` from `backend.app.core.config`. Settings are loaded from YAML → env vars with Pydantic Settings.

### Notification Pattern
Use `notification_service` or direct `db.add(Notification(...))` for user-facing alerts (cookie expiry, task failures). Never use print statements for user-visible events.
