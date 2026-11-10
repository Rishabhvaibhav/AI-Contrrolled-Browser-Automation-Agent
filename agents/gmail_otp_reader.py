"""
agents/gmail_otp_reader.py — Extracts OTP codes from Gmail using IMAP or browser-based reading.

Strategy:
  1. IMAP first (fast, no browser needed) — requires GMAIL_APP_PASSWORD in .env
  2. Browser fallback — opens Gmail in a new tab within the same persistent Chrome profile
     (already logged-in because Gmail session is saved in profile cookies)
"""
from __future__ import annotations

import asyncio
import imaplib
import email
import re
import time
import logging
from typing import Optional

logger = logging.getLogger("ShadowBrowser.GmailOTPReader")

# Regex patterns for OTP / verification codes
_OTP_PATTERNS = [
    r"\b(\d{6})\b",           # 6-digit OTP (most common)
    r"\b(\d{4})\b",           # 4-digit OTP
    r"\b(\d{5})\b",           # 5-digit OTP
    r"code[:\s]+(\d{4,8})",   # "code: 123456"
    r"OTP[:\s]+(\d{4,8})",    # "OTP: 123456"
    r"PIN[:\s]+(\d{4,8})",    # "PIN: 123456"
    r"verification[:\s]+(\d{4,8})",
]


# ──────────────────────────────────────────────────────────────────────────────
#  IMAP Reader (preferred - no browser needed)
# ──────────────────────────────────────────────────────────────────────────────

