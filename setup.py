import os

os.makedirs("src", exist_ok=True)

models = """from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Lead:
    name: str
    company: str
    industry: str
    website: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    score: Optional[int] = None
    score_justification: Optional[str] = None
    recommendation: Optional[str] = None
    research_summary: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[str] = None
    id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
    telegram_notified: bool = False
    follow_up_date: Optional[str] = None

    def to_dict(self):
        return {
            "name": self.name, "company": self.company, "industry": self.industry,
            "website": self.website, "email": self.email, "linkedin": self.linkedin,
            "phone": self.phone, "notes": self.notes, "score": self.score,
            "score_justification": self.score_justification,
            "recommendation": self.recommendation,
            "research_summary": self.research_summary,
            "priority": self.priority, "confidence": self.confidence,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "status": self.status,
            "telegram_notified": int(self.telegram_notified),
            "follow_up_date": self.follow_up_date,
        }

    @staticmethod
    def priority_from_score(score):
        if score >= 75: return "HIGH"
        elif score >= 45: return "MEDIUM"
        return "LOW"

    @staticmethod
    def confidence_from_research(research):
        wc = len(research.split())
        if wc >= 300: return "HIGH"
        elif wc >= 100: return "MEDIUM"
        return "LOW"

    def is_high_priority(self):
        return self.priority == "HIGH" and not self.telegram_notified
"""

