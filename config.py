"""
Configuration module for DouYin Auto Click Tool
Centralizes all configurable parameters
"""


class Config:
    """Centralized configuration"""

    # Browser settings
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    VIEWPORT = {"width": 1280, "height": 800}
    HEADLESS_ARGS = ["--disable-blink-features=AutomationControlled"]
    MAXIMIZED_ARGS = ["--start-maximized"]

    # Click area settings (0.0 - 0.5)
    CLICK_AREA_MARGIN = 0.2  # 20% margin, click in center 60%

    # Click interval settings (seconds)
    FAST_CLICK_MIN = 0.05
    FAST_CLICK_MAX = 0.2
    SLOW_CLICK_MIN = 0.5
    SLOW_CLICK_MAX = 1.5

    # Click probability (0.0 - 1.0)
    FAST_CLICK_PROBABILITY = 0.8

    # Cooldown settings
    COOLDOWN_SECONDS = 180  # 3 minutes
    MAX_CLICK_ERRORS = 20

    # Screenshot settings
    SCREENSHOT_DIR = "logs"
    SCREENSHOT_INTERVAL = 200  # every N likes

    # Captcha detection texts
    CAPTCHA_TEXTS = ["请完成下列验证后继续", "向右滑动完成拼图", "旋转图片", "短信验证", "获取验证码"]
    CAPTCHA_SELECTORS = [".captcha_verify_container", "#captcha-verify-image", "[class*='captcha']"]

    # Live end detection texts
    LIVE_END_TEXTS = ["直播已结束", "已下播"]

    # Speed limit text
    SPEED_LIMIT_TEXT = "手速太快了，请休息一下吧"

    # State file
    STATE_FILE = "state.json"

    # AI Comment Settings
    AI_ENABLED = True
    AI_PROVIDER = "dashscope"
    AI_API_KEY = "YOUR_API_KEY_HERE"  # Replace with your actual key
    AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    AI_MODEL = "qwen3-omni-flash-2025-12-01"
    AI_COMMENT_INTERVAL = 60  # seconds
    AI_HISTORY_DIR = "logs/history"
    AI_TEMPERATURE = 1.0  # Higher value = more creative/random (0.0 - 2.0)
    AI_USE_AUDIO = True  # Enable audio recording and transcription for context
    
    # AI System Prompt
    AI_PROMPT = """你是一个热情的直播间观众。
请根据直播画面内容，生成一句简短的提问（40字以内）。
提问内容必须围绕以下领域之一展开：当前直播间画面内容相关、兴隆咖啡相关领域，吉纳客公司相关，咖啡豆知识相关，速溶咖啡知识相关。
风格要自然、活跃气氛。

【关键约束】每次生成必须与之前完全不同，不要重复任何说过的句子，即使意思相近也要换一种表达方式。"""


# Default config for CLI (used by main.py)
DEFAULT_CONFIG = {
    "fast_click_prob": Config.FAST_CLICK_PROBABILITY,
    "fast_min": Config.FAST_CLICK_MIN,
    "fast_max": Config.FAST_CLICK_MAX,
    "slow_min": Config.SLOW_CLICK_MIN,
    "slow_max": Config.SLOW_CLICK_MAX,
    "cycle_mode": False,
    "work_min": 10,
    "rest_min": 5,
    "ai_enabled": Config.AI_ENABLED,
    "ai_interval": Config.AI_COMMENT_INTERVAL,
}
