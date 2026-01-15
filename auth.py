import asyncio
from playwright.async_api import async_playwright
import os

async def login():
    async with async_playwright() as p:
        print("正在启动浏览器...")
        # 启动有头模式，方便用户扫码
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}, # 设置一个较大的视口
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("正在打开抖音首页...")
        await page.goto("https://www.douyin.com/")
        
        print("\n" + "="*50)
        print("请在弹出的浏览器窗口中完成登录（推荐使用抖音APP扫码）。")
        print("登录成功后，请回到此命令行窗口，按【回车键】保存状态并退出。")
        print("="*50 + "\n")
        
        # 使用 run_in_executor 避免阻塞事件循环，尽管在这个简单脚本中直接 input 也可以
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, input, "登录完成后，请按回车键继续...")
        
        # 保存 cookies 和 local storage
        await context.storage_state(path="state.json")
        print("\n登录状态已保存到 state.json")
        print("您现在可以运行 main.py 进行自动点赞了。")
        
        await browser.close()

if __name__ == "__main__":
    print("准备开始登录流程...")
    asyncio.run(login())
