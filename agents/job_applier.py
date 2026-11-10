import os
import re
import csv
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from core.browser_engine import BrowserEngine
from core.dom_indexer import DOMIndexer
from core.human_emulator import HumanEmulator
from core.llm_client import LLMClient
from agents.base_agent import BaseBrowserAgent

logger = logging.getLogger("ShadowBrowser.JobApplier")

DEFAULT_CANDIDATE_PROFILE = {
    "first_name": "Rishabh",
    "last_name": "Vaibhav",
    "full_name": "Rishabh Vaibhav",
    "email": "rishabh.vaibhav.dev@gmail.com",
    "phone": "+91 9876543210",
    "city": "Bengaluru",
    "country": "India",
    "current_company": "Cloud Systems & AI Labs",
    "current_title": "Senior AI & Full Stack Engineer",
    "years_of_experience": "5",
    "notice_period_days": "30",
    "current_ctc": "24,00,000 INR",
    "expected_ctc": "35,00,000 INR",
    "linkedin_url": "https://www.linkedin.com/in/rishabh-vaibhav",
    "naukri_profile_url": "https://www.naukri.com/mnjuser/profile",
    "github_url": "https://github.com/rishabh-vaibhav",
    "portfolio_url": "https://rishabhvaibhav.dev",
    "resume_path": "resume.pdf",
    "work_authorization": "Yes",
    "sponsorship_required": "No",
    "gender": "Decline to identify",
    "summary": "Full Stack and Autonomous Systems Engineer with 5+ years of experience specializing in distributed backends, AI agents, and browser automation."
}

