"""
DouYin Auto Liker - Core module with optimized code
"""
import asyncio
import random
import os
import time
import base64
import difflib
from audio_handler import AudioHandler
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
        self.manual_pause = False  # 保留用于兼容性，作为"总暂停"
        self.manual_pause_like = False  # 独立控制点赞
        self.manual_pause_comment = False  # 独立控制评论

        # Config with defaults
        self.config = DEFAULT_CONFIG.copy()
        self.config["url"] = ""
        self.config["headless"] = True
        
        # AI State
        self.last_comment_time = 0
        self.ai_client = None
        self.comment_history = []  # Store recent comments to avoid duplicates
        
        # Audio Handler
        self.audio_handler = None

        # Runtime state
        self.total_likes = 0
        self.state = "IDLE"

    def update_stats(self):
        if self.status_callback:
            state_text = self.state

            # Add like status
            if self.manual_pause_like:
                like_status = "暂停"
            elif self.state == "COOLDOWN":
                like_status = "冷却中"
            elif self.state == "RESTING":
                like_status = "休息中"
            elif self.state == "PAUSED_FOR_CAPTCHA":
                like_status = "验证码等待"
            elif self.state == "LIKING":
                like_status = "运行中"
            else:
                like_status = "待机"

            # Add comment status
            if not self.config.get("ai_enabled", False):
                comment_status = "未启用"
            elif self.manual_pause_comment:
                comment_status = "暂停"
            else:
                comment_status = "运行中"

            # Add AI countdown if enabled
            if self.config.get("ai_enabled", False):
                countdown = self._get_next_comment_countdown()
                state_text = f"{self.state} | 点赞: {like_status} | 评论: {comment_status} | {countdown}"
            else:
                state_text = f"{self.state} | 点赞: {like_status}"

            self.status_callback(self.total_likes, state_text)

    def _get_next_comment_countdown(self):
        """Calculate time until next AI comment"""
        if not self.config.get("ai_enabled", False):
            return ""
            
        interval = self.config.get("ai_interval", Config.AI_COMMENT_INTERVAL)
        elapsed = time.time() - self.last_comment_time
        remaining = max(0, int(interval - elapsed))
        return f"AI倒计时: {remaining}秒"

    def pause(self):
        """总暂停 - 同时暂停点赞和评论"""
        self.manual_pause = True
        self.manual_pause_like = True
        self.manual_pause_comment = True
        self.state = "PAUSED_BY_USER"
        self.log("用户已暂停 (点赞+评论)")
        self.update_stats()

    def resume(self):
        """总恢复 - 同时恢复点赞和评论"""
        self.manual_pause = False
        self.manual_pause_like = False
        self.manual_pause_comment = False
        self.state = "LIKING"
        self.log("任务已恢复 (点赞+评论)")
        self.update_stats()

    def pause_like(self):
        """仅暂停点赞"""
        self.manual_pause_like = True
        self.log("点赞已暂停 (评论继续运行)")
        self.update_stats()

    def resume_like(self):
        """仅恢复点赞"""
        self.manual_pause_like = False
        if not self.manual_pause_comment:
            self.state = "LIKING"
        self.log("点赞已恢复")
        self.update_stats()

    def pause_comment(self):
        """仅暂停评论"""
        self.manual_pause_comment = True
        self.log("评论已暂停 (点赞继续运行)")
        self.update_stats()

    def resume_comment(self):
        """仅恢复评论"""
        self.manual_pause_comment = False
        self.log("评论已恢复")
        self.update_stats()

    async def start(self, config):
        self.config.update(config)
        self.should_stop = False
        self.is_running = True
        self.state = "STARTING"
        self.total_likes = 0
        self.comment_history = []  # Clear history on each task start
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
                
                self.log(f"AI 评论功能已开启")
                
                # Setup Audio Handler
                if self.config.get("ai_use_audio", Config.AI_USE_AUDIO):
                    self.audio_handler = AudioHandler(log_callback=self.log)
                    self.audio_handler.start_recording()
                
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
        if self.audio_handler:
            self.audio_handler.stop_and_save()
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
        last_update_time = 0

        # Speed limit state (affects only likes, not comments)
        speed_limit_cooldown = False
        speed_limit_end_time = 0

        while not self.should_stop:
            current_time = time.time()

            # Update stats every 1 second for real-time countdown
            if current_time - last_update_time >= 1.0:
                self.update_stats()
                last_update_time = current_time

            # Check total manual pause (both like and comment)
            if self.manual_pause:
                self.state = "PAUSED_BY_USER"
                await asyncio.sleep(0.5)
                continue

            # Check captcha (pauses both like and comment)
            if await self._check_captcha():
                continue

            # Check live end
            if await self._check_live_end():
                break

            # Handle speed limit (affects only likes, not comments)
            if speed_limit_cooldown:
                if current_time >= speed_limit_end_time:
                    speed_limit_cooldown = False
                    self.log("冷却结束，恢复点赞...")
                    if not self.manual_pause_like:
                        self.state = "LIKING"
                else:
                    remaining = int(speed_limit_end_time - current_time)
                    if self.status_callback:
                        self.status_callback(self.total_likes, f"冷却中({remaining}s)")
                    await asyncio.sleep(1)
                    # Continue to check speed limit again, but don't skip AI comment
            else:
                # Check for new speed limit
                if await self._check_speed_limit_inline():
                    speed_limit_cooldown = True
                    speed_limit_end_time = current_time + Config.COOLDOWN_SECONDS
                    self.log(f"检测到手速限制，冷却 {Config.COOLDOWN_SECONDS} 秒...")
                    self.state = "COOLDOWN"
                    await asyncio.sleep(1)
                    # Don't skip AI comment processing

            # Cycle mode (work/rest) - affects only likes
            if self.config["cycle_mode"]:
                if not self._handle_cycle_mode(current_time, cycle_start_time):
                    cycle_start_time = current_time
                    if self.state == "RESTING":
                        if await self._check_live_end():
                            break
                        await self._show_rest_countdown(current_time, cycle_start_time)
                    else:
                        pass

            # Resting state - skip click but allow AI comment
            if self.state == "RESTING":
                if await self._check_live_end():
                    break
                await self._show_rest_countdown(current_time, cycle_start_time)

            # Execute click (only if not paused and not in cooldown/resting)
            can_like = (self.state == "LIKING" and
                       not self.manual_pause_like and
                       not speed_limit_cooldown)
            if can_like:
                try:
                    await self._do_click(video_element)
                    click_errors = 0
                except Exception:
                    click_errors += 1
                    if click_errors > Config.MAX_CLICK_ERRORS:
                        self.log("连续错误次数过多，自动停止")
                        break
                    await asyncio.sleep(1)
            elif not speed_limit_cooldown and self.state != "RESTING":
                # Small sleep if we're not clicking (but not in cooldown/resting)
                await asyncio.sleep(0.1)

            # Process AI Comment (independent of like pause state)
            if self.config.get("ai_enabled", False) and not self.manual_pause_comment:
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

    async def _check_speed_limit_inline(self):
        """Check if speed limited (non-blocking, returns True if limited)"""
        try:
            if await self.page.get_by_text(Config.SPEED_LIMIT_TEXT).is_visible():
                return True
        except:
            pass
        return False

    async def _check_speed_limit(self):
        """Check if speed limited (legacy method with blocking - kept for compatibility)"""
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
        
        status_text = f"休息中... {m}分{s:02d}秒"
        if self.config.get("ai_enabled", False):
            countdown = self._get_next_comment_countdown()
            status_text += f" | {countdown}"
            
        if self.status_callback:
            self.status_callback(self.total_likes, status_text)
        await asyncio.sleep(1)

    async def _do_click(self, video_element):
        """Execute double click at random position"""
        x, y = self._get_click_position(video_element)
        await self.page.mouse.dblclick(x, y)
        self.total_likes += 1

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
        # Determine screenshot directory
        if Config.USE_BUILD_CONFIG:
            from build_config import get_logs_path
            screenshot_dir = get_logs_path()
        else:
            screenshot_dir = Config.SCREENSHOT_DIR

        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)
        ts = time.strftime("%H-%M-%S")
        asyncio.create_task(self.page.screenshot(path=f"{screenshot_dir}/auto_{ts}.png"))

    async def _process_ai_comment(self):
        """Process AI comment generation and sending"""
        now = time.time()
        interval = self.config.get("ai_interval", Config.AI_COMMENT_INTERVAL)
        
        if now - self.last_comment_time < interval:
            return

        self.last_comment_time = now
        
        try:
            self.log("[AI] 正在截取直播画面...")
            # Screenshot buffer (base64) - captures only the viewport
            screenshot_bytes = await self.page.screenshot(type="jpeg", quality=50)
            b64_image = base64.b64encode(screenshot_bytes).decode('utf-8')

            # self.log(f"[AI] 正在请求大模型生成评论...")
            
            # 1. Base System Prompt from GUI
            base_prompt = self.config.get("ai_prompt") or Config.AI_PROMPT
            system_content = base_prompt
            
            # Add comment history to system prompt
            if self.comment_history:
                history_str = "\n".join([f"- {c}" for c in self.comment_history[-5:]])
                system_content += f"\n\n【重要指令】\n请避开以下最近已生成的评论，不要重复：\n{history_str}"
            
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": system_content
                }
            ]
            
            # Handle Audio Transcription
            if self.audio_handler:
                try:
                    # Stop current recording, save, and restart immediately for next cycle
                    audio_file = self.audio_handler.stop_and_save()
                    self.audio_handler.start_recording()  # Start recording next segment immediately
                    
                    if audio_file:
                        api_key = self.config.get("ai_api_key") or Config.AI_API_KEY
                        transcript = await self.audio_handler.transcribe(audio_file, api_key)
                        
                        # Save transcript
                        self.audio_handler.save_transcript(transcript)
                        
                        if transcript:
                            # Update system content with transcript context
                            messages[0]["content"] += f"\n\n【参考信息】\n当前直播间语音转录：{transcript}"
                            
                except Exception as e:
                    self.log(f"[Audio] 音频处理失败: {e}")
            
            # Add user message with image
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "结合画面和语音内容，生成一句评论。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}"
                        }
                    }
                ]
            })

            self.log(f"[AI] 准备就绪，正在请求大模型生成评论...")
            
            comment = None # Reset comment
            try:
                response = await self.ai_client.chat.completions.create(
                    model=Config.AI_MODEL,
                    messages=messages,
                    max_tokens=100,
                    temperature=Config.AI_TEMPERATURE,  # High temperature for diversity
                    stream=True,
                    stream_options={"include_usage": True},
                    modalities=["text"]
                )
                
                full_content = []
                async for chunk in response:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            full_content.append(delta.content)
                    # elif hasattr(chunk, 'usage') and chunk.usage:
                    #     self.log(f"[AI] Token Usage: {chunk.usage}")

                comment = "".join(full_content).strip()
            except Exception as api_error:
                self.log(f"[AI] API调用失败: {type(api_error).__name__}: {api_error}")
                return

            self.log(f"[AI] 生成评论: {comment}")

            if not comment:
                self.log("[AI] 生成的评论为空，跳过发送")
                return

            # Strict deduplication: check if comment already exists in history
            if comment in self.comment_history:
                self.log(f"[AI] 检测到重复评论（已存在于历史记录），跳过发送: {comment}")
                return

            self.log(f"[AI] 评论生成成功: {comment}")
            self.comment_history.append(comment)
            # Keep history size manageable
            if len(self.comment_history) > 20:
                self.comment_history.pop(0)

            await self._send_comment(comment)
                
        except Exception as e:
            self.log(f"[AI] 评论生成流程异常: {e}")

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
