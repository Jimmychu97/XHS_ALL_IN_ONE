"""
测试 Creator Cookie 能否访问千帆工作台
用法: python test_qianfan_cookie.py
"""
import json
import sys
import requests
import urllib3

# 抑制 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from backend.app.core.config import get_settings
from backend.app.core.security import decrypt_text
from backend.app.models import PlatformAccount, AccountCookieVersion
from xhs_utils.xhs_qianfan_util import get_qianfan_headers_template
from xhs_utils.cookie_util import trans_cookies

settings = get_settings()
engine = create_engine(settings.database_url)

with Session(engine) as db:
    for sub_type in ("creator", "pc"):
        account = db.scalars(
            select(PlatformAccount).where(
                PlatformAccount.platform == "xhs",
                PlatformAccount.sub_type == sub_type,
            )
        ).first()
        if account:
            break

    if not account:
        print("❌ 没有找到任何账号")
        sys.exit(1)

    print(f"使用账号: {account.nickname} (sub_type={account.sub_type}, id={account.id})")

    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()

    cookie_string = decrypt_text(cookie_version.encrypted_cookies)

stripped = cookie_string.strip()
cookies = json.loads(stripped) if stripped.startswith("{") else trans_cookies(cookie_string)
print(f"Cookie 键: {list(cookies.keys())}")

url = "https://pgy.xiaohongshu.com/api/draco/distributor-square/distributors-tags"
params = {"types": "distribution_category"}
headers = get_qianfan_headers_template()

resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10, verify=False)
print(f"\n状态码: {resp.status_code}")
data = resp.json()
print(f"success: {data.get('success')}, code: {data.get('code')}, msg: {data.get('msg')}")

if data.get("success"):
    print(f"✅ {account.sub_type} Cookie 可以访问千帆！")
else:
    print(f"❌ {account.sub_type} Cookie 也不行，千帆必须单独登录 pgy.xiaohongshu.com")
