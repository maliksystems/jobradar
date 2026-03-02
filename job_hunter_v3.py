import os, json, time, hashlib, re, logging
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

# ── Load .env ──────────────────────────────────────────────────────────────
def load_env():
    for loc in [".env", Path(__file__).parent / ".env"]:
        p = Path(loc)
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return
load_env()
try:
    from dotenv import load_dotenv; load_dotenv(override=False)
except: pass

import requests, feedparser
from bs4 import BeautifulSoup

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
HUNTER_KEY     = os.environ.get("HUNTER_API_KEY", "")
REED_KEY       = os.environ.get("REED_API_KEY", "")

RESULTS_FILE   = Path("jobs_db.json")
SEEN_FILE      = Path("seen_ids.json")
DASHBOARD_FILE = Path("dashboard.html")

MAX_AGE_HOURS  = 72
CHECK_INTERVAL = 60   # minutes
YOUR_NAME      = "Malik Ibrahim"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# ─── YOUR PROFILE — used for relevance scoring ───────────────────────────────
PROFILE_KEYWORDS = [
    # Project & Programme Management
    "project manager", "project coordinator", "project management",
    "programme manager", "pmo", "technical project",
    "junior project", "assistant project manager", "project support",
    "project administrator", "project assistant", "project officer",
    "delivery coordinator", "delivery manager",

    # Entry-level / Graduate signals
    "entry level", "entry-level", "graduate scheme", "graduate programme",
    "graduate role", "graduate trainee", "no experience required",
    "training provided", "apprenticeship", "junior", "associate", "trainee",

    # Operations & Business
    "operations analyst", "operations coordinator", "operations support",
    "business analyst", "process improvement", "operations administrator",
    "office coordinator", "admin coordinator", "data analyst",
    "reporting analyst",

    # Tech / Automation
    "automation engineer", "automation analyst",
    "python developer", "python engineer",
    "technical analyst", "digital transformation", "systems analyst",
    "ai engineer", "ai analyst", "machine learning",
    "data engineer", "junior software engineer", "it analyst",
    "technical support", "it support", "service desk",
    "implementation analyst", "solutions analyst",

    # Engineering
    "electrical engineer", "electrical engineering", "graduate engineer",
    "engineering coordinator", "site engineer", "field engineer",
    "controls engineer", "commissioning engineer",

    # Transferable roles
    "scrum master", "agile", "product coordinator",
    "product analyst", "account coordinator", "client coordinator",
]

# Jobs containing ANY of these are instantly rejected
REJECT_KEYWORDS = [
    "driver", "delivery driver", "van driver", "hgv", "lorry",
    "nurse", "care worker", "carer", "healthcare assistant",
    "chef", "cook", "kitchen porter", "waiter", "waitress", "hospitality",
    "cleaner", "cleaning operative", "domestic assistant",
    "telesales", "cold calling", "door to door",
    "hairdresser", "beauty therapist",
    "teaching assistant", "nursery nurse",
    "warehouse operative", "picker packer", "forklift operator",
    "security guard", "security officer",
    "plumber", "gas engineer", "plasterer", "bricklayer",
    "finance director", "chief financial",
    "solicitor", "barrister", "conveyancer",
    "estate agent", "lettings agent",
    "mortgage broker", "insurance advisor",
    "social worker", "occupational therapist",
    "10 years experience", "15 years experience",
    "minimum 5 years", "minimum 7 years",
]

SPONSORSHIP_POSITIVE = [
    "visa sponsorship", "skilled worker", "tier 2", "sponsorship available",
    "we sponsor", "sponsorship provided", "certificate of sponsorship",
    "cos available", "visa support", "work permit", "relocation package",
    "sponsorship considered", "open to sponsorship",
]

SPONSORSHIP_NEGATIVE = [
    "no sponsorship", "no visa", "cannot sponsor", "unable to sponsor",
    "must have right to work", "must already have right to work",
    "uk citizen only", "british citizen only", "settled status only",
    "must be eligible to work in the uk without sponsorship",
    "no overseas applicants",
]

