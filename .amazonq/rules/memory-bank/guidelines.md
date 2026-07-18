# XHS_ALL_IN_ONE — Development Guidelines

## Code Quality Standards

### Python
- All files use `from __future__ import annotations` for forward-reference compatibility
- `loguru` for logging in SDK/utils layers; `logging.getLogger(__name__)` in service/scheduler layers
- `try/except Exception as e` wrapping every external HTTP call; always return `(success: bool, msg: str, data)` tuple from SDK methods
- Private helpers prefixed with `_` (e.g., `_log_api_error`, `_cookies_to_string`, `_serialize_publish_job`)
- Module-level docstrings in Chinese for SDK files; English for backend services
- `from __future__ import annotations` always first import

### TypeScript / React
- All types in `frontend/src/types/index.ts` — single source of truth, no inline type definitions in components
- `type` keyword preferred over `interface` for all type definitions
- Generic `Paginated<T>` wrapper for all list responses
- Optional fields use `?:` syntax; union types for status strings (e.g., `"active" | "expired" | string`)
- No `any` — use `Record<string, unknown>` for untyped JSON payloads

---

## Naming Conventions

### Python
- Classes: `PascalCase` (e.g., `XHS_Apis`, `XhsCreatorApiAdapter`, `BackgroundScheduler`)
- Functions/methods: `snake_case`
- Private helpers: `_snake_case` prefix
- Constants: `UPPER_SNAKE_CASE` (e.g., `REQUEST_TIMEOUT`, `PROXY_ENV_KEYS`)
- SQLAlchemy models: `PascalCase` matching table name in `snake_case` plural (e.g., `PlatformAccount` → `platform_accounts`)

### TypeScript
- Types: `PascalCase` (e.g., `PlatformAccount`, `XhsSearchNote`, `Paginated<T>`)
- Payload types: suffix `Payload` (e.g., `CreateDraftPayload`, `RewriteDraftPayload`)
- Response types: suffix `Response` (e.g., `SaveNotesResponse`, `XhsNoteSearchResponse`)
- React components: `PascalCase` files and exports
- Hooks: `use-` prefix with kebab-case filename (e.g., `use-auth.ts`)

---

## API Layer Patterns

### SDK Return Convention (apis/)
Every SDK method returns a 3-tuple: `(success: bool, msg: str, res_json: dict | list | None)`

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
        success, msg = res_json["success"], res_json["msg"]
    except Exception as e:
        success = False
        msg = _log_api_error(e)
    return success, msg, res_json
```

### Pagination Pattern (all list APIs)
All list endpoints return `{"total": int, "page": int, "page_size": int, "items": [...]}` — mirrored by `Paginated<T>` TypeScript type.

### Dependency Injection (FastAPI)
All DB sessions and current user obtained via `Depends()`:
```python
@router.get("/notes")
def list_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
```

### Adapter Factory Pattern
Platform API adapters are injected as factory functions (not instances) to allow per-request cookie injection and test overriding:
```python
def get_xhs_pc_api_adapter_factory():
    return XhsPcApiAdapter

@router.post("/xhs/pc/search/notes")
def search_notes(
    adapter_factory = Depends(get_xhs_pc_api_adapter_factory),
    ...
):
    adapter = adapter_factory(cookies_string)
```

### Ownership Enforcement
Every resource access checks `user_id` ownership. Cross-user access returns HTTP 404 (not 403) to avoid information leakage:
```python
account = db.query(PlatformAccount).filter(
    PlatformAccount.id == account_id,
    PlatformAccount.user_id == current_user.id,
).first()
if not account:
    raise HTTPException(status_code=404)
```

---

## Security Patterns

### Cookie / API Key Encryption
All sensitive data encrypted at rest with Fernet before DB storage:
```python
from backend.app.core.security import encrypt_text, decrypt_text

# Store
cookie_version.encrypted_cookies = encrypt_text(cookie_string)

# Retrieve
cookies = decrypt_text(cookie_version.encrypted_cookies)
```

### JWT Auth
- Access token + refresh token pair returned on login/register
- Bearer token in `Authorization` header for all protected endpoints
- `get_current_user` dependency raises HTTP 401 if token missing/invalid

### Proxy Isolation
All XHS SDK calls wrapped in `direct_xhs_request_env()` context manager to strip system proxy env vars, preventing broken proxy interference:
```python
with direct_xhs_request_env():
    result = adapter.search_note(keyword)
