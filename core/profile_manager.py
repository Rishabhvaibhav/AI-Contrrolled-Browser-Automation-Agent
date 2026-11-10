import os
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import PROFILES_DIR, DEFAULT_PROFILE_NAME
from core.browser_engine import BrowserEngine

logger = logging.getLogger("ShadowBrowser.ProfileManager")

TARGET_SERVICES = {
    "linkedin": {
        "name": "LinkedIn",
        "domain": "linkedin.com",
        "login_url": "https://www.linkedin.com/login",
        "check_url": "https://www.linkedin.com/feed/",
    },
    "naukri": {
        "name": "Naukri",
        "domain": "naukri.com",
        "login_url": "https://www.naukri.com/nlogin/login",
        "check_url": "https://www.naukri.com/mnjuser/homepage",
    },
    "indeed": {
        "name": "Indeed",
        "domain": "indeed.com",
        "login_url": "https://secure.indeed.com/account/login",
        "check_url": "https://www.indeed.com/",
    },
    "google": {
        "name": "Google",
        "domain": "google.com",
        "login_url": "https://accounts.google.com/signin",
        "check_url": "https://myaccount.google.com/",
    },
    "github": {
        "name": "GitHub",
        "domain": "github.com",
        "login_url": "https://github.com/login",
        "check_url": "https://github.com/",
    },
}

class ProfileManager:
    """
    Manages persistent Chrome profiles, cookie stores, and interactive login sessions.
    """

    def __init__(self, base_dir: Path = PROFILES_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> List[str]:
        """Lists all existing browser profiles."""
        profiles = [p.name for p in self.base_dir.iterdir() if p.is_dir()]
        if not profiles:
            (self.base_dir / DEFAULT_PROFILE_NAME).mkdir(parents=True, exist_ok=True)
            profiles = [DEFAULT_PROFILE_NAME]
        return sorted(profiles)

    def create_profile(self, profile_name: str) -> Path:
        """Creates a new profile directory."""
        profile_path = self.base_dir / profile_name
        profile_path.mkdir(parents=True, exist_ok=True)
        return profile_path

    async def inspect_profile_logins(self, profile_name: str = DEFAULT_PROFILE_NAME) -> Dict[str, Any]:
        """
        Launches the profile in headless mode to inspect active cookies & login states.
        """
        engine = BrowserEngine(profile_name=profile_name, headless=True)
        results = {
            "profile": profile_name,
            "services": {},
            "total_cookies": 0,
            "domains": [],
        }

        try:
            await engine.launch()
            cookies = await engine.context.cookies()
            results["total_cookies"] = len(cookies)
            domains = set()

            for c in cookies:
                d = c.get("domain", "").lstrip(".")
                if d:
                    domains.add(d)

            results["domains"] = sorted(list(domains))

            for key, svc in TARGET_SERVICES.items():
                domain = svc["domain"]
                matched = [c for c in cookies if domain in c.get("domain", "")]
                has_session = False
                # Check for critical auth cookies
                if key == "linkedin":
                    has_session = any(c.get("name") in ("li_at", "li_theme") for c in matched)
                elif key == "naukri":
                    has_session = any("naukri" in c.get("name", "").lower() or c.get("name") in ("logged_in", "user_type") for c in matched)
                elif key == "github":
                    has_session = any(c.get("name") in ("user_session", "logged_in") for c in matched)
                elif key == "google":
                    has_session = any(c.get("name") in ("SID", "SSID", "HSID") for c in matched)
                else:
                    has_session = len(matched) > 2

                results["services"][key] = {
                    "name": svc["name"],
                    "logged_in": has_session,
                    "cookie_count": len(matched),
                }

        except Exception as e:
            logger.error(f"Error inspecting profile: {e}")
            results["error"] = str(e)
        finally:
            await engine.close()

        return results

    async def open_manual_login(
        self,
        profile_name: str = DEFAULT_PROFILE_NAME,
        site_or_url: str = "linkedin",
        wait_seconds: Optional[int] = None,
    ):
        """
        Opens a visible, headful real Chrome browser so the user can log in to any site
        (LinkedIn, Naukri, Indeed, Google, etc.), solve 2FA/OTPs, and save the session permanently.
        """
        if site_or_url in TARGET_SERVICES:
            url = TARGET_SERVICES[site_or_url]["login_url"]
            svc_name = TARGET_SERVICES[site_or_url]["name"]
        elif site_or_url.startswith("http://") or site_or_url.startswith("https://"):
            url = site_or_url
            svc_name = "Custom URL"
        else:
            url = f"https://{site_or_url}"
            svc_name = site_or_url

        print("\n" + "=" * 65)
        print(f"🚀 OPENING MANUAL LOGIN SESSION FOR: {svc_name}")
        print(f"📂 Profile: {profile_name}")
        print(f"🔗 URL: {url}")
        print("=" * 65)
        print("💡 Complete your login (enter credentials, OTP/2FA, CAPTCHA).")
        print("💾 All cookies, localStorage, session states will be saved automatically.")
        print("=" * 65 + "\n")

        engine = BrowserEngine(profile_name=profile_name, headless=False)
        try:
            page = await engine.launch()
            await page.goto(url)

            if wait_seconds:
                print(f"⏳ Waiting for {wait_seconds} seconds before saving profile...")
                await asyncio.sleep(wait_seconds)
            else:
                # Run an async input loop or wait for enter
                loop = asyncio.get_event_loop()
                print("👉 Press [ENTER] in this terminal once you have finished logging in...")
                await loop.run_in_executor(None, input)

            # Check cookies saved
            cookies = await engine.context.cookies()
            print(f"\n✅ SUCCESS: Captured {len(cookies)} cookies into profile '{profile_name}'!")
        finally:
            await engine.close()
            print(f"🔒 Profile '{profile_name}' safely saved on disk.\n")