# ─── SEARCH PROFILES ─────────────────────────────────────────────────────────
SEARCH_PROFILES = [

    # ── PRIORITY 1: UK ENTRY-LEVEL (sponsored) ────────────────────────────────
    {
        "label": "🇬🇧 UK — Entry Level / Graduate (Sponsored)",
        "keywords": [
            "graduate project coordinator",
            "entry level project coordinator",
            "junior project coordinator",
            "graduate operations analyst",
            "entry level business analyst",
            "junior business analyst",
            "graduate trainee engineer",
            "entry level technical analyst",
            "associate project manager",
        ],
        "location": "United Kingdom",
        "sponsored_required": True,
        "boards": ["reed", "indeed_uk", "cv_library"],
    },
    {
        "label": "🇬🇧 UK — Junior PM & Coordinator (Sponsored)",
        "keywords": [
            "junior project manager",
            "project coordinator",
            "project support officer",
            "project administrator",
            "PMO analyst",
            "technical project coordinator",
            "assistant project manager",
        ],
        "location": "United Kingdom",
        "sponsored_required": True,
        "boards": ["reed", "indeed_uk", "cv_library"],
    },
    {
        "label": "🇬🇧 UK — Tech & IT Entry Level (Sponsored)",
        "keywords": [
            "junior technical analyst",
            "graduate technical analyst",
            "entry level automation",
            "junior python developer",
            "graduate software engineer",
            "IT analyst graduate",
            "junior data analyst",
            "digital transformation analyst",
            "implementation analyst",
            "junior systems analyst",
        ],
        "location": "United Kingdom",
        "sponsored_required": True,
        "boards": ["reed", "indeed_uk", "cv_library"],
    },
    {
        "label": "🇬🇧 UK — Graduate Engineering (Sponsored)",
        "keywords": [
            "graduate electrical engineer",
            "graduate engineer",
            "junior electrical engineer",
            "engineering graduate scheme",
            "graduate controls engineer",
        ],
        "location": "United Kingdom",
        "sponsored_required": True,
        "boards": ["reed", "indeed_uk"],
    },

    # ── PRIORITY 2: UAE (no sponsorship needed) ───────────────────────────────
    {
        "label": "🇦🇪 UAE — Entry / Junior PM & Engineering",
        "keywords": [
            "junior project coordinator",
            "project coordinator",
            "electrical engineer",
            "junior electrical engineer",
            "automation engineer",
            "graduate engineer",
            "PMO analyst",
            "operations coordinator",
        ],
        "location": "Dubai",
        "sponsored_required": False,
        "boards": ["indeed_international", "bayt", "gulfjobs"],
    },

    # ── PRIORITY 3: QATAR ─────────────────────────────────────────────────────
    {
        "label": "🇶🇦 Qatar — Junior Engineering / PM",
        "keywords": [
            "project coordinator",
            "electrical engineer",
            "junior engineer",
            "technical analyst",
            "operations coordinator",
        ],
        "location": "Qatar",
        "sponsored_required": False,
        "boards": ["indeed_international", "bayt"],
    },

    # ── PRIORITY 4: MALAYSIA ──────────────────────────────────────────────────
    {
        "label": "🇲🇾 Malaysia — Tech / Engineering / PM",
        "keywords": [
            "project coordinator",
            "junior engineer",
            "python developer",
            "technical analyst",
            "automation engineer",
        ],
        "location": "Malaysia",
        "sponsored_required": False,
        "boards": ["indeed_international"],
    },
]

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def jid(job):
    return hashlib.md5((job.get("title","").lower() + job.get("company","").lower() + job.get("url","")).encode()).hexdigest()[:12]

def load_seen():
    return set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()

def save_seen(s):
    SEEN_FILE.write_text(json.dumps(list(s)))

def load_db():
    if RESULTS_FILE.exists():
        try: return json.loads(RESULTS_FILE.read_text())
        except: pass
    return []

def save_db(jobs):
    RESULTS_FILE.write_text(json.dumps(jobs, indent=2, default=str))

