"""
agents/freelance_agent.py — Autonomous agent for freelance platform signup, profile creation,
and job/project discovery + application.

Workflow:
  1. Load prioritized platform list from data/freelance_platforms.json
  2. For each platform: signup → fill profile → search projects → apply
  3. Track status per platform in data/freelance_signup_status.json
  4. Handle OTP via GmailOTPReader (IMAP or browser fallback)
  5. Human-emulated interactions (HumanEmulator v2: Bezier, micro-tremor, burst typing)
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from core.browser_engine import BrowserEngine
from core.config import (
    FREELANCE_PLATFORMS_JSON,
    FREELANCE_STATUS_JSON,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    RESUME_PATH,
    DATA_DIR,
)
from core.freelance_profile import FreelanceProfile
from core.human_emulator import HumanEmulator
from agents.gmail_otp_reader import GmailOTPReader

logger = logging.getLogger("ShadowBrowser.FreelanceAgent")


# ──────────────────────────────────────────────────────────────────────────────
#  Platform Database
# ──────────────────────────────────────────────────────────────────────────────

def load_platforms(
    priority_filter: Optional[int] = None,
    category_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load and optionally filter platforms from freelance_platforms.json."""
    if not FREELANCE_PLATFORMS_JSON.exists():
        logger.error(f"Platform database not found: {FREELANCE_PLATFORMS_JSON}")
        return []

    data = json.loads(FREELANCE_PLATFORMS_JSON.read_text(encoding="utf-8"))
    platforms = data.get("platforms", [])

    if priority_filter is not None:
        platforms = [p for p in platforms if p.get("priority") == priority_filter]
    if category_filter:
        platforms = [p for p in platforms if p.get("category") == category_filter]

    # Sort: priority ASC, then alphabetical
    platforms.sort(key=lambda p: (p.get("priority", 99), p.get("name", "")))
    return platforms


def load_status() -> Dict[str, Any]:
    if FREELANCE_STATUS_JSON.exists():
        return json.loads(FREELANCE_STATUS_JSON.read_text(encoding="utf-8"))
    return {}


