"""
Browser base module - Shared browser utilities
"""
import os
import sys
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import Config


class BrowserBase:
    """Base class for browser operations"""

    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    async def launch_browser(self, headless=True, maximized=False):
        """Launch browser with anti-detection settings"""

        # Set Playwright browser path for packaged environment
        if getattr(sys, 'frozen', False):
            from build_config import get_base_path
            base_path = get_base_path()
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_path, "playwright", "driver")

        self.playwright = await async_playwright().start()

        args = Config.MAXIMIZED_ARGS if maximized else Config.HEADLESS_ARGS
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=args
        )

        # Build context options
        context_options = {
            "user_agent": Config.USER_AGENT,
            "viewport": Config.VIEWPORT
        }

        # Load saved state if exists (use build config path if available)
        if Config.USE_BUILD_CONFIG:
            from build_config import get_state_path
            state_file = get_state_path()
        else:
            state_file = Config.STATE_FILE

        if os.path.exists(state_file):
            context_options["storage_state"] = state_file
        else:
            self.log(f"Tip: No login state found ({state_file}), running as guest")

        self.context = await self.browser.new_context(**context_options)

        # Anti-detection script
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        self.page = await self.context.new_page()
        return self.page

    async def close(self):
        """Clean up browser resources"""
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

        self.context = None
        self.page = None

    async def save_state(self, path=None):
        """Save browser state (cookies, localStorage)"""
        if path:
            save_path = path
        elif Config.USE_BUILD_CONFIG:
            from build_config import get_state_path
            save_path = get_state_path()
        else:
            save_path = Config.STATE_FILE

        if self.context:
            await self.context.storage_state(path=save_path)
            self.log(f"Login state saved to {save_path}")