def is_recent(date_str):
    if not date_str: return True
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
        try:
            dt = datetime.strptime(str(date_str)[:len(fmt)+2].strip(), fmt)
            return datetime.utcnow() - dt.replace(tzinfo=None) < timedelta(hours=MAX_AGE_HOURS)
        except: continue
    return True

def score_relevance(title, desc=""):
    text = (title + " " + desc).lower()
    for rk in REJECT_KEYWORDS:
        if rk in text: return -1   # instant reject
    score = 0
    for pk in PROFILE_KEYWORDS:
        if pk in text: score += 1
    return score

def check_sponsorship(text):
    t = text.lower()
    for n in SPONSORSHIP_NEGATIVE:
        if n in t: return False
    for p in SPONSORSHIP_POSITIVE:
        if p in t: return True
    return None

def clean_url(url, source):
    """Fix broken job URLs"""
    if not url: return url
    url = url.strip()

    # Reed: convert API job ID to proper URL
    if "reed.co.uk" in url:
        m = re.search(r'/jobs/(\d+)', url)
        if m:
            return f"https://www.reed.co.uk/jobs/job/{m.group(1)}"
        if re.match(r'^https://www\.reed\.co\.uk/jobs/\d+$', url):
            job_id = url.split('/')[-1]
            return f"https://www.reed.co.uk/jobs/job/{job_id}"

    # Make sure URL is absolute
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http"):
        if "bayt" in source.lower():
            return "https://www.bayt.com" + url
        if "gulfjobs" in source.lower():
            return "https://www.gulfjobs.com" + url

    return url

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg,
                  "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        log.error(f"Telegram: {e}")

# ─── CONTACT FINDER ──────────────────────────────────────────────────────────
_contact_cache = {}

def find_contacts(company):
    if not company or company.lower() in ("unknown",""):
        return []
    if company in _contact_cache:
        return _contact_cache[company]

    contacts = []

    if HUNTER_KEY:
        try:
            # Step 1: get domain
            r = requests.get("https://api.hunter.io/v2/domain-search",
                params={"company": company, "api_key": HUNTER_KEY, "limit": 5,
                        "department": "management,hr,engineering,executive"},
                timeout=10)
            if r.ok:
                data = r.json().get("data", {})
                domain = data.get("domain", "")
                for e in data.get("emails", []):
                    fname = e.get("first_name","")
                    lname = e.get("last_name","")
                    contacts.append({
                        "name": f"{fname} {lname}".strip() or "Unknown",
                        "email": e.get("value",""),
                        "title": e.get("position","") or "Contact",
                        "confidence": e.get("confidence", 0),
                        "linkedin": e.get("linkedin",""),
                        "source": "Hunter.io",
                        "domain": domain
                    })
        except Exception as e:
            log.warning(f"Hunter error for {company}: {e}")

    # LinkedIn search URL (always add — free backup)
    li_url = f"https://www.linkedin.com/search/results/people/?keywords={quote(company + ' HR recruiter hiring manager')}"
    contacts.append({
        "name": f"Search LinkedIn for {company}",
        "email": "",
        "title": "HR / Talent Acquisition",
        "confidence": 0,
        "linkedin": li_url,
        "source": "LinkedIn Search",
        "domain": ""
    })

    _contact_cache[company] = contacts
    time.sleep(0.3)  # rate limit
    return contacts

# ─── JOB SCRAPERS ────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"}

