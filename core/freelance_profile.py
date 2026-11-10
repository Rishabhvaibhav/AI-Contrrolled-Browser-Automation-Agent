"""
core/freelance_profile.py — Builds a structured freelance profile from candidate_profile.json.
Used by FreelanceAgent to fill signup forms, bios, and gig/proposal descriptions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any

from core.config import CANDIDATE_PROFILE_JSON, RESUME_PATH, FREELANCE_HOURLY_RATE_USD


@dataclass
class FreelanceProfile:
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    city: str
    country: str
    headline: str
    summary: str
    skills: List[str]
    target_roles: List[str]
    certifications: List[str]
    notable_clients: List[str]
    linkedin_url: str
    github_url: str
    portfolio_url: str
    resume_path: Path
    hourly_rate_usd: int
    hourly_rate_range_usd: List[int]
    availability: str
    years_of_experience: str

    # Pre-computed fields
    _bio_long: str = field(default="", init=False, repr=False)
    _bio_short: str = field(default="", init=False, repr=False)

    def __post_init__(self):
        self._bio_long = self._build_bio(long=True)
        self._bio_short = self._build_bio(long=False)

    # ── Factory ──────────────────────────────────────────────────

    @classmethod
    def from_json(cls, path: Path = CANDIDATE_PROFILE_JSON) -> "FreelanceProfile":
        """Load from candidate_profile.json. Falls back to hardcoded defaults."""
        if path.exists():
            data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {}

        return cls(
            first_name=data.get("first_name", "Rishabh"),
            last_name=data.get("last_name", "Vaibhav"),
            full_name=data.get("full_name", "Rishabh Vaibhav"),
            email=data.get("email", "rishabhvaibhav7@gmail.com"),
            phone=data.get("phone", "+91 7061864929"),
            city=data.get("city", "Bengaluru"),
            country=data.get("country", "India"),
            headline=data.get(
                "headline",
                "Senior AI & Data Engineer | RAG Pipelines | LLM Integration | Python | FastAPI",
            ),
            summary=data.get(
                "summary",
                "Data Engineer and Gen AI Developer with 4 years of experience building "
                "production-grade ETL pipelines, RAG/LLM workflows, and browser automation systems.",
            ),
            skills=data.get("skills", [
                "Python", "PySpark", "SQL", "FastAPI", "LangChain", "Playwright",
                "Azure", "AWS", "ETL Pipelines", "RAG", "LLM Integration",
            ]),
            target_roles=data.get("target_roles", [
                "Data Engineer", "Gen AI Developer", "Python Developer",
            ]),
            certifications=data.get("certifications", ["Microsoft Azure Developer Associate (AZ-204)"]),
            notable_clients=data.get("notable_clients", ["Google", "AuditBoard", "Bank of America", "Airbus"]),
            linkedin_url=data.get("linkedin_url", "https://www.linkedin.com/in/rishabh-vaibhav"),
            github_url=data.get("github_url", "https://github.com/rishabhvaibhav"),
            portfolio_url=data.get("portfolio_url", "https://rishabhvaibhav.dev"),
            resume_path=RESUME_PATH,
            hourly_rate_usd=data.get("hourly_rate_usd", FREELANCE_HOURLY_RATE_USD),
            hourly_rate_range_usd=data.get("hourly_rate_range_usd", [35, 75]),
            availability=data.get("availability", "Immediate"),
            years_of_experience=str(data.get("years_of_experience", "4")),
        )

    # ── Public Accessors ─────────────────────────────────────────

    def get_bio(self, long: bool = True) -> str:
        return self._bio_long if long else self._bio_short

    def get_skills_string(self, max_skills: int = 10) -> str:
        return ", ".join(self.skills[:max_skills])

    def get_hourly_rate_string(self) -> str:
        lo, hi = self.hourly_rate_range_usd
        return f"${lo}–${hi}/hr"

    def get_headline(self) -> str:
        return self.headline

    def as_form_dict(self) -> Dict[str, str]:
        """Flat key-value dict ready to fill form fields."""
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "city": self.city,
            "country": self.country,
            "title": self.headline,
            "headline": self.headline,
            "bio": self._bio_short,
            "overview": self._bio_long,
            "skills": self.get_skills_string(),
            "hourly_rate": str(self.hourly_rate_usd),
            "rate": str(self.hourly_rate_usd),
            "availability": self.availability,
            "linkedin": self.linkedin_url,
            "github": self.github_url,
            "portfolio": self.portfolio_url,
            "website": self.portfolio_url,
        }

    # ── Internal builders ────────────────────────────────────────

    def _build_bio(self, long: bool = True) -> str:
        skills_str = ", ".join(self.skills[:8])
        clients_str = ", ".join(self.notable_clients)
        certs_str = ", ".join(self.certifications)
        short = (
            f"Senior AI & Data Engineer with {self.years_of_experience}+ years building "
            f"ETL pipelines, RAG/LLM workflows, and browser automation. "
            f"Skills: {skills_str}. "
            f"Azure certified. Immediate availability."
        )
        if not long:
            return short

        return (
            f"{short}\n\n"
            f"I specialize in:\n"
            f"- Large-scale ETL pipeline design and optimization (PySpark, Airflow, ClickHouse)\n"
            f"- RAG/LLM system integration (LangChain, LangGraph, OpenAI, Gemini)\n"
            f"- Browser automation and web scraping at scale (Playwright, Selenium)\n"
            f"- Multi-agent autonomous systems\n"
            f"- Cloud-native data infrastructure (Azure, AWS, GCP)\n\n"
            f"Notable clients: {clients_str}.\n"
            f"Certifications: {certs_str}.\n\n"
            f"Hourly rate: {self.get_hourly_rate_string()}. "
            f"Based in {self.city}, {self.country}. "
            f"Available for remote contract and freelance work worldwide."
        )
