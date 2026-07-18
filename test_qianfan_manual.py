"""
手动测试千帆 Cookie
用法: python test_qianfan_manual.py
"""
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 千帆 Cookie
COOKIE_STRING = """abRequestId=52935de7-eb99-5197-a090-534cf592213d; a1=19a5d498b0fkcv8oq6ey2mdp1zflti6l5irx0zfyk50000447865; webId=c357f9995a01ccc2834db167be8e1b90; gid=yj02f4jDKS28yj02f4jYD3ui8iTShYlAKdvJFvT6fUyuiC28193K1888844WYK28KDjyYJ8D; ets=1783904916754; websectiga=cf46039d1971c7b9a650d87269f31ac8fe3bf71d61ebf9d9a0a87efb414b816c; sec_poison_id=318ac876-391c-4e49-8380-3a111cfe447c; solar.beaker.session.id=AT-68c517663400328398962691u3koskmhwg26p7ca; access-token-pgy.xiaohongshu.com=customer.pgy.AT-68c517663400328398962691u3koskmhwg26p7ca; access-token-pgy.beta.xiaohongshu.com=customer.pgy.AT-68c517663400328398962691u3koskmhwg26p7ca; xsecappid=qual-center-pc; loadts=1784274504318"""

def parse_cookie(cookie_str):
    """解析 cookie 字符串"""
    cookies = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies

cookies = parse_cookie(COOKIE_STRING)
print(f"Cookie 键: {list(cookies.keys())}")

# 测试千帆 API
url = "https://pgy.xiaohongshu.com/api/draco/distributor-square/distributors-tags"
params = {"types": "distribution_category"}
headers = {
    "authority": "pgy.xiaohongshu.com",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10, verify=False)
print(f"\n状态码: {resp.status_code}")
data = resp.json()
print(f"success: {data.get('success')}, code: {data.get('code')}, msg: {data.get('msg')}")

if data.get("success"):
    print(f"\n✅ Cookie 有效！可以访问千帆 API")
    categories = data.get('data', {}).get('distributor_tag_map', {}).get('distribution_category', [])
    print(f"分销商类目数量: {len(categories)}")
else:
    print(f"\n❌ Cookie 无效或已过期")
