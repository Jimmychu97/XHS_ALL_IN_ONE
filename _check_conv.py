import sqlite3

conn = sqlite3.connect(r"F:\XHS_ALL_IN_ONE\data\spider_xhs.db")
cur = conn.cursor()
rows = cur.execute(
    """SELECT id, user_id, platform_account_id, app_cid, customer_name, customer_id, status
       FROM walle_conversations
       WHERE app_cid LIKE '%MjZkYTMwMDE1OTdmN2Ey%' OR app_cid LIKE '%NWY0MGQ4MGUwMDAwMDAwMDAxMDAyZjAx%'"""
).fetchall()
print("conversations:")
for r in rows:
    print(f"  id={r[0]} user_id={r[1]} platform_account_id={r[2]} customer_name={r[4]!r} customer_id={r[5]!r} status={r[6]}")
print("total:", len(rows))
conn.close()
