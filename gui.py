import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import os
import sys
import time
import json
import subprocess
from liker import DouYinLiker
from config import Config

# Import path utilities
try:
    from build_config import (
        get_app_path, get_config_path, get_state_path,
        get_default_config_path, get_data_path
    )
except ImportError:
    pass

    # Fallback functions for development
    def get_app_path():
        return os.path.dirname(os.path.abspath(__file__))
    def get_config_path():
        return os.path.join(get_app_path(), "config.json")
    def get_state_path():
        return os.path.join(get_app_path(), "state.json")
    def get_default_config_path():
        return os.path.join(get_app_path(), "config.json.default")
    def get_data_path():
        return os.path.dirname(os.path.abspath(__file__))

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("DouYin AutoLiker v2.0")
        self.root.geometry("600x780")

        # Ensure config file exists (create default on first run)
        config_path = get_config_path()
        if not os.path.exists(config_path):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            # Create empty default config
            default_config = {"url": ""}
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)

        # 状态标志
        self.is_showing_captcha_alert = False
        self._last_status_text = None  # 缓存上次状态文本，避免重复更新
        self._has_prompted_cleanup = False  # 防止重复弹出清理确认框

        # 异步循环和业务对象
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()

        self.liker = DouYinLiker(
            log_callback=self.append_log,
            status_callback=self.update_status
        )

        self.setup_ui()
        self.load_ui_config()

        # 检查登录状态
        if not os.path.exists(get_state_path()):
            self.append_log("Tip: No login state detected. Please click [Scan QR Login] first.")

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        # 样式
        style = ttk.Style()
        style.configure("TLabel", font=("微软雅黑", 10))
        style.configure("TButton", font=("微软雅黑", 10))
        
        # 创建 Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- Tab 1: 基础配置 ---
        self.tab_basic = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_basic, text="基础设置")
        
        # --- Tab 2: AI 智能评论 ---
        self.tab_ai = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ai, text="AI 智能评论")
        
        # ==================== Tab 1 内容 ====================
        
        # --- 1. 直播间设置 ---
        frame_basic = ttk.LabelFrame(self.tab_basic, text="直播间设置", padding=10)
        frame_basic.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_basic, text="直播间链接:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame_basic, textvariable=self.url_var, width=50).grid(row=0, column=1, columnspan=2, padx=5)
        
        ttk.Button(frame_basic, text="扫码登录", command=self.run_login).grid(row=1, column=2, sticky="e", pady=5)
        
        # --- 2. 点赞频率 ---
        frame_speed = ttk.LabelFrame(self.tab_basic, text="点赞频率 (秒)", padding=10)
        frame_speed.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_speed, text="快速连点间隔:").grid(row=0, column=0)
        self.fast_min = tk.DoubleVar(value=0.05)
        self.fast_max = tk.DoubleVar(value=0.2)
        ttk.Entry(frame_speed, textvariable=self.fast_min, width=5).grid(row=0, column=1)
        ttk.Label(frame_speed, text="-").grid(row=0, column=2)
        ttk.Entry(frame_speed, textvariable=self.fast_max, width=5).grid(row=0, column=3)
        
        ttk.Label(frame_speed, text="   慢速停顿间隔:").grid(row=0, column=4)
        self.slow_min = tk.DoubleVar(value=0.5)
        self.slow_max = tk.DoubleVar(value=1.5)
        ttk.Entry(frame_speed, textvariable=self.slow_min, width=5).grid(row=0, column=5)
        ttk.Label(frame_speed, text="-").grid(row=0, column=6)
        ttk.Entry(frame_speed, textvariable=self.slow_max, width=5).grid(row=0, column=7)

        # --- 3. 循环模式 ---
        frame_cycle = ttk.LabelFrame(self.tab_basic, text="循环休息模式 (防风控)", padding=10)
        frame_cycle.pack(fill="x", padx=10, pady=5)
        
        self.cycle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_cycle, text="启用循环模式", variable=self.cycle_var).grid(row=0, column=0, columnspan=4, sticky="w")
        
        ttk.Label(frame_cycle, text="工作时长 (分钟):").grid(row=1, column=0, sticky="w")
        self.work_min = tk.IntVar(value=10)
        ttk.Entry(frame_cycle, textvariable=self.work_min, width=8).grid(row=1, column=1, sticky="w")
        
        ttk.Label(frame_cycle, text="休息时长 (分钟):").grid(row=1, column=2, sticky="w")
        self.rest_min = tk.IntVar(value=5)
        ttk.Entry(frame_cycle, textvariable=self.rest_min, width=8).grid(row=1, column=3, sticky="w")
        
        # ==================== Tab 2 内容 (AI 配置) ====================
        
        frame_ai = ttk.LabelFrame(self.tab_ai, text="大模型配置", padding=10)
        frame_ai.pack(fill="both", expand=True, padx=10, pady=5)
        
        # API Key
        ttk.Label(frame_ai, text="API Key:").grid(row=0, column=0, sticky="w", pady=5)
        self.ai_key_var = tk.StringVar(value=Config.AI_API_KEY)
        ttk.Entry(frame_ai, textvariable=self.ai_key_var, width=50).grid(row=0, column=1, sticky="w", padx=5)

        # 评论间隔 (双输入框: 最小值 - 最大值)
        ttk.Label(frame_ai, text="评论循环时长 (秒):").grid(row=1, column=0, sticky="w", pady=5)
        # 创建输入框容器，使两个输入框紧密排列
        interval_frame = ttk.Frame(frame_ai)
        interval_frame.grid(row=1, column=1, sticky="w", padx=5)
        self.ai_interval_min_var = tk.IntVar(value=Config.AI_COMMENT_INTERVAL_MIN)
        self.ai_interval_max_var = tk.IntVar(value=Config.AI_COMMENT_INTERVAL_MAX)
        ttk.Entry(interval_frame, textvariable=self.ai_interval_min_var, width=8).pack(side="left")
        ttk.Label(interval_frame, text="-").pack(side="left", padx=2)
        ttk.Entry(interval_frame, textvariable=self.ai_interval_max_var, width=8).pack(side="left")
        
        # 提示词
        ttk.Label(frame_ai, text="AI 系统提示词:").grid(row=2, column=0, sticky="nw", pady=5)
        self.ai_prompt_text = scrolledtext.ScrolledText(frame_ai, height=10, width=50)
        self.ai_prompt_text.grid(row=2, column=1, sticky="w", padx=5)
        self.ai_prompt_text.insert("1.0", Config.AI_PROMPT)
        
        # ==================== 公共区域 ====================
        
        # --- 4. 运行日志 ---
        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(frame_log, height=15, state='disabled')
        self.log_area.pack(fill="both", expand=True)

        # Log buffer for saving to file
        self.log_buffer = []
        
        # --- 5. 底部控制栏 ---
        frame_ctrl = ttk.Frame(self.root, padding=10)
        frame_ctrl.pack(fill="x")

        # 第一行：状态栏
        self.status_var = tk.StringVar(value="状态: 就绪 | 累计点赞: 0")
        lbl_status = ttk.Label(frame_ctrl, textvariable=self.status_var, foreground="blue")
        lbl_status.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # 第二行：主任务控制
        frame_main = ttk.Frame(frame_ctrl)
        frame_main.grid(row=1, column=0, pady=5)

        self.btn_start = ttk.Button(frame_main, text="开始任务", command=self.start_task)
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = ttk.Button(frame_main, text="停止任务", command=self.stop_task, state="disabled")
        self.btn_stop.pack(side="left", padx=5)

        # 第三行：点赞控制
        frame_like = ttk.Frame(frame_ctrl)
        frame_like.grid(row=2, column=0, pady=5)

        self.btn_pause_like = ttk.Button(frame_like, text="暂停点赞", command=self.pause_like_task, state="disabled")
        self.btn_pause_like.pack(side="left", padx=5)

        self.btn_resume_like = ttk.Button(frame_like, text="恢复点赞", command=self.resume_like_task, state="disabled")
        self.btn_resume_like.pack(side="left", padx=5)

        # 第四行：评论控制
        frame_comment = ttk.Frame(frame_ctrl)
        frame_comment.grid(row=3, column=0, pady=5)

        self.btn_pause_comment = ttk.Button(frame_comment, text="暂停评论", command=self.pause_comment_task, state="disabled")
        self.btn_pause_comment.pack(side="left", padx=5)

        self.btn_resume_comment = ttk.Button(frame_comment, text="恢复评论", command=self.resume_comment_task, state="disabled")
        self.btn_resume_comment.pack(side="left", padx=5)

    def append_log(self, msg):
        # 线程安全更新UI
        self.root.after(0, lambda: self._append_log_impl(msg))
        
    def _append_log_impl(self, msg):
        # Full timestamp for log file
        full_timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ")
        # Short timestamp for display
        short_timestamp = time.strftime("[%H:%M:%S] ")

        log_line = full_timestamp + msg + "\n"
        display_line = short_timestamp + msg + "\n"

        # Add to buffer for saving
        self.log_buffer.append(log_line)

        # Display on screen
        self.log_area.config(state='normal')
        self.log_area.insert('end', display_line)
        self.log_area.see('end')
        self.log_area.config(state='disabled')
        
    def update_status(self, total_likes, state_text):
        # 缓存状态文本，避免重复更新导致界面跳动
        status_text = f"状态: {state_text} | 累计点赞: {total_likes}"
        if status_text != self._last_status_text:
            self._last_status_text = status_text
            self.root.after(0, lambda: self.status_var.set(status_text))
        
        # 处理特殊状态
        if state_text.startswith("PAUSED_FOR_CAPTCHA"):
            if not self.is_showing_captcha_alert:
                self.is_showing_captcha_alert = True
                self.root.after(0, self._show_captcha_alert)
            
        # 如果检测到停止，重置按钮状态
        if state_text.startswith("STOPPED"):
            self.root.after(0, self.reset_buttons)
            self.is_showing_captcha_alert = False # 重置标志
            # 弹窗询问是否清理临时文件（只弹一次）
            if not self._has_prompted_cleanup:
                self._has_prompted_cleanup = True
                self.root.after(100, self.prompt_cleanup)
            
    def _show_captcha_alert(self):
        messagebox.showwarning(
            "需要人工介入", 
            "⚠️ 检测到抖音弹出验证码！\n\n请切换到浏览器窗口完成验证。\n验证码消失后，程序会自动恢复点赞。"
        )
        self.is_showing_captcha_alert = False

    def reset_buttons(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_pause_like.config(state="disabled")
        self.btn_resume_like.config(state="disabled")
        self.btn_pause_comment.config(state="disabled")
        self.btn_resume_comment.config(state="disabled")

    def prompt_cleanup(self):
        """Prompt user to clean up audio and transcript files"""
        if not hasattr(self.liker, 'audio_handler') or not self.liker.audio_handler:
            return

        handler = self.liker.audio_handler
        
        # Check if there are any files to clean
        has_files = bool(handler.session_audio_files or handler.session_transcript_files)
        
        if has_files:
            file_count = len(handler.session_audio_files) + len(handler.session_transcript_files)
            if messagebox.askyesno("清理文件", f"本次任务生成了 {file_count} 个临时文件（音频/转录文本）。\n是否全部删除？"):
                if handler.session_audio_files:
                    handler.clear_audio_files()
                if handler.session_transcript_files:
                    handler.clear_transcript_files()
                self.append_log("已清理所有临时文件")

    def run_login(self):
        # 调用 auth.py 脚本
        try:
            if getattr(sys, 'frozen', False):
                # Packaged: use embedded Python
                from build_config import get_app_path
                app_path = get_app_path()
                script_path = os.path.join(app_path, "_internal", "auth.py")
                python_exe = sys.executable
            else:
                # Development
                script_path = "auth.py"
                python_exe = "python"

            subprocess.Popen([python_exe, script_path],
                            creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch login script: {e}")

    def load_ui_config(self):
        """Load UI configuration from file"""
        config_path = get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "url" in config:
                        self.url_var.set(config["url"])
                    if "ai_api_key" in config:
                        self.ai_key_var.set(config["ai_api_key"])
                    if "ai_prompt" in config:
                        self.ai_prompt_text.delete("1.0", "end")
                        self.ai_prompt_text.insert("1.0", config["ai_prompt"])
                    # Support new interval format
                    if "ai_interval_min" in config:
                        self.ai_interval_min_var.set(config["ai_interval_min"])
                    if "ai_interval_max" in config:
                        self.ai_interval_max_var.set(config["ai_interval_max"])
                    # Backward compatibility: if old ai_interval exists, use it for both
                    elif "ai_interval" in config:
                        interval = config["ai_interval"]
                        self.ai_interval_min_var.set(interval)
                        self.ai_interval_max_var.set(interval)
            except Exception as e:
                self.append_log(f"Failed to load config file: {e}")

    def save_ui_config(self):
        """Save UI configuration to file"""
        # Get values
        current_api_key = self.ai_key_var.get().strip()
        current_prompt = self.ai_prompt_text.get("1.0", "end-1c")

        # Determine if we should save AI config (only if not default placeholder)
        ai_config = {}
        if current_api_key and current_api_key != "YOUR_API_KEY_HERE":
            ai_config["ai_api_key"] = current_api_key

        if current_prompt:
            ai_config["ai_prompt"] = current_prompt

        config = {
            "url": self.url_var.get().strip(),
            **ai_config
        }

        try:
            config_path = get_config_path()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.append_log(f"Failed to save config file: {e}")

    def start_task(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入直播间链接")
            return

        # Save config
        self.save_ui_config()

        # 锁定按钮
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_pause_like.config(state="normal")
        self.btn_resume_like.config(state="disabled")
        self.btn_pause_comment.config(state="normal")
        self.btn_resume_comment.config(state="disabled")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, 'end')
        self.log_area.config(state='disabled')

        # Clear log buffer for new task
        self.log_buffer = []
        # 重置清理提示标志
        self._has_prompted_cleanup = False

        # 收集配置
        config = {
            "url": url,
            "headless": False,  # 强制显示浏览器
            "fast_min": self.fast_min.get(),
            "fast_max": self.fast_max.get(),
            "slow_min": self.slow_min.get(),
            "slow_max": self.slow_max.get(),
            "cycle_mode": self.cycle_var.get(),
            "work_min": self.work_min.get(),
            "rest_min": self.rest_min.get(),

            # AI Config from GUI
            "ai_api_key": self.ai_key_var.get().strip(),
            "ai_interval_min": self.ai_interval_min_var.get(),
            "ai_interval_max": self.ai_interval_max_var.get(),
            "ai_prompt": self.ai_prompt_text.get("1.0", "end-1c")
        }

        # 提交到异步线程
        asyncio.run_coroutine_threadsafe(self.liker.start(config), self.loop)

    def stop_task(self):
        self.btn_stop.config(state="disabled")
        self.btn_pause_like.config(state="disabled")
        self.btn_resume_like.config(state="disabled")
        self.btn_pause_comment.config(state="disabled")
        self.btn_resume_comment.config(state="disabled")
        self.append_log("正在请求停止...")
        asyncio.run_coroutine_threadsafe(self.liker.stop(), self.loop)

        # Save log after a short delay to ensure all logs are captured
        self.root.after(2000, self.save_task_log)

    def save_task_log(self):
        """Save task log to file"""
        if not self.log_buffer:
            return

        try:
            # Get logs path
            if Config.USE_BUILD_CONFIG:
                from build_config import get_logs_path
                logs_path = get_logs_path()
            else:
                logs_path = os.path.join(get_data_path(), "logs")

            # Create filename with timestamp
            filename = time.strftime("task_%Y%m%d_%H%M%S.log")
            filepath = os.path.join(logs_path, filename)

            # Write log buffer to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(self.log_buffer)

            self.append_log(f"日志已保存至: {filepath}")
        except Exception as e:
            self.append_log(f"保存日志失败: {e}")

    def pause_like_task(self):
        self.btn_pause_like.config(state="disabled")
        self.btn_resume_like.config(state="normal")
        self.liker.pause_like()

    def resume_like_task(self):
        self.btn_resume_like.config(state="disabled")
        self.btn_pause_like.config(state="normal")
        self.liker.resume_like()

    def pause_comment_task(self):
        self.btn_pause_comment.config(state="disabled")
        self.btn_resume_comment.config(state="normal")
        self.liker.pause_comment()

    def resume_comment_task(self):
        self.btn_resume_comment.config(state="disabled")
        self.btn_pause_comment.config(state="normal")
        self.liker.resume_comment()

if __name__ == "__main__":
    root = tk.Tk()
    # 设置图标（如果有的话）
    # root.iconbitmap("icon.ico")
    app = App(root)
    root.mainloop()