class IMAPOTPReader:
    """
    Reads OTP from Gmail via IMAP using an App Password (not the account password).
    Generate at: https://myaccount.google.com/apppasswords
    """

    def __init__(self, gmail_address: str, app_password: str):
        self.gmail_address = gmail_address
        self.app_password = app_password
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self):
        self._imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        self._imap.login(self.gmail_address, self.app_password)

    def _disconnect(self):
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def _extract_otp_from_body(self, body: str) -> Optional[str]:
        for pattern in _OTP_PATTERNS:
            m = re.search(pattern, body, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def wait_for_otp(
        self,
        sender_domain: Optional[str] = None,
        subject_contains: Optional[str] = None,
        timeout_seconds: int = 90,
        poll_interval: int = 5,
    ) -> Optional[str]:
        """
        Poll inbox for a new OTP email, returning the first code found.
        sender_domain:    filter by sender domain (e.g. 'upwork.com')
        subject_contains: filter by subject substring (e.g. 'verify')
        """
        self._connect()
        try:
            self._imap.select("INBOX")

            # Mark baseline: count of existing unseen messages before we start
            _, baseline_data = self._imap.search(None, "UNSEEN")
            baseline_ids = set(baseline_data[0].split()) if baseline_data[0] else set()
            logger.info(f"Baseline unseen emails: {len(baseline_ids)}")

            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                time.sleep(poll_interval)
                self._imap.select("INBOX")  # refresh
                _, new_data = self._imap.search(None, "UNSEEN")
                new_ids = set(new_data[0].split()) if new_data[0] else set()
                fresh = new_ids - baseline_ids

                for msg_id in fresh:
                    _, msg_data = self._imap.fetch(msg_id, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    sender = msg.get("From", "")
                    subject = msg.get("Subject", "")

                    # Apply optional filters
                    if sender_domain and sender_domain.lower() not in sender.lower():
                        continue
                    if subject_contains and subject_contains.lower() not in subject.lower():
                        continue

                    # Extract body text
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() in ("text/plain", "text/html"):
                                try:
                                    body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                except Exception:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                        except Exception:
                            body = str(msg.get_payload())

                    otp = self._extract_otp_from_body(body)
                    if otp:
                        logger.info(f"OTP found via IMAP: {otp} (from: {sender}, subject: {subject})")
                        # Mark as read
                        self._imap.store(msg_id, "+FLAGS", "\\Seen")
                        return otp

            logger.warning(f"OTP not found within {timeout_seconds}s timeout")
            return None
        finally:
            self._disconnect()


# ──────────────────────────────────────────────────────────────────────────────
#  Browser-based Gmail OTP Reader (fallback when IMAP not configured)
# ──────────────────────────────────────────────────────────────────────────────

class BrowserOTPReader:
    """
    Opens Gmail in a new browser tab (using the already-logged-in profile session)
    and reads OTP from the most recent email.
    """

    def __init__(self, browser_context):
        self.context = browser_context

    async def wait_for_otp(
        self,
        sender_domain: Optional[str] = None,
        timeout_seconds: int = 90,
        poll_interval: int = 6,
    ) -> Optional[str]:
        page = await self.context.new_page()
        try:
            await page.goto("https://mail.google.com/mail/u/0/#inbox", timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            deadline = asyncio.get_event_loop().time() + timeout_seconds
            seen_subjects = set()

            while asyncio.get_event_loop().time() < deadline:
                # Refresh inbox
                await page.reload()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)

                # Find unread emails (bold subject lines)
                rows = await page.query_selector_all("tr.zA.zE")  # unread rows
                if not rows:
                    rows = await page.query_selector_all("[data-thread-id]")

                for row in rows[:5]:  # check top 5 emails
                    subject_el = await row.query_selector("span.bog, .y6 span")
                    sender_el = await row.query_selector(".yW span, .zF")

                    subject_text = await subject_el.inner_text() if subject_el else ""
                    sender_text = await sender_el.get_attribute("email") or "" if sender_el else ""

                    if subject_text in seen_subjects:
                        continue

                    if sender_domain and sender_domain.lower() not in sender_text.lower():
                        continue

                    # Click to open email
                    await row.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(1.5)

                    body = await page.inner_text("body")
                    otp = _extract_otp_from_text(body)

                    if otp:
                        logger.info(f"OTP found via browser Gmail: {otp}")
                        await page.close()
                        return otp

                    seen_subjects.add(subject_text)
                    await page.go_back()
                    await asyncio.sleep(1)

                await asyncio.sleep(poll_interval)

            logger.warning("OTP not found in Gmail browser reader within timeout")
            return None
        except Exception as e:
            logger.error(f"Browser OTP reader error: {e}")
            return None
        finally:
            try:
                await page.close()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────────────────────
#  Unified OTP Reader (tries IMAP first, then browser)
# ──────────────────────────────────────────────────────────────────────────────

class GmailOTPReader:
    """
    Unified OTP reader. Auto-selects IMAP (fast) or browser fallback.
    Usage:
        reader = GmailOTPReader(gmail_address, app_password, browser_context)
        otp = await reader.wait_for_otp(sender_domain="upwork.com")
    """

    def __init__(
        self,
        gmail_address: str,
        app_password: str = "",
        browser_context=None,
    ):
        self.gmail_address = gmail_address
        self.app_password = app_password
        self.browser_context = browser_context

    async def wait_for_otp(
        self,
        sender_domain: Optional[str] = None,
        subject_contains: Optional[str] = None,
        timeout_seconds: int = 90,
    ) -> Optional[str]:
        """Try IMAP first (non-blocking thread), then browser fallback."""
        if self.app_password:
            logger.info("Using IMAP method for OTP extraction")
            reader = IMAPOTPReader(self.gmail_address, self.app_password)
            loop = asyncio.get_event_loop()
            otp = await loop.run_in_executor(
                None,
                lambda: reader.wait_for_otp(
                    sender_domain=sender_domain,
                    subject_contains=subject_contains,
                    timeout_seconds=timeout_seconds,
                ),
            )
            if otp:
                return otp

        if self.browser_context:
            logger.info("Falling back to browser-based Gmail OTP reading")
            browser_reader = BrowserOTPReader(self.browser_context)
            return await browser_reader.wait_for_otp(
                sender_domain=sender_domain,
                timeout_seconds=timeout_seconds,
            )

        logger.error("No IMAP password and no browser context — cannot read OTP")
        return None


def _extract_otp_from_text(text: str) -> Optional[str]:
    """Standalone helper used by browser reader."""
    for pattern in _OTP_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
