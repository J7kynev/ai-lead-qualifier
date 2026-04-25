# 🎯 AI Lead Qualifier

Autonomous lead qualification system that researches, scores and prioritizes leads using GPT-4o — with a real-time dashboard and Telegram alerts.

---

## 🚀 What it does

This system receives a lead (company or contact), autonomously researches them on the web, analyzes the gathered information using GPT-4o, and assigns a qualification score from 1 to 100 based on configurable business criteria. High-priority leads trigger instant Telegram notifications. All data is stored and visualized in a real-time dashboard.

---

## ⚙️ Core Features

- **Autonomous web research** — investigates each lead before scoring
- **AI-powered scoring** — GPT-4o assigns a 1–100 score with detailed justification
- **Configurable criteria** — define your own qualification rules via YAML
- **Real-time dashboard** — visualize leads by score, industry, and status
- **Telegram alerts** — instant notifications for high-priority leads
- **SQLite persistence** — full lead history with timestamps

---

## 🛠️ Tech Stack

- **Python 3.11**
- **OpenAI API** — GPT-4o for analysis and scoring
- **Streamlit** — web interface and dashboard
- **DuckDuckGo Search** — autonomous lead research
- **SQLite** — local database
- **Plotly** — interactive charts
- **Telegram Bot API** — real-time notifications

---

## 📁 Project Structure

    ai-lead-qualifier/
    ├── app.py                  # Main web interface (Streamlit)
    ├── dashboard.py            # Metrics and analytics dashboard
    ├── main.py                 # CLI entry point
    ├── src/
    │   ├── researcher.py       # Autonomous web research engine
    │   ├── qualifier.py        # AI scoring engine
    │   ├── database.py         # SQLite management
    │   ├── notifier.py         # Telegram notifications
    │   └── models.py           # Data models
    ├── config/
    │   └── criteria.yaml       # Configurable scoring criteria
    ├── data/
    │   └── leads.db            # SQLite database
    ├── .env.example
    ├── requirements.txt
    └── README.md

---

## 📌 Status

🔧 In development — first release coming soon.

---

## 👤 Author

**J7kynev** — AI Automation & Business Systems
