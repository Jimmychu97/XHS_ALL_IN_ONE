# XHS_ALL_IN_ONE — Development Guidelines

## Python Code Style

<<<<<<< HEAD
### Module Header
All Python files start with `from __future__ import annotations` for forward reference support.

### Return Convention — SDK Layer (apis/)
Every SDK method returns a `(success: bool, msg: str, res_json: dict | list | None)` tuple:
```python
def get_note_info(self, url: str, cookies_str: str, proxies: dict = None):
    res_json = None
    try:
        # ... HTTP call ...
=======
### Python
- All files start with `from __future__ import annotations` for forward-reference support
- Module-level docstrings explain purpose and design principles
- Private helpers prefixed with `_` (e.g., `_log_api_error`, `_cookies_to_string`, `_serialize_publish_job`)
- Minimal inline comments — code is self-documenting through clear naming
- `loguru` used in SDK layer (`apis/`, `xhs_utils/`); `logging.getLogger(__name__)` used in backend services
- Exception handling: always catch broadly, set `success = False`, log with `_log_api_error(e)`, return `(success, msg, res_json)` triple

### TypeScript / React
- All types defined in `frontend/src/types/index.ts` — single source of truth
- Payload types named `*Payload`, response types named `*Response`
- Generic `Paginated<T>` wrapper for all list responses
- Optional fields use `?` suffix; union types for status strings include `| string` fallback for extensibility
- No inline type definitions in component files — always import from `types/index.ts`

---

## Naming Conventions

### Python
- Classes: `PascalCase` (e.g., `XHS_Apis`, `WalleEvaAPI`, `OpenAICompatibleTextClient`)
- Functions/methods: `snake_case`
- Private helpers: `_snake_case`
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LOOPS`, `COMPRESS_CHAR_THRESHOLD`, `RETAIN_COUNT`)
- DB models: `PascalCase` matching table name in `snake_case` (e.g., `PlatformAccount` → `platform_accounts`)

### TypeScript
- Types/interfaces: `PascalCase`
- Variables/functions: `camelCase`
- API payload types: `*Payload` suffix
- API response types: `*Response` suffix
- Enum-like string unions: `"snake_case"` values (e.g., `"coming_soon"`, `"note_urls"`)

---

## API Layer Patterns

### SDK Return Convention (apis/)
Every SDK method returns a 3-tuple `(success: bool, msg: str, res_json: dict | list | None)`:
```python
def get_user_info(self, user_id: str, cookies_str: str, proxies: dict = None):
    res_json = None
    try:
        api = f"/api/sns/web/v1/user/otherinfo"
        params = {"target_user_id": user_id}
        splice_api = splice_str(api, params)
        headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
        response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies, timeout=REQUEST_TIMEOUT)
        res_json = response.json()
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
        success, msg = res_json["success"], res_json["msg"]
    except Exception as e:
        success = False
        msg = _log_api_error(e)
    return success, msg, res_json
```
- Always initialize `res_json = None` before the try block
- Use `logger.exception()` via `_log_api_error()` helper for error logging
- Never raise exceptions from SDK methods — always catch and return `(False, msg, None)`

<<<<<<< HEAD
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
=======
### FastAPI Router Pattern
- One router file per resource in `backend/app/api/`
- Router prefix set at file level: `router = APIRouter(prefix="/walle", tags=["walle"])`
- All routes use `Depends(get_current_user)` and `Depends(get_db)` for auth + DB injection
- Ownership enforced: always check `resource.user_id == current_user.id`, raise `HTTPException(404)` on mismatch (not 403, to avoid leaking existence)
- Delete responses return `{"id": resource_id, "status": "deleted"}`
- List responses use `paginated()` helper from `schemas/common.py`

```python
@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    k = db.get(WalleKnowledge, knowledge_id)
    if not k or k.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(k)
    db.commit()
    return {"id": knowledge_id, "status": "deleted"}
```

### Pydantic Request Models
Defined inline in the router file using `class *Payload(BaseModel)`:
```python
class ShopConfigPayload(BaseModel):
    ai_enabled: bool = False
    auto_send: bool = False
    model_config_id: Optional[int] = None
    system_prompt: str = ""
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
```

---

<<<<<<< HEAD
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
=======
## Database Patterns

### Session Management
- Sync routes: `db: Session = Depends(get_db)` — generator-based, auto-closes
- Background threads: `db = SessionLocal()` with explicit `try/finally: db.close()`
- Never share a Session across threads

### SQLAlchemy Query Style
Use `select()` + `db.scalars()` (SQLAlchemy 2.0 style), not legacy `db.query()`:
```python
items = db.scalars(
    select(WalleConversation)
    .where(WalleConversation.user_id == current_user.id)
    .order_by(WalleConversation.updated_at.desc())
).all()
```
Legacy `db.query()` still appears in older code — prefer `select()` for new code.

### Upsert Pattern
Check existence first, update if found, insert if not:
```python
existing = db.scalars(select(Model).where(...)).first()
if existing:
    existing.field = new_value
    existing.updated_at = now
else:
    db.add(Model(...))
db.commit()
```

### Flush vs Commit
- `db.flush()` to get auto-generated IDs before referencing them in the same transaction
- `db.commit()` at the end of the logical unit of work
- `db.rollback()` in per-item loops to recover from individual failures without aborting the batch

