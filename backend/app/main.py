from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import accounts, ai, auth, auto_tasks, drafts, files, keyword_groups, login_sessions, model_configs, notes, notifications, publish, tags, tasks, account_credentials_api, walle, ark
from backend.app.api.platforms import registry
from backend.app.api.platforms.xhs import analytics, crawl, creator, monitoring, pc, qianfan, qianfan_login_api
from backend.app.core.config import get_settings
from backend.app.core.database import init_db
from backend.app.services.scheduler_service import run_due_auto_tasks, shutdown_due_publish_scheduler, start_due_publish_scheduler
from backend.app.services.heartbeat_scheduler import start_heartbeat_scheduler, stop_heartbeat_scheduler


def _start_token_self_heal() -> threading.Thread:
    """backend_token.txt 自愈：每小时检查，临期(<3天)/无效自动重签，不依赖用户打开页面"""
    def _loop() -> None:
        import time as _time
        import pathlib
        from backend.app.core.security import create_refresh_token, decode_token
        token_file = pathlib.Path("F:/eva/backend_token.txt")
        while True:
            try:
                need = False
                if not token_file.exists():
                    need = True
                else:
                    tok = token_file.read_text("utf-8").strip()
                    try:
                        payload = decode_token(tok)
                        exp = payload.get("exp", 0)
                        if exp - _time.time() < 3 * 86400:
                            need = True
                    except Exception:
                        need = True
                if need:
                    token_file.write_text(create_refresh_token(1), encoding="utf-8")
                    print("[token-heal] backend_token 已自动续期")
            except Exception as e:
                print(f"[token-heal] 失败: {e}")
            _time.sleep(3600)

    t = threading.Thread(target=_loop, name="token-heal", daemon=True)
    t.start()
    return t


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    scheduler = None
    heartbeat = None

    # token 自愈（无条件启动，与 scheduler 开关无关）
    _token_heal = _start_token_self_heal()

    if settings.scheduler_enabled:
        scheduler = start_due_publish_scheduler(settings.scheduler_interval_seconds)
        # 启动心跳检测（每 1 小时检测一次）
        heartbeat = start_heartbeat_scheduler(interval_seconds=3600)
    
    app.state.scheduler = scheduler
    app.state.heartbeat = heartbeat
    
    try:
        yield
    finally:
        shutdown_due_publish_scheduler(scheduler)
        if heartbeat:
            stop_heartbeat_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.api_title, lifespan=lifespan)

    origins = [origin.strip() for origin in settings.backend_cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "service": "spider-xhs"}

    app.include_router(registry.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    app.include_router(login_sessions.router, prefix="/api")
    app.include_router(notes.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(drafts.router, prefix="/api")
    app.include_router(ai.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(model_configs.router, prefix="/api")
    app.include_router(tags.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(keyword_groups.router, prefix="/api")
    app.include_router(publish.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(pc.router, prefix="/api")
    app.include_router(creator.router, prefix="/api")
    app.include_router(crawl.router, prefix="/api")
    app.include_router(monitoring.router, prefix="/api")
    app.include_router(auto_tasks.router, prefix="/api")
    app.include_router(qianfan.router, prefix="/api")
    app.include_router(qianfan_login_api.router, prefix="/api")
    app.include_router(account_credentials_api.router, prefix="/api")
    app.include_router(walle.router, prefix="/api")
    app.include_router(ark.router, prefix="/api")

    # Serve pre-built frontend in production / Docker
    if settings.frontend_serve_static:
        frontend_dist = Path(settings.frontend_build_dir)
        if frontend_dist.is_dir():
            from starlette.responses import FileResponse

            # Serve index.html for SPA client-side routing (non-API, non-file paths)
            @app.middleware("http")
            async def _spa_fallback(request, call_next):
                response = await call_next(request)
                path = request.url.path
                if (
                    response.status_code == 404
                    and not path.startswith("/api")
                    and "." not in path.split("/")[-1]
                ):
                    return FileResponse(str(frontend_dist / "index.html"))
                return response

            app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
