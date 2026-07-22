"""
统一 watcher：维护 walle cookie、edith token，实时同步消息到后端
用法: python cookie_watcher.py [--eva-dir F:/eva] [--backend http://127.0.0.1:8000] [--cdp-port 9222] [--send-port 9223]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import threading
import time
import urllib.request
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer


def _parse_args():
    parser = argparse.ArgumentParser(description="XHS Walle Cookie Watcher")
    parser.add_argument("--eva-dir", default="F:/eva", help="千帆客服工作台安装目录")
    parser.add_argument("--backend", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--cdp-port", type=int, default=9222, help="CDP 调试端口")
    parser.add_argument("--send-port", type=int, default=9223, help="发消息服务端口")
    return parser.parse_args()


_args = _parse_args()
_EVA_DIR = pathlib.Path(_args.eva_dir)

BACKEND_BASE = _args.backend.rstrip("/")
BACKEND_SYNC_URL = BACKEND_BASE + "/api/walle/push-message"
BACKEND_TOKEN_FILE = _EVA_DIR / "backend_token.txt"

CDP_URL = f"http://localhost:{_args.cdp_port}"
WALLE_SAVE = _EVA_DIR / "eva_cookies.json"
EDITH_SAVE = _EVA_DIR / "edith_auth.json"

print(f"[配置] eva目录={_EVA_DIR}  后端={BACKEND_BASE}  CDP端口={_args.cdp_port}  发消息端口={_args.send_port}")

_walle_b_user_id = ""
_pushed_msg_ids: set[str] = set()

_cached_access_token = ""
_cached_access_token_exp = 0

SEND_SERVER_PORT = _args.send_port

# 主事件循环引用，供发消息线程使用
_main_loop: asyncio.AbstractEventLoop | None = None


def _get_access_token() -> str:
    global _cached_access_token, _cached_access_token_exp
    if _cached_access_token and time.time() < _cached_access_token_exp - 30:
        return _cached_access_token
    if not BACKEND_TOKEN_FILE.exists():
        return ""
    refresh_token = BACKEND_TOKEN_FILE.read_text("utf-8").strip()
    if not refresh_token:
        return ""
    try:
        data = json.dumps({"refresh_token": refresh_token}).encode("utf-8")
        req = urllib.request.Request(
            BACKEND_BASE + "/api/auth/refresh",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        _cached_access_token = resp.get("access_token", "")
        _cached_access_token_exp = time.time() + 14 * 60
        return _cached_access_token
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 刷新 access_token 失败: {e}")
        return ""


def push_message_to_backend(payload: dict):
    token = _get_access_token()
    if not token:
        print(f"[{time.strftime('%H:%M:%S')}] push_message 跳过: 无 access_token")
        return
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            BACKEND_SYNC_URL,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] push_message 失败: {e}")


def _extract_summary(content_raw: str) -> str:
    try:
        obj = json.loads(content_raw)
        summary = obj.get("summary", "")
        if summary:
            return summary
        inner_str = obj.get("data", "")
        if inner_str:
            inner = json.loads(inner_str) if isinstance(inner_str, str) else inner_str
            return inner.get("content", "") or inner.get("text", "")
    except Exception:
        pass
    return content_raw


def save_walle_cookies(cookie_string: str):
    global _walle_b_user_id
    cookies = dict(item.split("=", 1) for item in cookie_string.split("; ") if "=" in item)
    _walle_b_user_id = cookies.get("walle-eva-bUserId", "")
    WALLE_SAVE.write_text(
        json.dumps({"cookie_string": cookie_string, "cookies": cookies, "updated_at": int(time.time())},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[{time.strftime('%H:%M:%S')}] walle cookie 已保存")


def save_edith_auth(auth: str):
    EDITH_SAVE.write_text(
        json.dumps({"authorization": auth, "updated_at": int(time.time())},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[{time.strftime('%H:%M:%S')}] edith a1: token 已保存")


def get_all_pages() -> list[dict]:
    return json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())


def find_workbench_ws() -> str:
    for p in get_all_pages():
        url = p.get("url", "")
        if "walle.xiaohongshu.com" in url and "login" not in url and p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("找不到工作台页面，请确认客服工作台已启动并登录")


async def extract_walle_cookies(ws) -> str | None:
    await ws.send(json.dumps({"id": 99, "method": "Network.getCookies", "params": {}}))
    for _ in range(30):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        if msg.get("id") == 99:
            cookies = {c["name"]: c["value"] for c in msg["result"]["cookies"]}
            if "AT-" not in cookies.get("walle-eva-auth", ""):
                return None
            keep = ["walle-eva-auth", "walle-eva-bUserId", "access-token-walle.xiaohongshu.com",
                    "acw_tc", "gid", "websectiga", "xsecappid", "webId", "a1"]
            return "; ".join(f"{k}={cookies[k]}" for k in keep if k in cookies)
    return None


def _handle_sync_item(item_type: str, data_str: str):
    if item_type != "30001":
        return
    try:
        data = json.loads(data_str)
    except Exception:
        return
    user_msg = data.get("userMessage")
    if not user_msg:
        return

    app_cid = user_msg.get("appCid", "")
    create_at = user_msg.get("createAt", 0)
    msg_id = user_msg.get("imMessageId") or user_msg.get("msgId") or ""

    if msg_id and msg_id in _pushed_msg_ids:
        return
    if msg_id:
        _pushed_msg_ids.add(msg_id)
        if len(_pushed_msg_ids) > 2000:
            _pushed_msg_ids.clear()

    sender_app_uid = user_msg.get("senderAppUid") or ""
    if "bot" in sender_app_uid or sender_app_uid.startswith("1#4#"):
        sender_type = "bot"
    elif _walle_b_user_id and _walle_b_user_id in sender_app_uid:
        sender_type = "csa"
    else:
        sender_type = "customer"

    content_raw = user_msg.get("contentInfo", {}).get("content", "")
    if not isinstance(content_raw, str):
        content_raw = json.dumps(content_raw, ensure_ascii=False)
    summary = _extract_summary(content_raw)
    try:
        outer = json.loads(content_raw)
        inner_str = outer.get("data", "")
        if inner_str:
            inner = json.loads(inner_str) if isinstance(inner_str, str) else inner_str
            inner_content = inner.get("content", "")
            if inner_content and inner.get("content_type") == 2:
                img = json.loads(inner_content) if isinstance(inner_content, str) else inner_content
                src = img.get("src", "")
                if src:
                    summary = f"[图片] {src}"
    except Exception:
        pass

    _PLATFORM_BOT_KEYWORDS = (
        "请警惕任何脱离平台", "深度验机接入会话", "为了第一时间帮您查询", "商家为您推荐",
        "请提供订单号或订单卡片", "以便为您查询", "您好，请提供",
    )
    if any(kw in summary for kw in _PLATFORM_BOT_KEYWORDS):
        sender_type = "bot"

    label = {"customer": "👤 买家", "csa": "💬 客服", "bot": "🤖 机器人"}.get(sender_type, f"💬 {sender_type}")
    print(f"[{time.strftime('%H:%M:%S')}] {label} [{app_cid[-20:]}]: {summary[:120]}")

    push_message_to_backend({
        "type": "message_response",
        "data": {
            "messages": [{
                "imMessageId": msg_id,
                "appCid": app_cid,
                "content": summary,
                "senderType": sender_type,
                "createAt": create_at,
            }],
            "appCid": app_cid,
            "bUserId": _walle_b_user_id,
        }
    })


# WS hook 注入脚本：捕获 apppush WS 实例，并暴露 __ws_send 发消息函数
_WS_HOOK_JS = """
(function() {
    if (window.__apppush_ws_hooked) return 'already';
    window.__apppush_ws_hooked = true;
    const orig = WebSocket.prototype.send;
    WebSocket.prototype.send = function(data) {
        if (this.url && this.url.includes('apppush')) window.__apppush_ws = this;
        return orig.call(this, data);
    };
    return 'hooked';
})()
"""


async def _cdp_eval_independent(js: str, timeout: int = 15) -> dict:
    """新建独立 CDP 连接执行 JS，返回 result.value 解析后的 dict。"""
    ws_url = find_workbench_ws()
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": js, "awaitPromise": True, "returnByValue": True}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            resp = json.loads(raw)
            if resp.get("id") == 1:
                val = resp.get("result", {}).get("result", {}).get("value", "{}")
                return json.loads(val) if val else {}
    raise TimeoutError("cdp_eval 超时")


async def _cdp_send_message_independent(app_cid: str, text: str, receiver_app_uid: str = "") -> dict:
    """通过渲染进程的 apppush WebSocket 发消息。"""
    import uuid as _uuid
    now = int(time.time() * 1000)
    smid = f"{now:x}-{_uuid.uuid4().hex[:11]}"
    uid = f"text-{now:x}-{_uuid.uuid4().hex[:11]}"
    trace_id = _uuid.uuid4().hex

    frame = {
        "header": {
            "sTime": now, "seq": 0,  # seq 由 JS 端递增
            "type": 3, "bizId": 10, "contentType": "json",
            "traceId": trace_id, "action": "/message/send",
            "serviceId": "impaas.oi", "oneWay": False, "sMid": smid,
        },
        "body": {
            "appCid": app_cid, "convType": 1, "uuid": uid,
            "receiverAppUids": [receiver_app_uid] if receiver_app_uid else [],
            "contentInfo": {"contentType": 1, "content": text},
            "convCreateInfo": {},
        },
    }
    frame_str = json.dumps(frame, ensure_ascii=False)

    js = f"""
    (function() {{
        const ws = window.__apppush_ws;
        if (!ws || ws.readyState !== 1) return JSON.stringify({{ok: false, error: 'ws not ready'}});
        const frame = {frame_str};
        frame.header.seq = (window.__apppush_seq = (window.__apppush_seq || 500) + 1);
        ws.send(JSON.stringify(frame));
        return JSON.stringify({{ok: true, seq: frame.header.seq}});
    }})()
    """
    result = await _cdp_eval_independent(js)
    print(f"[{time.strftime('%H:%M:%S')}] [SEND] {result}")
    return result


class _SendHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        app_cid = body.get("app_cid", "")
        text = body.get("text", "")
        receiver_app_uid = body.get("receiver_app_uid", "")
        try:
            result = asyncio.run(_cdp_send_message_independent(app_cid, text, receiver_app_uid))
            ok = result.get("ok", False)
            resp = json.dumps({"ok": ok, "result": result}, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            resp = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp)


def _start_send_server():
    server = HTTPServer(("127.0.0.1", SEND_SERVER_PORT), _SendHandler)
    print(f"[{time.strftime('%H:%M:%S')}] 发消息服务已启动 http://127.0.0.1:{SEND_SERVER_PORT}")
    server.serve_forever()


async def watch():
    print("正在连接客服工作台...")
    ws_url = find_workbench_ws()
    print(f"已连接: {ws_url}")

    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable", "params": {}}))
        await ws.send(json.dumps({"id": 3, "method": "Network.enable", "params": {
            "maxTotalBufferSize": 10000000, "maxResourceBufferSize": 5000000
        }}))

        # 注入 WS hook，捕获 apppush 实例
        await ws.send(json.dumps({"id": 98, "method": "Runtime.evaluate",
                                  "params": {"expression": _WS_HOOK_JS, "returnByValue": True}}))

        cookie_string = await extract_walle_cookies(ws)
        if cookie_string:
            save_walle_cookies(cookie_string)
            print("walle cookie 有效，开始监听...")
        else:
            print("walle cookie 无效，等待登录...")
            for _ in range(60):
                await asyncio.sleep(5)
                try:
                    if find_workbench_ws() != ws_url:
                        return
                except RuntimeError:
                    pass
            return

        last_walle_save = time.time()
        last_edith_auth = ""
        pending_requests: dict = {}
        _next_id = 1000

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                cookie_string = await extract_walle_cookies(ws)
                if cookie_string:
                    save_walle_cookies(cookie_string)
                    last_walle_save = time.time()
                continue

            msg = json.loads(raw)
            method = msg.get("method", "")

            # ── WS 帧：买家/客服/机器人实时消息 ──
            if method in ("Network.webSocketFrameReceived", "Network.webSocketFrameSent"):
                is_sent = method == "Network.webSocketFrameSent"
                params = msg["params"]
                payload_data = (
                    params.get("response", {}).get("payloadData", "")
                    or params.get("request", {}).get("payloadData", "")
                )
                if not payload_data:
                    continue
                try:
                    frame = json.loads(payload_data)
                    header = frame.get("header", {})
                    body = frame.get("body", {})
                    if is_sent and header.get("type") == 3 and header.get("action") == "/message/send":
                        app_cid = body.get("appCid", "")
                        msg_id = header.get("sMid") or ""
                        if msg_id and msg_id in _pushed_msg_ids:
                            continue
                        if msg_id:
                            _pushed_msg_ids.add(msg_id)
                            if len(_pushed_msg_ids) > 2000:
                                _pushed_msg_ids.clear()
                        create_at = header.get("sTime") or int(time.time() * 1000)
                        content_raw = body.get("contentInfo", {}).get("content", "")
                        if not isinstance(content_raw, str):
                            content_raw = json.dumps(content_raw, ensure_ascii=False)
                        summary = _extract_summary(content_raw)
                        print(f"[{time.strftime('%H:%M:%S')}] 💬 客服 [{app_cid[-20:]}]: {summary[:60]}")
                        push_message_to_backend({
                            "type": "message_response",
                            "data": {
                                "messages": [{
                                    "imMessageId": msg_id,
                                    "appCid": app_cid,
                                    "content": summary,
                                    "senderType": "csa",
                                    "createAt": create_at,
                                }],
                                "appCid": app_cid,
                                "bUserId": _walle_b_user_id,
                            }
                        })
                    elif header.get("type") == 4 and header.get("domain") == "cs":
                        for item in body.get("payload", []):
                            threading.Thread(
                                target=_handle_sync_item,
                                args=(str(item.get("type", "")), item.get("data", "")),
                                daemon=True,
                            ).start()
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] WS帧解析失败: {e}")

            # ── Electron 注入的 a1: token ──
            elif method == "Network.requestWillBeSentExtraInfo":
                headers = msg["params"].get("headers", {})
                auth = headers.get("authorization", "") or headers.get("Authorization", "")
                if auth and auth.startswith("a1:") and auth != last_edith_auth:
                    last_edith_auth = auth
                    save_edith_auth(auth)

            # ── HTTP 响应：impaas batch 接口补充历史消息 ──
            elif method == "Network.responseReceived":
                url = msg["params"].get("response", {}).get("url", "")
                req_id = msg["params"].get("requestId", "")
                if "impaas" in url and ("message" in url or "conv" in url):
                    _next_id += 1
                    pending_requests[_next_id] = req_id
                    await ws.send(json.dumps({"id": _next_id, "method": "Network.getResponseBody",
                                              "params": {"requestId": req_id}}))

            elif msg.get("id") in pending_requests:
                pending_requests.pop(msg["id"])
                body_str = msg.get("result", {}).get("body", "")
                if body_str:
                    try:
                        body = json.loads(body_str)
                        if body.get("code") == 0 and body.get("data"):
                            data_block = body["data"]
                            messages = data_block.get("messages") if isinstance(data_block.get("messages"), list) else None
                            if messages:
                                new_msgs = []
                                for m in messages:
                                    mid = m.get("imMessageId") or m.get("msgId") or ""
                                    if mid and mid in _pushed_msg_ids:
                                        continue
                                    if mid:
                                        _pushed_msg_ids.add(mid)
                                        if len(_pushed_msg_ids) > 2000:
                                            _pushed_msg_ids.clear()
                                    new_msgs.append(m)
                                if not new_msgs:
                                    continue
                                data_block = {**data_block, "messages": new_msgs}
                            push_message_to_backend({"type": "message_response", "data": data_block})
                            print(f"[{time.strftime('%H:%M:%S')}] impaas batch 推送到后端")
                    except Exception:
                        pass

            # ── walle token 刷新 ──
            elif method == "Network.responseReceivedExtraInfo":
                hdrs = {k.lower(): v for k, v in msg["params"].get("headers", {}).items()}
                if "walle-eva" in hdrs.get("set-cookie", "") or "access-token" in hdrs.get("set-cookie", ""):
                    await asyncio.sleep(0.5)
                    cookie_string = await extract_walle_cookies(ws)
                    if cookie_string:
                        save_walle_cookies(cookie_string)
                        last_walle_save = time.time()

            if time.time() - last_walle_save > 600:
                cookie_string = await extract_walle_cookies(ws)
                if cookie_string:
                    save_walle_cookies(cookie_string)
                    last_walle_save = time.time()


async def main():
    threading.Thread(target=_start_send_server, daemon=True).start()
    while True:
        try:
            await watch()
        except RuntimeError as e:
            print(f"[{time.strftime('%H:%M:%S')}] {e}，10 秒后重试...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 连接断开: {e}，5 秒后重连...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
