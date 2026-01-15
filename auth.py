"""
DouYin Login Module - Simplified using BrowserBase
"""
import asyncio
from base import BrowserBase


class LoginHandler(BrowserBase):
    """Handle DouYin login process"""

    async def login(self):
        """Run login flow"""
        print("Starting browser...")

        # Launch browser in visible mode for QR code scanning
        await self.launch_browser(headless=False, maximized=True)

        print("Opening DouYin homepage...")
        await self.page.goto("https://www.douyin.com/")

        print("\n" + "=" * 50)
        print("Please login in the browser window (QR code recommended).")
        print("Press [Enter] here after login is complete.")
        print("=" * 50 + "\n")

        # Wait for user confirmation
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, input, "Press Enter when done...")

        # Save state
        await self.save_state()

        print("\nLogin state saved!")
        print("You can now run the auto-liker.")

        await self.close()


async def main():
    print("Preparing login...")
    handler = LoginHandler()
    try:
        await handler.login()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