class JobApplier(BaseBrowserAgent):
    """
    Automated Job Application Engine that processes a CSV of job postings,
    navigates with persistent Chrome session (LinkedIn, Naukri, Indeed),
    fills multi-step forms, uploads resumes, and logs application status.
    """

    def __init__(
        self,
        engine: BrowserEngine,
        llm: Optional[LLMClient] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        safe_mode: bool = False,
        output_csv: str = "applied_jobs_report.csv",
    ):
        super().__init__(engine, llm)
        self.candidate = candidate_profile or DEFAULT_CANDIDATE_PROFILE
        self.safe_mode = safe_mode
        self.output_csv = output_csv
        self.results: List[Dict[str, Any]] = []

    def load_candidate_profile(self, profile_path: str):
        """Loads candidate details from JSON file."""
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                self.candidate.update(json.load(f))
                logger.info(f"Loaded candidate profile from {profile_path}")

    @staticmethod
    def read_jobs_csv(csv_path: str) -> List[Dict[str, str]]:
        """
        Reads CSV file containing job listings and returns list of records.
        Automatically identifies URL column.
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        df = pd.read_csv(csv_path)
        # Find URL column with exact or prioritized matching
        url_col = None
        # Priority 1: exact matches
        for col in df.columns:
            cleaned = str(col).lower().strip()
            if cleaned in ("url", "link", "job_url", "job_link", "apply_link", "apply_url", "href"):
                url_col = col
                break
        
        # Priority 2: contains url or link
        if not url_col:
            for col in df.columns:
                cleaned = str(col).lower().strip()
                if "url" in cleaned or "link" in cleaned or "href" in cleaned:
                    url_col = col
                    break

        if not url_col:
            # Fall back to first column
            url_col = df.columns[0]

        records = []
        for idx, row in df.iterrows():
            item = dict(row)
            item["target_url"] = str(row[url_col]).strip()
            item["row_id"] = idx + 1
            records.append(item)

        return records

    async def check_login_status(self, domain: str) -> bool:
        """Checks if current browser session has active login for target domain."""
        cookies = await self.engine.context.cookies()
        domain_cookies = [c for c in cookies if domain in c.get("domain", "")]
        
        if "linkedin.com" in domain:
            return any(c.get("name") in ("li_at", "li_theme") for c in domain_cookies)
        elif "naukri.com" in domain:
            return any("naukri" in c.get("name", "").lower() for c in domain_cookies)
        return len(domain_cookies) > 2

    async def apply_single_job(self, job_item: Dict[str, str]) -> Dict[str, Any]:
        """
        Navigates to a single job link and attempts multi-step application.
        """
        url = job_item["target_url"]
        job_title = job_item.get("title", job_item.get("job_title", "Unknown Role"))
        company = job_item.get("company", job_item.get("company_name", "Unknown Company"))

        record = {
            "row_id": job_item.get("row_id"),
            "url": url,
            "title": job_title,
            "company": company,
            "timestamp": datetime.now().isoformat(),
            "status": "FAILED",
            "message": "",
        }

        logger.info(f"\n=======================================================")
        logger.info(f"💼 Processing Job [{job_item.get('row_id')}]: {job_title} at {company}")
        logger.info(f"🔗 URL: {url}")
        logger.info(f"=======================================================")

        try:
            # 1. Navigate to Job URL
            nav_success = await self.engine.navigate(url)
            if not nav_success:
                record["message"] = "Failed to load job URL"
                return record

            await asyncio.sleep(2.0)

            # 2. Check for already applied status
            page_text = (await DOMIndexer.get_page_markdown(self.page)).lower()
            if any(term in page_text for term in ("already applied", "applied on", "application submitted", "you have applied")):
                record["status"] = "ALREADY_APPLIED"
                record["message"] = "Job already applied previously."
                logger.info(f"⏩ {record['message']}")
                return record

            # 3. Find Apply / Easy Apply button
            apply_clicked = await self._find_and_click_apply_button()
            if not apply_clicked:
                record["status"] = "NO_EASY_APPLY"
                record["message"] = "Could not locate 'Easy Apply' or direct 'Apply' button on page."
                logger.warning(record["message"])
                return record

            await asyncio.sleep(2.0)

            # 4. Fill Application Steps (up to 8 modal steps)
            for step_num in range(1, 9):
                logger.info(f"Handling application form step {step_num}...")
                
                # Check for upload input
                await self._handle_file_uploads()

                # Fill standard inputs
                await self._fill_form_fields()

                # Handle dropdowns & radios
                await self._handle_dropdowns_and_radios()

                # Check if this is the final Review / Submit step
                is_submit_step = await self._is_submit_step()

                if is_submit_step:
                    if self.safe_mode:
                        record["status"] = "REVIEW_REQUIRED"
                        record["message"] = "Application filled; paused for manual review before submit (Safe Mode)."
                        logger.info(f"🛡️ {record['message']}")
                        return record
                    else:
                        submit_success = await self._click_submit_button()
                        if submit_success:
                            record["status"] = "APPLIED"
                            record["message"] = "Application submitted successfully!"
                            logger.info(f"✅ {record['message']}")
                            await asyncio.sleep(2.0)
                            return record

                # If not submit step, click Next / Continue
                advanced = await self._click_next_button()
                if not advanced:
                    # If cannot advance further, check if submitted or done
                    await asyncio.sleep(1.5)
                    break

            record["status"] = "FORM_PROCESSED"
            record["message"] = "Processed form steps."

        except Exception as e:
            logger.error(f"Error applying to job {url}: {e}")
            record["status"] = "ERROR"
            record["message"] = str(e)

        return record

    async def _find_and_click_apply_button(self) -> bool:
        """Searches for Easy Apply or standard Apply buttons."""
        selectors = [
            "button:has-text('Easy Apply')",
            "button:has-text('Quick Apply')",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "a:has-text('Easy Apply')",
            "a:has-text('Apply now')",
            "[aria-label*='Easy Apply']",
            "[aria-label*='Apply to']",
            "button.jobs-apply-button",
        ]
        for sel in selectors:
            loc = self.page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                box = await loc.bounding_box()
                if box:
                    await HumanEmulator.move_mouse(self.page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                await loc.click()
                logger.info(f"Clicked apply button matching: {sel}")
                return True
        return False

    async def _handle_file_uploads(self):
        """Attaches candidate resume PDF if a file input is present."""
        resume_path = self.candidate.get("resume_path", "")
        if not resume_path or not os.path.exists(resume_path):
            return

        file_inputs = self.page.locator("input[type=file]")
        count = await file_inputs.count()
        if count > 0:
            for i in range(count):
                inp = file_inputs.nth(i)
                try:
                    await inp.set_input_files(resume_path)
                    logger.info(f"Attached resume PDF from {resume_path}")
                    await asyncio.sleep(1.0)
                    break
                except Exception as e:
                    logger.warning(f"File upload attempt error: {e}")

    async def _fill_form_fields(self):
        """Intelligently matches form input fields with candidate profile data."""
        inputs = self.page.locator("input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), textarea")
        count = await inputs.count()

        for i in range(count):
            inp = inputs.nth(i)
            if not await inp.is_visible():
                continue

            # Skip if already has value
            current_val = await inp.input_value()
            if current_val and len(current_val.strip()) > 1:
                continue

            # Extract label, name, placeholder, aria-label
            name = (await inp.get_attribute("name") or "").lower()
            placeholder = (await inp.get_attribute("placeholder") or "").lower()
            aria = (await inp.get_attribute("aria-label") or "").lower()
            label_text = ""
            inp_id = await inp.get_attribute("id")
            if inp_id:
                lbl = self.page.locator(f"label[for='{inp_id}']").first
                if await lbl.count() > 0:
                    label_text = (await lbl.inner_text()).lower()

            combined = f"{name} {placeholder} {aria} {label_text}"

            # Match value from profile
            value_to_fill = None
            if any(k in combined for k in ("phone", "mobile", "contact number")):
                value_to_fill = self.candidate.get("phone")
            elif any(k in combined for k in ("first name", "firstname", "given name")):
                value_to_fill = self.candidate.get("first_name")
            elif any(k in combined for k in ("last name", "lastname", "surname", "family name")):
                value_to_fill = self.candidate.get("last_name")
            elif any(k in combined for k in ("email", "mail")):
                value_to_fill = self.candidate.get("email")
            elif any(k in combined for k in ("city", "location", "address")):
                value_to_fill = self.candidate.get("city")
            elif any(k in combined for k in ("experience", "years of exp", "total experience")):
                value_to_fill = self.candidate.get("years_of_experience")
            elif any(k in combined for k in ("notice", "notice period")):
                value_to_fill = self.candidate.get("notice_period_days")
            elif any(k in combined for k in ("linkedin", "profile link")):
                value_to_fill = self.candidate.get("linkedin_url")
            elif any(k in combined for k in ("github", "repo")):
                value_to_fill = self.candidate.get("github_url")
            elif any(k in combined for k in ("current ctc", "current salary")):
                value_to_fill = self.candidate.get("current_ctc")
            elif any(k in combined for k in ("expected ctc", "expected salary")):
                value_to_fill = self.candidate.get("expected_ctc")

            if value_to_fill:
                await inp.click()
                await HumanEmulator.human_type(inp, str(value_to_fill))
                logger.info(f"Filled '{combined[:30]}' with '{value_to_fill}'")
                await asyncio.sleep(0.2)

    async def _handle_dropdowns_and_radios(self):
        """Answers standard screening radios and selects."""
        # Work authorization radios (Yes/No)
        yes_radios = self.page.locator("label:has-text('Yes'), input[value='Yes'], input[value='true']")
        count = await yes_radios.count()
        for i in range(count):
            r = yes_radios.nth(i)
            try:
                if await r.is_visible() and not await r.is_checked():
                    await r.click()
                    await asyncio.sleep(0.1)
            except Exception:
                pass

    async def _is_submit_step(self) -> bool:
        """Detects if current page is showing Submit or Review button."""
        submit_btn = self.page.locator(
            "button:has-text('Submit application'), button:has-text('Submit'), button[aria-label*='Submit application']"
        ).first
        return await submit_btn.count() > 0 and await submit_btn.is_visible()

    async def _click_submit_button(self) -> bool:
        """Clicks the final submit application button."""
        btn = self.page.locator(
            "button:has-text('Submit application'), button:has-text('Submit'), button[aria-label*='Submit application']"
        ).first
        if await btn.count() > 0 and await btn.is_visible():
            box = await btn.bounding_box()
            if box:
                await HumanEmulator.move_mouse(self.page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            await btn.click()
            logger.info("Clicked SUBMIT APPLICATION button!")
            return True
        return False

    async def _click_next_button(self) -> bool:
        """Clicks Next or Continue button to advance to next form step."""
        next_selectors = [
            "button:has-text('Next')",
            "button:has-text('Continue to next step')",
            "button:has-text('Review')",
            "button[aria-label*='Continue to next step']",
            "button[aria-label*='Review your application']",
        ]
        for sel in next_selectors:
            btn = self.page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                box = await btn.bounding_box()
                if box:
                    await HumanEmulator.move_mouse(self.page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                await btn.click()
                logger.info(f"Clicked form progression button: {sel}")
                await asyncio.sleep(1.5)
                return True
        return False

    async def run_batch_from_csv(self, csv_path: str, max_jobs: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Executes automated application pipeline over all jobs in the CSV file.
        """
        jobs = self.read_jobs_csv(csv_path)
        if max_jobs:
            jobs = jobs[:max_jobs]

        logger.info(f"Loaded {len(jobs)} jobs from {csv_path}. Starting batch...")

        for job in jobs:
            result = await self.apply_single_job(job)
            self.results.append(result)
            self._save_results_to_csv()
            # Realistic pause between applications
            await asyncio.sleep(3.0)

        logger.info(f"Batch processing completed for {len(jobs)} jobs!")
        return self.results

    def _save_results_to_csv(self):
        """Appends/updates execution results to CSV report file."""
        if not self.results:
            return
        df = pd.DataFrame(self.results)
        df.to_csv(self.output_csv, index=False, encoding="utf-8")
        logger.info(f"Saved results update to {self.output_csv}")