def scrape_reed(keyword, location, sponsored_req):
    jobs = []
    if not REED_KEY:
        return jobs
    try:
        r = requests.get("https://www.reed.co.uk/api/1.0/search",
            params={"keywords": keyword, "locationName": location, "resultsToTake": 25},
            auth=(REED_KEY, ""), timeout=15)
        if not r.ok:
            log.warning(f"Reed {r.status_code}: {r.text[:100]}")
            return jobs
        for j in r.json().get("results", []):
            title = j.get("jobTitle","")
            desc  = j.get("jobDescription","") or ""
            score = score_relevance(title, desc)
            if score < 0: continue
            spons = check_sponsorship(desc + " " + title)
            if sponsored_req and spons is False: continue

            # ✅ Fixed Reed URL
            job_id_val = j.get("jobId","")
            url = f"https://www.reed.co.uk/jobs/{job_id_val}" if job_id_val else ""

            sal = ""
            mn, mx = j.get("minimumSalary"), j.get("maximumSalary")
            if mn and mx: sal = f"£{int(mn):,} – £{int(mx):,}"
            elif mn: sal = f"From £{int(mn):,}"

            jobs.append({
                "title": title, "company": j.get("employerName",""),
                "location": j.get("locationName", location),
                "salary": sal, "date": j.get("date",""),
                "url": url, "description": desc[:800],
                "source": "Reed.co.uk", "sponsorship": spons,
                "relevance": score,
            })
    except Exception as e:
        log.error(f"Reed error: {e}")
    return jobs


def scrape_indeed(keyword, location, sponsored_req, uk=True):
    jobs = []
    base  = "https://uk.indeed.com" if uk else "https://www.indeed.com"
    query = keyword + (" visa sponsorship" if sponsored_req else "")
    url   = f"{base}/rss?q={quote(query)}&l={quote(location)}&fromage=3&sort=date"
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
        for e in feed.entries[:25]:
            title = e.get("title","")
            desc  = BeautifulSoup(e.get("summary",""), "html.parser").get_text()
            score = score_relevance(title, desc)
            if score < 0: continue
            spons = check_sponsorship(desc + " " + title)
            if sponsored_req and spons is False: continue
            if not is_recent(e.get("published","")): continue

            parts = title.split(" - ")
            clean = parts[0].strip()
            comp  = parts[1].strip() if len(parts) > 1 else ""
            link  = clean_url(e.get("link",""), "indeed")

            jobs.append({
                "title": clean, "company": comp,
                "location": location, "salary": "",
                "date": e.get("published",""),
                "url": link, "description": desc[:800],
                "source": f"Indeed ({'UK' if uk else 'INT'})",
                "sponsorship": spons, "relevance": score,
            })
    except Exception as e:
        log.error(f"Indeed error: {e}")
    return jobs


def scrape_cv_library(keyword, location):
    jobs = []
    url = f"https://www.cv-library.co.uk/search-jobs-rss?q={quote(keyword)}&loc={quote(location)}&distance=30&posted=3"
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:20]:
            title = e.get("title","")
            desc  = BeautifulSoup(e.get("summary",""), "html.parser").get_text()
            score = score_relevance(title, desc)
            if score < 0: continue
            if not is_recent(e.get("published","")): continue
            jobs.append({
                "title": title, "company": e.get("author",""),
                "location": location, "salary": "",
                "date": e.get("published",""),
                "url": clean_url(e.get("link",""), "cv_library"),
                "description": desc[:800],
                "source": "CV-Library",
                "sponsorship": check_sponsorship(desc + title),
                "relevance": score_relevance(title, desc),
            })
    except Exception as e:
        log.error(f"CV-Library error: {e}")
    return jobs


def scrape_bayt(keyword, location):
    jobs = []
    country = "ae" if "dubai" in location.lower() or "uae" in location.lower() else "qa" if "qatar" in location.lower() else "ae"
    kw_slug = re.sub(r'\s+', '-', keyword.lower().strip())
    url = f"https://www.bayt.com/en/{country}/jobs/{kw_slug}-jobs/?format=rss"
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
        for e in feed.entries[:20]:
            title = e.get("title","")
            desc  = BeautifulSoup(e.get("summary",""), "html.parser").get_text()
            score = score_relevance(title, desc)
            if score < 0: continue
            # extract company from title "Role at Company"
            m = re.search(r' at (.+)$', title)
            comp = m.group(1).strip() if m else ""
            clean = re.sub(r' at .+$', '', title).strip()
            link = clean_url(e.get("link",""), "bayt")
            jobs.append({
                "title": clean, "company": comp,
                "location": location, "salary": "",
                "date": e.get("published",""),
                "url": link, "description": desc[:800],
                "source": "Bayt.com",
                "sponsorship": None, "relevance": score,
            })
    except Exception as e:
        log.error(f"Bayt error: {e}")
    return jobs


