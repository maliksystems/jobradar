# jobradar
# 🎯 JobRadar

> Multi-board job search automation with NLP filtering, contact finding, and AI email generation.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat-square&logo=telegram&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-API-cc785c?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-00e87a?style=flat-square)

---

## The Problem

Manually checking 6 job boards every day, copying links into a spreadsheet, missing roles, no way to track what I'd applied to. Time-consuming and inefficient.

## What I Built

An automated job search pipeline that runs every 60 minutes and handles everything from discovery to personalised outreach — without manual input.

---

## Key Results

| Metric | Result |
|--------|--------|
| Jobs found in first week | **565** |
| Job boards monitored | **6** |
| Direct HR emails found | **248** |
| Boards covered | Reed, Indeed, CV-Library, Bayt, GulfJobs, LinkedIn |

---

## How It Works

```
Every 60 mins
    ↓
Scrape 6 job boards simultaneously
    ↓
NLP relevance filter (removes drivers, nurses, unrelated roles)
    ↓
Deduplication (seen_ids.json — no repeat alerts)
    ↓
Hunter.io API → find HR contact emails
    ↓
Telegram alert with job summary + contact details
    ↓
Claude API → generate personalised cold email per role
    ↓
HTML dashboard → full pipeline tracking
```

---

## Features

- **Multi-board scraping** — Reed, Indeed UK/International, CV-Library, Bayt, GulfJobs
- **NLP relevance scoring** — 40+ profile keywords, 20+ hard reject terms
- **Deduplication** — persistent memory across restarts via JSON
- **Contact finding** — Hunter.io integration with confidence scoring
- **AI email generation** — Claude API writes tailored cold emails per job
- **Telegram alerts** — instant notifications with full job details
- **Local dashboard** — HTML tracker with pipeline stages, search, filters
- **Sponsorship detection** — flags UK Skilled Worker visa mentions

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Scraping | BeautifulSoup, feedparser, requests |
| Scheduling | schedule library |
| Contact finding | Hunter.io API |
| AI generation | Anthropic Claude API |
| Alerts | Telegram Bot API |
| Storage | JSON (jobs_db.json, seen_ids.json) |
| Dashboard | Vanilla HTML/CSS/JS |

---

## Screenshots

> *![JobRadar Dashboard](screenshot.png)*

---

## Built By

**Malik Ibrahim** — Technical PM & Automation Engineer  
[malikibrahim.dev](https://malikibrahim.dev) · [LinkedIn](https://linkedin.com/in/YOUR_LINKEDIN) · [GitHub](https://github.com/maliksystems)

> Built and used in production during my own job search. The best proof of concept is using your own tool.