```

---

## Service Layer Patterns

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

### Task Records
Every significant background operation creates a `Task` record with `status` lifecycle: `pending → running → completed/failed`. Task payload stores operation-specific metadata as JSON.

### Cookie String Normalization
Cookies stored as either JSON dict string or `key=value; key=value` format. Always normalize before use:
```python
def _cookies_to_string(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("{"):
        cookies = json.loads(stripped)
        return "; ".join(f"{key}={v}" for key, v in cookies.items())
    return stripped
```

### Metrics Extraction
Raw note JSON has inconsistent field names across sources. Use multi-key fallback:
```python
def _first_metric(raw: dict, keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw.get(key))
    return 0

likes = _first_metric(merged, ("likes", "liked_count", "like_count", "likedCount"))
```

---

## Testing Patterns

### Test Structure
- `TestClient(app)` at module level — single shared client
- `_override_database(tmp_path)` helper creates isolated SQLite DB per test
- Always clean up `app.dependency_overrides` in `finally` blocks
- Fake adapter classes (e.g., `FakePcLoginAdapter`, `FakeCreatorLoginAdapter`) defined inline or at module level for login flow tests

### Dependency Override Pattern
```python
app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
try:
    response = client.post("/api/xhs/login-sessions/pc/qrcode", ...)
    assert response.status_code == 200
finally:
    app.dependency_overrides.pop(get_pc_login_adapter, None)
```

### Source Code Assertion Tests
Some tests assert frontend source code contains required strings (UI components, function names, Chinese labels). This enforces UI contract without running a browser:
```python
def test_accounts_page_uses_antd_components_and_shows_check_state():
    source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()
    assert "antd" in source
    assert "checkingAccountIds" in source
    assert "检查" in source
```

### Auth Test Helpers
```python
def _register_and_get_access_token(username: str = "operator") -> str:
    response = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]
```

---

## Frontend Patterns

### API Client
All HTTP calls go through `frontend/src/lib/api.ts` (Axios instance with auth interceptors). Never use `fetch` directly.

### Type Safety
All API request/response shapes defined in `types/index.ts`. Import types explicitly — no inline type definitions in page components.

### Component Organization
- Feature pages: `src/pages/platforms/xhs/<feature>-page.tsx`
- Shared platform components: `src/components/platforms/`
- Generic UI primitives: `src/components/ui/`
- Layout (sidebar, notifications): `src/components/layout/`

### UI Library
Ant Design 6 (`antd`) is the primary component library. Use Ant Design components for all forms, tables, modals, and notifications. `lucide-react` for supplementary icons.

### Keep-Alive
Use `keepalive-for-react-router` to preserve page state on navigation (prevents re-fetching data when switching between tabs).

---

## Configuration Patterns

### Settings Singleton
`get_settings()` is `@lru_cache` — call it anywhere, always returns the same instance:
```python
from backend.app.core.config import get_settings
settings = get_settings()
```

### Config Priority
`config/default.yaml` < `CONFIG_FILE` env var < `.env` file < environment variables

### Database URL Construction
`database_url` is auto-constructed from component fields in `model_post_init` if not explicitly set. Supports SQLite (dev) and MySQL (prod) without code changes.

---

## Common Idioms

### SQLAlchemy Queries
Use `db.scalars(select(...)).all()` (SQLAlchemy 2.0 style), not `db.query(...).all()` in new code. Legacy code uses `db.query()` — both patterns coexist.

### Shanghai Timezone
All timestamps use `shanghai_now()` from `backend.app.core.time` — never `datetime.now()` or `datetime.utcnow()`.

### JSON Serialization
Use `json.dumps(..., ensure_ascii=False)` for Chinese content to avoid Unicode escaping.

### Error Response Format
HTTP errors use FastAPI `HTTPException`:
```python
raise HTTPException(status_code=404, detail="Account not found")
raise HTTPException(status_code=400, detail="Default text model not configured")
raise HTTPException(status_code=502, detail=f"XHS API error: {str(exc)}")
```
502 is used specifically for upstream XHS API failures (adapter errors).
