# Development Guidelines

## Code Quality Standards

### Python Backend Standards

**Testing Patterns** (from `test_api.py`):
- Use FastAPI TestClient for endpoint testing
- Mock external adapters with fake implementations using dependency injection
- Test authentication, authorization, and ownership enforcement
- Use `tmp_path` fixture for SQLite test databases
- Verify database state after operations with direct ORM queries
- Test cross-user access denial as critical security tests
- Use helper functions to reduce test boilerplate (`_override_database`, `_register_and_get_access_token`, `_create_pc_account_with_cookie`)
- Always commit database changes in tests before asserting state
- Clean up dependency overrides in finally blocks

**API Design Patterns** (from `walle.py`):
- Use router prefix for resource grouping
- Implement SSE (Server-Sent Events) for real-time data streams with `StreamingResponse`
- Store in-memory log buffers with size limits (`deque(maxlen=200)`)
- Use background threads for long-running operations (`threading.Thread(target=..., daemon=True)`)
- Parse timestamps from multiple formats defensively
- Normalize data from external APIs before storage
- Use `try-except` with specific error handling, log exceptions
- Return consistent response structure (`{"ok": bool, ...}`)

**Service Layer** (from `scheduler_service.py`):
- Separate business logic from API routes
- Use SessionLocal for background tasks with proper cleanup
- Implement idempotent operations for scheduled jobs
- Handle exceptions gracefully without breaking scheduler
- Use logging for debugging and monitoring
- Implement helper functions for data transformation
- Secure credentials with decrypt_text before use
- Validate ownership before operations

### SDK Layer Standards (from `xhs_pc_apis.py`)

**Class Design**:
- Initialize with base_url as instance variable
- Accept cookies_str as parameter to methods (stateless authentication)
- Return consistent `(success: bool, msg: str, res_json: dict)` tuples
- Use docstrings for API method documentation
- Implement pagination helpers that call single-page methods
- Parse URLs defensively with urllib.parse
- Extract query parameters for xsec_token and xsec_source

**HTTP Client Usage**:
- Always use `generate_request_params()` for signature generation
- Set proper headers including x-rap-param for search endpoints
- Use UTF-8 encoding for POST request bodies
- Handle JSON parsing exceptions
- Log errors with loguru logger
- Use REQUEST_TIMEOUT constant for consistency

**Data Normalization**:
- Extract note_id from URL path
- Parse xsec_token/xsec_source from query parameters
- Convert cookie JSON strings to header format
- Handle multiple field name variations (likes/liked_count)

### Frontend TypeScript Standards (from `index.ts`)

**Type Definitions**:
- Export all types at module level
- Use union types for status enums (`"active" | "paused" | "expired"`)
- Use Partial<T> for update payloads
- Include both API response types and request payload types
- Document timestamp fields as `string | null` (ISO format from backend)
- Use `Record<string, unknown>` for flexible JSON fields
- Group related types by feature (Walle, Ark, Publishing)

**Naming Conventions**:
- Use PascalCase for type names
- Use camelCase for type properties
- Add "Payload" suffix for request types
- Add "Response" suffix for API response wrappers
- Use descriptive names: `XhsSearchNote`, `MonitoringTarget`, `PublishJob`

## Architectural Patterns

### Dependency Injection Pattern
```python
# FastAPI route with dependency overrides for testing
@router.get("/items")
def list_items(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Business logic
    pass

# Test setup
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: mock_user
```

### Adapter Pattern for SDK Isolation
```python
# SDK adapter layer wraps low-level API
class XhsPcApiAdapter:
    def __init__(self, cookies: str):
        self.cookies = cookies
        self.api = XHS_Apis()
    
    def search_note(self, keyword: str, page: int = 1):
        success, msg, res = self.api.search_note(keyword, self.cookies, page)
        # Normalize and return
```

### Repository Pattern for Data Access
```python
# Business logic shouldn't write raw SQL
# Use SQLAlchemy ORM models
draft = AiDraft(user_id=user_id, platform="xhs", title=title, body=body)
db.add(draft)
db.commit()
db.refresh(draft)  # Get auto-generated fields
```

### Background Task Pattern
```python
def _execute_auto_task_background(db: Session, task: AutoTask) -> None:
    try:
        # Long-running operation
        adapter = XhsPcApiAdapter(cookies)
        success, message, raw = adapter.search_note(keyword, page=1)
        # Process results
        db.commit()
    except Exception as exc:
        logger.warning(f"Auto task {task.id} failed: {exc}")
    finally:
        _calculate_next_run_at(task)
```

## Code Formatting Conventions

### Python
- **Imports**: Standard library → Third-party → Local (separated by blank lines)
- **Line length**: No explicit limit, prefer readability
- **Indentation**: 4 spaces
- **String quotes**: Prefer double quotes, use single for SQL
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Comments**: Use docstrings for public methods, inline comments sparingly
- **Error handling**: Specific exceptions, log with context
- **Type hints**: Required for function signatures in services

