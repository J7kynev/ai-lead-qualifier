# researcher.py
# Autonomous web research engine for the AI Lead Qualifier system
# Investigates companies and contacts using DuckDuckGo search
# before passing findings to the AI qualification engine

import time
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


def research_lead(
    company: str,
    industry: str,
    website: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Perform autonomous multi-query web research on a lead.

    Executes several targeted searches about the company, aggregates
    the results into a structured research report, and returns both
    the full summary and individual findings per query angle.

    Args:
        company:  Company name to research.
        industry: Industry vertical for context-aware queries.
        website:  Optional website URL for additional context.
        name:     Optional contact name to include in research.

    Returns:
        A dictionary with keys 'summary', 'raw_findings', and 'sources'.
    """
    logger.info(f"Starting research for: {company} ({industry})")

    all_findings: List[str] = []
    sources: List[str] = []
    query_results: Dict[str, str] = {}

    for query_template in RESEARCH_QUERIES:
        query = query_template.format(company=company, industry=industry)
        logger.info(f"Searching: {query}")

        try:
            findings = _search(query)
            if findings:
                all_findings.append(findings)
                query_results[query_template.split("{company}")[1].strip()] = findings
        except Exception as e:
            logger.warning(f"Query failed: {query} — {e}")

        time.sleep(DELAY_BETWEEN_QUERIES)

    # Additional contact-specific search if name is provided
    if name:
        contact_query = f"{name} {company} LinkedIn founder CEO"
        try:
            contact_findings = _search(contact_query)
            if contact_findings:
                all_findings.append(contact_findings)
                query_results["contact_profile"] = contact_findings
        except Exception as e:
            logger.warning(f"Contact search failed: {e}")

    # Compile full summary
    raw_combined = "\n\n".join(all_findings)
    summary = _build_summary(company, industry, raw_combined, website)

    logger.info(f"Research complete for {company} — {len(summary.split())} words gathered")

    return {
        "summary": summary,
        "raw_findings": raw_combined[:MAX_SUMMARY_LENGTH],
        "sources": sources,
        "query_results": query_results,
    }


def _search(query: str) -> str:
    """
    Execute a single DuckDuckGo search and return aggregated text snippets.

    Args:
        query: The search query string.

    Returns:
        A concatenated string of result snippets, or empty string if no results.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY))

        if not results:
            return ""

        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            if body:
                snippets.append(f"[{title}] {body} (source: {href})")

        return " | ".join(snippets)

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return ""


def _build_summary(
    company: str,
    industry: str,
    raw_text: str,
    website: Optional[str],
) -> str:
    """
    Structure the raw research findings into a readable summary block
    that will be passed to the AI qualification engine.

    Args:
        company:  Company name.
        industry: Industry vertical.
        raw_text: Concatenated search snippets.
        website:  Optional company website.

    Returns:
        A structured string summary ready for GPT-4o analysis.
    """
    if not raw_text.strip():
        return f"No substantial information found online for {company} in the {industry} industry."

    truncated = raw_text[:MAX_SUMMARY_LENGTH]

    header = (
        f"=== RESEARCH REPORT: {company.upper()} ===\n"
        f"Industry: {industry}\n"
        f"Website: {website or 'Not provided'}\n"
        f"Research Date: {_today()}\n"
        f"{'=' * 40}\n\n"
    )

    return header + truncated


def _today() -> str:
    """Return today's date as a formatted string."""
    from datetime import date
    return date.today().strftime("%B %d, %Y")


def quick_company_check(company: str) -> bool:
    """
    Perform a lightweight check to verify the company exists online.
    Returns True if at least one search result is found, False otherwise.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(company, max_results=1))
        return len(results) > 0
    except Exception:
        return False