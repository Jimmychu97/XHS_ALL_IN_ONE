import sys, os
sys.path.insert(0, r"F:\XHS_ALL_IN_ONE")
os.chdir(r"F:\XHS_ALL_IN_ONE")

app_cid = "$3$MSMyIzIjNWY0MGQ4MGUwMDAwMDAwMDAxMDAyZjAx.MSMzIzYjNjlhYmM2ZjI5MjZkYTMwMDE1OTdmN2Ey"

from backend.app.api.walle import _extract_buyer_id_from_app_cid, _check_order_status, _fetch_buyer_orders

buyer_id = _extract_buyer_id_from_app_cid(app_cid)
print(f"Buyer ID: {buyer_id}")
print()

print("=== _check_order_status ===")
status, detail = _check_order_status(app_cid)
print(f"Status: {status}")
if detail:
    keys = list(detail.keys())[:15]
    print(f"Keys: {keys}")
    skus = detail.get("skuSnapshots", [])
    if skus:
        print(f"  Goods: {skus[0].get('name', 'N/A')}")
        print(f"  Spec: {skus[0].get('scskuCode', 'N/A')}")

print()
print("=== _fetch_buyer_orders ===")
info = _fetch_buyer_orders(app_cid)
print(f"Orders: {info if info else 'EMPTY'}")
