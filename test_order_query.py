"""
测试订单查询两条路径是否能跑通
用法：python test_order_query.py
"""
import json

# ── 测试1：ArkAPI 订单查询（Agent 工具用的路径）──────────────────────────────
print("=" * 60)
print("测试1：ArkAPI.get_orders_by_user（Agent check_order_status 工具）")
print("=" * 60)

TEST_BUYER_USER_ID = ""  # ← 填一个真实买家的 XHS userId，如 5f40d80e0000000001002f01

try:
    from apis.xhs_walle_eva_apis import ArkAPI
    api = ArkAPI()

    if not TEST_BUYER_USER_ID:
        # 不指定 userId，查全部订单看接口是否通
        print("未填 TEST_BUYER_USER_ID，查全部订单（前5条）...")
        ok, msg, res = api.get_orders(page_size=5)
    else:
        ok, msg, res = api.get_orders_by_user(TEST_BUYER_USER_ID)

    print(f"ok={ok}, msg={msg}")
    if res:
        packages = (res.get("data") or {}).get("packages") or []
        print(f"返回包裹数: {len(packages)}")
        for pkg in packages[:3]:
            print(f"  orderId={pkg.get('orderId')} status={pkg.get('status')} userId={pkg.get('userId')}")
    else:
        print("res=None")
except Exception as e:
    import traceback
    traceback.print_exc()

# ── 测试2：WalleEvaAPI.get_buyer_packages（前置拦截用的路径）────────────────
print()
print("=" * 60)
print("测试2：WalleEvaAPI.get_buyer_packages（_check_order_status 前置拦截）")
print("=" * 60)

TEST_APP_CID = ""  # ← 填一个真实 app_cid，如 $3$xxxxxxxx

try:
    from apis.xhs_walle_eva_apis import WalleEvaAPI
    api2 = WalleEvaAPI()

    if TEST_APP_CID:
        buyer_id = TEST_APP_CID[-20:] if len(TEST_APP_CID) >= 20 else TEST_APP_CID
        print(f"从 app_cid 提取 buyer_id: {buyer_id}")
        ok, msg, res = api2.get_buyer_packages(buyer_id)
        print(f"ok={ok}, msg={msg}")
        if res:
            data = res.get("data") or {}
            packages = data.get("resultList") or data.get("packages") or []
            print(f"返回包裹数: {len(packages)}")
            for pkg in packages[:3]:
                status = pkg.get("erpStatusStr") or pkg.get("orderStatus") or ""
                print(f"  status={status}")
        else:
            print("res=None")
    else:
        print("未填 TEST_APP_CID，跳过测试2")
except Exception as e:
    import traceback
    traceback.print_exc()

print()
print("完成。如果测试1 ok=True 且有包裹数据，说明 ArkAPI 订单查询正常。")
