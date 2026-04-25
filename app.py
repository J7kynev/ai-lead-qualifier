# app.py
# Main Streamlit web interface for the AI Lead Qualifier system
# Provides a full-featured UI for lead entry, qualification,
# pipeline management and real-time dashboard visualization

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Optional

from src.models import Lead
from src.database import (
    init_db, save_lead, update_lead_score, mark_notified,
    get_all_leads, get_lead_by_id, get_lead_log,
    get_analytics, export_to_csv, export_to_json, archive_lead
)
from src.researcher import research_lead
from src.qualifier import qualify_lead, load_criteria
from src.notifier import send_lead_alert, send_daily_digest, test_connection

# ─────────────────────────────────────────
# PAGE CONFIGURATION
# ─────────────────────────────────────────
st.set_page_config(
    page_title="AI Lead Qualifier",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on startup
init_db()

# ─────────────────────────────────────────
# CUSTOM STYLES
# ─────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        border-left: 4px solid #6366f1;
        margin-bottom: 10px;
    }
    .high-priority { border-left-color: #ef4444; }
    .medium-priority { border-left-color: #f59e0b; }
    .low-priority { border-left-color: #22c55e; }
    .score-badge {
        font-size: 2rem;
        font-weight: bold;
        color: #6366f1;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/96/target.png", width=60)
st.sidebar.title("AI Lead Qualifier")
st.sidebar.markdown("*Autonomous lead research & scoring*")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    ["🎯 Qualify Lead", "📦 Batch Import", "📊 Dashboard", "📋 Pipeline", "⚙️ Settings"],
    label_visibility="collapsed"
)

st.sidebar.divider()
st.sidebar.markdown("**Quick Stats**")
analytics = get_analytics()
st.sidebar.metric("Total Leads", analytics["total_leads"])
st.sidebar.metric("Avg Score", f"{analytics['avg_score']}/100")
st.sidebar.metric("High Priority", analytics["high_priority"])


# ─────────────────────────────────────────
# PAGE: QUALIFY LEAD
# ─────────────────────────────────────────
if page == "🎯 Qualify Lead":
    st.title("🎯 Qualify a New Lead")
    st.markdown("Enter lead information below. The system will autonomously research the company and score the lead using GPT-4o.")
    st.divider()

    with st.form("qualify_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Contact Name *", placeholder="John Smith")
            company = st.text_input("Company *", placeholder="Acme Corp")
            industry = st.selectbox("Industry *", [
                "SaaS", "E-commerce", "Digital Marketing", "Consulting",
                "Fintech", "Healthcare Tech", "Real Estate Tech",
                "Education Tech", "Logistics", "Other"
            ])
        with col2:
            website = st.text_input("Website", placeholder="https://acmecorp.com")
            email = st.text_input("Email", placeholder="john@acmecorp.com")
            linkedin = st.text_input("LinkedIn", placeholder="linkedin.com/in/johnsmith")

        notes = st.text_area(
            "Additional Notes",
            placeholder="Any context about this lead — how you met, their pain points, budget signals...",
            height=100
        )

        enable_research = st.checkbox("Enable autonomous web research", value=True)
        submitted = st.form_submit_button("🚀 Qualify Lead", type="primary", use_container_width=True)

    if submitted:
        if not name or not company:
            st.error("Contact name and company are required.")
        else:
            lead = Lead(
                name=name, company=company, industry=industry,
                website=website or None, email=email or None,
                linkedin=linkedin or None, notes=notes or None,
                status="researching"
            )
            lead_id = save_lead(lead)
            lead.id = lead_id

            # Research phase
            research_summary = ""
            if enable_research:
                with st.status("🔍 Researching company online...", expanded=True) as status:
                    st.write(f"Searching for information about {company}...")
                    research_data = research_lead(
                        company=company, industry=industry,
                        website=website or None, name=name
                    )
                    research_summary = research_data["summary"]
                    st.write(f"✅ Research complete — {len(research_summary.split())} words gathered.")
                    status.update(label="Research complete", state="complete")

            # Qualification phase
            with st.status("🤖 Scoring lead with GPT-4o...", expanded=True) as status:
                st.write("Analyzing research findings against scoring criteria...")
                try:
                    criteria = load_criteria()
                    score, justification, recommendation, confidence = qualify_lead(
                        lead=lead,
                        research=research_summary or f"{company} in {industry}",
                        criteria=criteria,
                    )
                    priority = Lead.priority_from_score(score)
                    update_lead_score(
                        lead_id=lead_id, score=score,
                        justification=justification, recommendation=recommendation,
                        research=research_summary, priority=priority,
                        confidence=confidence, status="qualified"
                    )
                    status.update(label="Qualification complete", state="complete")

                    # Results display
                    st.divider()
                    st.subheader("📊 Qualification Results")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Score", f"{score}/100")
                    col2.metric("Priority", priority)
                    col3.metric("Confidence", confidence)
                    col4.metric("Lead ID", f"#{lead_id}")

                    priority_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
                    st.markdown(f"### {priority_color} {priority} PRIORITY LEAD")

                    with st.expander("📋 Justification", expanded=True):
                        st.write(justification)
                    with st.expander("⚡ Recommended Action", expanded=True):
                        st.write(recommendation)
                    if research_summary:
                        with st.expander("🔍 Research Summary"):
                            st.write(research_summary[:1500] + "..." if len(research_summary) > 1500 else research_summary)

                    # Telegram notification
                    if score >= 75:
                        notified = send_lead_alert(
                            name=name, company=company, industry=industry,
                            score=score, justification=justification,
                            recommendation=recommendation, confidence=confidence,
                            website=website or None, email=email or None,
                            lead_id=lead_id,
                        )
                        if notified:
                            mark_notified(lead_id)
                            st.success("✅ Telegram alert sent to your team.")

                except Exception as e:
                    st.error(f"Qualification failed: {str(e)}")
                    st.info("Ensure your OpenAI API key has available credits.")


# ─────────────────────────────────────────
# PAGE: BATCH IMPORT
# ─────────────────────────────────────────
elif page == "📦 Batch Import":
    st.title("📦 Batch Lead Import")
    st.markdown("Upload a CSV file to qualify multiple leads at once. The system will process each lead sequentially.")
    st.divider()

    st.info("**Required CSV columns:** name, company, industry | **Optional:** website, email, notes")

    sample_data = pd.DataFrame([
        {"name": "Jane Doe", "company": "TechFlow", "industry": "SaaS", "website": "techflow.io", "email": "jane@techflow.io", "notes": "Met at SaaStr 2024"},
        {"name": "Carlos Ruiz", "company": "ShopNow", "industry": "E-commerce", "website": "shopnow.com", "email": "carlos@shopnow.com", "notes": "Inbound inquiry"},
    ])
    with st.expander("📄 Download sample CSV template"):
        st.dataframe(sample_data)
        csv_sample = sample_data.to_csv(index=False)
        st.download_button("⬇️ Download Template", csv_sample, "leads_template.csv", "text/csv")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])

    if uploaded:
        df = pd.read_csv(uploaded)
        st.success(f"✅ {len(df)} leads detected.")
        st.dataframe(df, use_container_width=True)

        if st.button("🚀 Start Batch Qualification", type="primary"):
            progress = st.progress(0)
            results = []
            for i, row in df.iterrows():
                st.write(f"Processing {i+1}/{len(df)}: {row.get('name')} @ {row.get('company')}")
                try:
                    lead = Lead(
                        name=str(row.get("name", "")),
                        company=str(row.get("company", "")),
                        industry=str(row.get("industry", "Other")),
                        website=str(row.get("website", "")) or None,
                        email=str(row.get("email", "")) or None,
                        notes=str(row.get("notes", "")) or None,
                        status="researching"
                    )
                    lead_id = save_lead(lead)
                    lead.id = lead_id
                    research_data = research_lead(company=lead.company, industry=lead.industry)
                    score, justification, recommendation, confidence = qualify_lead(
                        lead=lead, research=research_data["summary"], criteria=load_criteria()
                    )
                    priority = Lead.priority_from_score(score)
                    update_lead_score(lead_id, score, justification, recommendation,
                                      research_data["summary"], priority, confidence)
                    results.append({"name": lead.name, "company": lead.company,
                                    "score": score, "priority": priority})
                except Exception as e:
                    st.warning(f"Failed: {row.get('name')} — {e}")
                progress.progress((i + 1) / len(df))

            st.success(f"✅ Batch complete — {len(results)} leads qualified.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)


# ─────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────
elif page == "📊 Dashboard":
    st.title("📊 Lead Intelligence Dashboard")
    st.markdown("Real-time analytics across your entire lead pipeline.")
    st.divider()

    analytics = get_analytics()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Leads", analytics["total_leads"])
    col2.metric("Avg Score", f"{analytics['avg_score']}/100")
    col3.metric("🔴 High", analytics["high_priority"])
    col4.metric("🟡 Medium", analytics["medium_priority"])
    col5.metric("🟢 Low", analytics["low_priority"])

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Priority Distribution")
        priority_data = {
            "Priority": ["High", "Medium", "Low"],
            "Count": [analytics["high_priority"], analytics["medium_priority"], analytics["low_priority"]]
        }
        fig = px.pie(
            pd.DataFrame(priority_data), values="Count", names="Priority",
            color_discrete_map={"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"},
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Leads by Industry")
        if analytics["by_industry"]:
            industry_df = pd.DataFrame(analytics["by_industry"])
            fig = px.bar(
                industry_df, x="industry", y="count",
                color="avg_score", color_continuous_scale="Viridis",
                labels={"count": "Leads", "avg_score": "Avg Score"}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No industry data yet.")

    st.subheader("🏆 Top Leads")
    if analytics["top_leads"]:
        top_df = pd.DataFrame(analytics["top_leads"])
        st.dataframe(top_df, use_container_width=True)
    else:
        st.info("No scored leads yet.")

    if st.button("📩 Send Daily Digest to Telegram"):
        sent = send_daily_digest(analytics)
        st.success("Digest sent.") if sent else st.error("Failed — check Telegram credentials.")


# ─────────────────────────────────────────
# PAGE: PIPELINE
# ─────────────────────────────────────────
elif page == "📋 Pipeline":
    st.title("📋 Lead Pipeline")
    st.markdown("View, filter and manage all leads in your qualification pipeline.")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        priority_filter = st.selectbox("Filter by Priority", ["All", "HIGH", "MEDIUM", "LOW"])
    with col2:
        status_filter = st.selectbox("Filter by Status", ["All", "pending", "researching", "qualified", "notified"])
    with col3:
        min_score = st.slider("Minimum Score", 0, 100, 0)

    leads = get_all_leads(
        priority_filter=priority_filter if priority_filter != "All" else None,
        status_filter=status_filter if status_filter != "All" else None,
        min_score=min_score,
    )

    if leads:
        df = pd.DataFrame(leads)
        display_cols = ["id", "name", "company", "industry", "score", "priority", "confidence", "status", "created_at"]
        existing_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[existing_cols], use_container_width=True, height=400)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            csv_path = export_to_csv()
            if csv_path:
                with open(csv_path, "rb") as f:
                    st.download_button("⬇️ Export CSV", f, "leads_export.csv", "text/csv")
        with col2:
            json_path = export_to_json()
            if json_path:
                with open(json_path, "rb") as f:
                    st.download_button("⬇️ Export JSON", f, "leads_export.json", "application/json")

        st.divider()
        st.subheader("Lead Detail View")
        lead_id = st.number_input("Enter Lead ID to inspect", min_value=1, step=1)
        if st.button("Load Lead"):
            lead = get_lead_by_id(int(lead_id))
            if lead:
                st.json(lead)
                log = get_lead_log(int(lead_id))
                if log:
                    st.subheader("Event Log")
                    st.dataframe(pd.DataFrame(log), use_container_width=True)
                if st.button("Archive this lead"):
                    archive_lead(int(lead_id))
                    st.success("Lead archived.")
            else:
                st.error("Lead not found.")
    else:
        st.info("No leads found matching the selected filters.")


# ─────────────────────────────────────────
# PAGE: SETTINGS
# ─────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ Settings & Configuration")
    st.divider()

    st.subheader("🔌 Telegram Connection")
    st.markdown("Test your Telegram bot connection to ensure notifications are working correctly.")
    if st.button("Send Test Telegram Message"):
        result = test_connection()
        st.success("✅ Telegram connected successfully.") if result else st.error("❌ Connection failed — check your credentials in .env")

    st.divider()
    st.subheader("🗄️ Database")
    st.markdown("Export or reset your lead database.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export all leads to CSV"):
            path = export_to_csv()
            st.success(f"Exported to: {path}")
    with col2:
        if st.button("Export all leads to JSON"):
            path = export_to_json()
            st.success(f"Exported to: {path}")

    st.divider()
    st.subheader("📋 Scoring Criteria")
    st.markdown("Current criteria loaded from `config/criteria.yaml`.")
    criteria = load_criteria()
    st.json(criteria)