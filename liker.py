"""
DouYin Auto Liker - Core module with optimized code
"""
import asyncio
import random
import os
import time
from base import BrowserBase
from config import Config, DEFAULT_CONFIG


class DouYinLiker(BrowserBase):
    """Auto like functionality for DouYin live streams"""

    def __init__(self, log_callback=None, status_callback=None):
        super().__init__(log_callback)
        self.status_callback = status_callback
        self.is_running = False
        self.should_stop = False
        self.manual_pause = False

        # Config with defaults
        self.config = DEFAULT_CONFIG.copy()
        self.config["url"] = ""
        self.config["headless"] = True

        # Runtime state
        self.total_likes = 0
        self.state = "IDLE"

    def update_stats(self):
        if self.status_callback:
            self.status_callback(self.total_likes, self.state)

    def pause(self):
        self.manual_pause = True
        self.state = "PAUSED_BY_USER"
        self.log("用户已暂停")
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
            await self._run()
        except Exception as e:
            self.log(f"发生错误: {e}")
        finally:
            await self.stop()

    async def stop(self):
        self.should_stop = True
        self.state = "STOPPING"
        self.update_stats()
        await self.close()
        self.is_running = False
        self.state = "STOPPED"
        self.log("任务已停止")
        self.update_stats()

    async def _run(self):
        """Main run loop"""
        # Launch browser
        await self.launch_browser(headless=self.config["headless"])

        self.log(f"正在连接直播间: {self.config['url']}")
        try:
            await self.page.goto(self.config["url"], timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            self.log(f"连接失败: {e}")
            return

        # Wait for video
        self.log("正在等待视频加载...")
        video_element = await self._wait_for_video()

        self.state = "LIKING"
        cycle_start_time = time.time()
        click_errors = 0

        while not self.should_stop:
            current_time = time.time()

            # Check manual pause
            if self.manual_pause:
                self.state = "PAUSED_BY_USER"
                await asyncio.sleep(0.5)
                continue

            # Check captcha
            if await self._check_captcha():
                continue

            # Check speed limit
            if await self._check_speed_limit():
                continue

            # Check live end
            if await self._check_live_end():
                break

            # Cycle mode (work/rest)
            if self.config["cycle_mode"]:
                if not self._handle_cycle_mode(current_time, cycle_start_time):
                    cycle_start_time = current_time
                    continue

            # Resting state - skip click
            if self.state == "RESTING":
                await self._show_rest_countdown(current_time, cycle_start_time)
                continue

            # Execute click
            try:
                await self._do_click(video_element)
                click_errors = 0
            except Exception:
                click_errors += 1
                if click_errors > Config.MAX_CLICK_ERRORS:
                    self.log("连续错误次数过多，自动停止")
                    break
                await asyncio.sleep(1)

    async def _wait_for_video(self):
        """Wait for video element"""
        try:
            video = await self.page.wait_for_selector("video", state="attached", timeout=30000)
            self.log("视频加载成功!")
            return video
        except:
            self.log("警告: 未找到视频元素，将尝试盲点")
            return None

    async def _check_captcha(self):
        """Check and wait for captcha"""
        try:
            # Check main page
            for text in Config.CAPTCHA_TEXTS:
                if await self.page.get_by_text(text).is_visible():
                    return await self._wait_captcha_clear()

            # Check frames
            for frame in self.page.frames:
                try:
                    for text in Config.CAPTCHA_TEXTS:
                        if await frame.get_by_text(text).is_visible():
                            return await self._wait_captcha_clear()
                except:
                    continue

            # Check selectors
            for sel in Config.CAPTCHA_SELECTORS:
                if await self.page.locator(sel).first.is_visible():
                    return await self._wait_captcha_clear()

            return False
        except:
            return False

    async def _wait_captcha_clear(self):
        """Wait for captcha to be resolved"""
        if self.state != "PAUSED_FOR_CAPTCHA":
            self.log("检测到验证码! 等待用户处理...")
            self.state = "PAUSED_FOR_CAPTCHA"
            self.update_stats()

        while not self.should_stop:
            still_captcha = False
            try:
                # Check texts
                for text in Config.CAPTCHA_TEXTS:
                    if await self.page.get_by_text(text).is_visible():
                        still_captcha = True
                        break
                
                # Check frames if not found yet
                if not still_captcha:
                    for frame in self.page.frames:
                        try:
                            for text in Config.CAPTCHA_TEXTS:
                                if await frame.get_by_text(text).is_visible():
                                    still_captcha = True
                                    break
                            if still_captcha: break
                        except: continue
                
                # Check selectors if not found yet
                if not still_captcha:
                    for sel in Config.CAPTCHA_SELECTORS:
                        if await self.page.locator(sel).first.is_visible():
                            still_captcha = True
                            break
            except:
                pass

            if not still_captcha:
                self.log("验证码已解决，恢复运行...")
                self.state = "LIKING"
                self.update_stats()
                break
            
            # 延长检测间隔，避免频繁占用资源
            await asyncio.sleep(2)
        return True

    async def _check_speed_limit(self):
        """Check if speed limited"""
        try:
            if await self.page.get_by_text(Config.SPEED_LIMIT_TEXT).is_visible():
                self.log(f"检测到手速限制，冷却 {Config.COOLDOWN_SECONDS} 秒...")
                self.state = "COOLDOWN"

                for i in range(Config.COOLDOWN_SECONDS, 0, -1):
                    if self.should_stop or self.manual_pause:
                        break
                    if self.status_callback:
                        self.status_callback(self.total_likes, f"冷却中({i}s)")
                    await asyncio.sleep(1)

                if not self.should_stop and not self.manual_pause:
                    self.log("冷却结束，恢复运行...")
                    self.state = "LIKING"
                    self.update_stats()
                return True
        except:
            pass
        return False

    async def _check_live_end(self):
        """Check if live stream ended"""
        try:
            for text in Config.LIVE_END_TEXTS:
                if await self.page.get_by_text(text).is_visible():
                    self.log("直播已结束")
                    return True

            if not await self.page.locator("video").count():
                await asyncio.sleep(2)
                if not await self.page.locator("video").count():
                    self.log("视频流丢失")
                    return True
        except:
            pass
        return False

    def _handle_cycle_mode(self, current_time, cycle_start_time):
        """Handle work/rest cycle, return False to skip this iteration"""
        elapsed = (current_time - cycle_start_time) / 60

        if self.state == "LIKING" and elapsed >= float(self.config["work_min"]):
            self.state = "RESTING"
            self.log(f"已工作 {int(elapsed)} 分钟，休息 {self.config['rest_min']} 分钟...")
            self.update_stats()
            return False

        if self.state == "RESTING" and elapsed >= float(self.config["rest_min"]):
            self.state = "LIKING"
            self.log("休息结束，开始工作...")
            self.update_stats()
            return False

        return True

    async def _show_rest_countdown(self, current_time, cycle_start_time):
        """Show rest countdown"""
        elapsed_min = (current_time - cycle_start_time) / 60
        rest_min = float(self.config["rest_min"])
        remaining_sec = max(0, int((rest_min - elapsed_min) * 60))
        m, s = divmod(remaining_sec, 60)
        if self.status_callback:
            self.status_callback(self.total_likes, f"休息中... {m}分{s:02d}秒")
        await asyncio.sleep(1)

    async def _do_click(self, video_element):
        """Execute double click at random position"""
        x, y = self._get_click_position(video_element)
        await self.page.mouse.dblclick(x, y)
        self.total_likes += 1

        # Update stats periodically
        if self.total_likes % 50 == 0:
            self.update_stats()

        # Screenshot in headless mode
        if self.config["headless"] and self.total_likes % Config.SCREENSHOT_INTERVAL == 0:
            self._save_screenshot()

        # Random delay
        if random.random() < self.config["fast_click_prob"]:
            await asyncio.sleep(random.uniform(self.config["fast_min"], self.config["fast_max"]))
        else:
            await asyncio.sleep(random.uniform(self.config["slow_min"], self.config["slow_max"]))

    def _get_click_position(self, video_element):
        """Calculate random click position"""
        if video_element:
            try:
                box = video_element.bounding_box()
                if box:
                    margin = box["width"] * Config.CLICK_AREA_MARGIN
                    x = box["x"] + random.uniform(margin, box["width"] - margin)
                    y = box["y"] + random.uniform(margin, box["height"] - margin)
                    return x, y
            except:
                pass

        # Fallback to center
        vp = self.page.viewport_size
        if vp:
            return vp["width"] / 2 + random.randint(-50, 50), vp["height"] / 2 + random.randint(-50, 50)
        return 500, 500

    def _save_screenshot(self):
        """Save screenshot for verification"""
        if not os.path.exists(Config.SCREENSHOT_DIR):
            os.makedirs(Config.SCREENSHOT_DIR)
        ts = time.strftime("%H-%M-%S")
        asyncio.create_task(self.page.screenshot(path=f"{Config.SCREENSHOT_DIR}/auto_{ts}.png"))
