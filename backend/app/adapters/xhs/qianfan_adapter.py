from __future__ import annotations
from backend.app.adapters.xhs.request_env import direct_xhs_request_env
from xhs_utils.cookie_util import trans_cookies


class QianFanAdapter:
    def _get_api(self):
        from apis.xhs_qianfan_apis import QianFanAPI
        return QianFanAPI()

    def get_categories(self, cookies_str: str) -> list:
        with direct_xhs_request_env():
            api = self._get_api()
            cookies = trans_cookies(cookies_str)
            return api.get_all_categories(cookies)

    def get_distributors(self, cookies_str: str, choice: str, page: int = 1) -> dict:
        with direct_xhs_request_env():
            api = self._get_api()
            cookies = trans_cookies(cookies_str)
            categories = api.get_all_categories(cookies)
            user_list, total = api.get_user_by_page(choice, categories, page, cookies)
            return {"items": user_list, "total": total}

    def get_distributor_detail(self, cookies_str: str, user_id: str) -> dict:
        with direct_xhs_request_env():
            api = self._get_api()
            cookies = trans_cookies(cookies_str)
            detail = api.get_user_detail(user_id, cookies)
            cooperation = api.get_user_cooperation(user_id, cookies)
            fans = api.get_user_fans(user_id, cookies)
            items = api.get_user_item(user_id, cookies)
            return {
                "detail": detail.get("data", {}),
                "cooperation": cooperation.get("data", {}),
                "fans": fans.get("data", {}),
                "items": items.get("data", {}),
            }