### TypeScript
- **Naming**: `PascalCase` for types/interfaces, `camelCase` for properties
- **Exports**: Use named exports, avoid default exports
- **Optional fields**: Use `field?: Type` syntax
- **Union types**: Prefer string literal unions over enums
- **Null handling**: Use `| null` explicitly when API can return null

## Common Implementation Patterns

### User Ownership Verification
```python
# Always verify resource belongs to current user
draft = db.get(AiDraft, draft_id)
if not draft or draft.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Not found")
```

### Pagination Response
```python
def paginated(items: list, page: int, page_size: int):
    return {
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "items": items[(page-1)*page_size : page*page_size]
    }
```

### Cookie String Normalization
```python
def _cookies_to_string(value: str) -> str:
    """Convert JSON cookie dict to header string format."""
    if value.startswith("{"):
        cookies = json.loads(value)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    return value
```

### Timestamp Handling
```python
# Use Shanghai timezone for all timestamps
from backend.app.core.time import shanghai_now

now = shanghai_now()
task.last_run_at = now
task.next_run_at = _calculate_next_run_at(task)
```

### Fernet Encryption
```python
# Always encrypt sensitive data before storage
from backend.app.core.security import encrypt_text, decrypt_text

encrypted = encrypt_text(cookie_string)
stored = AccountCookieVersion(encrypted_cookies=encrypted)

# Decrypt when needed
decrypted = decrypt_text(stored.encrypted_cookies)
```

## API Usage Patterns

### HTTP Client (Frontend)
```typescript
import { http } from '../lib/api'

// Use axios wrapper with auth interceptor
const res = await http.get('/api/notes', { params: { platform: 'xhs' } })

// For SSE, use fetch with manual token
const token = getAccessToken()
const resp = await fetch(`/api/walle/logs/stream?token=${token}`)
```

### XHS SDK Methods
```python
# Search notes with sorting
success, msg, res = api.search_note(
    query=keyword,
    cookies_str=cookies,
    page=1,
    sort_type_choice=2,  # 0=综合 1=最新 2=点赞 3=评论 4=收藏
    note_type=0,         # 0=不限 1=视频 2=图文
)

# Get note details
success, msg, res = api.get_note_info(note_url, cookies)

# Get all comments recursively
success, msg, comments = api.get_note_all_comment(note_url, cookies)
```

### Task Recording
```python
# Create task record for audit trail
task = Task(
    user_id=user_id,
    platform="xhs",
    task_type="ai_rewrite",
    status="running",
    progress=20,
    payload={"draft_id": draft_id}
)
db.add(task)

# Update on completion
task.status = "completed"
task.progress = 100
task.finished_at = shanghai_now()
db.commit()
```

## Security Best Practices

1. **Input Validation**: Use Pydantic models for request validation
2. **SQL Injection**: Use SQLAlchemy ORM, never raw string interpolation
3. **XSS**: Frontend uses React's default escaping
4. **Authentication**: JWT with 15-minute expiry, refresh token for re-auth
5. **Cookie Security**: Encrypt with Fernet before storage
6. **API Keys**: Encrypt in database, decrypt only when needed
7. **Ownership Checks**: Verify `resource.user_id == current_user.id` for all mutations
8. **Dependency Injection**: Use DI for testability and isolation

## Error Handling Patterns

### Backend
```python
try:
    result = external_api_call()
    db.commit()
    return {"success": True, "data": result}
except Exception as e:
    db.rollback()
    logger.exception(f"Operation failed: {e}")
    raise HTTPException(status_code=502, detail=str(e))
```

### Frontend
```typescript
try {
    const res = await http.post('/api/endpoint', payload)
    return res.data
} catch (error) {
    if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail || 'Request failed')
    }
    throw error
}
```

## Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed diagnostic information")
logger.info("Normal operational message")
logger.warning("Unexpected but handled situation")
logger.error("Error that should be investigated")
logger.exception("Exception with full traceback")  # Use instead of logger.error + print_exc
```

## Database Session Management

```python
# In FastAPI routes
@router.get("/items")
def list_items(db: Session = Depends(get_db)):
    # Session automatically closed

# In background tasks / scheduler
db = SessionLocal()
try:
    # Operations
    db.commit()
finally:
    db.close()  # Always close
```

## Test Structure

```
tests/backend/
├── test_api.py          # API endpoint tests
├── test_platforms.py    # Platform-specific tests
└── test_root_main.py    # Application startup tests
```

Key test patterns:
- Use fixtures for database setup
- Mock external dependencies with fake implementations
- Test success, failure, and authorization cases
- Verify database state changes
- Clean up resources in finally blocks
