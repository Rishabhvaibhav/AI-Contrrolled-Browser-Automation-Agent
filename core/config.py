"""
core/config.py — Central configuration for ShadowBrowser.
All environment variables loaded from .env at the project root.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ── Workspace Paths ────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = BASE_DIR / "profiles"
DOWNLOADS_DIR = BASE_DIR / "downloads"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"

for _d in (DATA_DIR, PROFILES_DIR, DOWNLOADS_DIR, SCREENSHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Alpme Gateway ──────────────────────────────────────────────
ALPME_BASE_URL = os.getenv("ALPME_BASE_URL", "https://alpme.com/v1")
ALPME_API_KEY = os.getenv("ALPME_API_KEY", "")
DEFAULT_MODEL = os.getenv("ALPME_MODEL", "gemini-2.5-flash")

# ── Fallback LLM ───────────────────────────────────────────────
FALLBACK_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FALLBACK_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# ── Browser ────────────────────────────────────────────────────
DEFAULT_PROFILE_NAME = os.getenv("DEFAULT_PROFILE", "default")
HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")
SLOW_MO_MS = int(os.getenv("SLOW_MO_MS", "50"))
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "30000"))

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}

# ── Candidate / Freelance ──────────────────────────────────────
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "rishabhvaibhav7@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # 16-char app password for IMAP

FREELANCE_HOURLY_RATE_USD = int(os.getenv("FREELANCE_HOURLY_RATE", "50"))
FREELANCE_PLATFORMS_JSON = DATA_DIR / "freelance_platforms.json"
FREELANCE_STATUS_JSON = DATA_DIR / "freelance_signup_status.json"
CANDIDATE_PROFILE_JSON = BASE_DIR / "candidate_profile.json"
RESUME_PATH = BASE_DIR / "Resume.pdf"
