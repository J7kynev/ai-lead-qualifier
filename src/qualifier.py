import os
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
    prompt = f"""You are qualifying a B2B sales lead.

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
"""
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
    score = extract(r"SCORE:\s*(\d+)", "50")
    justification = extract(r"JUSTIFICATION:\s*(.+?)(?=\nRECOMMENDATION:|$)", "Score assigned based on available data.")
    recommendation = extract(r"RECOMMENDATION:\s*(.+?)(?=\nCONFIDENCE:|$)", "Schedule a discovery call.")
    confidence = extract(r"CONFIDENCE:\s*(HIGH|MEDIUM|LOW)", "MEDIUM")
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
    return "\n".join(lines)

def _default_criteria():
    return {"scoring_criteria":{"budget":{"weight":30},"industry_fit":{"weight":25},"intent":{"weight":25},"maturity":{"weight":20}},"thresholds":{"high_priority":75,"medium_priority":45}}
