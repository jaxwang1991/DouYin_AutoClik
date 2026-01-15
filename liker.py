import asyncio
import random
import os
import time
from playwright.async_api import async_playwright

class DouYinLiker:
    def __init__(self, log_callback=None, status_callback=None):
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.is_running = False
        self.should_stop = False
        self.browser = None
        self.page = None
        self.playwright = None
        
        # 默认配置
        self.config = {
            "url": "",
            "headless": True,
            "fast_click_prob": 0.8,
            "fast_min": 0.05,
            "fast_max": 0.2,
            "slow_min": 0.5,
            "slow_max": 1.5,
            "cycle_mode": False,
            "work_min": 10,  # 分钟
            "rest_min": 5    # 分钟
        }
        
        # 状态变量
        self.total_likes = 0
        self.state = "IDLE" # IDLE, LIKING, RESTING, STOPPED, PAUSED_BY_USER, COOLDOWN, PAUSED_FOR_CAPTCHA
        self.manual_pause = False

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def update_stats(self):
        if self.status_callback:
            self.status_callback(self.total_likes, self.state)

    def pause(self):
        self.manual_pause = True
        self.state = "PAUSED_BY_USER"
        self.log("用户暂停了任务")
        self.update_stats()

    def resume(self):
        self.manual_pause = False
        self.state = "LIKING"
        self.log("任务已恢复")
        self.update_stats()

    async def start(self, config):
        self.config.update(config)
        self.should_stop = False
        self.is_running = True
        self.state = "STARTING"
        self.total_likes = 0
        self.update_stats()
        
        try:
            await self._run_browser()
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
        finally:
            await self.stop()

    async def stop(self):
        self.should_stop = True
        self.state = "STOPPING"
        self.update_stats()
        
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
            self.browser = None
            
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
            self.playwright = None
            
        self.is_running = False
        self.state = "STOPPED"
        self.log("任务已结束")
        self.update_stats()

    async def _run_browser(self):
        # 检查登录状态
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        
        if os.path.exists("state.json"):
            context_options["storage_state"] = "state.json"
        else:
            self.log("提示: 未找到登录状态(state.json)，将以游客模式运行")

        self.playwright = await async_playwright().start()
        
        self.log("正在启动浏览器...")
        self.browser = await self.playwright.chromium.launch(
            headless=self.config["headless"],
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = await self.browser.new_context(**context_options)
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.page = await context.new_page()
        
        self.log(f"正在进入直播间: {self.config['url']}")
        try:
            await self.page.goto(self.config["url"], timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            self.log(f"连接超时或失败: {e}")
            return

        # 等待加载
        self.log("正在等待视频加载...")
        video_element = None
        try:
            video_element = await self.page.wait_for_selector("video", state="attached", timeout=30000)
            self.log("视频加载成功！")
        except:
            self.log("警告: 未检测到video标签，将尝试盲点")

        # 循环变量
        self.state = "LIKING"
        cycle_start_time = time.time()
        click_errors = 0
        
        while not self.should_stop:
            current_time = time.time()

            # --- -1. 检查用户暂停 ---
            if self.manual_pause:
                self.state = "PAUSED_BY_USER" # 确保状态正确
                await asyncio.sleep(0.5)
                continue
            
            # --- 0. 检查验证码 (Captcha) ---
            try:
                # 方案：文本特征全域扫描
                is_captcha_detected = False
                
                # 特征 1: 核心文本 (主页面 + 所有 Frame)
                captcha_texts = ["请完成下列验证后继续", "向右滑动完成拼图", "旋转图片"]
                
                # 1.1 扫描主页面
                for text in captcha_texts:
                    if await self.page.get_by_text(text).is_visible():
                        is_captcha_detected = True
                        break
                
                # 1.2 扫描所有 Frames (如果主页面没找到)
                if not is_captcha_detected:
                    for frame in self.page.frames:
                        try:
                            for text in captcha_texts:
                                if await frame.get_by_text(text).is_visible():
                                    is_captcha_detected = True
                                    break
                            if is_captcha_detected: break
                        except: continue

                # 特征 2: 兜底选择器 (如果文本没找到)
                if not is_captcha_detected:
                    selectors = [".captcha_verify_container", "#captcha-verify-image", "[class*='captcha']"]
                    
                    # 2.1 主页面
                    for sel in selectors:
                         if await self.page.locator(sel).first.is_visible():
                             is_captcha_detected = True
                             break
                    
                    # 2.2 Frames
                    if not is_captcha_detected:
                        for frame in self.page.frames:
                            try:
                                for sel in selectors:
                                    if await frame.locator(sel).first.is_visible():
                                        is_captcha_detected = True
                                        break
                                if is_captcha_detected: break
                            except: continue

                if is_captcha_detected:
                    self.log("⚠️ 检测到验证码弹出！(通过特征匹配)")
                    self.state = "PAUSED_FOR_CAPTCHA"
                    self.update_stats()
                    
                    # 持续等待直到验证码消失
                    while not self.should_stop:
                        still_visible = False
                        
                        # 复查逻辑：只要任意特征还存在，就认为没消失
                        # 1. 查主页面文本
                        for text in captcha_texts:
                            if await self.page.get_by_text(text).is_visible():
                                still_visible = True
                                break
                        
                        # 2. 查Frames文本
                        if not still_visible:
                            for frame in self.page.frames:
                                try:
                                    for text in captcha_texts:
                                        if await frame.get_by_text(text).is_visible():
                                            still_visible = True
                                            break
                                    if still_visible: break
                                except: continue
                        
                        if not still_visible:
                            self.log("✅ 验证码已消失，恢复自动点赞...")
                            self.state = "LIKING"
                            self.update_stats()
                            break
                        await asyncio.sleep(1)
                    
                    if self.should_stop:
                        break
                    
                    continue
            except Exception as e:
                pass # 检测验证码出错不应中断

            # --- 0.5 检查"手速太快"提示 ---
            try:
                # 检查是否存在 "手速太快了，请休息一下吧~"
                if await self.page.get_by_text("手速太快了，请休息一下吧").is_visible():
                    self.log("⚠️ 检测到【手速太快】提示，进入3分钟冷却模式...")
                    self.state = "COOLDOWN"
                    
                    # 倒计时 180 秒
                    cooldown_seconds = 180
                    for i in range(cooldown_seconds, 0, -1):
                        if self.should_stop or self.manual_pause: break
                        
                        # 更新状态文本显示倒计时
                        if self.status_callback:
                            self.status_callback(self.total_likes, f"冷却中({i}s)")
                        
                        await asyncio.sleep(1)
                    
                    if not self.should_stop and not self.manual_pause:
                        self.log("冷却结束，恢复点赞...")
                        self.state = "LIKING"
                        self.update_stats()
                    
                    # 冷却结束后跳过本次循环
                    continue
            except Exception as e:
                pass

            # --- 1. 检查直播是否结束 ---
            try:
                # 策略A: 检查是否存在“直播已结束”相关文本
                # 这是一个模糊匹配，可能需要根据实际页面调整
                if await self.page.get_by_text("直播已结束").is_visible() or \
                   await self.page.get_by_text("已下播").is_visible():
                    self.log("检测到【直播已结束】提示，停止运行。")
                    break
                
                # 策略B: 检查视频元素是否还在
                # 如果video元素消失超过一定时间（这里简单检查当前瞬间）
                if not await self.page.locator("video").count():
                    # 双重确认
                    await asyncio.sleep(2)
                    if not await self.page.locator("video").count():
                        self.log("检测到视频流消失，判定直播结束。")
                        break
            except Exception as e:
                pass # 页面检测出错不应中断主循环

            # --- 2. 循环模式 (工作/休息) ---
            if self.config["cycle_mode"]:
                elapsed = (current_time - cycle_start_time) / 60 # 分钟
                
                if self.state == "LIKING":
                    if elapsed >= float(self.config["work_min"]):
                        self.state = "RESTING"
                        self.log(f"已工作 {int(elapsed)} 分钟，开始休息 {self.config['rest_min']} 分钟...")
                        cycle_start_time = current_time # 重置计时器用于休息
                        self.update_stats()
                
                elif self.state == "RESTING":
                    if elapsed >= float(self.config["rest_min"]):
                        self.state = "LIKING"
                        self.log("休息结束，继续工作...")
                        cycle_start_time = current_time # 重置计时器用于工作
                        self.update_stats()
                        
            # --- 3. 执行动作 ---
            if self.state == "RESTING":
                # 实时显示倒数时间
                if self.config["cycle_mode"]:
                    elapsed_min = (current_time - cycle_start_time) / 60
                    rest_min = float(self.config["rest_min"])
                    remaining_sec = max(0, int((rest_min - elapsed_min) * 60))
                    m, s = divmod(remaining_sec, 60)
                    if self.status_callback:
                        self.status_callback(self.total_likes, f"休息中... 剩余 {m}分{s:02d}秒")

                await asyncio.sleep(1)
                continue
                
            # 执行点赞逻辑
            try:
                # 动态获取位置
                x, y = 0, 0
                if video_element:
                    try:
                        box = await video_element.bounding_box()
                        if box:
                            margin_x = box["width"] * 0.2
                            margin_y = box["height"] * 0.2
                            x = box["x"] + random.uniform(margin_x, box["width"] - margin_x)
                            y = box["y"] + random.uniform(margin_y, box["height"] - margin_y)
                    except:
                        video_element = None # 元素失效
                
                if x == 0: # 降级
                    vp = self.page.viewport_size
                    if vp:
                        x = vp["width"] / 2 + random.randint(-50, 50)
                        y = vp["height"] / 2 + random.randint(-50, 50)
                    else:
                        x, y = 500, 500
                
                await self.page.mouse.dblclick(x, y)
                self.total_likes += 1
                
                # 每50次更新一次UI
                if self.total_likes % 50 == 0:
                    self.update_stats()
                    # 截图验证
                    if self.config["headless"] and self.total_likes % 200 == 0:
                         if not os.path.exists("logs"):
                             os.makedirs("logs")
                         ts = time.strftime("%H-%M-%S")
                         await self.page.screenshot(path=f"logs/auto_{ts}.png")

                # 随机间隔
                if random.random() < self.config["fast_click_prob"]:
                    await asyncio.sleep(random.uniform(self.config["fast_min"], self.config["fast_max"]))
                else:
                    await asyncio.sleep(random.uniform(self.config["slow_min"], self.config["slow_max"]))
                
                click_errors = 0 # 重置错误计数

            except Exception as e:
                click_errors += 1
                if click_errors > 20:
                    self.log("连续操作失败，可能页面崩溃或网络断开")
                    break
                await asyncio.sleep(1)
