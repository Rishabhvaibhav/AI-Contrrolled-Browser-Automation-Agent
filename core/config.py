import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Workspace paths
PROFILES_DIR = BASE_DIR / "profiles"
DOWNLOADS_DIR = BASE_DIR / "downloads"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"

PROFILES_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Alpme Gateway Configuration
ALPME_BASE_URL = os.getenv("ALPME_BASE_URL", "https://alpme.com/v1")
ALPME_API_KEY = os.getenv("ALPME_API_KEY", "")
DEFAULT_MODEL = os.getenv("ALPME_MODEL", "gemini-3.8-flash")

# Fallback LLM Configuration (if Alpme is under heavy load)
FALLBACK_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FALLBACK_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# Browser Configuration
DEFAULT_PROFILE_NAME = os.getenv("DEFAULT_PROFILE", "default")
HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")  # 'chrome' or 'chromium'
SLOW_MO_MS = int(os.getenv("SLOW_MO_MS", "50"))
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "30000"))

# User-Agent mimicking real Chrome on Windows 11
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Viewport
DEFAULT_VIEWPORT = {
    "width": 1366,
    "height": 768
}