---

## Security Patterns

### Ownership Enforcement
Cross-user access always returns 404 (not 403) to avoid leaking resource existence:
```python
resource = db.get(Model, resource_id)
if not resource or resource.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Not found")
```

### Sensitive Data
- Cookies and API keys encrypted with Fernet before DB storage
- Decrypt with `decrypt_text()` from `credential_service` / `security`
- API responses never expose `encrypted_api_key` — use `has_api_key: bool` instead
- JWT tokens: `access_token` (short-lived) + `refresh_token` (long-lived), validated via `decode_token()`

### SSE Auth
EventSource cannot set headers, so SSE endpoints accept `token` as a query parameter:
```python
@router.get("/logs/stream")
async def log_stream(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    payload = decode_token(token)
    user_id: int = payload.get("user_id")
```

---

## Testing Patterns

### Test Structure
- `TestClient(app)` at module level — shared across all tests
- DB isolation: `_override_database(tmp_path)` creates a fresh SQLite DB per test, overrides `get_db` via `app.dependency_overrides`
- Always clean up overrides in `finally` blocks
- Adapter injection: `app.dependency_overrides[get_adapter] = lambda: FakeAdapter()`

### Fake Adapter Pattern
Fake adapters are plain classes with the same method signatures as real adapters:
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
```python
class FakePcLoginAdapter:
    def create_qrcode(self):
        return {"cookies": {"a1": "temp-a1"}, "qr_id": "qr-123", ...}

<<<<<<< HEAD
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
=======
    def check_qrcode_status(self, qr_id, code, cookies):
        return {"status": "confirmed", "cookies": {...}}
```

### Test Naming
`test_<resource>_<action>_<condition>` — descriptive, behavior-focused:
- `test_xhs_pc_qrcode_login_session_persists_and_confirms_account`
- `test_account_delete_requires_owner_and_removes_account`
- `test_notes_batch_save_rejects_cross_user_account`

### Source-level Tests
Some tests read frontend source files directly to assert UI invariants:
```python
def test_accounts_page_uses_antd_components_and_shows_check_state():
    source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()
    assert "antd" in source
    assert "checkingAccountIds" in source
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
```

---

<<<<<<< HEAD
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
=======
## Agent / Tool Registry Pattern

### @agent_tool Decorator
Register tools with a Pydantic param model for automatic JSON schema generation:
```python
@agent_tool(
    name="search_knowledge",
    description="搜索知识库",
    param_model=SearchKnowledgeParams,
)
def search_knowledge(params: SearchKnowledgeParams) -> str:
    ...
```

### Tool Execution
`execute_tool(name, arguments, dependencies)` — dependencies dict injects context (user_id, platform_account_id, etc.) into tool params automatically, without requiring callers to pass them explicitly.

### Agent Loop
```python
# Max 5 iterations: LLM → tool_calls → execute → append results → repeat
while loop_count < MAX_LOOPS:
    resp = requests.post(endpoint, json=req_body, ...)
    choice = resp.json()["choices"][0]
    if choice["finish_reason"] == "tool_calls":
        # execute tools, append results, continue
    else:
        # final answer, break
```

---

## Background Task Patterns

### Scheduler Jobs
APScheduler jobs are registered in `build_due_publish_scheduler()`:
- `max_instances=1` and `coalesce=True` prevent overlapping runs
- Each job function opens its own `SessionLocal()` and closes it in `finally`
- Failures are logged but never crash the scheduler

### Background Threads
For fire-and-forget tasks triggered by incoming requests (e.g., AI agent on message arrival):
```python
import threading
threading.Thread(
    target=_auto_ai_suggest,
    args=(user_id, account_id, app_cid, message),
    daemon=True,
).start()
```

### SSE Streaming
```python
async def generate():
    try:
        for entry in history:
            yield f"data: {json.dumps(entry)}\\n\\n"
        while True:
            try:
                entry = await asyncio.wait_for(q.get(), timeout=25)
                yield f"data: {json.dumps(entry)}\\n\\n"
            except asyncio.TimeoutError:
                yield 'data: {"ping": true}\\n\\n'  # keepalive
    finally:
        subs.remove(q)  # always clean up subscriber

return StreamingResponse(generate(), media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

## Frontend Patterns

### API Client
All HTTP calls go through `frontend/src/lib/api.ts` (Axios instance with auth header injection). Never use `fetch` directly.

### Component Organization
Feature pages live in `frontend/src/pages/platforms/xhs/<feature>-page.tsx`. Each page is self-contained with its own state and API calls.

### UI Library
Ant Design (antd v6) is the primary UI library. All tables, forms, modals, and notifications use antd components. Lucide React is used for icons.

### Type Safety
All API request/response shapes are typed in `types/index.ts`. Use `Paginated<T>` for list responses. Never use `any` for API data — define a proper type.

---

## SDK Isolation Rule

`apis/` is the bottom-layer SDK — **do not modify directly**. All upper-layer code calls through `backend/app/adapters/xhs/` adapters. This ensures:
1. Signing logic stays isolated and testable
2. Adapters can be swapped in tests via `app.dependency_overrides`
3. Proxy environment is managed cleanly via `direct_xhs_request_env()` context manager in all adapters
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
