# main.py
# CLI entry point for the AI Lead Qualifier system
# Supports single lead qualification, batch processing from CSV,
# database export, Telegram testing and analytics reporting

import argparse
import csv
import logging
import sys
from typing import Optional

from dotenv import load_dotenv

from src.models import Lead
from src.database import init_db, save_lead, update_lead_score, mark_notified, get_analytics, export_to_csv, export_to_json
from src.researcher import research_lead
from src.qualifier import qualify_lead, load_criteria
from src.notifier import send_lead_alert, send_batch_summary, send_daily_digest, test_connection

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_single_lead(
    name: str,
    company: str,
    industry: str,
    website: Optional[str] = None,
    email: Optional[str] = None,
    notes: Optional[str] = None,
) -> Lead:
    """
    Run the full qualification pipeline for a single lead.
    Performs research, scores the lead with GPT-4o, saves to database,
    and sends a Telegram alert if the lead meets the priority threshold.

    Args:
        name:     Contact full name.
        company:  Company name.
        industry: Industry vertical.
        website:  Optional company website URL.
        email:    Optional contact email address.
        notes:    Optional additional context notes.

    Returns:
        The fully qualified Lead instance with score and priority assigned.
    """
    logger.info(f"Starting qualification pipeline for: {name} @ {company}")
    init_db()

    lead = Lead(
        name=name,
        company=company,
        industry=industry,
        website=website,
        email=email,
        notes=notes,
        status="researching",
    )

    lead_id = save_lead(lead)
    lead.id = lead_id
    logger.info(f"Lead saved to database with ID: #{lead_id}")

    # Step 1 — Autonomous web research
    logger.info("Step 1/3 — Researching lead online...")
    research_data = research_lead(
        company=company,
        industry=industry,
        website=website,
        name=name,
    )
    research_summary = research_data["summary"]
    confidence_estimate = Lead.confidence_from_research(research_summary)

    # Step 2 — AI qualification scoring
    logger.info("Step 2/3 — Scoring lead with GPT-4o...")
    criteria = load_criteria()
    score, justification, recommendation, confidence = qualify_lead(
        lead=lead,
        research=research_summary,
        criteria=criteria,
    )

    priority = Lead.priority_from_score(score)
    update_lead_score(
        lead_id=lead_id,
        score=score,
        justification=justification,
        recommendation=recommendation,
        research=research_summary,
        priority=priority,
        confidence=confidence,
        status="qualified",
    )

    lead.score = score
    lead.justification = justification
    lead.recommendation = recommendation
    lead.research_summary = research_summary
    lead.priority = priority
    lead.confidence = confidence

    # Step 3 — Telegram notification for high priority leads
    logger.info("Step 3/3 — Checking notification threshold...")
    if score >= 75:
        logger.info(f"High priority lead detected (score: {score}) — sending Telegram alert...")
        notified = send_lead_alert(
            name=name,
            company=company,
            industry=industry,
            score=score,
            justification=justification,
            recommendation=recommendation,
            confidence=confidence,
            website=website,
            email=email,
            lead_id=lead_id,
        )
        if notified:
            mark_notified(lead_id)

    # Summary output
    print("\n" + "═" * 50)
    print(f"  QUALIFICATION COMPLETE — Lead #{lead_id}")
    print("═" * 50)
    print(f"  Name:           {name}")
    print(f"  Company:        {company}")
    print(f"  Score:          {score}/100")
    print(f"  Priority:       {priority}")
    print(f"  Confidence:     {confidence}")
    print(f"  Justification:  {justification}")
    print(f"  Next Action:    {recommendation}")
    print("═" * 50 + "\n")

    return lead


