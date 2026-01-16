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
}
