# XHS_ALL_IN_ONE — Development Guidelines

## Code Quality Standards

### Python
- All files start with `from __future__ import annotations` for forward-reference compatibility
- `loguru` is used for logging in SDK/utility layers; `logging.getLogger(__name__)` is used in service/scheduler layers
- Error handling in SDK methods always follows the `(success: bool, msg: str, res_json)` triple-return pattern
- Every SDK method wraps its body in `try/except Exception as e` and returns `success=False, msg=_log_api_error(e)` on failure
- `from typing import Any, Optional` is imported explicitly; modern union syntax (`X | Y`) is avoided for compatibility
- `from __future__ import annotations` enables PEP 604 style hints in docstrings without runtime cost

### TypeScript / React
- All shared types live in `frontend/src/types/index.ts` — no inline type definitions in component files
- Generic pagination wrapper: `Paginated<T>` with `{ total, page, page_size, items }`
- Union string literals are used for status fields (e.g., `"pending" | "running" | "completed" | "failed" | string`) — the trailing `| string` allows forward-compatible extension
- Payload types are separate from response types (e.g., `ModelConfigPayload` vs `ModelConfig`)

---

## Structural Conventions

### Backend Layer Separation (strict)
```
apis/           ← raw XHS SDK (never import from backend/)
adapters/xhs/   ← only layer allowed to import from apis/
services/       ← business logic, imports from adapters/ and models/
api/            ← FastAPI routers, imports from services/ and core/
```
Violating this boundary (e.g., importing `apis/` directly in a router) is forbidden.

### FastAPI Router Pattern
```python
# All routers use prefix="/api" at registration in main.py
# Router files define their own sub-prefix:
router = APIRouter(prefix="/xhs/...", tags=["..."])

# Dependency injection for auth + DB:
@router.post("/endpoint")
def my_endpoint(
    payload: SomeSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ...
```

### Ownership Enforcement (universal pattern)
Every resource (note, draft, tag, account, publish job, etc.) is scoped to `user_id`. Cross-user access always returns HTTP 404 (not 403) to avoid information leakage:
```python
item = db.query(Model).filter(Model.id == item_id, Model.user_id == current_user.id).first()
if item is None:
    raise HTTPException(status_code=404, detail="Not found")
```

### SDK Method Signature Convention
```python
def method_name(self, param1: str, cookies_str: str, proxies: dict = None):
    res_json = None
    try:
        api = "/api/sns/web/v1/..."
        # build params / data
        headers, cookies, data = generate_request_params(cookies_str, api, data, 'POST')
        response = requests.post(self.base_url + api, headers=headers, data=data, cookies=cookies, proxies=proxies, timeout=REQUEST_TIMEOUT)
        res_json = response.json()
        success, msg = res_json["success"], res_json["msg"]
    except Exception as e:
        success = False
        msg = _log_api_error(e)
    return success, msg, res_json
```

### Pagination Cursor Pattern (SDK)
Paginated SDK methods follow a `while True` loop with cursor advancement:
```python
cursor = ''
items = []
while True:
    success, msg, res_json = self.get_page(cursor, ...)
    if not success:
        raise Exception(msg)
    items.extend(res_json["data"]["items"])
    cursor = str(res_json["data"].get("cursor", ""))
    if not res_json["data"]["has_more"] or not items:
        break
return success, msg, items
```

---

## Semantic Patterns

### Dependency Injection for Adapters (testability)
Adapters are injected via FastAPI `Depends()` so tests can swap them with fakes:
```python
# In router file:
def get_pc_login_adapter() -> XhsPcLoginAdapter:
    return XhsPcLoginAdapter()

@router.post("/qrcode")
def create_qrcode(adapter=Depends(get_pc_login_adapter), ...):
    ...

# In tests:
app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
```

### Test Database Override Pattern
```python
def _override_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return get_db  # return key for cleanup

# Always clean up in finally:
app.dependency_overrides.pop(get_db, None)
```

### Fake Adapter Pattern (tests)
Test fakes are plain classes with the same method signatures as real adapters. They use `assert` to validate inputs and return hardcoded data:
```python
class FakePcLoginAdapter:
    def create_qrcode(self):
        return {"cookies": {"a1": "temp-a1"}, "qr_id": "qr-123", "qr_url": "https://example.test/qr"}

    def check_qrcode_status(self, qr_id, code, cookies):
        assert qr_id == "qr-123"
        return {"status": "confirmed", "cookies": {"a1": "final-a1", "web_session": "session-123"}}
```

### Cookie Encryption Pattern
All cookies and API keys are encrypted with Fernet before DB storage:
```python
from backend.app.core.security import encrypt_text, decrypt_text

# Store:
cookie_version = AccountCookieVersion(
    platform_account_id=account.id,
    encrypted_cookies=encrypt_text(json.dumps(cookies_dict)),
)

# Retrieve:
raw = decrypt_text(cookie_version.encrypted_cookies)
cookies = json.loads(raw) if raw.startswith("{") else raw  # handle both JSON and string formats
```

