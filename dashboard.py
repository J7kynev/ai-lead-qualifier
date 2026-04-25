# dashboard.py
# Advanced analytics and visualization module for the AI Lead Qualifier
# Provides reusable chart and metrics functions used by the Streamlit interface

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List


def render_score_distribution(leads: List[Dict[str, Any]]):
    """Render a histogram showing the distribution of lead scores."""
    if not leads:
        return None
    scores = [l["score"] for l in leads if l.get("score")]
    if not scores:
        return None
    fig = px.histogram(
        x=scores, nbins=10,
        labels={"x": "Score", "y": "Number of Leads"},
        color_discrete_sequence=["#6366f1"],
        title="Score Distribution"
    )
    fig.update_layout(bargap=0.1, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def render_priority_gauge(high: int, medium: int, low: int):
    """Render a gauge chart showing pipeline health based on priority ratios."""
    total = high + medium + low
    if total == 0:
        return None
    health_score = round((high * 100 + medium * 50) / total)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=health_score,
        title={"text": "Pipeline Health"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#6366f1"},
            "steps": [
                {"range": [0, 40], "color": "#ef4444"},
                {"range": [40, 70], "color": "#f59e0b"},
                {"range": [70, 100], "color": "#22c55e"},
            ],
        }
    ))
    fig.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)")
    return fig


def render_industry_breakdown(by_industry: List[Dict[str, Any]]):
    """Render a bar chart showing lead count and average score by industry."""
    if not by_industry:
        return None
    df = pd.DataFrame(by_industry)
    fig = px.bar(
        df, x="industry", y="count",
        color="avg_score", color_continuous_scale="Viridis",
        labels={"count": "Leads", "avg_score": "Avg Score", "industry": "Industry"},
        title="Leads by Industry"
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def render_score_over_time(leads: List[Dict[str, Any]]):
    """Render a line chart showing average score trend over time."""
    if not leads:
        return None
    df = pd.DataFrame(leads)
    if "created_at" not in df.columns or "score" not in df.columns:
        return None
    df = df[df["score"].notna()].copy()
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    trend = df.groupby("date")["score"].mean().reset_index()
    fig = px.line(
        trend, x="date", y="score",
        labels={"date": "Date", "score": "Avg Score"},
        color_discrete_sequence=["#6366f1"],
        title="Score Trend Over Time"
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def render_conversion_funnel(analytics: Dict[str, Any]):
    """Render a funnel chart showing lead pipeline stages."""
    stages = ["Total Leads", "Qualified", "High Priority", "Notified"]
    total = analytics.get("total_leads", 0)
    qualified = total - analytics.get("pending", 0)
    high = analytics.get("high_priority", 0)
    notified = analytics.get("notified", 0)
    values = [total, qualified, high, notified]
    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent initial",
        marker={"color": ["#6366f1", "#8b5cf6", "#f59e0b", "#22c55e"]}
    ))
    fig.update_layout(
        title="Lead Conversion Funnel",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def build_leads_dataframe(leads: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert raw lead dicts to a display-ready DataFrame with formatted columns."""
    if not leads:
        return pd.DataFrame()
    df = pd.DataFrame(leads)
    display_cols = ["id", "name", "company", "industry", "score", "priority", "confidence", "status", "created_at"]
    existing = [c for c in display_cols if c in df.columns]
    return df[existing]