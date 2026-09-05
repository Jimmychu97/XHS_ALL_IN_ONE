"""
ark_capture.py — 用 Playwright 打开 ark.xiaohongshu.com
- 抓包模式（默认）：手动操作，Ctrl+C 保存 cookie
- 常驻模式（--daemon）：headless 后台保活，每 30 分钟自动刷新 cookie 写入文件

用法:
    pip install playwright
    playwright install chromium
    python ark_capture.py           # 抓包模式（手动操作）
    python ark_capture.py --daemon  # 常驻保活模式（后端自动调用）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright, Request, Response

ARK_URL = "https://ark.xiaohongshu.com/app-system/home"
_BASE = Path(__file__).parent
COOKIE_FILE = _BASE / "data" / "ark_cookies.json"
PROFILE_DIR = _BASE / "data" / "ark_profile"
LOG_DIR = _BASE / "data" / "logs"

COOKIE_REFRESH_INTERVAL = 30 * 60  # 30 分钟刷新一次

# 登录失效信号文件：后端同步商品检测到登录失败时写入，daemon 轮询到后自动打开有头浏览器
RELOCK_FLAG = _BASE / "data" / "ark_relogin.flag"


def _relogin_requested(max_age: int = 300) -> bool:
    """是否有登录失效信号（文件存在且 5 分钟内刚写入）"""
    try:
        if not RELOCK_FLAG.exists():
            return False
        return time.time() - RELOCK_FLAG.stat().st_mtime <= max_age
    except Exception:
        return False


def _clear_relogin_flag() -> None:
    try:
        RELOCK_FLAG.unlink(missing_ok=True)
    except Exception:
        pass

CAPTURE_DOMAINS = (
    "ark.xiaohongshu.com",
    "edith.xiaohongshu.com",
    "walle.xiaohongshu.com",
    "api.xiaohongshu.com",
)
IGNORE_EXTS = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf")

_log_file: Path | None = None
_log_fp = None
_last_at_token: str = ""


def _init_log():
    global _log_file, _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _log_file = LOG_DIR / f"ark_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    _log_fp = _log_file.open("a", encoding="utf-8")
    print(f"[INFO] 完整日志写入: {_log_file}")


def _write_log(record: dict):
    if _log_fp:
        _log_fp.write(json.dumps(record, ensure_ascii=False) + "\n")
        _log_fp.flush()


def _should_capture(url: str) -> bool:
    if not any(d in url for d in CAPTURE_DOMAINS):
        return False
    path = url.split("?")[0]
    return not any(path.endswith(ext) for ext in IGNORE_EXTS)


def _fmt_preview(data: str | bytes | None, limit: int = 300) -> str:
    if not data:
        return ""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    try:
        s = json.dumps(json.loads(data), ensure_ascii=False, indent=2)
    except Exception:
        s = str(data)
    return s[:limit] + ("..." if len(s) > limit else "")


def _parse_json(data: str | bytes | None):
    if not data:
        return None
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    try:
        return json.loads(data)
    except Exception:
        return data


def _save_to_db(playwright_cookies: list, at_token: str) -> bool:
    """将 playwright_cookies 和 at_token 更新到 ark_server_configs 关联的 cookie 文件"""
    # ark 凭证统一写文件，_load_ark_cookies 会优先读文件
    # 此函数始终返回 False，让 _save_cookies 走文件写入路径
    return False


async def _save_cookies(context) -> int:
    """保存当前 context 的 cookie 到文件"""
    cookies = await context.cookies()
    at_token = _last_at_token
    existing = {}
    if COOKIE_FILE.exists():
        try:
            existing = json.loads(COOKIE_FILE.read_text("utf-8"))
        except Exception:
            pass
    existing["playwright_cookies"] = cookies
    if at_token:
        existing["at_token"] = at_token
    existing["updated_at"] = int(time.time())
    COOKIE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cookies)


def _save_at_token(at_token: str):
    global _last_at_token
    if not at_token or at_token == _last_at_token:
        return
    _last_at_token = at_token
    _save_at_token_to_file(at_token)


def _save_at_token_to_file(at_token: str):
    existing = {}
    if COOKIE_FILE.exists():
        try:
            existing = json.loads(COOKIE_FILE.read_text("utf-8"))
        except Exception:
            pass
    existing["at_token"] = at_token
    existing["updated_at"] = int(time.time())
    COOKIE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] AT token 已写文件: {at_token[:30]}...")


async def _on_request(req: Request):
    if not _should_capture(req.url):
        return
    ts = time.strftime("%H:%M:%S")
    post_data_raw = ""
    try:
        post_data_raw = req.post_data or ""
    except Exception:
        pass
    hdrs = req.headers
    auth = hdrs.get("authorization", "")
    if auth.startswith("AT-"):
        _save_at_token(auth)
    print(f"\n{'='*70}")
    print(f"[{ts}] ➡  {req.method}  {req.url}")
    for k in ("content-type", "authorization", "x-s", "x-t", "x-s-common"):
        if k in hdrs:
            print(f"  {k}: {hdrs[k][:120]}")
    if post_data_raw:
        print(f"  BODY: {_fmt_preview(post_data_raw)}")
    _write_log({
        "ts": ts, "direction": "request", "method": req.method, "url": req.url,
        "headers": {k: v for k, v in hdrs.items() if k in ("content-type", "authorization", "x-s", "x-t", "x-s-common")},
        "body": _parse_json(post_data_raw),
    })


async def _on_response(resp: Response):
    if not _should_capture(resp.url):
        return
    ts = time.strftime("%H:%M:%S")
    body_raw = b""
    try:
        body_raw = await resp.body()
    except Exception:
        pass
    print(f"[{ts}] ⬅  {resp.status}  {resp.url}")
    if body_raw:
        print(f"  RESP: {_fmt_preview(body_raw)}")
    _write_log({"ts": ts, "direction": "response", "status": resp.status, "url": resp.url, "body": _parse_json(body_raw)})


async def _capture_mode():
    """抓包模式：有头浏览器，手动操作，Ctrl+C 保存"""
    _init_log()
    async with async_playwright() as p:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900},
        )
        if COOKIE_FILE.exists():
            try:
                data = json.loads(COOKIE_FILE.read_text("utf-8"))
                cookies = data.get("playwright_cookies") or []
                if cookies:
                    await context.add_cookies(cookies)
                    print(f"[INFO] 已注入 {len(cookies)} 条 cookie")
            except Exception as e:
                print(f"[WARN] cookie 注入失败: {e}")

        page = context.pages[0] if context.pages else await context.new_page()
        page.on("request", lambda req: asyncio.ensure_future(_on_request(req)))
        page.on("response", lambda resp: asyncio.ensure_future(_on_response(resp)))

        print(f"[INFO] 正在打开 {ARK_URL}")
        print("[INFO] 请在浏览器中操作，所有 API 请求将实时打印到此终端")
        print("[INFO] 按 Ctrl+C 退出\n")
        await page.goto(ARK_URL, wait_until="domcontentloaded")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            # asyncio.run 收到 Ctrl+C 时先取消主任务（CancelledError），
            # 只 catch KeyboardInterrupt 会导致保存逻辑永远不执行
            print("\n[INFO] 退出，正在保存 cookies...")
            n = await _save_cookies(context)
            print(f"[INFO] {n} 条 cookie 已保存到 {COOKIE_FILE}")
            if _log_fp:
                _log_fp.close()
        await context.close()


async def _daemon_mode():
    """
    常驻模式：headless 后台保活，每 30 分钟刷新 cookie。
    发现会话失效（自身检测或收到后端同步请求）时，自动切到有头浏览器请人工确认登录态，
    登录恢复后保存 cookie 并切回 headless 保活。
    """
    print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] ark cookie 保活服务启动（会话失效将自动打开浏览器请人工登录）")
    headless = True
    while True:
        async with async_playwright() as p:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            context = await p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1440, "height": 900} if not headless else None,
            )
            # 注入已有 cookie
            if COOKIE_FILE.exists():
                try:
                    data = json.loads(COOKIE_FILE.read_text("utf-8"))
                    cookies = data.get("playwright_cookies") or []
                    if cookies:
                        await context.add_cookies(cookies)
                        print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 已注入 {len(cookies)} 条 cookie")
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] cookie 注入失败: {e}")

            page = context.pages[0] if context.pages else await context.new_page()

            # 首次加载页面，触发登录态验证
            try:
                await page.goto(ARK_URL, wait_until="domcontentloaded", timeout=30000)
                n = await _save_cookies(context)
                print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 初始 cookie 已保存 ({n} 条)")
                session_ok = await _check_session_valid(page)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 初始加载失败: {e}")
                session_ok = False

            # headless 模式下若初始会话即失效 → 直接切有头浏览器
            if headless and not session_ok:
                print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] ⚠️ 会话可能失效（登录过期），自动打开浏览器请人工确认登录态")
                headless = False
                await context.close()
                continue

            # ── 有头模式：等待用户人工登录确认 ──
            if not headless:
                print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 浏览器已打开（有头），请在窗口中人工确认/重新登录...")
                while True:
                    await asyncio.sleep(5)
                    if await _check_session_valid(page):
                        n = await _save_cookies(context)
                        print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] ✅ 登录态已恢复，保存 {n} 条 cookie，切回后台保活")
                        headless = True
                        break
                    if not context.pages:  # 用户关闭了浏览器窗口
                        print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 浏览器窗口已关闭，切回后台保活")
                        headless = True
                        break
                _clear_relogin_flag()
                await context.close()
                continue

            # ── headless 保活心跳（每 10s 检查失效信号 + 每 30min 刷新 cookie）──
            last_refresh = time.time()
            while True:
                if _relogin_requested():
                    print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] ⚠️ 收到登录失效信号，自动打开浏览器请人工确认登录态")
                    _clear_relogin_flag()
                    headless = False
                    break
                if time.time() - last_refresh >= COOKIE_REFRESH_INTERVAL:
                    last_refresh = time.time()
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        n = await _save_cookies(context)
                        print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] cookie 已刷新 ({n} 条)")
                        if not await _check_session_valid(page):
                            print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] ⚠️ 会话可能失效（登录过期），自动打开浏览器请人工确认登录态")
                            headless = False
                            break
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 刷新失败: {e}，5 秒后重试...")
                        await asyncio.sleep(5)
                        try:
                            await page.goto(ARK_URL, wait_until="domcontentloaded", timeout=30000)
                            n = await _save_cookies(context)
                            print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 重试成功 ({n} 条)")
                        except Exception as e2:
                            print(f"[{time.strftime('%H:%M:%S')}] [DAEMON] 重试失败: {e2}")
                await asyncio.sleep(10)

            _clear_relogin_flag()
            await context.close()


async def _check_session_valid(page) -> bool:
    """校验 ark 会话是否仍有效（页面内 fetch seller/info，code=0 为有效）"""
    try:
        valid = await page.evaluate("""
            async () => {
                try {
                    const r = await fetch('/api/edith/seller/info/v2', {credentials: 'include'});
                    const j = await r.json();
                    return (j.code === 0) || (j.success === true);
                } catch (e) { return false; }
            }
        """)
        return bool(valid)
    except Exception:
        return False


def _save_sku_to_db(item_id: str, extras: dict):
    """将 _sku_list/_item_properties/_sale_properties 写入 ark_products.raw_json"""
    import sys
    sys.path.insert(0, str(_BASE))
    from backend.app.core.database import SessionLocal
    from backend.app.models.ark import ArkProduct
    from sqlalchemy import select

    db = SessionLocal()
    try:
        p = db.scalars(select(ArkProduct).where(ArkProduct.item_id == item_id)).first()
        if not p:
            print(f"  [SKIP] item_id={item_id} 不在数据库")
            return
        merged = dict(p.raw_json or {})
        merged.update(extras)
        p.raw_json = merged
        db.commit()
        print(f"  [OK] item_id={item_id} skus={len(extras.get('_sku_list', []))}")
    finally:
        db.close()


async def _sync_skus_mode():
    """
    SKU 同步模式：让页面自己发 publish_render，拦截响应写入数据库
    """
    import sys
    sys.path.insert(0, str(_BASE))
    from backend.app.core.database import SessionLocal
    from backend.app.models.ark import ArkProduct
    from sqlalchemy import select

    db = SessionLocal()
    try:
        todo = [p.item_id for p in db.scalars(select(ArkProduct)).all()]
    finally:
        db.close()

    if not todo:
        print("[INFO] 没有商品需要同步")
        return

    print(f"[INFO] 需要同步 SKU 的商品：{len(todo)} 件")

    async with async_playwright() as pw:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        context = await pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        if COOKIE_FILE.exists():
            try:
                data = json.loads(COOKIE_FILE.read_text("utf-8"))
                cookies = data.get("playwright_cookies") or []
                if cookies:
                    await context.add_cookies(cookies)
            except Exception:
                pass

        page = context.pages[0] if context.pages else await context.new_page()

        print("[INFO] 正在打开 ark 页面...")
        await page.goto(ARK_URL, wait_until="domcontentloaded", timeout=30000)

        if "login" in page.url:
            print("[INFO] 请在浏览器中登录，登录完成后自动继续...")
            for _ in range(300):
                await asyncio.sleep(1)
                if "login" not in page.url:
                    print("[INFO] 登录成功")
                    break
            else:
                print("[ERROR] 登录超时")
                await context.close()
                return

        await asyncio.sleep(2)
        print("[INFO] 开始同步 SKU...")

        for item_id in todo:
            print(f"[SYNC] {item_id}")
            try:
                # 让页面自己发请求，页面 JS 会自动注入签名
                body_str = json.dumps({"publishType": 2, "sourceType": 1, "itemId": item_id})
                result = await page.evaluate(f"""
                async () => {{
                    const r = await fetch('/api/edith/product/publish_render', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{data: {json.dumps(body_str)}}})
                    }});
                    return await r.text();
                }}
                """)
                res = json.loads(result)
                code = res.get("code")
                if code not in (0, 200) or not res.get("success"):
                    print(f"  [FAIL] code={code} msg={res.get('msg','')}")
                    continue
                data = res.get("data")
                if isinstance(data, str):
                    data = json.loads(data)
                pd = data.get("product", {}).get("productDetail", {})
                extras = {
                    "_sku_list": pd.get("skuList") or [],
                    "_item_properties": pd.get("item", {}).get("properties") or [],
                    "_sale_properties": (
                        data.get("category", {})
                            .get("categoryPropertyInfo", {})
                            .get("saleProperties") or []
                    ),
                }
                _save_sku_to_db(item_id, extras)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  [ERROR] {e}")

        print("[INFO] SKU 同步完成，浏览器保持开启，可继续手动操作")
        print("[INFO] 按 Ctrl+C 退出并保存 cookies")
        # 开启日志拦截，方便手动调试
        _init_log()
        page.on("request", lambda req: asyncio.ensure_future(_on_request(req)))
        page.on("response", lambda resp: asyncio.ensure_future(_on_response(resp)))
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        n = await _save_cookies(context)
        print(f"[INFO] {n} 条 cookie 已保存")
        if _log_fp:
            _log_fp.close()
        await context.close()
    print("[INFO] 退出")


def _fix_stdio_encoding():
    """stdout/stderr 被重定向时 Python 默认用 GBK 编码，print 的 ➡/⬅ 箭头会抛
    UnicodeEncodeError 导致请求/响应日志丢失。重定向时强制切 UTF-8；
    控制台模式保持原样（控制台 API 可正常显示 unicode）。"""
    try:
        if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if not sys.stderr.isatty() and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


if __name__ == "__main__":
    _fix_stdio_encoding()
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="常驻保活模式（headless，自动刷新 cookie）")
    parser.add_argument("--sync-skus", action="store_true", help="SKU 同步模式：批量抓取所有商品规格写入数据库")
    args = parser.parse_args()

    if args.daemon:
        asyncio.run(_daemon_mode())
    elif args.sync_skus:
        asyncio.run(_sync_skus_mode())
    else:
        asyncio.run(_capture_mode())