def scrape_gulfjobs(keyword, location):
    jobs = []
    try:
        url = f"https://www.gulfjobs.com/jobs/?q={quote(keyword)}&l={quote(location)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok: return jobs
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all(["div","li"], class_=re.compile(r"job|listing|result", re.I))[:15]:
            a = card.find("a", href=True)
            h = card.find(re.compile("h[23456]"))
            if not a or not h: continue
            title = h.get_text(strip=True)
            score = score_relevance(title)
            if score < 0: continue
            href = a["href"]
            if not href.startswith("http"):
                href = "https://www.gulfjobs.com" + href
            jobs.append({
                "title": title, "company": "",
                "location": location, "salary": "",
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "url": href, "description": "",
                "source": "GulfJobs", "sponsorship": None, "relevance": score,
            })
    except Exception as e:
        log.error(f"GulfJobs error: {e}")
    return jobs


def run_board(board, keyword, location, sponsored):
    try:
        if board == "reed":            return scrape_reed(keyword, location, sponsored)
        if board == "indeed_uk":       return scrape_indeed(keyword, location, sponsored, uk=True)
        if board == "indeed_international": return scrape_indeed(keyword, location, sponsored, uk=False)
        if board == "cv_library":      return scrape_cv_library(keyword, location)
        if board == "bayt":            return scrape_bayt(keyword, location)
        if board == "gulfjobs":        return scrape_gulfjobs(keyword, location)
    except Exception as e:
        log.error(f"Board {board}: {e}")
    return []

