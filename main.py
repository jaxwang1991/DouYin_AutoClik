"""
DouYin Auto Like - CLI version (simplified, uses DouYinLiker)
"""
import asyncio
import os
import sys
from liker import DouYinLiker
from config import Config


class CLIController:
    """Controller for CLI mode with keyboard support"""

    def __init__(self):
        self.liker = None
        self.paused = False

    def print_header(self):
        print("=" * 45)
        print("  DouYin Live Auto Like Tool (CLI)")
        print("=" * 45)

    def get_url(self):
        """Get live stream URL from user"""
        if len(sys.argv) > 1:
            url = sys.argv[1]
        else:
            self.print_header()
            url = input("Enter live stream URL: ").strip()

        if not url:
            print("No URL provided, exiting.")
            sys.exit(1)

        if "douyin.com" not in url:
            print("Warning: This doesn't look like a DouYin URL, but will proceed.")

        return url

    def get_headless_mode(self):
        """Ask if user wants headless mode"""
        mode = input("Show browser window? (y/n, default n): ").strip().lower()
        return mode != 'y'

    def log_callback(self, msg):
        """Log callback from liker"""
        print(msg)

    def status_callback(self, total_likes, state):
        """Status callback from liker"""
        # Could update status line here
        pass

    async def run(self):
        """Main entry point"""
        url = self.get_url()
        headless = self.get_headless_mode()

        print(f"\nStarting browser (headless={headless})...")

        self.liker = DouYinLiker(
            log_callback=self.log_callback,
            status_callback=self.status_callback
        )

        config = {
            "url": url,
            "headless": headless,
        }

        # Create screenshot dir if needed
        if headless and not os.path.exists(Config.SCREENSHOT_DIR):
            os.makedirs(Config.SCREENSHOT_DIR)

        # Start liker in background
        task = asyncio.create_task(self.liker.start(config))

        # Handle keyboard input (Windows only)
        if not headless and os.name == 'nt':
            await self._handle_keyboard_windows()
        else:
            # Just wait for task to complete
            await task

        print(f"\nFinished. Total likes: {self.liker.total_likes}")

    async def _handle_keyboard_windows(self):
        """Handle keyboard input on Windows"""
        import msvcrt

        while self.liker.is_running:
            await asyncio.sleep(0.1)

            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore').lower()

                if key == 'p':
                    self.liker.pause()
                    print("\n[PAUSED] Press 'r' to resume...")
                    while True:
                        await asyncio.sleep(0.1)
                        if msvcrt.kbhit():
                            if msvcrt.getch().decode('utf-8', errors='ignore').lower() == 'r':
                                self.liker.resume()
                                print("[RESUMED]")
                                break

                elif key == 'q':
                    print("\nStopping...")
                    await self.liker.stop()
                    break


async def main():
    """Entry point"""
    controller = CLIController()
    try:
        await controller.run()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        if controller.liker:
            await controller.liker.stop()


if __name__ == "__main__":
    asyncio.run(main())
