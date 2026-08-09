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
_ARK_DEFAULT_SAVE = pathlib.Path("F:/eva/ark_cookies.json")  # 旧路径兼容
_ARK_PROJECT_SAVE = pathlib.Path(__file__).resolve().parent.parent / "data" / "ark_cookies.json"
_CACHE_MAX_AGE = 3600 * 6


def _resolve_ark_save(cookie_file: str = "") -> pathlib.Path:
    """按优先级解析 ark_cookies.json 路径：参数 > 项目 data/ > F:/eva/"""
    if cookie_file:
        p = pathlib.Path(cookie_file)
        if p.exists():
            return p
    if _ARK_PROJECT_SAVE.exists():
        return _ARK_PROJECT_SAVE
    return _ARK_DEFAULT_SAVE


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
    def get_conv_order(self, app_cid: str):
        """按会话 appCid 查询买家订单列表"""
        return _walle_call(
            f"/api/edith/walle/order/list?appCid={app_cid}&pageNum=1&pageSize=10", "GET"
        )

    def get_buyer_packages(self, buyer_user_id: str):
        """按买家 userId 查询订单包裹列表（eva.xiaohongshu.com/api/edith/customer/{userId}/packages/v2）"""
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
            url = f"https://eva.xiaohongshu.com/api/edith/customer/{buyer_user_id}/packages/v2"
            r = requests.get(url, headers=headers, timeout=15)
            res_json = r.json()
            success = res_json.get("msg") == "ok" or bool(res_json.get("data"))
            msg = res_json.get("msg", "")
        except Exception as e:
            logger.error(e)
            success, msg = False, str(e)
        return success, msg, res_json

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


def _load_ark_cookies(cookie_file: str = "") -> tuple[str, str]:
    """返回 (cookie_string, at_token)，优先从数据库读，fallback 文件"""
    import re

    # 优先从数据库读
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.security import decrypt_text
        from backend.app.models.platform_account import AccountCookieVersion, PlatformAccount
        from sqlalchemy import select

        db = SessionLocal()
        try:
            acc = db.scalars(select(PlatformAccount).where(PlatformAccount.sub_type == "ark")).first()
            if acc:
                ver = db.scalars(
                    select(AccountCookieVersion)
                    .where(AccountCookieVersion.platform_account_id == acc.id)
                    .order_by(AccountCookieVersion.created_at.desc())
                ).first()
                if ver:
                    data = json.loads(decrypt_text(ver.encrypted_cookies))
                    at_token = data.get("at_token", "")
                    pw_cookies = data.get("playwright_cookies") or []
                    cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in pw_cookies)
                    if at_token:
                        return cookie_string, at_token
        finally:
            db.close()
    except Exception:
        pass

    # fallback: 文件
    save = _resolve_ark_save(cookie_file)
    cookie_string = ""
    at_token = ""
    if save.exists():
        try:
            data = json.loads(save.read_text("utf-8"))
            at_token = data.get("at_token", "")
            pw_cookies: list[dict] = data.get("playwright_cookies") or []
            cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in pw_cookies)
            if not at_token:
                for c in pw_cookies:
                    if c["value"].startswith("AT-"):
                        at_token = c["value"]
                        break
        except Exception:
            pass

    if not at_token:
        raise ValueError("缺失登录凭证, 请重新登录")
    return cookie_string, at_token


async def _ark_page_fetch(api_path: str, method: str = "GET", body: dict = None, cookie_file: str = "") -> dict:
    """通过 CDP 让 ark 页面自身发请求（自动携带 x-s/x-t 签名）"""
    pages = json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())
    ws_url = None
    for p in pages:
        if "ark.xiaohongshu.com" in p.get("url", "") and p.get("type") == "page":
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        return await _ark_direct_fetch(api_path, method, body, cookie_file)

    body_json = json.dumps(body, ensure_ascii=False) if body is not None else None
    body_repr = json.dumps(body_json) if body_json else "null"
    full_url = f"https://ark.xiaohongshu.com{api_path}"

    js = f"""
    (async function() {{
        try {{
            const opts = {{
                method: '{method}',
                headers: {{'Content-Type': 'application/json', 'Accept': 'application/json'}},
                credentials: 'include',
            }};
            if ({body_repr} !== null) opts.body = {body_repr};
            const r = await fetch({json.dumps(full_url)}, opts);
            const text = await r.text();
            return JSON.stringify({{status: r.status, body: text}});
        }} catch(e) {{
            return JSON.stringify({{error: e.message}});
        }}
    }})()
    """
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": js, "awaitPromise": True, "returnByValue": True}}))
        for _ in range(30):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if msg.get("id") == 1:
                val = msg.get("result", {}).get("result", {}).get("value", "{}")
                outer = json.loads(val) if val else {}
                if "error" in outer:
                    raise RuntimeError(outer["error"])
                return json.loads(outer.get("body", "{}"))
    return {}


async def _ark_direct_fetch(api_path: str, method: str = "GET", body: dict = None, cookie_file: str = "") -> dict:
    """ark 没有开着时，用存储的 cookie 直接请求（无签名，可能 401）"""
    cookie_string, at_token = _load_ark_cookies(cookie_file)
    headers = {
        "authorization": at_token,
        "cookie": cookie_string,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://ark.xiaohongshu.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        "origin": "https://ark.xiaohongshu.com",
    }
    url = f"https://ark.xiaohongshu.com{api_path}"
    r = requests.request(method, url, headers=headers, json=body, timeout=15)
    return r.json()


