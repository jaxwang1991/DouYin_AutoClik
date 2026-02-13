"""
DouYin Auto Liker - Core module with optimized code
"""
import asyncio
import random
import os
import time
import base64
import difflib
import re
import json
import concurrent.futures
from audio_handler import AudioHandler
from openai import AsyncOpenAI
import dashscope
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
        self.next_comment_interval = 0  # Actual interval for current cycle (for display)
        self._ai_comment_in_progress = False  # Prevent concurrent AI comment calls

        # Audio Handler
        self.audio_handler = None

        # Runtime state
        self.total_likes = 0
        self.state = "IDLE"

        # 用于冷却/休息倒计时显示
        self._cooldown_remaining = 0

        # Thread pool executor for blocking API calls
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def update_stats(self, remaining_seconds=None):
        """更新状态显示

        Args:
            remaining_seconds: 可选，用于 COOLDOWN/RESTING 状态的剩余秒数
        """
        if self.status_callback:
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

            # COOLDOWN 状态：显示倒计时
            if self.state == "COOLDOWN":
                if remaining_seconds is not None:
                    m, s = divmod(int(remaining_seconds), 60)
                    if m > 0:
                        state_prefix = f"冷却中 {m}分{s:02d}秒"
                    else:
                        state_prefix = f"冷却中 {s}秒"
                else:
                    state_prefix = "冷却中"
                if self.config.get("ai_enabled", False):
                    countdown = self._get_next_comment_countdown()
                    state_text = f"{state_prefix} | 点赞: {like_status} | 评论: {comment_status} | {countdown}"
                else:
                    state_text = f"{state_prefix} | 点赞: {like_status}"

            # RESTING 状态：显示倒计时
            elif self.state == "RESTING":
                if remaining_seconds is not None:
                    m, s = divmod(int(remaining_seconds), 60)
                    state_prefix = f"休息中 {m}分{s:02d}秒"
                else:
                    state_prefix = "休息中"
                if self.config.get("ai_enabled", False):
                    countdown = self._get_next_comment_countdown()
                    state_text = f"{state_prefix} | 点赞: {like_status} | 评论: {comment_status} | {countdown}"
                else:
                    state_text = f"{state_prefix} | 点赞: {like_status}"

            # 其他状态：显示状态码
            else:
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

        # Use the actual interval for current cycle if set, otherwise get configured interval
        if self.next_comment_interval > 0:
            interval = self.next_comment_interval
        else:
            # Get interval from config (support both old and new format)
            interval_min = self.config.get("ai_interval_min", Config.AI_COMMENT_INTERVAL_MIN)
            interval_max = self.config.get("ai_interval_max", Config.AI_COMMENT_INTERVAL_MAX)
            interval = interval_max  # Use max for countdown display

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

        # Load comment history from file (don't clear, keep persistent history)
        self._load_comment_history()

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

        # Save comment history before stopping
        self._save_comment_history()

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
                # 如果在冷却中，传递剩余时间
                if speed_limit_cooldown:
                    remaining = int(speed_limit_end_time - current_time)
                    self.update_stats(remaining_seconds=remaining)
                else:
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
                        self.update_stats()  # 恢复正常状态显示
                else:
                    # 不再直接调用 status_callback，让每秒的 update_stats() 处理
                    remaining = int(speed_limit_end_time - current_time)
                    self._cooldown_remaining = remaining  # 保存剩余时间供 update_stats() 使用
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
                    # If transitioned to RESTING, skip this iteration and show countdown
                    if self.state == "RESTING":
                        if await self._check_live_end():
                            break
                        await self._show_rest_countdown(current_time, cycle_start_time)
                        continue  # Skip the rest of this loop iteration
                    # If transitioned to LIKING, continue normally
            elif self.state == "RESTING":
                # Non-cycle mode should not have RESTING state, but handle it
                self.state = "LIKING"

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
            # Run as background task to avoid blocking the like loop
            if self.config.get("ai_enabled", False) and not self.manual_pause_comment:
                asyncio.create_task(self._process_ai_comment())

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

        # 先稳定检测验证码确实存在（避免误判临时弹窗）
        stable_count = 0
        required_stable = 2  # 需要连续2次确认验证码存在
        while stable_count < required_stable:
            still_captcha = await self._detect_captcha_once()
            if still_captcha:
                stable_count += 1
            else:
                # 验证码消失了，可能被误判，退出
                self.log("验证码检测中断，可能为误判，恢复运行...")
                self.state = "LIKING"
                self.update_stats()
                return True
            await asyncio.sleep(1)

        # 验证码确认存在，等待清除
        self.log("确认验证码存在，等待用户处理...")
        clear_count = 0
        required_clear_count = 5  # 连续5次检测不到才确认（约10秒）

        while not self.should_stop:
            still_captcha = await self._detect_captcha_once()

            if not still_captcha:
                clear_count += 1
                if clear_count >= required_clear_count:
                    self.log("验证码已解决，恢复运行...")
                    self.state = "LIKING"
                    self.update_stats()
                    break
            else:
                clear_count = 0

            await asyncio.sleep(2)
        return True

    async def _detect_captcha_once(self):
        """单次检测验证码是否存在（不阻塞）"""
        try:
            # Check texts
            for text in Config.CAPTCHA_TEXTS:
                if await self.page.get_by_text(text).is_visible():
                    return True

            # Check frames
            for frame in self.page.frames:
                try:
                    for text in Config.CAPTCHA_TEXTS:
                        if await frame.get_by_text(text).is_visible():
                            return True
                except:
                    continue

            # Check selectors
            for sel in Config.CAPTCHA_SELECTORS:
                if await self.page.locator(sel).first.is_visible():
                    return True
        except:
            pass
        return False

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
            # 不在这里调用 update_stats()，让 _show_rest_countdown() 独占 RESTING 状态显示
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

        # 调用 update_stats() 统一处理状态显示
        self.update_stats(remaining_seconds=remaining_sec)
        await asyncio.sleep(1)

    async def _do_click(self, video_element):
        """Execute click at random position"""
        x, y = self._get_click_position(video_element)
        await self.page.mouse.click(x, y)
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
        # Prevent concurrent calls (running in background task)
        if self._ai_comment_in_progress:
            return
        self._ai_comment_in_progress = True

        try:
            now = time.time()

            # Check interval - use random interval between min and max
            interval_min = self.config.get("ai_interval_min", Config.AI_COMMENT_INTERVAL_MIN)
            interval_max = self.config.get("ai_interval_max", Config.AI_COMMENT_INTERVAL_MAX)

            # Backward compatibility: if only ai_interval is set, use it
            if "ai_interval" in self.config and "ai_interval_min" not in self.config:
                interval_min = self.config.get("ai_interval", Config.AI_COMMENT_INTERVAL)
                interval_max = interval_min

            # For countdown display, use the current cycle's interval or max
            if self.next_comment_interval > 0:
                check_interval = self.next_comment_interval
            else:
                check_interval = interval_max

            if now - self.last_comment_time < check_interval:
                return

            # Set new random interval for next cycle
            self.next_comment_interval = random.uniform(interval_min, interval_max)
            # Note: last_comment_time will be set AFTER comment is successfully sent

            self.log("[AI] 正在准备生成评论...")

            # 1. Base System Prompt from GUI
            base_prompt = self.config.get("ai_prompt") or Config.AI_PROMPT
            system_content = base_prompt

            # Add comment history to system prompt
            if self.comment_history:
                history_str = "\n".join([f"- {c}" for c in self.comment_history[-10:]])
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

            # Add user message (text only, qwen-plus does not support images)
            messages.append({
                "role": "user",
                "content": "根据主播语音内容，生成一句评论。"
            })

            self.log(f"[AI] 准备就绪，正在请求大模型生成评论...")

            comment = None  # Reset comment
            try:
                # Use native DashScope API in thread pool to avoid blocking event loop
                api_key = self.config.get("ai_api_key") or Config.AI_API_KEY
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: dashscope.Generation.call(
                        api_key=api_key,
                        model=Config.AI_MODEL,
                        messages=messages,
                        max_tokens=100,
                        temperature=Config.AI_TEMPERATURE,
                        result_format="message",
                        enable_thinking=Config.AI_ENABLE_THINKING
                    )
                )

                if response.status_code == 200:
                    # Optional: Log thinking process for debugging
                    if hasattr(response.output.choices[0].message, 'reasoning_content'):
                        thinking_content = response.output.choices[0].message.reasoning_content
                        if thinking_content:
                            self.log(f"[AI] 思考过程: {thinking_content[:100]}...")
                    comment = response.output.choices[0].message.content.strip()
                else:
                    self.log(f"[AI] API调用失败: HTTP {response.status_code}, 错误码: {response.code}, 错误信息: {response.message}")
                    self.next_comment_interval = 0  # Reset interval to retry sooner
                    return
            except Exception as api_error:
                self.log(f"[AI] API调用失败: {type(api_error).__name__}: {api_error}")
                self.next_comment_interval = 0  # Reset interval to retry sooner
                return

            self.log(f"[AI] 生成评论: {comment}")

            if not comment:
                self.log("[AI] 生成的评论为空，跳过发送")
                self.next_comment_interval = 0  # Reset interval to retry sooner
                return

            # Enhanced deduplication: check both exact match and normalized match
            normalized_comment = self._normalize_comment(comment)

            # Check exact match
            if comment in self.comment_history:
                self.log(f"[AI] 检测到重复评论（完全匹配），跳过发送: {comment}")
                self.next_comment_interval = 0  # Reset interval to retry sooner
                return

            # Check normalized match (removes punctuation, spaces for fuzzy comparison)
            for hist_comment in self.comment_history:
                if self._normalize_comment(hist_comment) == normalized_comment:
                    self.log(f"[AI] 检测到重复评论（相似匹配），跳过发送: {comment} (相似于: {hist_comment})")
                    self.next_comment_interval = 0  # Reset interval to retry sooner
                    return

            self.log(f"[AI] 评论生成成功: {comment}")
            self.comment_history.append(comment)
            # Keep history size manageable
            if len(self.comment_history) > 50:
                self.comment_history = self.comment_history[-50:]

            await self._send_comment(comment)
            # Set timestamp AFTER comment is sent successfully
            self.last_comment_time = time.time()
            self.log(f"[AI] 评论已发送，下次评论将在 {self.next_comment_interval:.0f} 秒后")

        except Exception as e:
            self.log(f"[AI] 评论生成流程异常: {e}")
        finally:
            self._ai_comment_in_progress = False

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

    def _normalize_comment(self, text):
        """Normalize comment text for deduplication comparison.

        Removes punctuation, extra whitespace, and converts to lowercase
        for fuzzy matching of similar comments.
        """
        # Remove common punctuation and spaces, convert to lowercase
        normalized = re.sub(r'[^\w]', '', text.strip()).lower()
        return normalized

    def _get_comment_history_path(self):
        """Get the path to the comment history file."""
        if Config.USE_BUILD_CONFIG:
            from build_config import get_comment_history_path
            return get_comment_history_path()
        else:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), Config.AI_HISTORY_FILE)

    def _load_comment_history(self):
        """Load comment history from file."""
        try:
            history_path = self._get_comment_history_path()
            if os.path.exists(history_path):
                with open(history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.comment_history = data.get("comments", [])
                    self.log(f"[AI] 已加载 {len(self.comment_history)} 条历史评论")
            else:
                self.comment_history = []
        except Exception as e:
            self.log(f"[AI] 加载评论历史失败: {e}")
            self.comment_history = []

    def _save_comment_history(self):
        """Save comment history to file."""
        try:
            history_path = self._get_comment_history_path()
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump({
                    "comments": self.comment_history,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2, ensure_ascii=False)
            self.log(f"[AI] 已保存 {len(self.comment_history)} 条历史评论")
        except Exception as e:
            self.log(f"[AI] 保存评论历史失败: {e}")
