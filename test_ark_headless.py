import asyncio, json, tempfile
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_FILE = Path('data/ark_cookies.json')
item_id = '69be73d315bd7400015f6592'

async def test():
    async with async_playwright() as pw:
        # 用临时 profile，避免和 daemon 冲突
        with tempfile.TemporaryDirectory() as tmp_dir:
            context = await pw.chromium.launch_persistent_context(
                tmp_dir, headless=False,
                args=['--disable-blink-features=AutomationControlled'],
                viewport={'width': 1440, 'height': 900},
            )
            if COOKIE_FILE.exists():
                data = json.loads(COOKIE_FILE.read_text('utf-8'))
                cookies = data.get('playwright_cookies') or []
                if cookies:
                    await context.add_cookies(cookies)
                    print(f'injected {len(cookies)} cookies')

            page = context.pages[0] if context.pages else await context.new_page()

            async def on_request(req):
                if 'publish_render' in req.url:
                    pd = req.post_data or ''
                    print(f'\n[REQ] body: {pd}')
                    try:
                        outer = json.loads(pd)
                        inner = json.loads(outer.get('data', '{}'))
                        print(f'[REQ] inner: {json.dumps(inner, ensure_ascii=False)}')
                    except Exception as e:
                        print(f'[REQ] parse err: {e}')

            async def on_response(resp):
                if 'publish_render' in resp.url:
                    try:
                        body = await resp.json()
                        print(f'[RESP] code={body.get("code")} success={body.get("success")}')
                        if body.get('success'):
                            d = body.get('data')
                            if isinstance(d, str): d = json.loads(d)
                            skus = d.get('product', {}).get('productDetail', {}).get('skuList') or []
                            print(f'[RESP] skuList: {len(skus)}')
                            if skus:
                                print(f'[RESP] first sku: {json.dumps(skus[0], ensure_ascii=False)[:400]}')
                        else:
                            print(f'[RESP] full: {json.dumps(body, ensure_ascii=False)[:300]}')
                    except Exception as e:
                        print(f'[RESP] err: {e}')

            page.on('request', lambda r: asyncio.ensure_future(on_request(r)))
            page.on('response', lambda r: asyncio.ensure_future(on_response(r)))

            # 先去列表页建立会话，再跳编辑页
            print('goto list page first...')
            await page.goto('https://ark.xiaohongshu.com/app-item/list/shelf', wait_until='networkidle', timeout=45000)
            print(f'list url: {page.url}')
            await asyncio.sleep(1)

            edit_url = f'https://ark.xiaohongshu.com/app-item/good/edit/{item_id}'
            print(f'goto {edit_url}')
            await page.goto(edit_url, wait_until='networkidle', timeout=45000)
            print(f'url: {page.url}')
            await asyncio.sleep(3)
            print('\n等待 publish_render（按 Ctrl+C 退出）')

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass

            await context.close()

asyncio.run(test())