### Cookie Format Normalization
Cookies may be stored as JSON dict or as a `key=value; key2=value2` string. Always normalize before use:
```python
def _cookies_to_string(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("{"):
        cookies = json.loads(stripped)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    return stripped
```

### Task Record Pattern
Every significant operation creates a `Task` record for audit:
```python
task = Task(
    user_id=current_user.id,
    platform="xhs",
    task_type="ai_rewrite",   # snake_case type identifier
    status="running",
    progress=20,
    payload={"draft_id": draft.id, "model_config_id": config.id},
)
db.add(task)
db.commit()
# ... do work ...
task.status = "completed"
task.progress = 100
task.payload = {**task.payload, "result_key": result_value}
db.commit()
```

### Scheduler Jobs (APScheduler)
All background jobs use `max_instances=1, coalesce=True` to prevent overlap:
```python
scheduler.add_job(
    job_func,
    "interval",
    seconds=interval_seconds,
    id="unique_job_id",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```
Scheduler jobs open their own `SessionLocal()` session and always close it in `finally`.

### Notification Pattern
Cookie expiry and task failures create `Notification` records:
```python
db.add(Notification(
    user_id=account.user_id,
    title="账号 Cookie 过期",
    body=f"账号「{account.nickname}」Cookie 已失效，请重新绑定。",
    level="warning",  # "info" | "warning" | "error"
))
```

### Metrics Extraction (flexible raw_json)
Note engagement metrics are extracted from `raw_json` with multiple key fallbacks:
```python
def _first_metric(raw: dict, keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw.get(key))
    return 0

likes = _first_metric(merged, ("likes", "liked_count", "like_count", "likedCount"))
```

---

## Naming Conventions

### Python
- Module-level private helpers: `_snake_case` prefix (e.g., `_log_api_error`, `_cookies_to_string`)
- Service functions that run once: `run_X_once()` (e.g., `run_due_publish_jobs_once`)
- Service functions for all users: `run_X_for_all_users()` (e.g., `run_due_publish_jobs_for_all_users`)
- Adapter factories injected via `Depends`: `get_X_adapter` or `get_X_adapter_factory`
- SQLAlchemy models: `PascalCase` (e.g., `PlatformAccount`, `PublishJob`)
- DB table names: `snake_case` plural (e.g., `platform_accounts`, `publish_jobs`)

### TypeScript
- Types: `PascalCase` (e.g., `PlatformAccount`, `PublishJob`)
- Payload types: `XxxPayload` suffix (e.g., `CreateDraftPayload`)
- Response types: `XxxResponse` suffix (e.g., `SaveNotesResponse`)
- API client functions: `camelCase` verbs (e.g., `deleteSavedNote`, `batchSaveNotes`)

---

## API Response Shapes

### Standard list response
```json
{ "total": 10, "page": 1, "page_size": 20, "items": [...] }
```

### Standard delete response
```json
{ "id": 42, "status": "deleted" }
```

### Standard task-backed operation response
```json
{ "task": { "id": 1, "task_type": "crawl", "status": "completed", ... }, "saved_count": 3, "items": [...] }
```

### SSE (Server-Sent Events) for long-running crawls
Events are `data: <json>` lines. Each event has a `type` field:
- `type: "item"` — individual result item
- `type: "done"` — final summary with `total`, `success_count`, `failed_count`

---

## Security Practices
- JWT tokens for all API authentication; `Authorization: Bearer <token>` header
- Refresh token flow: `/api/auth/refresh` accepts `{ refresh_token }` and returns new tokens
- All sensitive fields (`encrypted_cookies`, `encrypted_api_key`) are never returned in API responses
- API responses for model configs include `has_api_key: bool` instead of the key itself
- Cross-user resource access returns 404 (not 403) to prevent enumeration
- Proxy environment variables (`HTTPS_PROXY`, `HTTP_PROXY`) are temporarily removed during XHS SDK calls via `direct_xhs_request_env()` context manager to prevent routing XHS traffic through system proxies

---

## Frontend Patterns

### API Client (`frontend/src/lib/api.ts`)
- Single Axios instance with JWT interceptor
- All API functions are named exports (no default export)
- Functions follow `verbNoun` naming: `getSavedNotes`, `deleteSavedNote`, `batchSaveNotes`

### Page State
- `keepalive-for-react-router` is used to preserve page state across route changes
- Ant Design (`antd`) is the primary component library for all UI elements
- `lucide-react` is used for supplementary icons

### Type Safety
- All API request/response shapes have corresponding TypeScript types in `types/index.ts`
- `zod` is available for runtime validation but types are the primary contract
