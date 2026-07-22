from __future__ import annotations

import asyncio
import json
import pathlib
import time
import urllib.request

import requests
import websockets
from loguru import logger

CDP_URL = "http://localhost:9222"
WALLE_SAVE = pathlib.Path("F:/eva/eva_cookies.json")
EDITH_SAVE = pathlib.Path("F:/eva/edith_auth.json")
_CACHE_MAX_AGE = 3600 * 6


def _load_edith_auth() -> str:
    if not EDITH_SAVE.exists():
        raise FileNotFoundError("edith_auth.json 不存在，请先运行 cookie_watcher.py 并触发一次会话请求")
    data = json.loads(EDITH_SAVE.read_text("utf-8"))
    age = time.time() - data.get("updated_at", 0)
    if age > _CACHE_MAX_AGE:
        raise ValueError(f"edith token 已过期 ({int(age/3600)}h)，请确认 cookie_watcher.py 正在运行")
    return data["authorization"]


def _find_workbench_ws() -> str:
    pages = json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())
    for p in pages:
        url = p.get("url", "")
        if "walle.xiaohongshu.com" in url and "login" not in url and p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("找不到工作台页面")


async def _page_fetch(api_path: str, method: str = "GET", body: dict = None) -> dict:
    """walle.xiaohongshu.com 接口：通过 CDP 让页面自身发请求（自动携带签名和 token）"""
    ws_url = _find_workbench_ws()
    base = "https://walle.xiaohongshu.com"
    body_repr = repr(json.dumps(body)) if body is not None else "null"
    js = f"""
    (async function() {{
        const token = localStorage.getItem('accessToken') || '';
        let xs = '', xt = '', xsc = '';
        try {{
            const s = window._webmsxyw('{api_path}', {body_repr if body is None else repr(json.dumps(body))});
            xs = s['X-s']||''; xt = String(s['X-t']||''); xsc = s['X-S-Common']||'';
        }} catch(e) {{}}
        const opts = {{
            method: '{method}',
            headers: {{'Content-Type':'application/json','Accept':'application/json',
                       'Authorization': token, 'x-subsystem':'eva',
                       'X-s':xs,'X-t':xt,'X-S-Common':xsc}},
        }};
        if ({body_repr} !== null) opts.body = {body_repr};
        const r = await fetch('{base}{api_path}', opts);
        return JSON.stringify(await r.json());
    }})()
    """
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": js, "awaitPromise": True, "returnByValue": True}}))
        for _ in range(30):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg.get("id") == 1:
                val = msg.get("result", {}).get("result", {}).get("value")
                return json.loads(val) if val else {}
    return {}


def _walle_call(api_path: str, method: str = "GET", body: dict = None):
    res_json = None
    try:
        res_json = asyncio.run(_page_fetch(api_path, method, body))
        success = res_json.get("success", False) or res_json.get("code") == 0
        msg = res_json.get("msg", "")
    except Exception as e:
        logger.error(e)
        success, msg = False, str(e)
    return success, msg, res_json


def _edith_call(api_path: str, method: str = "POST", body: dict = None):
    res_json = None
    try:
        auth = _load_edith_auth()
        headers = {
            "authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://walle.xiaohongshu.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 eva/1.2.6 Chrome/128.0.6613.186 Electron/32.2.8 Safari/537.36",
        }
        url = f"https://edith.xiaohongshu.com{api_path}"
        r = requests.request(method, url, headers=headers, json=body, timeout=15)
        res_json = r.json()
        success = res_json.get("code") == 0
        msg = res_json.get("msg", "")
    except Exception as e:
        logger.error(e)
        success, msg = False, str(e)
    return success, msg, res_json


class WalleEvaAPI:

    # ── walle 接口 ────────────────────────────────────────────
    def get_csa_info(self):
        """获取当前登录客服账号信息"""
        return _walle_call("/api/edith/mcs/get_csa_info", "GET")

    def get_realtime_data(self):
        """实时客服数据（回复率、排队数等）"""
        return _walle_call("/api/edith/walle/mcs/csa_realtime_data", "POST", {})

    def get_bot_suggest(self, im_chat_id: str):
        """获取某会话的机器人建议回复"""
        return _walle_call(f"/api/edith/walle/cs/bot/suggest/latest?imChatId={im_chat_id}", "GET")

    def get_unchecked_ai_msg(self, chat_id_list: list[str]):
        """获取未读 AI 消息"""
        return _walle_call("/api/edith/cs/seller/get/unchecked/ai/msg", "POST",
                           {"chatIdList": chat_id_list})

    # ── edith 接口 ────────────────────────────────────────────
    def get_conv_list(self, cursor: int = -1, count: int = 25,
                      ctag: str = None, has_hide: bool = False):
        """获取会话列表"""
        body = {"cursor": cursor, "count": count, "direction": False,
                "hasHide": has_hide, "withCtag": True, "topPolicy": 0, "offset": 0, "byOffset": True}
        if ctag:
            body["ctag"] = ctag
        return _edith_call("/api/impaas/conv/user/list", "POST", body)

    def get_message_list(self, app_cid: str, cursor: int = -1, count: int = 20):
        """获取单个会话的历史消息"""
        return _edith_call("/api/impaas/message/user/list", "POST",
                           {"appCid": app_cid, "cursor": cursor, "count": count, "direction": False})

    def get_message_list_batch(self, app_cids: list[str], count: int = 10):
        """批量获取多个会话的最新消息"""
        return _edith_call("/api/impaas/message/user/list/batch", "POST",
                           {"appCids": app_cids, "count": count})

    def send_message(self, app_cid: str, text: str):
        """向指定会话发送文本消息（调用 cookie_watcher 本地服务，通过常驻 CDP 连接发送）"""
        res_json = None
        try:
            data = json.dumps({"app_cid": app_cid, "text": text}, ensure_ascii=False).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:9223/send",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            res_json = json.loads(urllib.request.urlopen(req, timeout=25).read())
            success = res_json.get("ok", False)
            msg = res_json.get("result", {}).get("msg", "") if not success else "ok"
        except Exception as e:
            logger.error(e)
            success, msg = False, str(e)
        return success, msg, res_json


if __name__ == "__main__":
    api = WalleEvaAPI()

    success, msg, res = api.get_csa_info()
    logger.info(f"客服信息: success={success} name={res.get('data',{}).get('csa_real_name','')}")

    success, msg, res = api.get_realtime_data()
    logger.info(f"实时数据: success={success} 在线={res.get('data',{}).get('consultCustomerCount')}")

    success, msg, res = api.get_conv_list()
    logger.info(f"会话列表: success={success} msg={msg}")
    if success:
        convs = res.get("data", {}).get("userConversationInfos", [])
        logger.info(f"共 {len(convs)} 个会话")
