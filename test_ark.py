import sys, os
sys.path.insert(0, '.')
os.chdir(r'f:/XHS_ALL_IN_ONE')

from apis.xhs_walle_eva_apis import ArkAPI

print('=== test get_item_detail ===')
try:
    api = ArkAPI()
    ok, msg, res = api.get_item_detail('69be73d315bd7400015f6592')
    print('ok:', ok)
    print('msg:', msg)
    if res:
        print('res keys:', list(res.keys()))
        print('code:', res.get('code'))
        data = res.get('data')
        print('data type:', type(data))
        if isinstance(data, str):
            import json
            data = json.loads(data)
            skus = data.get('product',{}).get('productDetail',{}).get('skuList',[])
            print('skuList count:', len(skus))
            if skus:
                print('sku[0] variantInfos:', skus[0].get('skuVariantInfos'))
    else:
        print('res is None/empty')
except Exception as e:
    import traceback
    print('EXCEPTION:', e)
    traceback.print_exc()

print('\n=== test search_items ===')
try:
    api2 = ArkAPI()
    ok2, msg2, res2 = api2.search_items(card_type=2, page_no=1, page_size=2)
    print('ok:', ok2, 'msg:', msg2)
    if res2:
        items = (res2.get('data') or {}).get('items', [])
        print('items count:', len(items))
except Exception as e:
    import traceback
    print('EXCEPTION:', e)
    traceback.print_exc()