database = """import sqlite3
import csv
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from src.models import Lead

DB_PATH = "data/leads.db"

def get_connection():
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    con = get_connection()
    con.executescript(\"\"\"
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, company TEXT NOT NULL, industry TEXT NOT NULL,
            website TEXT, email TEXT, linkedin TEXT, phone TEXT, notes TEXT,
            score INTEGER, score_justification TEXT, recommendation TEXT,
            research_summary TEXT, priority TEXT, confidence TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            telegram_notified INTEGER NOT NULL DEFAULT 0,
            follow_up_date TEXT
        );
        CREATE TABLE IF NOT EXISTS qualification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES leads(id),
            event TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry);
    \"\"\")
    con.commit()
    con.close()

def save_lead(lead):
    con = get_connection()
    cur = con.execute(\"\"\"
        INSERT INTO leads (name,company,industry,website,email,linkedin,phone,
            notes,score,score_justification,recommendation,research_summary,
            priority,confidence,created_at,updated_at,status,telegram_notified,follow_up_date)
        VALUES (:name,:company,:industry,:website,:email,:linkedin,:phone,
            :notes,:score,:score_justification,:recommendation,:research_summary,
            :priority,:confidence,:created_at,:updated_at,:status,:telegram_notified,:follow_up_date)
    \"\"\", lead.to_dict())
    lead_id = cur.lastrowid
    _log_event(con, lead_id, "CREATED", f"Lead created: {lead.status}")
    con.commit()
    con.close()
    return lead_id

def update_lead_score(lead_id, score, justification, recommendation, research, priority, confidence, status="qualified"):
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute(\"\"\"UPDATE leads SET score=?,score_justification=?,recommendation=?,
        research_summary=?,priority=?,confidence=?,status=?,updated_at=? WHERE id=?
    \"\"\", (score,justification,recommendation,research,priority,confidence,status,now,lead_id))
    _log_event(con, lead_id, "SCORED", f"Score:{score} Priority:{priority}")
    con.commit()
    con.close()

def mark_notified(lead_id):
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute("UPDATE leads SET telegram_notified=1,status='notified',updated_at=? WHERE id=?", (now,lead_id))
    _log_event(con, lead_id, "NOTIFIED", "Telegram alert sent")
    con.commit()
    con.close()

def archive_lead(lead_id):
    now = datetime.now().isoformat()
    con = get_connection()
    con.execute("UPDATE leads SET status='archived',updated_at=? WHERE id=?", (now,lead_id))
    _log_event(con, lead_id, "ARCHIVED", "Lead archived")
    con.commit()
    con.close()

def get_all_leads(status_filter=None, priority_filter=None, industry_filter=None, min_score=0, exclude_archived=True):
    query = "SELECT * FROM leads WHERE score >= ?"
    params = [min_score]
    if status_filter: query += " AND status=?"; params.append(status_filter)
    if priority_filter: query += " AND priority=?"; params.append(priority_filter)
    if industry_filter: query += " AND industry=?"; params.append(industry_filter)
    if exclude_archived: query += " AND status!='archived'"
    query += " ORDER BY score DESC"
    con = get_connection()
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_lead_by_id(lead_id):
    con = get_connection()
    row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    con.close()
    return dict(row) if row else None

def get_lead_log(lead_id):
    con = get_connection()
    rows = con.execute("SELECT * FROM qualification_log WHERE lead_id=? ORDER BY created_at ASC", (lead_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_analytics():
    con = get_connection()
    total = con.execute("SELECT COUNT(*) FROM leads WHERE status!='archived'").fetchone()[0]
    avg_score = con.execute("SELECT AVG(score) FROM leads WHERE score IS NOT NULL AND status!='archived'").fetchone()[0]
    high = con.execute("SELECT COUNT(*) FROM leads WHERE priority='HIGH'").fetchone()[0]
    medium = con.execute("SELECT COUNT(*) FROM leads WHERE priority='MEDIUM'").fetchone()[0]
    low = con.execute("SELECT COUNT(*) FROM leads WHERE priority='LOW'").fetchone()[0]
    pending = con.execute("SELECT COUNT(*) FROM leads WHERE status='pending'").fetchone()[0]
    notified = con.execute("SELECT COUNT(*) FROM leads WHERE telegram_notified=1").fetchone()[0]
    industry_rows = con.execute("SELECT industry,COUNT(*) as count,AVG(score) as avg_score FROM leads WHERE status!='archived' GROUP BY industry ORDER BY count DESC").fetchall()
    top_leads = con.execute("SELECT name,company,score,priority FROM leads WHERE score IS NOT NULL AND status!='archived' ORDER BY score DESC LIMIT 5").fetchall()
    con.close()
    return {
        "total_leads": total, "avg_score": round(avg_score,1) if avg_score else 0,
        "high_priority": high, "medium_priority": medium, "low_priority": low,
        "pending": pending, "notified": notified,
        "by_industry": [dict(r) for r in industry_rows],
        "top_leads": [dict(r) for r in top_leads],
    }

def export_to_csv(filepath="data/leads_export.csv"):
    leads = get_all_leads(exclude_archived=True)
    if not leads: return None
    with open(filepath,"w",newline="",encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader(); writer.writerows(leads)
    return filepath

def export_to_json(filepath="data/leads_export.json"):
    leads = get_all_leads(exclude_archived=True)
    with open(filepath,"w",encoding="utf-8") as f:
        json.dump(leads,f,indent=2,ensure_ascii=False)
    return filepath

def _log_event(con, lead_id, event, detail=""):
    con.execute("INSERT INTO qualification_log (lead_id,event,detail,created_at) VALUES (?,?,?,?)",
        (lead_id,event,detail,datetime.now().isoformat()))
"""

