import asyncio
import random
import os
import time
from playwright.async_api import async_playwright

# --- 配置参数 ---
# 点击区域范围 (0.0 - 0.5): 
# 0.2 表示在视频中间 60% 的区域内点击 (上下左右各留 20% 边距)
CLICK_AREA_MARGIN = 0.2 

# 快速点击模式概率 (0.0 - 1.0): 
# 0.8 表示 80% 的概率会进行快速连点
FAST_CLICK_PROBABILITY = 0.8

# 快速点击间隔 (秒):
FAST_CLICK_INTERVAL_MIN = 0.05
FAST_CLICK_INTERVAL_MAX = 0.2

# 慢速(停顿)间隔 (秒):
SLOW_CLICK_INTERVAL_MIN = 0.5
SLOW_CLICK_INTERVAL_MAX = 1.5
# ----------------

async def auto_like(url, headless=True):
    if not os.path.exists("state.json"):
        print("警告: 未找到登录状态文件 state.json。")
        print("建议先运行 auth.py 进行登录，否则点赞可能无效或被频繁打断。")
        confirm = input("是否继续以游客身份运行？(y/n): ")
        if confirm.lower() != 'y':
            return
            
    # 创建截图目录
    if headless:
        if not os.path.exists("logs"):
            os.makedirs("logs")

    async with async_playwright() as p:
        print("正在后台启动浏览器..." if headless else "正在启动浏览器(可视化模式)...")
        # 启动参数配置，尽量模拟真实环境
        browser = await p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        
        if os.path.exists("state.json"):
            context_options["storage_state"] = "state.json"
            
        context = await browser.new_context(**context_options)
        
        # 添加一些防检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()

        print(f"正在连接直播间: {url}")
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"加载页面出错: {e}")
            return

        print("等待直播视频加载...")
        # 尝试定位视频元素
        video_element = None
        try:
            # 等待video标签出现
            video_element = await page.wait_for_selector("video", state="attached", timeout=30000)
            print("找到视频元素！")
        except:
            print("未找到视频元素，尝试直接点击屏幕中心。")

        print("开始自动点赞 (按 Ctrl+C 停止)...")
        if headless:
            print("提示: 程序将每隔100次点赞保存一张截图到 logs 文件夹，以便您确认运行状态。")
        else:
            print("提示: 可视化模式下，如果在命令行按 'p' 键可以暂停点赞(方便处理验证码)，按 'r' 键恢复。")
        
        count = 0
        click_errors = 0
        
        try:
            while True:
                # 检查按键 (仅Windows有效)
                if os.name == 'nt' and not headless:
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                        if key == 'p':
                            print("\n[已暂停] 请手动处理验证码或其他操作。处理完成后回到此窗口按 'r' 继续...")
                            while True:
                                if msvcrt.kbhit():
                                    if msvcrt.getch().decode('utf-8', errors='ignore').lower() == 'r':
                                        print("[已恢复] 继续点赞...")
                                        break
                                await asyncio.sleep(0.1)

                # 确定点击位置
                x, y = 0, 0
                
                if video_element:
                    try:
                        box = await video_element.bounding_box()
                        if box:
                            # 在视频区域中间 60% 的范围内随机点击
                            margin_x = box["width"] * CLICK_AREA_MARGIN
                            margin_y = box["height"] * CLICK_AREA_MARGIN
                            x = box["x"] + random.uniform(margin_x, box["width"] - margin_x)
                            y = box["y"] + random.uniform(margin_y, box["height"] - margin_y)
                    except:
                        video_element = None # 元素可能失效了
                
                if x == 0 and y == 0:
                    # 降级方案：点击屏幕中心
                    vp = page.viewport_size
                    if vp:
                        x = vp["width"] / 2 + random.randint(-100, 100)
                        y = vp["height"] / 2 + random.randint(-100, 100)
                    else:
                        x, y = 640, 400

                # 执行双击
                try:
                    await page.mouse.dblclick(x, y)
                    count += 1
                    if count % 50 == 0:
                        print(f"已执行 {count} 次点赞动作...")
                        
                    # 截图验证 (仅在无头模式下，每100次)
                    if headless and count % 100 == 0:
                        timestamp = time.strftime("%H-%M-%S")
                        screenshot_path = f"logs/screenshot_{timestamp}.png"
                        await page.screenshot(path=screenshot_path)
                        print(f"  [验证] 已保存截图: {screenshot_path}")
                    
                    # 动态调整间隔，模拟真人
                    # 快速连点几下，然后停顿
                    if random.random() < FAST_CLICK_PROBABILITY:
                        # 快速点击模式
                        await asyncio.sleep(random.uniform(FAST_CLICK_INTERVAL_MIN, FAST_CLICK_INTERVAL_MAX))
                    else:
                        # 停顿模式
                        await asyncio.sleep(random.uniform(SLOW_CLICK_INTERVAL_MIN, SLOW_CLICK_INTERVAL_MAX))
                        
                except Exception as e:
                    click_errors += 1
                    if click_errors > 10:
                        print("连续点击失败，可能页面已关闭或结构改变。")
                        break
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n已停止运行。")
        finally:
            await browser.close()
            print(f"本次运行共尝试点赞 {count} 次。")

if __name__ == "__main__":
    import sys
    
    # 简单的命令行参数处理
    target_url = ""
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    
    if not target_url:
        print("="*40)
        print("   抖音直播间自动点赞工具 (后台版)")
        print("="*40)
        target_url = input("请输入直播间链接: ").strip()
    
    # 询问是否显示窗口
    headless_mode = True
    if target_url:
        mode_input = input("是否显示浏览器窗口以便观察? (y/n, 默认n): ").strip().lower()
        if mode_input == 'y':
            headless_mode = False
            
        if "douyin.com" not in target_url:
            print("警告: 这看起来不像是一个抖音链接，但程序仍将尝试运行。")
            
        asyncio.run(auto_like(target_url, headless=headless_mode))
    else:
        print("未输入链接，退出。")
