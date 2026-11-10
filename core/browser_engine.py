import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from playwright_stealth.stealth import Stealth

from core.config import (
    PROFILES_DIR,
    DOWNLOADS_DIR,
    CHROME_PATH,
    BROWSER_CHANNEL,
    HEADLESS_MODE,
    SLOW_MO_MS,
    TIMEOUT_MS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
    DEFAULT_PROFILE_NAME,
)

logger = logging.getLogger("ShadowBrowser.Engine")

# Advanced anti-detection JavaScript to inject before any script runs
STEALTH_INIT_SCRIPT = """
(() => {
    // 1. Remove navigator.webdriver flag
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Mock window.chrome object
    if (!window.chrome) {
        window.chrome = {
            runtime: {
                OnInstalledReason: {
                    CHROME_UPDATE: "chrome_update",
                    INSTALL: "install",
                    SHARED_MODULE_UPDATE: "shared_module_update",
                    UPDATE: "update"
                },
                PlatformArch: {
                    ARM: "arm",
                    ARM64: "arm64",
                    MIPS: "mips",
                    MIPS64: "mips64",
                    X86_32: "x86-32",
                    X86_64: "x86-64"
                },
                PlatformNaclArch: {
                    ARM: "arm",
                    MIPS: "mips",
                    MIPS64: "mips64",
                    X86_32: "x86-32",
                    X86_64: "x86-64"
                },
                PlatformOs: {
                    ANDROID: "android",
                    CROS: "cros",
                    LINUX: "linux",
                    MAC: "mac",
                    OPENBSD: "openbsd",
                    WIN: "win"
                },
                RequestUpdateCheckStatus: {
                    NO_UPDATE: "no_update",
                    THROTTLED: "throttled",
                    UPDATE_AVAILABLE: "update_available"
                }
            },
            app: {
                isInstalled: false,
                InstallState: {
                    DISABLED: "disabled",
                    INSTALLED: "installed",
                    NOT_INSTALLED: "not_installed"
                },
                RunningState: {
                    CANNOT_RUN: "cannot_run",
                    READY_TO_RUN: "ready_to_run",
                    RUNNING: "running"
                }
            },
            csi: function() {},
            loadTimes: function() {}
        };
    }

    // 3. Mock navigator.plugins and mimeTypes
    if (navigator.plugins.length === 0) {
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin"
                },
                {
                    0: {type: "application/pdf", suffixes: "pdf", description: ""},
                    description: "",
                    filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                    length: 1,
                    name: "Chrome PDF Viewer"
                }
            ]
        });
    }

    // 4. Overwrite permissions query to emulate real user granted status
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );

    // 5. Spoof hardware concurrency & device memory if absent
    if (!navigator.hardwareConcurrency || navigator.hardwareConcurrency < 4) {
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    }
    if (!navigator.deviceMemory) {
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    }

    // 6. Clean up console debug overrides
    window.console.debug = function() {};
})();
"""

