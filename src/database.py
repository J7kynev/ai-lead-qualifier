# database.py
# Full database layer for the AI Lead Qualifier system
# Handles all SQLite operations with connection management,
# schema migrations, filtering, analytics and export capabilities

import sqlite3
import csv
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from src.models import Lead

DB_PATH = "data/leads.db"


def get_connection() -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    """
    Initialize the database schema.
    Creates all required tables and indexes if they don't exist.
    Safe to call multiple times — will not overwrite existing data.
    """
    con = get_connection()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            company             TEXT NOT NULL,
            industry            TEXT NOT NULL,
            website             TEXT,
            email               TEXT,
            linkedin            TEXT,
            phone               TEXT,
            notes               TEXT,
            score               INTEGER CHECK(score BETWEEN 1 AND 100),
            score_justification TEXT,
            recommendation      TEXT,
            research_summary    TEXT,
            priority            TEXT CHECK(priority IN ('HIGH', 'MEDIUM', 'LOW')),
            confidence          TEXT CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'pending'
                                CHECK(status IN ('pending','researching','qualified','notified','archived')),
            telegram_notified   INTEGER NOT NULL DEFAULT 0,
            follow_up_date      TEXT
        );

        CREATE TABLE IF NOT EXISTS qualification_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id     INTEGER NOT NULL REFERENCES leads(id),
            event       TEXT NOT NULL,
            detail      TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_leads_score    ON leads(score DESC);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_status   ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry);
        CREATE INDEX IF NOT EXISTS idx_log_lead_id    ON qualification_log(lead_id);
    """)
    con.commit()
    con.close()


def save_lead(lead: Lead) -> int:
    """
    Insert a new lead into the database.
    Returns the auto-generated lead ID.
    """
    con = get_connection()
    cur = con.execute("""
        INSERT INTO leads (
            name, company, industry, website, email, linkedin, phone,
            notes, score, score_justification, recommendation,
            research_summary, priority, confidence,
            created_at, updated_at, status, telegram_notified, follow_up_date
        ) VALUES (
            :name, :company, :industry, :website, :email, :linkedin, :phone,
            :notes, :score, :score_justification, :recommendation,
            :research_summary, :priority, :confidence,
            :created_at, :updated_at, :status, :telegram_notified, :follow_up_date
        )
    """, lead.to_dict())
    lead_id = cur.lastrowid
    _log_event(con, lead_id, "CREATED", f"Lead created with status: {lead.status}")
    con.commit()
    con.close()
    return lead_id


def update_lead_score(
    lead_id: int,
    score: int,
    justification: str,
    recommendation: str,
    research: str,
    priority: str,
    confidence: str,
    status: str = "qualified"
):
    """
    Update a lead with AI qualification results.
    Logs the scoring event to the qualification_log table.
    """
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute("""
        UPDATE leads SET
            score = ?,
            score_justification = ?,
            recommendation = ?,
            research_summary = ?,
            priority = ?,
            confidence = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (score, justification, recommendation, research, priority, confidence, status, now, lead_id))
    _log_event(con, lead_id, "SCORED", f"Score: {score}/100 | Priority: {priority} | Confidence: {confidence}")
    con.commit()
    con.close()


def mark_notified(lead_id: int):
    """Mark a lead as notified via Telegram and update its status."""
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute("""
        UPDATE leads SET telegram_notified = 1, status = 'notified', updated_at = ?
        WHERE id = ?
    """, (now, lead_id))
    _log_event(con, lead_id, "NOTIFIED", "Telegram alert sent successfully")
    con.commit()
    con.close()


def archive_lead(lead_id: int):
    """Move a lead to archived status."""
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute("UPDATE leads SET status = 'archived', updated_at = ? WHERE id = ?", (now, lead_id))
    _log_event(con, lead_id, "ARCHIVED", "Lead manually archived")
    con.commit()
    con.close()


def get_all_leads(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    industry_filter: Optional[str] = None,
    min_score: int = 0,
    exclude_archived: bool = True
) -> List[Dict[str, Any]]:
    """
    Retrieve leads with optional filtering.
    Returns a list of dictionaries ordered by score descending.
    """
    query = "SELECT * FROM leads WHERE score >= ?"
    params: list = [min_score]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if priority_filter:
        query += " AND priority = ?"
        params.append(priority_filter)
    if industry_filter:
        query += " AND industry = ?"
        params.append(industry_filter)
    if exclude_archived:
        query += " AND status != 'archived'"

    query += " ORDER BY score DESC"

    con = get_connection()
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single lead by its ID."""
    con = get_connection()
    row = con.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_lead_log(lead_id: int) -> List[Dict[str, Any]]:
    """Retrieve the full qualification event log for a specific lead."""
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM qualification_log WHERE lead_id = ? ORDER BY created_at ASC",
        (lead_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_analytics() -> Dict[str, Any]:
    """
    Return aggregate analytics for the dashboard.
    Includes counts, score distribution, industry breakdown and priority split.
    """
    con = get_connection()

    total = con.execute("SELECT COUNT(*) FROM leads WHERE status != 'archived'").fetchone()[0]
    avg_score = con.execute("SELECT AVG(score) FROM leads WHERE score IS NOT NULL AND status != 'archived'").fetchone()[0]
    high_count = con.execute("SELECT COUNT(*) FROM leads WHERE priority = 'HIGH'").fetchone()[0]
    medium_count = con.execute("SELECT COUNT(*) FROM leads WHERE priority = 'MEDIUM'").fetchone()[0]
    low_count = con.execute("SELECT COUNT(*) FROM leads WHERE priority = 'LOW'").fetchone()[0]
    pending_count = con.execute("SELECT COUNT(*) FROM leads WHERE status = 'pending'").fetchone()[0]
    notified_count = con.execute("SELECT COUNT(*) FROM leads WHERE telegram_notified = 1").fetchone()[0]

    industry_rows = con.execute("""
        SELECT industry, COUNT(*) as count, AVG(score) as avg_score
        FROM leads WHERE status != 'archived'
        GROUP BY industry ORDER BY count DESC
    """).fetchall()

    top_leads = con.execute("""
        SELECT name, company, score, priority
        FROM leads WHERE score IS NOT NULL AND status != 'archived'
        ORDER BY score DESC LIMIT 5
    """).fetchall()

    con.close()

    return {
        "total_leads": total,
        "avg_score": round(avg_score, 1) if avg_score else 0,
        "high_priority": high_count,
        "medium_priority": medium_count,
        "low_priority": low_count,
        "pending": pending_count,
        "notified": notified_count,
        "by_industry": [dict(r) for r in industry_rows],
        "top_leads": [dict(r) for r in top_leads],
    }


def export_to_csv(filepath: str = "data/leads_export.csv"):
    """Export all non-archived leads to a CSV file."""
    leads = get_all_leads(exclude_archived=True)
    if not leads:
        return None
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)
    return filepath


def export_to_json(filepath: str = "data/leads_export.json"):
    """Export all non-archived leads to a JSON file."""
    leads = get_all_leads(exclude_archived=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    return filepath


def _log_event(con: sqlite3.Connection, lead_id: int, event: str, detail: str = ""):
    """Internal helper to write an event to the qualification_log table."""
    con.execute(
        "INSERT INTO qualification_log (lead_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
        (lead_id, event, detail, datetime.now().isoformat())
    )