# ─── HTML DASHBOARD ──────────────────────────────────────────────────────────
def build_dashboard(all_jobs):
    jobs = sorted(all_jobs, key=lambda j: (j.get("relevance",0), j.get("date","")), reverse=True)

    # Stats
    by_country = {}
    for j in jobs:
        p = j.get("profile","Other")
        flag = p[:2] if p else "🌍"
        by_country[flag] = by_country.get(flag, 0) + 1

    country_pills = "".join(
        f'<button class="pill" onclick="filterCountry(\'{f}\')">{f} {c}</button>'
        for f, c in by_country.items()
    )

    def spons_badge(s):
        if s is True:  return '<span class="badge b-green">✅ Sponsorship</span>'
        if s is False: return '<span class="badge b-red">❌ No Sponsor</span>'
        return '<span class="badge b-gray">❓ Unknown</span>'

    def contact_html(contacts):
        if not contacts: return "<p class='no-contact'>No contacts found</p>"
        rows = ""
        for c in contacts:
            email_str = f'<a href="mailto:{c["email"]}">{c["email"]}</a>' if c.get("email") else "—"
            li_str    = f'<a href="{c["linkedin"]}" target="_blank">🔗 LinkedIn</a>' if c.get("linkedin") else ""
            conf      = f'<small>{c["confidence"]}% confidence</small>' if c.get("confidence") else ""
            rows += f"""
            <div class="contact-row">
                <div>
                    <strong>{c.get("name","?")}</strong>
                    <span class="ctitle">{c.get("title","")}</span>
                    {conf}
                </div>
                <div class="contact-links">{email_str} {li_str}</div>
            </div>"""
        return rows

    cards_html = ""
    for job in jobs:
        contacts = job.get("contacts", [])
        flag = job.get("profile","")[:2] if job.get("profile") else "🌍"
        desc_safe = (job.get("description","") or "No description available.").replace("<","&lt;").replace(">","&gt;")
        salary_str = f'<span class="salary">💰 {job["salary"]}</span>' if job.get("salary") else ""
        date_str   = str(job.get("date",""))[:10]
        card_id    = jid(job)

        cards_html += f"""
        <div class="card" data-country="{flag}" data-relevance="{job.get('relevance',0)}" id="c-{card_id}">
            <div class="card-header">
                <div>
                    <div class="job-title">{job.get('title','Unknown')}</div>
                    <div class="job-meta">
                        <span class="company">🏢 {job.get('company','Unknown')}</span>
                        <span class="loc">📍 {job.get('location','')}</span>
                        <span class="src">📌 {job.get('source','')}</span>
                        {salary_str}
                        <span class="date">🕐 {date_str}</span>
                    </div>
                </div>
                <div class="badges">
                    {spons_badge(job.get('sponsorship'))}
                    <a href="{job.get('url','#')}" target="_blank" class="apply-btn">Apply →</a>
                </div>
            </div>
            <div class="card-body">
                <div class="section-label">📄 Job Description</div>
                <div class="desc">{desc_safe}</div>
                <div class="section-label">👤 Contacts at {job.get('company','this company')}</div>
                <div class="contacts">{contact_html(contacts)}</div>
            </div>
        </div>"""

    now = datetime.now().strftime("%d %b %Y %H:%M")
    total = len(jobs)
    sponsored_count = sum(1 for j in jobs if j.get("sponsorship") is True)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Malik's Job Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');
  :root {{
    --bg: #0d0f14; --surface: #13161d; --card: #181c25;
    --border: #252a35; --accent: #00d4aa; --accent2: #3b82f6;
    --text: #e2e8f0; --muted: #64748b; --green: #22c55e;
    --red: #ef4444; --yellow: #f59e0b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; min-height: 100vh; }}

  header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
    display: flex; justify-content: space-between; align-items: center;
    position: sticky; top: 0; z-index: 100;
  }}
  .logo {{ font-family: 'IBM Plex Mono', monospace; font-size: 18px; color: var(--accent); font-weight: 600; }}
  .logo span {{ color: var(--muted); font-weight: 400; }}
  .stats {{ display: flex; gap: 24px; }}
  .stat {{ text-align: center; }}
  .stat-num {{ font-size: 22px; font-weight: 700; color: var(--accent); font-family: 'IBM Plex Mono', monospace; }}
  .stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}
  .updated {{ font-size: 12px; color: var(--muted); }}

  .toolbar {{
    padding: 16px 32px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  }}
  .pill {{
    background: var(--card); border: 1px solid var(--border);
    color: var(--text); padding: 6px 14px; border-radius: 20px;
    cursor: pointer; font-size: 13px; transition: all .2s;
    font-family: inherit;
  }}
  .pill:hover, .pill.active {{ background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }}
  .search-box {{
    margin-left: auto;
    background: var(--card); border: 1px solid var(--border);
    color: var(--text); padding: 7px 14px; border-radius: 8px;
    font-family: 'IBM Plex Mono', monospace; font-size: 13px;
    width: 220px; outline: none;
  }}
  .search-box:focus {{ border-color: var(--accent); }}

  .main {{ padding: 24px 32px; max-width: 1400px; margin: 0 auto; }}
  .count-bar {{ margin-bottom: 16px; font-size: 13px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; }}

  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; margin-bottom: 16px;
    overflow: hidden; transition: border-color .2s;
  }}
  .card:hover {{ border-color: var(--accent2); }}
  .card-header {{
    padding: 18px 20px;
    display: flex; justify-content: space-between; align-items: flex-start;
    cursor: pointer;
  }}
  .job-title {{ font-size: 17px; font-weight: 700; color: var(--text); margin-bottom: 6px; }}
  .job-meta {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--muted); align-items: center; }}
  .company {{ color: var(--accent2); font-weight: 500; }}
  .salary {{ color: var(--green); font-weight: 600; }}
  .badges {{ display: flex; flex-direction: column; gap: 8px; align-items: flex-end; min-width: 160px; }}
  .badge {{ font-size: 11px; padding: 3px 10px; border-radius: 20px; font-weight: 600; text-align: center; }}
  .b-green {{ background: #14532d; color: var(--green); border: 1px solid #166534; }}
  .b-red   {{ background: #450a0a; color: var(--red);   border: 1px solid #7f1d1d; }}
  .b-gray  {{ background: #1e2330; color: var(--muted); border: 1px solid var(--border); }}
  .apply-btn {{
    background: var(--accent); color: #000; padding: 7px 18px;
    border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 13px;
    transition: opacity .2s; white-space: nowrap;
  }}
  .apply-btn:hover {{ opacity: .85; }}

  .card-body {{ display: none; padding: 0 20px 18px; border-top: 1px solid var(--border); }}
  .card-body.open {{ display: block; }}
  .section-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin: 16px 0 8px; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }}
  .desc {{ font-size: 14px; line-height: 1.7; color: #94a3b8; white-space: pre-wrap; max-height: 200px; overflow-y: auto; padding: 12px; background: var(--surface); border-radius: 6px; border: 1px solid var(--border); }}
  .contacts {{ display: flex; flex-direction: column; gap: 8px; }}
  .contact-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 14px; background: var(--surface); border-radius: 6px;
    border: 1px solid var(--border); font-size: 13px;
  }}
  .ctitle {{ color: var(--muted); margin-left: 8px; font-size: 12px; }}
  .contact-links {{ display: flex; gap: 12px; }}
  .contact-links a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
  .contact-links a:hover {{ text-decoration: underline; }}
  .no-contact {{ color: var(--muted); font-size: 13px; font-style: italic; padding: 8px 0; }}

  .hidden {{ display: none !important; }}
  .empty-state {{ text-align: center; padding: 60px; color: var(--muted); }}
  .empty-state .big {{ font-size: 40px; margin-bottom: 12px; }}
</style>
</head>
<body>

<header>
  <div class="logo">nezaam<span>_hunter</span>.bot <span style="font-size:12px;margin-left:8px;">v3.0</span></div>
  <div class="stats">
    <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Total Jobs</div></div>
    <div class="stat"><div class="stat-num">{sponsored_count}</div><div class="stat-label">With Sponsorship</div></div>
    <div class="stat"><div class="stat-num">{len([j for j in jobs if "🇦🇪" in j.get("profile","") or "🇶🇦" in j.get("profile","")])}</div><div class="stat-label">Gulf Jobs</div></div>
  </div>
  <div class="updated">Last updated: {now}</div>
</header>

<div class="toolbar">
  <button class="pill active" onclick="filterCountry('all')">🌍 All</button>
  {country_pills}
  <button class="pill" onclick="filterSponsorship()">✅ Sponsorship Only</button>
  <input class="search-box" type="text" placeholder="Search title / company..." oninput="searchJobs(this.value)">
</div>

<div class="main">
  <div class="count-bar" id="count-bar">Showing {total} jobs</div>
  <div id="cards">
    {cards_html}
  </div>
  <div id="empty" class="empty-state hidden">
    <div class="big">🔍</div>
    <p>No jobs match your filter.</p>
  </div>
</div>

<script>
let activeCountry = 'all';
let sponsorOnly = false;
let searchTerm = '';

function filterCountry(flag) {{
  activeCountry = flag;
  sponsorOnly = false;
  document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  applyFilters();
}}

function filterSponsorship() {{
  sponsorOnly = !sponsorOnly;
  event.target.classList.toggle('active');
  applyFilters();
}}

function searchJobs(val) {{
  searchTerm = val.toLowerCase();
  applyFilters();
}}

function applyFilters() {{
  const cards = document.querySelectorAll('.card');
  let visible = 0;
  cards.forEach(card => {{
    const country = card.dataset.country;
    const text = card.textContent.toLowerCase();
    const hasSponsor = card.innerHTML.includes('b-green');
    const matchCountry = activeCountry === 'all' || country === activeCountry;
    const matchSponsor = !sponsorOnly || hasSponsor;
    const matchSearch = !searchTerm || text.includes(searchTerm);
    if (matchCountry && matchSponsor && matchSearch) {{
      card.classList.remove('hidden'); visible++;
    }} else {{
      card.classList.add('hidden');
    }}
  }});
  document.getElementById('count-bar').textContent = `Showing ${{visible}} jobs`;
  document.getElementById('empty').classList.toggle('hidden', visible > 0);
}}

document.querySelectorAll('.card-header').forEach(h => {{
  h.addEventListener('click', function(e) {{
    if (e.target.classList.contains('apply-btn')) return;
    const body = this.nextElementSibling;
    body.classList.toggle('open');
  }});
}});
</script>
</body>
</html>"""

    DASHBOARD_FILE.write_text(html, encoding="utf-8")
    log.info(f"✅ Dashboard saved → {DASHBOARD_FILE.resolve()}")


# ─── MAIN RUNNER ─────────────────────────────────────────────────────────────
def run():
    log.info("\n" + "═"*55)
    log.info(f"🔍 JOB HUNT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("═"*55)

    seen     = load_seen()
    existing = load_db()
    new_jobs = []

    for profile in SEARCH_PROFILES:
        log.info(f"\n{profile['label']}")
        found = 0
        for keyword in profile["keywords"]:
            for board in profile["boards"]:
                raw = run_board(board, keyword, profile["location"],
                                profile.get("sponsored_required", False))
                for j in raw:
                    j["profile"] = profile["label"]
                    j["url"] = clean_url(j.get("url",""), j.get("source",""))
                    uid = jid(j)
                    if uid not in seen and j.get("relevance", 0) >= 0:
                        seen.add(uid)
                        j["id"] = uid
                        j["found_at"] = datetime.utcnow().isoformat()
                        # Find contacts
                        if j.get("company"):
                            j["contacts"] = find_contacts(j["company"])
                        else:
                            j["contacts"] = []
                        new_jobs.append(j)
                        found += 1
                time.sleep(1)
        log.info(f"  → {found} new jobs")

    if new_jobs:
        all_jobs = new_jobs + existing
        save_db(all_jobs[:600])
        save_seen(seen)
        build_dashboard(all_jobs[:600])

        # Telegram summary
        by_profile = {}
        for j in new_jobs:
            by_profile.setdefault(j["profile"], []).append(j)

        for p, pjobs in by_profile.items():
            msg = f"<b>{p}</b>  🆕 {len(pjobs)} new\n\n"
            for j in sorted(pjobs, key=lambda x: x.get("relevance",0), reverse=True)[:4]:
                s = j.get("sponsorship")
                si = "✅" if s else ("❓" if s is None else "❌")
                c = j.get("contacts",[])
                best_email = next((x["email"] for x in c if x.get("email") and x.get("confidence",0)>40), "")
                msg += (
                    f"📌 <b>{j['title'][:50]}</b>\n"
                    f"🏢 {j.get('company','?')}  📍 {j.get('location','?')}\n"
                    f"{si} Sponsorship\n"
                    f"{'📧 '+best_email+chr(10) if best_email else ''}"
                    f"🔗 <a href='{j.get('url','')}'>View Job</a>\n"
                    f"──────────\n"
                )
            send_telegram(msg)
            time.sleep(0.5)

        log.info(f"\n✅ {len(new_jobs)} new jobs | Dashboard → {DASHBOARD_FILE.resolve()}")
        send_telegram(f"📊 <b>Dashboard updated</b>\nOpen: <code>{DASHBOARD_FILE.resolve()}</code>\nTotal in DB: {len(existing)+len(new_jobs)}")
    else:
        log.info("No new jobs this run.")
        build_dashboard(existing)  # refresh dashboard with existing
        send_telegram("😴 No new jobs this run — dashboard refreshed.")

    return new_jobs


# ─── ENTRY ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print(f"""

Config:
  Telegram  : {'✅' if TELEGRAM_TOKEN else '❌ MISSING'}
  Reed API  : {'✅' if REED_KEY else '⚠️  not set'}
  Hunter.io : {'✅' if HUNTER_KEY else '⚠️  not set (no email lookup)'}
  Dashboard : {DASHBOARD_FILE.resolve()}
""")

    if "--once" in sys.argv or "test" in sys.argv:
        run()
        sys.exit(0)

    # Run now then every hour
    run()
    try:
        import schedule
        schedule.every(CHECK_INTERVAL).minutes.do(run)
        print(f"\n⏰ Running every {CHECK_INTERVAL} mins. Ctrl+C to stop.\n")
        while True:
            schedule.run_pending()
            time.sleep(30)
    except ImportError:
        print("install 'schedule' for continuous mode: pip install schedule")