class BrowserEngine:
    """
    Manages the lifecycle of a real, stealth-instrumented Google Chrome browser
    with persistent user-data profiles (preserving cookies, cache, tokens, and logins).
    """

    def __init__(
        self,
        profile_name: str = DEFAULT_PROFILE_NAME,
        headless: bool = HEADLESS_MODE,
        viewport: Optional[Dict[str, int]] = None,
        chrome_path: Optional[str] = None,
    ):
        self.profile_name = profile_name
        self.headless = headless
        self.viewport = viewport or DEFAULT_VIEWPORT
        self.chrome_path = chrome_path or CHROME_PATH

        self.user_data_dir = PROFILES_DIR / profile_name
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._active_page: Optional[Page] = None
        self._stealth = Stealth()

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Browser is not running. Call launch() first.")
        return self._context

    @property
    def page(self) -> Page:
        if not self._active_page:
            raise RuntimeError("No active page available. Call launch() first.")
        return self._active_page

    async def launch(self) -> Page:
        """
        Launches the browser with persistent context and applies all anti-detection layers.
        """
        logger.info(f"Launching browser with profile: {self.profile_name} (Headless: {self.headless})")
        logger.info(f"Persistent data dir: {self.user_data_dir}")

        self._playwright = await async_playwright().start()

        # Real Chrome launch flags optimized for stealth, stability, and anti-bot evasion
        chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--ignore-certificate-errors",
            f"--window-size={self.viewport['width']},{self.viewport['height']}",
        ]

        launch_kwargs: Dict[str, Any] = {
            "user_data_dir": str(self.user_data_dir),
            "headless": self.headless,
            "args": chrome_args,
            "viewport": self.viewport,
            "user_agent": DEFAULT_USER_AGENT,
            "ignore_https_errors": True,
            "slow_mo": SLOW_MO_MS,
            "accept_downloads": True,
            "color_scheme": "dark",
            "locale": "en-US",
            "timezone_id": "Asia/Kolkata",
        }

        # Prefer real installed Chrome if available on disk
        if self.chrome_path and Path(self.chrome_path).exists():
            launch_kwargs["executable_path"] = self.chrome_path
            logger.info(f"Using host Google Chrome executable: {self.chrome_path}")
        else:
            launch_kwargs["channel"] = BROWSER_CHANNEL
            logger.info(f"Using Playwright channel: {BROWSER_CHANNEL}")

        try:
            self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            logger.warning(f"Failed to launch with executable {self.chrome_path}: {e}")
            # Fallback to standard Playwright chromium channel
            launch_kwargs.pop("executable_path", None)
            launch_kwargs["channel"] = "chromium"
            self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Apply stealth scripts to context
        await self._context.add_init_script(STEALTH_INIT_SCRIPT)

        # Hook existing pages or open new page
        pages = self._context.pages
        if pages:
            self._active_page = pages[0]
        else:
            self._active_page = await self._context.new_page()

        # Apply Playwright-Stealth evasions
        await self._stealth.apply_stealth_async(self._active_page)

        # Listen for newly created pages/tabs
        self._context.on("page", self._handle_new_page)

        self._active_page.set_default_timeout(TIMEOUT_MS)
        self._active_page.set_default_navigation_timeout(TIMEOUT_MS)

        logger.info(f"Browser launched successfully! Active page ready.")
        return self._active_page

    async def _handle_new_page(self, new_page: Page):
        """Applies stealth evasions automatically to any new tab or popup."""
        logger.info("New tab detected, applying stealth evasions...")
        try:
            await self._stealth.apply_stealth_async(new_page)
            await new_page.add_init_script(STEALTH_INIT_SCRIPT)
            self._active_page = new_page
        except Exception as e:
            logger.warning(f"Error initializing new page: {e}")

    async def navigate(self, url: str, wait_until: str = "load") -> bool:
        """Navigates the active page to a URL with timeout recovery."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        logger.info(f"Navigating to: {url}")
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=TIMEOUT_MS)
            await asyncio.sleep(1.0)
            return True
        except Exception as e:
            logger.warning(f"Navigation warning ({url}): {e}")
            return False

    async def switch_to_tab(self, index: int = -1) -> Page:
        """Switches active page to a specific tab index (default: most recent tab)."""
        pages = self._context.pages
        if not pages:
            raise RuntimeError("No open tabs.")
        target_page = pages[index]
        await target_page.bring_to_front()
        self._active_page = target_page
        return self._active_page

    async def take_screenshot(self, save_path: Optional[str] = None, full_page: bool = False) -> bytes:
        """Captures a screenshot of the active page."""
        screenshot_bytes = await self.page.screenshot(full_page=full_page)
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(screenshot_bytes)
        return screenshot_bytes

    async def get_cookies_domains(self) -> List[str]:
        """Returns list of domains for which cookies are currently saved."""
        cookies = await self.context.cookies()
        domains = sorted(list({c.get("domain", "").lstrip(".") for c in cookies if c.get("domain")}))
        return domains

    async def close(self):
        """Gracefully closes active context and saves persistent profile."""
        logger.info("Saving session and closing browser...")
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self._context = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None
        logger.info("Browser closed and profile saved successfully.")