def save_status(status: Dict[str, Any]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FREELANCE_STATUS_JSON.write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_platform_key(platform: Dict[str, Any]) -> str:
    """Canonical key for a platform (domain extracted from URL)."""
    url = platform.get("url", platform.get("name", ""))
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return platform.get("name", "unknown").lower().replace(" ", "_")


# ──────────────────────────────────────────────────────────────────────────────
#  Platform-specific signup strategies
# ──────────────────────────────────────────────────────────────────────────────

SIGNUP_STRATEGIES: Dict[str, Dict[str, Any]] = {
    # Maps domain → field selectors and flow hints
    "upwork.com": {
        "signup_url": "https://www.upwork.com/signup/",
        "flow": "standard",
        "fields": {
            "first_name": ["#first-name", "[name='firstName']", "input[placeholder*='First']"],
            "last_name": ["#last-name", "[name='lastName']", "input[placeholder*='Last']"],
            "email": ["#email-address", "[name='email']", "input[type='email']"],
            "password": ["#password", "[name='password']", "input[type='password']"],
        },
        "submit_selector": "[data-test='submit-btn'], button[type='submit']",
        "otp_trigger": "email",
    },
    "fiverr.com": {
        "signup_url": "https://www.fiverr.com/join",
        "flow": "standard",
        "fields": {
            "email": ["input[name='email']", "input[type='email']"],
            "password": ["input[name='password']", "input[type='password']"],
            "full_name": ["input[name='username']", "input[placeholder*='username']"],
        },
        "submit_selector": "button[data-testid='join-submit-btn'], button[type='submit']",
        "otp_trigger": "email",
    },
    "freelancer.com": {
        "signup_url": "https://www.freelancer.com/signup",
        "flow": "standard",
        "fields": {
            "email": ["#signup-email", "input[name='email']"],
            "password": ["#signup-password", "input[name='password']"],
            "full_name": ["#signup-name", "input[name='name']"],
        },
        "submit_selector": "#signup-btn, button[type='submit']",
        "otp_trigger": "email",
    },
    "guru.com": {
        "signup_url": "https://www.guru.com/register.aspx",
        "flow": "standard",
        "fields": {
            "first_name": ["input[name='ctl00$WorkArea$txtFirstName']", "input[placeholder*='First']"],
            "last_name": ["input[name='ctl00$WorkArea$txtLastName']", "input[placeholder*='Last']"],
            "email": ["input[name='ctl00$WorkArea$txtEmail']", "input[type='email']"],
            "password": ["input[name='ctl00$WorkArea$txtPassword']", "input[type='password']"],
        },
        "submit_selector": "input[type='submit'], button[type='submit']",
        "otp_trigger": "email",
    },
    "peopleperhour.com": {
        "signup_url": "https://www.peopleperhour.com/register",
        "flow": "standard",
        "fields": {
            "first_name": ["input[name='firstName']", "input[placeholder*='First']"],
            "last_name": ["input[name='lastName']", "input[placeholder*='Last']"],
            "email": ["input[name='email']", "input[type='email']"],
            "password": ["input[name='password']", "input[type='password']"],
        },
        "submit_selector": "button[type='submit']",
        "otp_trigger": "email",
    },
    "wellfound.com": {
        "signup_url": "https://wellfound.com/join",
        "flow": "standard",
        "fields": {
            "email": ["input[type='email']", "input[name='email']"],
            "password": ["input[type='password']", "input[name='password']"],
        },
        "submit_selector": "button[type='submit']",
        "otp_trigger": "email",
    },
    "contra.com": {
        "signup_url": "https://contra.com/signup",
        "flow": "email_link",  # Contra sends a magic link, no password
        "fields": {
            "email": ["input[type='email']", "input[name='email']"],
        },
        "submit_selector": "button[type='submit']",
        "otp_trigger": "magic_link",
    },
}

# Default fallback strategy for unknown platforms
DEFAULT_STRATEGY = {
    "flow": "standard",
    "fields": {
        "first_name": [
            "input[name='first_name']", "input[name='firstName']",
            "input[placeholder*='First']", "#first-name",
        ],
        "last_name": [
            "input[name='last_name']", "input[name='lastName']",
            "input[placeholder*='Last']", "#last-name",
        ],
        "email": ["input[type='email']", "input[name='email']", "#email"],
        "password": ["input[type='password']", "input[name='password']", "#password"],
        "full_name": ["input[name='name']", "input[placeholder*='Full Name']"],
    },
    "submit_selector": "button[type='submit']",
    "otp_trigger": "email",
}


# ──────────────────────────────────────────────────────────────────────────────
#  FreelanceAgent
# ──────────────────────────────────────────────────────────────────────────────

class FreelanceAgent:
    """
    Autonomous agent that signs up on freelance platforms, builds profiles,
    and applies to projects — with full human emulation and OTP handling.
    """

    def __init__(
        self,
        engine: BrowserEngine,
        profile: Optional[FreelanceProfile] = None,
        safe_mode: bool = True,
        headless: bool = False,
    ):
        self.engine = engine
        self.profile = profile or FreelanceProfile.from_json()
        self.safe_mode = safe_mode
        self.headless = headless
        self._status: Dict[str, Any] = load_status()
        self._otp_reader = GmailOTPReader(
            gmail_address=GMAIL_ADDRESS,
            app_password=GMAIL_APP_PASSWORD,
        )
        self._log: List[str] = []

    def log(self, msg: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log.append(line)
        getattr(logger, level)(msg)

    def get_log(self) -> List[str]:
        return list(self._log)

    # ── Status helpers ────────────────────────────────────────────

    def _get_platform_status(self, key: str) -> Dict[str, Any]:
        return self._status.get(key, {
            "status": "pending",
            "signed_up": False,
            "profile_complete": False,
            "last_attempted": None,
            "last_error": None,
            "applied_jobs": [],
        })

    def _set_platform_status(self, key: str, **kwargs):
        current = self._get_platform_status(key)
        current.update(kwargs)
        current["last_updated"] = datetime.now().isoformat()
        self._status[key] = current
        save_status(self._status)

    # ── Core: Signup ──────────────────────────────────────────────

    async def signup_platform(self, platform: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to create an account on a single freelance platform.
        Returns a result dict with status, error, and log entries.
        """
        key = get_platform_key(platform)
        name = platform.get("name", key)
        url = platform.get("url", "")
        self.log(f"Starting signup: {name} ({url})")

        self._set_platform_status(key, status="in_progress", last_attempted=datetime.now().isoformat())

        strategy = SIGNUP_STRATEGIES.get(key, {})
        signup_url = strategy.get("signup_url") or self._guess_signup_url(url)
        flow = strategy.get("flow", "standard")

        try:
            page = self.engine.page
            human = HumanEmulator()

            # Navigate to signup page
            self.log(f"Navigating to {signup_url}")
            await page.goto(signup_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            await human.idle_drift(page, seconds=1.5)

            # Fill form fields
            await self._fill_signup_form(page, strategy or DEFAULT_STRATEGY, human)

            # Handle post-submit OTP
            if not self.safe_mode:
                await self._submit_form(page, strategy or DEFAULT_STRATEGY, human)
                otp_result = await self._handle_otp_flow(page, platform, flow)
                self.log(f"OTP result: {otp_result}")
                self._set_platform_status(key, status="signed_up", signed_up=True)
            else:
                self.log(f"[SAFE MODE] Paused before submit on {name}. Manual review needed.")
                self._set_platform_status(key, status="paused_safe_mode")

            return {"platform": name, "status": "success", "key": key, "log": self.get_log()}

        except Exception as e:
            err = str(e)
            self.log(f"Signup failed on {name}: {err}", level="error")
            self._set_platform_status(key, status="error", last_error=err)
            return {"platform": name, "status": "error", "error": err, "key": key}

    async def _fill_signup_form(self, page, strategy: Dict, human: HumanEmulator):
        """Fill all signup form fields with human-emulated typing."""
        form_data = self.profile.as_form_dict()
        field_map = strategy.get("fields", DEFAULT_STRATEGY["fields"])

        # Generate a strong password for new account
        signup_password = self._generate_password()

        fill_order = ["first_name", "last_name", "full_name", "email", "password"]
        for field_key in fill_order:
            if field_key not in field_map:
                continue
            selectors = field_map[field_key]
            value = signup_password if field_key == "password" else form_data.get(field_key, "")
            if not value:
                continue

            for selector in selectors:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await human.click_element(page, selector)
                        await asyncio.sleep(random.uniform(0.3, 0.6))
                        await human.clear_and_type(page, selector, value)
                        self.log(f"  Filled '{field_key}' with {len(value)} chars")
                        break
                except Exception as e:
                    self.log(f"  Selector {selector} failed: {e}", level="debug")
                    continue

            # Small natural pause between fields
            await asyncio.sleep(random.uniform(0.5, 1.2))

    async def _submit_form(self, page, strategy: Dict, human: HumanEmulator):
        """Click the submit button with human-like movement."""
        submit_sel = strategy.get("submit_selector", "button[type='submit']")
        for sel in submit_sel.split(","):
            sel = sel.strip()
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await human.click_element(page, sel)
                    self.log(f"  Clicked submit: {sel}")
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    return
            except Exception:
                continue
        self.log("  Submit button not found, pressing Enter", level="warning")
        await page.keyboard.press("Enter")

    async def _handle_otp_flow(self, page, platform: Dict, flow: str) -> str:
        """Wait for OTP/magic link, extract, and fill it."""
        domain = get_platform_key(platform)
        await asyncio.sleep(2)  # Give time for email to arrive

        if flow == "magic_link":
            self.log(f"Magic link flow — checking Gmail for link from {domain}")
            # For magic links, just wait — user may need to click the link in Gmail
            # (future: open Gmail tab, click link)
            return "magic_link_sent"

        self.log(f"Waiting for OTP email from {domain}...")
        otp = await self._otp_reader.wait_for_otp(
            sender_domain=domain,
            timeout_seconds=90,
        )

        if otp:
            self.log(f"OTP received: {otp}")
            # Try to find OTP input field
            otp_selectors = [
                "input[name='otp']", "input[name='code']", "input[name='verificationCode']",
                "input[placeholder*='code']", "input[placeholder*='OTP']",
                "input[maxlength='6']", "input[maxlength='4']",
            ]
            human = HumanEmulator()
            for sel in otp_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await human.click_element(page, sel)
                        await human.human_type(page, otp)
                        await page.keyboard.press("Enter")
                        self.log(f"OTP filled in {sel}")
                        return f"otp_filled:{otp}"
                except Exception:
                    continue
            self.log("OTP input field not found — manual OTP entry needed", level="warning")
            return f"otp_found_no_field:{otp}"
        else:
            self.log("OTP not received within timeout", level="warning")
            return "otp_timeout"

    # ── Core: Profile Creation ────────────────────────────────────

    async def build_profile(self, platform: Dict[str, Any]) -> Dict[str, Any]:
        """
        After signup, navigate to profile settings and populate bio, skills,
        hourly rate, and resume upload.
        """
        key = get_platform_key(platform)
        name = platform.get("name", key)
        self.log(f"Building profile on {name}")

        try:
            page = self.engine.page
            human = HumanEmulator()

            # Platform-specific profile URLs
            profile_urls = {
                "upwork.com": "https://www.upwork.com/freelancers/settings/profileVisibility",
                "fiverr.com": "https://www.fiverr.com/users/settings/professional_info",
                "freelancer.com": "https://www.freelancer.com/users/settings/account",
                "guru.com": "https://www.guru.com/freelancers/edit-profile.aspx",
            }
            profile_url = profile_urls.get(key)
            if profile_url:
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

            # Fill bio/overview field
            bio_selectors = [
                "textarea[name='overview']", "textarea[name='description']",
                "textarea[name='bio']", "textarea[placeholder*='bio']",
                "textarea[placeholder*='overview']", ".profile-bio textarea",
            ]
            for sel in bio_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await human.click_element(page, sel)
                        await human.clear_and_type(page, sel, self.profile.get_bio(long=True))
                        self.log(f"Bio filled in {sel}")
                        break
                except Exception:
                    continue

            # Upload resume if field exists
            if RESUME_PATH.exists():
                file_inputs = await page.query_selector_all("input[type='file']")
                for fi in file_inputs:
                    try:
                        await fi.set_input_files(str(RESUME_PATH))
                        self.log(f"Resume uploaded: {RESUME_PATH.name}")
                        break
                    except Exception:
                        continue

            self._set_platform_status(key, profile_complete=True)
            return {"platform": name, "status": "profile_built"}

        except Exception as e:
            err = str(e)
            self.log(f"Profile build failed on {name}: {err}", level="error")
            return {"platform": name, "status": "error", "error": err}

    # ── Core: Job Search & Apply ──────────────────────────────────

    async def search_and_apply(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        max_per_platform: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for projects matching the query on specified platforms and apply.
        platforms: list of platform keys (e.g. ['upwork.com', 'fiverr.com'])
        """
        all_results = []
        platform_list = load_platforms(priority_filter=1)

        if platforms:
            platform_list = [p for p in platform_list if get_platform_key(p) in platforms]

        for platform in platform_list:
            key = get_platform_key(platform)
            self.log(f"Searching '{query}' on {platform.get('name')}")
            results = await self._search_platform(platform, query, max_per_platform)
            all_results.extend(results)

        return all_results

    async def _search_platform(
        self, platform: Dict[str, Any], query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Platform-specific job/project search."""
        key = get_platform_key(platform)
        search_patterns = {
            "upwork.com": f"https://www.upwork.com/nx/search/jobs/?q={query.replace(' ', '+')}&sort=recency",
            "fiverr.com": f"https://www.fiverr.com/search/gigs?query={query.replace(' ', '%20')}",
            "freelancer.com": f"https://www.freelancer.com/jobs/?keyword={query.replace(' ', '+')}",
            "guru.com": f"https://www.guru.com/d/jobs/q/{query.replace(' ', '-')}/",
            "peopleperhour.com": f"https://www.peopleperhour.com/freelance-jobs?q={query.replace(' ', '+')}",
            "wellfound.com": f"https://wellfound.com/jobs?q={query.replace(' ', '%20')}",
        }

        search_url = search_patterns.get(key)
        if not search_url:
            return []

        try:
            page = self.engine.page
            human = HumanEmulator()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))
            await human.idle_drift(page, seconds=1)

            # Extract job/project listings
            jobs = await self._extract_job_listings(page, key)
            self.log(f"Found {len(jobs)} jobs on {key}")
            return jobs[:limit]

        except Exception as e:
            self.log(f"Search failed on {key}: {e}", level="error")
            return []

    async def _extract_job_listings(self, page, platform_key: str) -> List[Dict[str, Any]]:
        """Extract job listings from the current search results page."""
        selectors = {
            "upwork.com": {"container": "section.air3-card", "title": "h3", "link": "a"},
            "freelancer.com": {"container": ".JobSearchCard-item", "title": "h2 a", "link": "h2 a"},
            "fiverr.com": {"container": "li.gig-card-layout", "title": "h3 a", "link": "h3 a"},
        }
        config = selectors.get(platform_key, {"container": "article", "title": "h2,h3,h4", "link": "a"})

        jobs = []
        try:
            containers = await page.query_selector_all(config["container"])
            for c in containers[:10]:
                title_el = await c.query_selector(config["title"])
                link_el = await c.query_selector(config["link"])

                title = await title_el.inner_text() if title_el else "Unknown"
                href = await link_el.get_attribute("href") if link_el else ""
                if href and not href.startswith("http"):
                    base = f"https://{platform_key}"
                    href = base + href

                jobs.append({"title": title.strip(), "url": href, "platform": platform_key})
        except Exception as e:
            self.log(f"Listing extraction error on {platform_key}: {e}", level="debug")

        return jobs

    # ── Batch operations ──────────────────────────────────────────

    async def signup_all(
        self,
        priority: int = 1,
        skip_existing: bool = True,
    ) -> List[Dict[str, Any]]:
        """Sign up on all platforms of given priority level."""
        platforms = load_platforms(priority_filter=priority)
        results = []
        for platform in platforms:
            key = get_platform_key(platform)
            if skip_existing and self._get_platform_status(key).get("signed_up"):
                self.log(f"Skipping {platform['name']} — already signed up")
                continue
            result = await self.signup_platform(platform)
            results.append(result)
            # Natural pause between platform signups
            await asyncio.sleep(random.uniform(3, 7))
        return results

    # ── Utilities ─────────────────────────────────────────────────

    def _guess_signup_url(self, base_url: str) -> str:
        """Guess signup URL for unknown platforms."""
        for suffix in ["/signup", "/register", "/join", "/create-account"]:
            return base_url.rstrip("/") + suffix
        return base_url

    def _generate_password(self) -> str:
        """Generate a strong password for new platform accounts."""
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "!@#$%"
        base = secrets.token_urlsafe(12)
        # Ensure uppercase, digit, special
        return base[:8] + "Rv" + str(random.randint(10, 99)) + "!"

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of signup status across all platforms."""
        total = len(self._status)
        signed_up = sum(1 for v in self._status.values() if v.get("signed_up"))
        profiles = sum(1 for v in self._status.values() if v.get("profile_complete"))
        errors = sum(1 for v in self._status.values() if v.get("status") == "error")
        return {
            "total_attempted": total,
            "signed_up": signed_up,
            "profiles_complete": profiles,
            "errors": errors,
            "pending": total - signed_up - errors,
        }
