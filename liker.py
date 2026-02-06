"""
DouYin Auto Liker - Core module with optimized code
"""
import asyncio
import random
import os
import time
import base64
import difflib
from openai import AsyncOpenAI
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
        
        # AI State
        self.last_comment_time = 0
        self.ai_client = None
        self.history_file = None
        self.comment_history = []
        self.rejected_history = []  # Store recently rejected comments

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

        # Initialize AI Client if enabled
        if self.config.get("ai_enabled", False):
            try:
                # Use config values passed from GUI if available
                api_key = self.config.get("ai_api_key") or Config.AI_API_KEY
                
                self.ai_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=Config.AI_BASE_URL
                )
                
                # Setup history file
                if not os.path.exists(Config.AI_HISTORY_DIR):
                    os.makedirs(Config.AI_HISTORY_DIR)
                
                ts = time.strftime("%Y%m%d_%H%M%S")
                self.history_file = os.path.join(Config.AI_HISTORY_DIR, f"comments_{ts}.txt")
                self.comment_history = []
                self.rejected_history = []
                self.log(f"AI 评论功能已开启 (记录文件: {self.history_file})")
                
            except Exception as e:
                self.log(f"AI 初始化失败: {e}")
                self.config["ai_enabled"] = False

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
        
        # Cleanup history file
        if self.history_file and os.path.exists(self.history_file):
            try:
                os.remove(self.history_file)
                self.log(f"已清理临时历史文件: {self.history_file}")
            except Exception as e:
                self.log(f"清理历史文件失败: {e}")
                
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
                    # 即使在状态切换的瞬间，也要继续往下走，如果是RESTING状态会在下面被拦截
                    # 但如果是刚切换回LIKING，应该继续执行
                    if self.state == "RESTING":
                        # 在休息状态下，也要检查直播是否结束
                        if await self._check_live_end():
                            break
                        await self._show_rest_countdown(current_time, cycle_start_time)
                        continue
                    else:
                        continue

            # Resting state - skip click
            if self.state == "RESTING":
                # 在休息状态下，也要检查直播是否结束
                if await self._check_live_end():
                    break
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

            # Process AI Comment
            if self.config.get("ai_enabled", False):
                await self._process_ai_comment()

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
                    # Check if live ended during cooldown
                    if await self._check_live_end():
                        self.log("冷却期间直播已结束，停止任务")
                        self.should_stop = True
                        return True

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

    def _is_duplicate(self, new_comment, history, threshold=None):
        """Check for duplicate comments using fuzzy matching"""
        if not history:
            return False
            
        if threshold is None:
            threshold = Config.AI_SIMILARITY_THRESHOLD
            
        # First check exact match (faster)
        if new_comment in history:
            return True
            
        # Check fuzzy match
        # Only check recent history to save performance
        for old_comment in history[-Config.AI_MAX_HISTORY_ITEMS:]:
            ratio = difflib.SequenceMatcher(None, new_comment, old_comment).ratio()
            if ratio > threshold:
                self.log(f"[AI] 发现相似评论 (相似度 {ratio:.2f}): '{new_comment}' vs '{old_comment}'")
                return True
                
        return False

    async def _process_ai_comment(self, retry_count=0):
        """Process AI comment generation and sending"""
        now = time.time()
        interval = self.config.get("ai_interval", Config.AI_COMMENT_INTERVAL)
        
        # Only check interval if not retrying
        if retry_count == 0 and now - self.last_comment_time < interval:
            return

        if retry_count == 0:
            self.last_comment_time = now  # Reset timer immediately to avoid double firing
        
        try:
            if retry_count == 0:
                self.log("[AI] 正在截取直播画面...")
                # Screenshot buffer (base64) - captures only the viewport
                screenshot_bytes = await self.page.screenshot(type="jpeg", quality=50)
                # Save screenshot bytes to instance to reuse in retry
                self._current_screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            b64_image = getattr(self, '_current_screenshot_b64', None)
            if not b64_image:
                 # Fallback if retry called without screenshot (shouldn't happen)
                 screenshot_bytes = await self.page.screenshot(type="jpeg", quality=50)
                 b64_image = base64.b64encode(screenshot_bytes).decode('utf-8')

            self.log(f"[AI] 正在请求大模型生成评论... (尝试 {retry_count + 1})")
            
            # Build prompt with history
            # Use GUI config if available, fallback to default
            base_prompt = self.config.get("ai_prompt") or Config.AI_PROMPT
            
            system_content = base_prompt
            
            # 1. Add History
            if self.comment_history:
                # 获取最近的 N 条历史
                recent_history = self.comment_history[-Config.AI_MAX_HISTORY_ITEMS:]
                history_list = "\n".join([f"- {c}" for c in recent_history])
                
                # Append history strict requirement at the end for recency bias
                system_content += f"\n\n【历史已发送记录】\n{history_list}"

            # 2. Add Rejected History (Critical for breaking loops)
            if self.rejected_history:
                rejected_list = "\n".join([f"- {c}" for c in self.rejected_history[-10:]]) # Last 10 rejected
                system_content += f"\n\n【最近被拦截的重复尝试】(AI刚才生成的这些内容因为重复被系统拦截，请绝对避免再次生成类似内容)\n{rejected_list}"

            # 3. Add Final Strict Instructions
            system_content += "\n\n【最高优先级指令】\n1. 请检查【历史已发送记录】和【最近被拦截的重复尝试】。\n2. 你生成的评论必须与列表中的任何一条内容都不同。\n3. 严禁生成语义相似或句式雷同的评论。\n4. 如果生成重复内容将被视为任务失败。"
            
            response = await self.ai_client.chat.completions.create(
                model=Config.AI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这是当前的直播画面，请生成一句评论。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=100,
                temperature=Config.AI_TEMPERATURE  # High temperature for diversity
            )
            
            comment = response.choices[0].message.content.strip()
            self.log(f"[AI] 生成评论: {comment}")
            
            if comment:
                # Local duplication check (Fuzzy)
                if self._is_duplicate(comment, self.comment_history):
                    self.log(f"[AI] 警告: 检测到重复/相似评论: {comment}")
                    
                    # Record rejection
                    self.rejected_history.append(comment)
                    
                    # Retry logic
                    if retry_count < 1:
                        self.log(f"[AI] 正在尝试重新生成 (Retry 1/1)...")
                        await asyncio.sleep(2) # Brief pause
                        await self._process_ai_comment(retry_count=1)
                    else:
                        self.log(f"[AI] 重试次数耗尽，跳过本次发送。")
                    
                    return

                # Save to history
                self.comment_history.append(comment)
                try:
                    with open(self.history_file, "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%H:%M:%S')} - {comment}\n")
                except Exception as ex:
                    self.log(f"[AI] 保存历史记录失败: {ex}")

                await self._send_comment(comment)
                
        except Exception as e:
            self.log(f"[AI] 评论生成失败: {e}")

    async def _send_comment(self, text):
        """Send comment to chat"""
        try:
            # Try to find input box
            input_box = None
            selectors = [
                "textarea[placeholder*='说点什么']",
                "textarea[class*='webcast-chatroom']",
                "[contenteditable='true']",
                "input[placeholder*='说点什么']"
            ]
            
            for sel in selectors:
                try:
                    if await self.page.locator(sel).first.is_visible():
                        input_box = self.page.locator(sel).first
                        break
                except:
                    continue
            
            if input_box:
                await input_box.click()
                await input_box.fill(text)
                await asyncio.sleep(0.5)
                await self.page.keyboard.press("Enter")
                self.log(f"[AI] 评论已发送")
            else:
                self.log("[AI] 未找到评论输入框")
                
        except Exception as e:
            self.log(f"[AI] 发送评论失败: {e}")