def _ark_call(api_path: str, method: str = "GET", body: dict = None, cookie_file: str = ""):
    res_json = None
    try:
        res_json = asyncio.run(_ark_page_fetch(api_path, method, body, cookie_file))
        success = res_json.get("success", False) or res_json.get("code") in (0, 200)
        msg = res_json.get("msg", "")
    except Exception as e:
        logger.error(e)
        success, msg = False, str(e)
    return success, msg, res_json


class ArkAPI:
    """ark.xiaohongshu.com 商家后台接口（千帆卖家平台）"""

    def __init__(self, cookie_file: str = ""):
        self._cookie_file = cookie_file

    # ── 卖家基础信息 ──────────────────────────────────────────
    def get_seller_info_v2(self) -> tuple:
        return _ark_call("/api/edith/seller/info/v2", cookie_file=self._cookie_file)

    def get_seller_info(self) -> tuple:
        return _ark_call("/api/edith/seller/get_seller_info", cookie_file=self._cookie_file)

    def get_shop_score(self) -> tuple:
        return _ark_call("/api/edith/home/get_shop_score", "POST", {"data": {"source": "PC"}}, self._cookie_file)

    def get_todolist(self) -> tuple:
        return _ark_call("/edith/api/seller/todolist?end_type=pc", cookie_file=self._cookie_file)

    def get_menu_tree(self) -> tuple:
        return _ark_call("/api/edith/juliet/uno/get_menu_tree", cookie_file=self._cookie_file)

    def get_sidebar(self) -> tuple:
        return _ark_call("/api/edith/bench/sidebar?system_code=system_ark_v3", cookie_file=self._cookie_file)

    def get_key_metric_realtime(self, date_type: int = -1) -> tuple:
        return _ark_call("/edith/api/seller/home/key_metric_realtime", "POST", {"date_type": date_type}, self._cookie_file)

    # ── 商品管理 ──────────────────────────────────────────────
    def search_items(
        self,
        page_no: int = 1,
        page_size: int = 20,
        sort_field: str = "create_time",
        order: str = "desc",
        card_type: int = 2,
        is_channel: bool = False,
        keyword: str = None,
    ) -> tuple:
        """
        搜索商品列表 POST /api/edith/product/search_item_v2
        card_type: 2=在售 3=仓库中 4=已售罄 5=审核中 6=已下架 10=违规下架
        """
        search_filter: dict = {"card_type": card_type, "is_channel": is_channel}
        if keyword:
            search_filter["keyword"] = keyword
        body = {
            "page_no": page_no,
            "page_size": page_size,
            "search_order": {"sort_field": sort_field, "order": order},
            "search_filter": search_filter,
            "search_item_detail_option": {
                "with_product_quality_score": True,
                "with_hot_item_award_text_info": True,
                "with_ai_publish_note_permission": True,
                "with_inventory_risk_info": True,
                "with_item_lock_info": True,
            },
        }
        return _ark_call("/api/edith/product/search_item_v2", "POST", body, self._cookie_file)

    def get_item_count(self) -> tuple:
        return _ark_call("/api/edith/product/seller_item_count", "POST", {}, self._cookie_file)

    def get_common_config(self) -> tuple:
        return _ark_call("/api/edith/product/get_common_config", "POST", {}, self._cookie_file)

    def get_logistics_info(self) -> tuple:
        return _ark_call("/api/edith/product/get_logistics_info", "POST", {}, self._cookie_file)

    def get_delivery_time_rule(self, param_list: list[dict] = None) -> tuple:
        return _ark_call("/api/edith/product/get_delivery_time_rule", "POST",
                         {"paramList": param_list or [{}]}, self._cookie_file)

    def check_freeze(self) -> tuple:
        return _ark_call("/api/edith/product/check_freeze", "POST", {}, self._cookie_file)

    def get_out_of_inventory_items(self, channel: bool = False) -> tuple:
        return _ark_call(f"/api/edith/product/stock/getout_of_inventory_item?channel={str(channel).lower()}",
                         cookie_file=self._cookie_file)

    def get_inventory_gray_config(self) -> tuple:
        return _ark_call("/api/edith/inventory/gray_config", cookie_file=self._cookie_file)

    def get_seller_property_hosting_status(self) -> tuple:
        return _ark_call("/api/edith/product/seller_property_hosting_status", cookie_file=self._cookie_file)

    def get_item_list_resource_card(self, source: int = 1) -> tuple:
        return _ark_call("/api/edith/product/get_item_list_resource_card", "POST", {"source": source}, self._cookie_file)

    def get_item_detail(self, item_id: str, publish_type: int = 2, source_type: int = 1) -> tuple:
        """
        商品完整规格/SKU 详情 POST /api/edith/product/publish_render
        返回 data.product.productDetail.skuList[] 含规格、价格、库存、发货时效
        """
        data_str = json.dumps({"publishType": publish_type, "sourceType": source_type, "itemId": item_id})
        return _ark_call("/api/edith/product/publish_render", "POST", {"data": data_str}, self._cookie_file)

    # ── 消息中心 ──────────────────────────────────────────────
    def get_unread_count(self) -> tuple:
        return _ark_call("/api/edith/open/message/v2/unread-count", cookie_file=self._cookie_file)

    def get_important_msgs(self, page_size: int = 1, create_time_gt: int = None) -> tuple:
        ts = create_time_gt or int(time.time()) - 7 * 86400
        return _ark_call(
            f"/api/edith/open/message/v2/important-msgs?information_levels=100&page_size={page_size}&create_time_gt={ts}",
            cookie_file=self._cookie_file,
        )

    def get_latest_group_msgs(self, channel: int = 1) -> tuple:
        return _ark_call("/api/edith/open/message/latest_group_mgs", "POST", {"channel": channel}, self._cookie_file)


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
