"""
用 Playwright 打开千帆登录页，用户扫码登录后自动抓取 Cookie
用法: python test_qianfan_login.py
"""
import json
import requests
from playwright.sync_api import sync_playwright
from xhs_utils.xhs_qianfan_util import get_qianfan_headers_template


def verify_qianfan_cookie(cookies: dict) -> bool:
    url = "https://pgy.xiaohongshu.com/api/draco/distributor-square/distributors-tags"
    params = {"types": "distribution_category"}
    resp = requests.get(url, headers=get_qianfan_headers_template(), cookies=cookies, params=params, timeout=10)
    data = resp.json()
    print(f"验证结果: status={resp.status_code}, success={data.get('success')}, msg={data.get('msg')}")
    return data.get("success", False)


def get_qianfan_cookies_via_browser() -> dict | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("正在打开千帆登录页...")
        page.goto("https://pgy.xiaohongshu.com")

        print("请在浏览器中完成登录（扫码或账号密码），登录成功后脚本自动继续...")

        # 等待登录成功：检测跳转到工作台页面
        page.wait_for_url("**/pgy.xiaohongshu.com/**", timeout=120_000)

        # 等待页面稳定后再抓 Cookie
        page.wait_for_load_state("networkidle", timeout=30_000)

        # 确认已离开登录页
        if "login" in page.url:
            print("还在登录页，继续等待...")
            page.wait_for_function("!window.location.href.includes('login')", timeout=60_000)

        cookies_list = context.cookies("https://pgy.xiaohongshu.com")
        browser.close()

        cookies = {c["name"]: c["value"] for c in cookies_list}
        print(f"\n抓到 {len(cookies)} 个 Cookie: {list(cookies.keys())}")
        return cookies


if __name__ == "__main__":
    cookies = get_qianfan_cookies_via_browser()
    if not cookies:
        print("未抓到 Cookie")
        raise SystemExit(1)

    print("\n开始验证 Cookie 是否能访问千帆接口...")
    if verify_qianfan_cookie(cookies):
        print("\nCookie 字符串（可用于导入）:")
        print("; ".join(f"{k}={v}" for k, v in cookies.items()))
    else:
        print("Cookie 无效，请重试")
