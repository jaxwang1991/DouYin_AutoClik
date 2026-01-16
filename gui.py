import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import os
import sys
import subprocess
from liker import DouYinLiker

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音直播自动点赞助手 v2.0")
        self.root.geometry("600x750")
        
        # 状态标志
        self.is_showing_captcha_alert = False
        
        # 异步循环和业务对象
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        
        self.liker = DouYinLiker(
            log_callback=self.append_log,
            status_callback=self.update_status
        )
        
        self.setup_ui()
        
        # 检查登录状态
        if not os.path.exists("state.json"):
            self.append_log("提示: 未检测到登录信息，建议先点击【扫码登录】")

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        # 样式
        style = ttk.Style()
        style.configure("TLabel", font=("微软雅黑", 10))
        style.configure("TButton", font=("微软雅黑", 10))
        
        # --- 1. 基础设置 ---
        frame_basic = ttk.LabelFrame(self.root, text="基础设置", padding=10)
        frame_basic.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_basic, text="直播间链接:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame_basic, textvariable=self.url_var, width=50).grid(row=0, column=1, columnspan=2, padx=5)
        
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_basic, text="后台静默运行 (不显示浏览器)", variable=self.headless_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        
        ttk.Button(frame_basic, text="扫码登录", command=self.run_login).grid(row=1, column=2, sticky="e")
        
        # --- 2. 点赞频率 ---
        frame_speed = ttk.LabelFrame(self.root, text="点赞频率 (秒)", padding=10)
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

        # --- 3. 循环模式 (新功能) ---
        frame_cycle = ttk.LabelFrame(self.root, text="循环休息模式 (防风控)", padding=10)
        frame_cycle.pack(fill="x", padx=10, pady=5)
        
        self.cycle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_cycle, text="启用循环模式", variable=self.cycle_var).grid(row=0, column=0, columnspan=4, sticky="w")
        
        ttk.Label(frame_cycle, text="工作时长 (分钟):").grid(row=1, column=0, sticky="w")
        self.work_min = tk.IntVar(value=10)
        ttk.Entry(frame_cycle, textvariable=self.work_min, width=8).grid(row=1, column=1, sticky="w")
        
        ttk.Label(frame_cycle, text="休息时长 (分钟):").grid(row=1, column=2, sticky="w")
        self.rest_min = tk.IntVar(value=5)
        ttk.Entry(frame_cycle, textvariable=self.rest_min, width=8).grid(row=1, column=3, sticky="w")
        
        # --- 4. 运行日志 ---
        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(frame_log, height=15, state='disabled')
        self.log_area.pack(fill="both", expand=True)
        
        # --- 5. 底部控制栏 ---
        frame_ctrl = ttk.Frame(self.root, padding=10)
        frame_ctrl.pack(fill="x")
        
        # 使用 grid 布局来分行显示
        # 第一行：状态栏
        self.status_var = tk.StringVar(value="状态: 就绪 | 累计点赞: 0")
        lbl_status = ttk.Label(frame_ctrl, textvariable=self.status_var, foreground="blue")
        lbl_status.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        
        # 第二行：按钮组 (使用一个子Frame来居中或右对齐按钮)
        frame_btns = ttk.Frame(frame_ctrl)
        frame_btns.grid(row=1, column=0, columnspan=4, sticky="e")
        
        self.btn_start = ttk.Button(frame_btns, text="开始任务", command=self.start_task)
        self.btn_start.pack(side="left", padx=5)

        self.btn_pause = ttk.Button(frame_btns, text="暂停", command=self.pause_task, state="disabled")
        self.btn_pause.pack(side="left", padx=5)

        self.btn_resume = ttk.Button(frame_btns, text="恢复", command=self.resume_task, state="disabled")
        self.btn_resume.pack(side="left", padx=5)
        
        self.btn_stop = ttk.Button(frame_btns, text="停止任务", command=self.stop_task, state="disabled")
        self.btn_stop.pack(side="left", padx=5)

    def append_log(self, msg):
        # 线程安全更新UI
        self.root.after(0, lambda: self._append_log_impl(msg))
        
    def _append_log_impl(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert('end', msg + "\n")
        self.log_area.see('end')
        self.log_area.config(state='disabled')
        
    def update_status(self, total_likes, state_text):
        self.root.after(0, lambda: self.status_var.set(f"状态: {state_text} | 累计点赞: {total_likes}"))
        
        # 处理特殊状态
        if state_text == "PAUSED_FOR_CAPTCHA":
            if not self.is_showing_captcha_alert:
                self.is_showing_captcha_alert = True
                self.root.after(0, self._show_captcha_alert)
            
        # 如果检测到停止，重置按钮状态
        if state_text == "STOPPED":
            self.root.after(0, self.reset_buttons)
            self.is_showing_captcha_alert = False # 重置标志
            
    def _show_captcha_alert(self):
        messagebox.showwarning(
            "需要人工介入", 
            "⚠️ 检测到抖音弹出验证码！\n\n请切换到浏览器窗口完成验证。\n验证码消失后，程序会自动恢复点赞。"
        )
        self.is_showing_captcha_alert = False

    def reset_buttons(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_pause.config(state="disabled")
        self.btn_resume.config(state="disabled")

    def run_login(self):
        # 调用 auth.py 脚本
        try:
            # 使用 start 异步运行，避免卡住界面
            subprocess.Popen(["python", "auth.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            messagebox.showerror("错误", f"无法启动登录脚本: {e}")

    def start_task(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入直播间链接")
            return
            
        # 锁定按钮
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_pause.config(state="normal")
        self.btn_resume.config(state="disabled")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, 'end')
        self.log_area.config(state='disabled')
        
        # 收集配置
        config = {
            "url": url,
            "headless": self.headless_var.get(),
            "fast_min": self.fast_min.get(),
            "fast_max": self.fast_max.get(),
            "slow_min": self.slow_min.get(),
            "slow_max": self.slow_max.get(),
            "cycle_mode": self.cycle_var.get(),
            "work_min": self.work_min.get(),
            "rest_min": self.rest_min.get()
        }
        
        # 提交到异步线程
        asyncio.run_coroutine_threadsafe(self.liker.start(config), self.loop)

    def stop_task(self):
        self.btn_stop.config(state="disabled")
        self.btn_pause.config(state="disabled")
        self.btn_resume.config(state="disabled")
        self.append_log("正在请求停止...")
        asyncio.run_coroutine_threadsafe(self.liker.stop(), self.loop)

    def pause_task(self):
        self.btn_pause.config(state="disabled")
        self.btn_resume.config(state="normal")
        self.liker.pause()

    def resume_task(self):
        self.btn_resume.config(state="disabled")
        self.btn_pause.config(state="normal")
        self.liker.resume()

if __name__ == "__main__":
    root = tk.Tk()
    # 设置图标（如果有的话）
    # root.iconbitmap("icon.ico")
    app = App(root)
    root.mainloop()
