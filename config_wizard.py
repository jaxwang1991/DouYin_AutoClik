"""
First-run configuration wizard
Guides user through initial setup
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json

try:
    from build_config import get_config_path, get_default_config_path, get_app_path
except ImportError:
    # Development environment fallbacks
    def get_app_path():
        return os.path.dirname(os.path.abspath(__file__))
    def get_config_path():
        return os.path.join(get_app_path(), "data", "config.json")
    def get_default_config_path():
        return os.path.join(get_app_path(), "config.json.default")

class ConfigWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DouYin AutoLiker - Setup")
        self.root.geometry("500x350")
        self.root.resizable(False, False)

        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

        self.setup_ui()
        self.load_defaults()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#4A90E2", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(header, text="Welcome to DouYin AutoLiker",
                        font=("Microsoft YaHei", 14, "bold"), bg="#4A90E2", fg="white")
        title.pack(pady=15)

        # Content
        content = tk.Frame(self.root, padx=30, pady=20)
        content.pack(fill="both", expand=True)

        # API Key
        tk.Label(content, text="API Key (Aliyun DashScope):",
                font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", pady=(10, 5))
        self.api_key_var = tk.StringVar()
        tk.Entry(content, textvariable=self.api_key_var, width=50,
                font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=(0, 15))

        # Help text
        help_text = ("Get API Key:\n"
                    "1. Visit https://dashscope.aliyun.com\n"
                    "2. Login with Aliyun account\n"
                    "3. Create API Key in API-KEY management")
        tk.Label(content, text=help_text, font=("Microsoft YaHei", 9),
                fg="#666", justify="left").grid(row=2, column=0, sticky="w", pady=(0, 15))

        # Prompt
        tk.Label(content, text="AI System Prompt (Optional):",
                font=("Microsoft YaHei", 10)).grid(row=3, column=0, sticky="w", pady=(10, 5))
        self.prompt_text = tk.Text(content, height=5, width=50, font=("Microsoft YaHei", 9))
        self.prompt_text.grid(row=4, column=0, sticky="w")

        # Buttons
        btn_frame = tk.Frame(content)
        btn_frame.grid(row=5, column=0, sticky="e", pady=(20, 0))

        tk.Button(btn_frame, text="Save and Exit", command=self.save_and_exit,
                 bg="#4A90E2", fg="white", font=("Microsoft YaHei", 10),
                 width=15, height=1, relief="flat").pack(side="right", padx=5)
        tk.Button(btn_frame, text="Skip", command=self.skip,
                 font=("Microsoft YaHei", 10), width=10, relief="flat").pack(side="right")

    def load_defaults(self):
        """Load default config values"""
        default_path = get_default_config_path()
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.api_key_var.set(config.get("ai_api_key", ""))
                    self.prompt_text.insert("1.0", config.get("ai_prompt", ""))
            except Exception:
                pass

    def save_and_exit(self):
        """Save configuration and exit"""
        api_key = self.api_key_var.get().strip()
        prompt = self.prompt_text.get("1.0", "end-1c").strip()

        if not api_key or api_key == "YOUR_API_KEY_HERE":
            if not messagebox.askyesno("Confirm", "API Key is empty. AI comment feature will be disabled.\nContinue?"):
                return

        config = {
            "url": "",
            "ai_api_key": api_key,
            "ai_prompt": prompt or "You are an enthusiastic live stream viewer."
        }

        try:
            config_path = get_config_path()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", "Configuration saved!\nYou can now launch the main program.")
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def skip(self):
        """Skip configuration"""
        if messagebox.askyesno("Confirm", "Skipping configuration will require manual editing of config.json.\nSkip anyway?"):
            self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ConfigWizard()
    app.run()