researcher = """import time
import logging
from typing import Optional, Dict, List
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESEARCH_QUERIES = [
    "{company} {industry} company overview",
    "{company} funding revenue employees size",
    "{company} clients customers case studies",
    "{company} news announcements 2024 2025",
    "{company} hiring jobs growth expansion",
]
MAX_RESULTS_PER_QUERY = 3
DELAY_BETWEEN_QUERIES = 1.2
MAX_SUMMARY_LENGTH = 4000

def research_lead(company, industry, website=None, name=None):
    logger.info(f"Researching: {company}")
    all_findings = []
    query_results = {}
    for qt in RESEARCH_QUERIES:
        query = qt.format(company=company, industry=industry)
        try:
            findings = _search(query)
            if findings:
                all_findings.append(findings)
                query_results[qt] = findings
        except Exception as e:
            logger.warning(f"Query failed: {e}")
        time.sleep(DELAY_BETWEEN_QUERIES)
    if name:
        try:
            cf = _search(f"{name} {company} LinkedIn founder CEO")
            if cf: all_findings.append(cf)
        except: pass
    raw = "\\n\\n".join(all_findings)
    summary = _build_summary(company, industry, raw, website)
    return {"summary": summary, "raw_findings": raw[:MAX_SUMMARY_LENGTH], "sources": [], "query_results": query_results}

def _search(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY))
        if not results: return ""
        snippets = []
        for r in results:
            body = r.get("body","")
            if body: snippets.append(f"[{r.get('title','')}] {body}")
        return " | ".join(snippets)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

def _build_summary(company, industry, raw_text, website):
    if not raw_text.strip():
        return f"No information found for {company} in {industry}."
    from datetime import date
    header = f"=== RESEARCH: {company.upper()} ===\\nIndustry: {industry}\\nWebsite: {website or 'N/A'}\\nDate: {date.today().strftime('%B %d, %Y')}\\n{'='*40}\\n\\n"
    return header + raw_text[:MAX_SUMMARY_LENGTH]

def quick_company_check(company):
    try:
        with DDGS() as ddgs:
            return len(list(ddgs.text(company, max_results=1))) > 0
    except: return False
"""

qualifier = """import os
import re
import logging
import yaml
from typing import Tuple, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv
from src.models import Lead

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CRITERIA_PATH = "config/criteria.yaml"

def load_criteria():
    try:
        with open(CRITERIA_PATH,"r",encoding="utf-8") as f:
            return yaml.safe_load(f)
    except: return _default_criteria()

def qualify_lead(lead, research, criteria=None):
    if criteria is None: criteria = load_criteria()
    criteria_text = _format_criteria(criteria)
    prompt = f\"\"\"You are qualifying a B2B sales lead.

LEAD: {lead.name} @ {lead.company} | Industry: {lead.industry}
Website: {lead.website or 'N/A'} | Email: {lead.email or 'N/A'}
Notes: {lead.notes or 'None'}

RESEARCH:
{research}

CRITERIA:
{criteria_text}

Respond ONLY in this format:
SCORE: [1-100]
JUSTIFICATION: [2-3 sentences]
RECOMMENDATION: [one next action]
CONFIDENCE: [HIGH/MEDIUM/LOW]
\"\"\"
    logger.info(f"Qualifying: {lead.name} @ {lead.company}")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role":"system","content":"You are a senior B2B sales strategist. Be precise and direct."},
                  {"role":"user","content":prompt}],
        temperature=0.2, max_tokens=600,
    )
    return _parse_response(response.choices[0].message.content.strip())

def _parse_response(content):
    def extract(pattern, default):
        m = re.search(pattern, content, re.DOTALL|re.IGNORECASE)
        return m.group(1).strip() if m else default
    score = extract(r"SCORE:\\s*(\\d+)", "50")
    justification = extract(r"JUSTIFICATION:\\s*(.+?)(?=\\nRECOMMENDATION:|$)", "Score assigned based on available data.")
    recommendation = extract(r"RECOMMENDATION:\\s*(.+?)(?=\\nCONFIDENCE:|$)", "Schedule a discovery call.")
    confidence = extract(r"CONFIDENCE:\\s*(HIGH|MEDIUM|LOW)", "MEDIUM")
    try: score_int = max(1, min(100, int(score)))
    except: score_int = 50
    return score_int, justification, recommendation, confidence

def _format_criteria(criteria):
    lines = []
    for cat, data in criteria.get("scoring_criteria",{}).items():
        if isinstance(data, dict):
            lines.append(f"- {cat.replace('_',' ').title()} (weight: {data.get('weight','?')}%)")
    t = criteria.get("thresholds",{})
    if t:
        lines.append(f"HIGH >= {t.get('high_priority',75)} | MEDIUM >= {t.get('medium_priority',45)}")
    return "\\n".join(lines)

def _default_criteria():
    return {"scoring_criteria":{"budget":{"weight":30},"industry_fit":{"weight":25},"intent":{"weight":25},"maturity":{"weight":20}},"thresholds":{"high_priority":75,"medium_priority":45}}
"""

