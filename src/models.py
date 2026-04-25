# models.py
# Core data models for the AI Lead Qualifier system
# Defines the Lead dataclass with full qualification lifecycle support

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Lead:
    """
    Represents a business lead throughout the full qualification lifecycle.
    Tracks contact information, research findings, AI scoring, and pipeline status.
    """

    # --- Contact Information ---
    name: str
    company: str
    industry: str
    website: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

    # --- AI Qualification Results ---
    score: Optional[int] = None
    score_justification: Optional[str] = None
    recommendation: Optional[str] = None
    research_summary: Optional[str] = None
    priority: Optional[str] = None         # HIGH / MEDIUM / LOW
    confidence: Optional[str] = None       # HIGH / MEDIUM / LOW (AI confidence in score)

    # --- Pipeline Tracking ---
    id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"                # pending / researching / qualified / notified / archived
    telegram_notified: bool = False
    follow_up_date: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the lead to a flat dictionary for database storage."""
        return {
            "name": self.name,
            "company": self.company,
            "industry": self.industry,
            "website": self.website,
            "email": self.email,
            "linkedin": self.linkedin,
            "phone": self.phone,
            "notes": self.notes,
            "score": self.score,
            "score_justification": self.score_justification,
            "recommendation": self.recommendation,
            "research_summary": self.research_summary,
            "priority": self.priority,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "telegram_notified": int(self.telegram_notified),
            "follow_up_date": self.follow_up_date,
        }

    @staticmethod
    def priority_from_score(score: int) -> str:
        """Map a numeric score to a priority label."""
        if score >= 75:
            return "HIGH"
        elif score >= 45:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def confidence_from_research(research: str) -> str:
        """Estimate AI confidence based on research depth."""
        word_count = len(research.split())
        if word_count >= 300:
            return "HIGH"
        elif word_count >= 100:
            return "MEDIUM"
        return "LOW"

    def is_high_priority(self) -> bool:
        """Return True if this lead qualifies for immediate Telegram notification."""
        return self.priority == "HIGH" and not self.telegram_notified

    def summary_line(self) -> str:
        """Return a single-line summary for display in dashboards and logs."""
        score_str = f"{self.score}/100" if self.score else "Not scored"
        return f"[{self.priority or 'PENDING'}] {self.name} @ {self.company} — {score_str}"