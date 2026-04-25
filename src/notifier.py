# notifier.py
# Telegram notification engine for the AI Lead Qualifier system
# Sends structured alerts for high-priority leads with full details
# Supports single alerts, batch summaries and daily digest reports

import os
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
REQUEST_TIMEOUT = 10


def _get_headers() -> Dict[str, str]:
    return {"Content-Type": "application/json"}


def _send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Core Telegram message dispatcher.
    Sends a message to the configured chat ID.

    Args:
        text:       The message body. Supports HTML formatting.
        parse_mode: Telegram parse mode — HTML or Markdown.

    Returns:
        True if the message was delivered successfully, False otherwise.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured — skipping notification.")
        return False

    url = f"{TELEGRAM_API_BASE}{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        logger.info("Telegram notification sent successfully.")
        return True
    except requests.exceptions.Timeout:
        logger.error("Telegram request timed out.")
        return False
    except requests.exceptions.HTTPError as e:
        logger.error(f"Telegram HTTP error: {e.response.status_code} — {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram request failed: {e}")
        return False


def send_lead_alert(
    name: str,
    company: str,
    industry: str,
    score: int,
    justification: str,
    recommendation: str,
    confidence: str,
    website: Optional[str] = None,
    email: Optional[str] = None,
    lead_id: Optional[int] = None,
) -> bool:
    """
    Send a structured Telegram alert for a high-priority qualified lead.

    Formats a rich HTML message with all relevant lead details including
    score, justification, recommended next action and contact information.

    Args:
        name:           Contact name.
        company:        Company name.
        industry:       Industry vertical.
        score:          Qualification score (1-100).
        justification:  AI-generated score explanation.
        recommendation: Recommended next action.
        confidence:     AI confidence level (HIGH/MEDIUM/LOW).
        website:        Optional company website.
        email:          Optional contact email.
        lead_id:        Optional database ID for reference.

    Returns:
        True if notification was delivered, False otherwise.
    """
    priority_emoji = "🔴" if score >= 75 else "🟡" if score >= 45 else "🟢"
    confidence_emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(confidence, "⚠️")
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")

    message = (
        f"🚨 <b>HIGH PRIORITY LEAD DETECTED</b>\n"
        f"{'─' * 30}\n\n"
        f"👤 <b>{name}</b>\n"
        f"🏢 {company} | {industry}\n"
        f"{f'🌐 {website}' if website else ''}\n"
        f"{f'📧 {email}' if email else ''}\n\n"
        f"{'─' * 30}\n"
        f"{priority_emoji} <b>Score: {score}/100</b>\n"
        f"{confidence_emoji} Confidence: {confidence}\n\n"
        f"📋 <b>Justification:</b>\n{justification}\n\n"
        f"⚡ <b>Recommended Action:</b>\n{recommendation}\n"
        f"{'─' * 30}\n"
        f"🕐 Qualified: {timestamp}\n"
        f"{f'🔗 Lead ID: #{lead_id}' if lead_id else ''}"
    )

    return _send_message(message.strip())


def send_batch_summary(leads: List[Dict[str, Any]]) -> bool:
    """
    Send a summary notification after processing a batch of leads.
    Includes total counts broken down by priority and top 3 leads by score.

    Args:
        leads: List of qualified lead dictionaries from the database.

    Returns:
        True if notification was delivered, False otherwise.
    """
    if not leads:
        return False

    high = [l for l in leads if l.get("priority") == "HIGH"]
    medium = [l for l in leads if l.get("priority") == "MEDIUM"]
    low = [l for l in leads if l.get("priority") == "LOW"]
    top_3 = sorted(leads, key=lambda x: x.get("score") or 0, reverse=True)[:3]
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")

    top_lines = "\n".join([
        f"  {i+1}. {l['name']} @ {l['company']} — {l.get('score', 'N/A')}/100"
        for i, l in enumerate(top_3)
    ])

    message = (
        f"📊 <b>BATCH QUALIFICATION COMPLETE</b>\n"
        f"{'─' * 30}\n\n"
        f"📦 Total leads processed: <b>{len(leads)}</b>\n\n"
        f"🔴 High priority:   <b>{len(high)}</b>\n"
        f"🟡 Medium priority: <b>{len(medium)}</b>\n"
        f"🟢 Low priority:    <b>{len(low)}</b>\n\n"
        f"🏆 <b>Top Leads:</b>\n{top_lines}\n\n"
        f"{'─' * 30}\n"
        f"🕐 Completed: {timestamp}"
    )

    return _send_message(message)


def send_daily_digest(analytics: Dict[str, Any]) -> bool:
    """
    Send a daily analytics digest summarizing the full lead pipeline.
    Intended to be triggered by a scheduled job or manual dashboard action.

    Args:
        analytics: Analytics dictionary returned by database.get_analytics().

    Returns:
        True if notification was delivered, False otherwise.
    """
    timestamp = datetime.now().strftime("%B %d, %Y")
    top_leads = analytics.get("top_leads", [])

    top_lines = "\n".join([
        f"  • {l['name']} @ {l['company']} — {l.get('score', 'N/A')}/100 [{l.get('priority', '?')}]"
        for l in top_leads
    ]) or "  No scored leads yet."

    industry_lines = "\n".join([
        f"  • {r['industry']}: {r['count']} leads (avg score: {round(r['avg_score'] or 0, 1)})"
        for r in analytics.get("by_industry", [])[:5]
    ]) or "  No industry data yet."

    message = (
        f"📈 <b>DAILY LEAD DIGEST — {timestamp}</b>\n"
        f"{'─' * 30}\n\n"
        f"📦 Total leads:      <b>{analytics.get('total_leads', 0)}</b>\n"
        f"⭐ Average score:    <b>{analytics.get('avg_score', 0)}/100</b>\n"
        f"⏳ Pending:          <b>{analytics.get('pending', 0)}</b>\n"
        f"📩 Notified:         <b>{analytics.get('notified', 0)}</b>\n\n"
        f"🎯 <b>Priority Breakdown:</b>\n"
        f"  🔴 High:   {analytics.get('high_priority', 0)}\n"
        f"  🟡 Medium: {analytics.get('medium_priority', 0)}\n"
        f"  🟢 Low:    {analytics.get('low_priority', 0)}\n\n"
        f"🏆 <b>Top 5 Leads:</b>\n{top_lines}\n\n"
        f"🏭 <b>Top Industries:</b>\n{industry_lines}\n"
        f"{'─' * 30}\n"
        f"🤖 AI Lead Qualifier — Automated Report"
    )

    return _send_message(message)


def test_connection() -> bool:
    """
    Send a test message to verify Telegram credentials are configured correctly.
    Useful for initial setup validation.

    Returns:
        True if the test message was delivered, False otherwise.
    """
    message = (
        f"✅ <b>AI Lead Qualifier — Connection Test</b>\n\n"
        f"Telegram notifications are configured correctly.\n"
        f"🕐 {datetime.now().strftime('%B %d, %Y at %H:%M')}"
    )
    result = _send_message(message)
    if result:
        logger.info("Telegram connection test passed.")
    else:
        logger.error("Telegram connection test failed.")
    return result