def process_batch_from_csv(filepath: str) -> list:
    """
    Process multiple leads from a CSV file in sequence.
    Expected CSV columns: name, company, industry, website, email, notes.
    Sends a batch summary notification via Telegram upon completion.

    Args:
        filepath: Path to the input CSV file.

    Returns:
        List of qualified Lead instances.
    """
    logger.info(f"Starting batch processing from: {filepath}")
    qualified_leads = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
        sys.exit(1)

    logger.info(f"Found {len(rows)} leads to process.")

    for i, row in enumerate(rows, start=1):
        logger.info(f"Processing lead {i}/{len(rows)}: {row.get('name')} @ {row.get('company')}")
        try:
            lead = process_single_lead(
                name=row.get("name", "Unknown"),
                company=row.get("company", "Unknown"),
                industry=row.get("industry", "Unknown"),
                website=row.get("website"),
                email=row.get("email"),
                notes=row.get("notes"),
            )
            qualified_leads.append(lead)
        except Exception as e:
            logger.error(f"Failed to process lead {row.get('name')}: {e}")
            continue

    logger.info(f"Batch complete — {len(qualified_leads)}/{len(rows)} leads qualified.")

    leads_as_dicts = [
        {"name": l.name, "company": l.company, "score": l.score, "priority": l.priority}
        for l in qualified_leads
    ]
    send_batch_summary(leads_as_dicts)

    return qualified_leads


def print_analytics():
    """Fetch and print a formatted analytics summary to the console."""
    init_db()
    stats = get_analytics()
    print("\n" + "═" * 50)
    print("  LEAD PIPELINE ANALYTICS")
    print("═" * 50)
    print(f"  Total leads:      {stats['total_leads']}")
    print(f"  Average score:    {stats['avg_score']}/100")
    print(f"  High priority:    {stats['high_priority']}")
    print(f"  Medium priority:  {stats['medium_priority']}")
    print(f"  Low priority:     {stats['low_priority']}")
    print(f"  Pending:          {stats['pending']}")
    print(f"  Notified:         {stats['notified']}")
    print("\n  Top Leads:")
    for lead in stats.get("top_leads", []):
        print(f"    • {lead['name']} @ {lead['company']} — {lead['score']}/100 [{lead['priority']}]")
    print("\n  By Industry:")
    for row in stats.get("by_industry", []):
        print(f"    • {row['industry']}: {row['count']} leads (avg: {row['avg_score']})")
    print("═" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="AI Lead Qualifier — Autonomous lead research and scoring system"
    )
    subparsers = parser.add_subparsers(dest="command")

    # qualify command
    qualify_parser = subparsers.add_parser("qualify", help="Qualify a single lead")
    qualify_parser.add_argument("--name", required=True)
    qualify_parser.add_argument("--company", required=True)
    qualify_parser.add_argument("--industry", required=True)
    qualify_parser.add_argument("--website", default=None)
    qualify_parser.add_argument("--email", default=None)
    qualify_parser.add_argument("--notes", default=None)

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Process leads from a CSV file")
    batch_parser.add_argument("--file", required=True, help="Path to CSV file")

    # analytics command
    subparsers.add_parser("analytics", help="Print pipeline analytics")

    # export command
    export_parser = subparsers.add_parser("export", help="Export leads to CSV or JSON")
    export_parser.add_argument("--format", choices=["csv", "json"], default="csv")

    # digest command
    subparsers.add_parser("digest", help="Send daily digest to Telegram")

    # test command
    subparsers.add_parser("test-telegram", help="Test Telegram connection")

    args = parser.parse_args()

    if args.command == "qualify":
        process_single_lead(
            name=args.name,
            company=args.company,
            industry=args.industry,
            website=args.website,
            email=args.email,
            notes=args.notes,
        )

    elif args.command == "batch":
        process_batch_from_csv(args.file)

    elif args.command == "analytics":
        print_analytics()

    elif args.command == "export":
        init_db()
        if args.format == "csv":
            path = export_to_csv()
        else:
            path = export_to_json()
        print(f"Exported to: {path}")

    elif args.command == "digest":
        init_db()
        stats = get_analytics()
        send_daily_digest(stats)

    elif args.command == "test-telegram":
        test_connection()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()