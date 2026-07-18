"""
千帆平台自动登录工具 - 批量下载浏览器版本
用法: 
  1. python qianfan_login.py download  # 下载浏览器
  2. python qianfan_login.py           # 运行登录
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

# 浏览器下载地址
CHROMIUM_URL = "https://cdn.playwright.dev/builds/cft/149.0.7827.55/win64/chrome-win64.zip"
CHROMIUM_PATH = Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1228" / "chrome-win64"


def download_browser():
    """下载 Chromium 浏览器"""
    print("=" * 60)
    print("下载 Chromium 浏览器")
    print("=" * 60)
    
    if CHROMIUM_PATH.exists():
        print(f"✅ 浏览器已存在: {CHROMIUM_PATH}")
        return True
    
    CHROMIUM_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    zip_path = CHROMIUM_PATH.parent / "chrome-win64.zip"
    
    print(f"\n下载地址: {CHROMIUM_URL}")
    print(f"保存路径: {zip_path}")
    print("\n正在下载...")
    
    try:
        # 使用 curl 下载（支持忽略 SSL）
        result = subprocess.run(
            ["curl", "-k", "-L", "-o", str(zip_path), CHROMIUM_URL],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ 下载失败: {result.stderr}")
            print("\n请手动下载:")
            print(f"  1. 浏览器打开: {CHROMIUM_URL}")
            print(f"  2. 下载后解压到: {CHROMIUM_PATH}")
            return False
        
        print("✅ 下载完成")
        
        # 解压
        print("\n正在解压...")
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(CHROMIUM_PATH.parent)
        
        print(f"✅ 解压完成: {CHROMIUM_PATH}")
        zip_path.unlink()
        return True
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("\n请手动下载:")
        print(f"  1. 浏览器打开: {CHROMIUM_URL}")
        print(f"  2. 下载后解压到: {CHROMIUM_PATH}")
        return False


async def login_qianfan():
    """打开浏览器，等待用户登录，自动抓取 Cookie"""
    print("=" * 60)
    print("千帆平台自动登录工具")
    print("=" * 60)
    print("\n步骤：")
    print("1. 浏览器将自动打开千帆登录页")
    print("2. 请手动扫码或输入账号密码登录")
    print("3. 登录成功后，程序自动保存 Cookie")
    print("=" * 60 + "\n")
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 请先安装 playwright:")
        print("  pip install playwright")
        return
    
    # 检查浏览器是否存在
    chrome_exe = CHROMIUM_PATH / "chrome.exe"
    if not chrome_exe.exists():
        print(f"❌ 浏览器不存在: {chrome_exe}")
        print("\n请先运行: python qianfan_login.py download")
        return
    
    async with async_playwright() as p:
        # 使用本地浏览器
        browser = await p.chromium.launch(
            headless=False,
            executable_path=str(chrome_exe),
            args=["--start-maximized"]
        )
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # 打开千帆登录页
        await page.goto("https://pgy.xiaohongshu.com")
        print("✅ 浏览器已打开，请在页面中完成登录...\n")
        
        # 等待登录成功的标志
        print("等待登录...")
        
        logged_in = False
        while not logged_in:
            await asyncio.sleep(1)
            cookies = await context.cookies()
            
            # 检查是否有关键的登录 Cookie
            has_access_token = any(c["name"].startswith("access-token") for c in cookies)
            has_session = any(c["name"] == "solar.beaker.session.id" for c in cookies)
            
            if has_access_token or has_session:
                logged_in = True
                print("✅ 检测到登录成功！正在保存 Cookie...\n")
        
        # 获取所有 Cookie
        cookies = await context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        cookie_string = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        
        # 保存到文件
        output_dir = Path("data/cookies")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / "qianfan_cookies.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "cookie_string": cookie_string,
                "cookie_dict": cookie_dict
            }, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Cookie 已保存到: {output_file}")
        print(f"\nCookie 字符串（可复制）：\n{cookie_string[:100]}...")
        print("\n现在可以在前端「账号矩阵」页面导入此 Cookie")
        
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "download":
        download_browser()
    else:
        asyncio.run(login_qianfan())