notifier = """import os
import logging
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

def _send_message(text, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured.")
        return False
    try:
        r = requests.post(f"{TELEGRAM_API_BASE}{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":parse_mode,"disable_web_page_preview":True},
            timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def send_lead_alert(name, company, industry, score, justification, recommendation, confidence, website=None, email=None, lead_id=None):
    emoji = "🔴" if score >= 75 else "🟡" if score >= 45 else "🟢"
    msg = (f"🚨 <b>HIGH PRIORITY LEAD</b>\\n{'─'*30}\\n"
           f"👤 <b>{name}</b>\\n🏢 {company} | {industry}\\n"
           f"{f'🌐 {website}' if website else ''}\\n{f'📧 {email}' if email else ''}\\n\\n"
           f"{emoji} <b>Score: {score}/100</b> | Confidence: {confidence}\\n\\n"
           f"📋 <b>Why:</b> {justification}\\n\\n"
           f"⚡ <b>Next:</b> {recommendation}\\n{'─'*30}\\n"
           f"🕐 {datetime.now().strftime('%B %d, %Y at %H:%M')}"
           f"{f'  |  Lead #{lead_id}' if lead_id else ''}")
    return _send_message(msg.strip())

def send_batch_summary(leads):
    if not leads: return False
    high = sum(1 for l in leads if l.get("priority")=="HIGH")
    medium = sum(1 for l in leads if l.get("priority")=="MEDIUM")
    low = sum(1 for l in leads if l.get("priority")=="LOW")
    top = sorted(leads, key=lambda x: x.get("score") or 0, reverse=True)[:3]
    top_lines = "\\n".join([f"  {i+1}. {l['name']} @ {l['company']} — {l.get('score','N/A')}/100" for i,l in enumerate(top)])
    msg = (f"📊 <b>BATCH COMPLETE</b>\\n{'─'*30}\\n"
           f"Total: <b>{len(leads)}</b>\\n🔴 High: <b>{high}</b>  🟡 Medium: <b>{medium}</b>  🟢 Low: <b>{low}</b>\\n\\n"
           f"🏆 <b>Top Leads:</b>\\n{top_lines}\\n{'─'*30}\\n"
           f"🕐 {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    return _send_message(msg)

def send_daily_digest(analytics):
    top = "\\n".join([f"  • {l['name']} @ {l['company']} — {l.get('score','N/A')}/100" for l in analytics.get("top_leads",[])])
    msg = (f"📈 <b>DAILY DIGEST — {datetime.now().strftime('%B %d, %Y')}</b>\\n{'─'*30}\\n"
           f"Total: <b>{analytics.get('total_leads',0)}</b>  |  Avg: <b>{analytics.get('avg_score',0)}/100</b>\\n"
           f"🔴 {analytics.get('high_priority',0)}  🟡 {analytics.get('medium_priority',0)}  🟢 {analytics.get('low_priority',0)}\\n\\n"
           f"🏆 <b>Top Leads:</b>\\n{top or 'None yet'}\\n{'─'*30}\\n🤖 AI Lead Qualifier")
    return _send_message(msg)

def test_connection():
    return _send_message(f"✅ <b>AI Lead Qualifier — Connected</b>\\n🕐 {datetime.now().strftime('%B %d, %Y at %H:%M')}")
"""

files = {
    "src/__init__.py": "",
    "src/models.py": models,
    "src/database.py": database,
    "src/researcher.py": researcher,
    "src/qualifier.py": qualifier,
    "src/notifier.py": notifier,
}

for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    size = os.path.getsize(path)
    print(f"✅ {path} ({size} bytes)")

print("\n✅ All src files written successfully.")