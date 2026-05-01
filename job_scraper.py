"""
IT/Helpdesk/Security Job Alert Bot — Multi-Source Edition v3
Sources: Indeed, LinkedIn, USAJobs, Glassdoor, ZipRecruiter,
         Dice, Monster, SimplyHired, SecurityJobs, Snagajob, Joblist
Sends daily HTML email digest via Gmail SMTP
"""

import feedparser
import smtplib
import json
import os
import hashlib
import urllib.request
import urllib.parse
import re
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", "your_email@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "your_app_password")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_email@outlook.com")
USAJOBS_API_KEY = os.environ.get("USAJOBS_API_KEY", "")

SEEN_JOBS_FILE  = "seen_jobs.json"

# ─────────────────────────────────────────────
# SEARCH TERMS
# ─────────────────────────────────────────────
SEARCH_TERMS = [
    # IT / Helpdesk
    "help desk technician",
    "IT support specialist",
    "desktop support technician",
    "service desk analyst",
    "IT technician",
    "technical support specialist",
    "entry level IT support",
    "computer support technician",
    "systems support technician",
    "network support technician",
    # Security
    "security guard",
    "security officer",
    "unarmed security",
    "armed security officer",
    "unarmed security officer",
    "security professional",
    "loss prevention officer",
    "security specialist",
    "site security officer",
    "patrol officer",
    "security patrol",
    "security concierge",
    "security dispatcher",
    "security alarm monitor",
    "surveillance officer",
    "command center operator",
    "control room operator",
    "loss prevention agent",
    "asset protection",
]

# ─────────────────────────────────────────────
# TITLE FILTER
# ─────────────────────────────────────────────
JOB_KEYWORDS = [
    # IT / Helpdesk
    "it support", "it technician", "it specialist", "it analyst",
    "it help", "it coordinator", "it administrator", "it manager",
    "helpdesk", "help desk", "help-desk", "desktop support",
    "desktop technician", "service desk", "deskside",
    "end user support", "end-user support", "support specialist",
    "support analyst", "support engineer", "support technician",
    "field technician", "field tech", "pc technician", "pc support",
    "pc tech", "computer support", "computer technician",
    "network support", "network technician", "network administrator",
    "systems administrator", "systems analyst", "sysadmin", "sys admin",
    "infrastructure", "information technology", "information systems",
    "software support", "hardware support", "hardware technician",
    "technical support",
    # Security
    "security guard", "security officer", "security professional",
    "security specialist", "security patrol", "security concierge",
    "security dispatcher", "security alarm monitor", "site security",
    "unarmed security", "armed security", "loss prevention",
    "loss prevention agent", "patrol officer", "surveillance officer",
    "command center operator", "control room operator", "asset protection",
]

JOB_EXCLUSIONS = [
    "diesel", "automotive", "auto body", "auto tech", "mechanic",
    "patient care", "patient tech", "dental", "medical", "clinical",
    "culinary", "food", "hvac", "plumbing", "electrical", "construction",
    "nursing", "pharmacy", "radiology", "surgical", "veterinary",
    "childcare", "custodial", "janitorial", "welding", "forklift",
    "warehouse", "housing", "case manager",
]

# ─────────────────────────────────────────────
# TARGET STATES
# ─────────────────────────────────────────────
TARGET_STATES = {"GA", "NC", "CO", "TN", "AL"}
TARGET_STATE_NAMES = {"georgia", "north carolina", "colorado", "tennessee", "alabama"}

# ─────────────────────────────────────────────
# TARGET LOCATIONS
# ─────────────────────────────────────────────
LOCATIONS = [
    # Georgia
    ("Suwanee", "GA"), ("Lawrenceville", "GA"), ("Gainesville", "GA"),
    ("Cumming", "GA"), ("Dahlonega", "GA"), ("Cleveland", "GA"),
    ("Toccoa", "GA"), ("Cornelia", "GA"), ("Clayton", "GA"),
    ("Blue Ridge", "GA"), ("Ellijay", "GA"), ("Jasper", "GA"),
    ("Canton", "GA"), ("Ball Ground", "GA"), ("Athens", "GA"),
    ("Alpharetta", "GA"), ("Kennesaw", "GA"), ("Marietta", "GA"),
    ("Rome", "GA"), ("Dalton", "GA"), ("Cartersville", "GA"),
    # North Carolina
    ("Murphy", "NC"), ("Andrews", "NC"), ("Robbinsville", "NC"),
    ("Hayesville", "NC"), ("Brasstown", "NC"), ("Cherokee", "NC"),
    ("Sylva", "NC"), ("Franklin", "NC"), ("Highlands", "NC"),
    ("Asheville", "NC"), ("Waynesville", "NC"), ("Brevard", "NC"),
    ("Hendersonville", "NC"),
    # Colorado
    ("Nederland", "CO"), ("Glenwood Springs", "CO"), ("Golden", "CO"),
    ("Boulder", "CO"), ("Blackhawk", "CO"), ("Idaho Springs", "CO"),
    ("Vail", "CO"), ("Evergreen", "CO"), ("Conifer", "CO"),
    ("Morrison", "CO"), ("Dillon", "CO"), ("Frisco", "CO"),
    ("Silverthorne", "CO"), ("Breckenridge", "CO"), ("Avon", "CO"),
    ("Eagle", "CO"), ("Gypsum", "CO"), ("Lakewood", "CO"),
    ("Arvada", "CO"), ("Central City", "CO"), ("Georgetown", "CO"),
    ("Silver Plume", "CO"), ("Empire", "CO"), ("Wheat Ridge", "CO"),
    ("Edgewater", "CO"), ("Lakeside", "CO"), ("Rollinsville", "CO"),
    ("Genesee", "CO"), ("Kittredge", "CO"), ("Dumont", "CO"),
    ("Lawson", "CO"), ("Littleton", "CO"), ("Englewood", "CO"),
    ("Highlands Ranch", "CO"),
    # Tennessee
    ("Cleveland", "TN"), ("Chattanooga", "TN"),
    # Alabama
    ("Huntsville", "AL"),
]

# ─────────────────────────────────────────────
# FILTER FUNCTIONS
# ─────────────────────────────────────────────
def is_good_job(title: str) -> bool:
    t = title.lower()
    if not any(k in t for k in JOB_KEYWORDS):
        return False
    if any(e in t for e in JOB_EXCLUSIONS):
        return False
    return True

def is_target_location(location: str) -> bool:
    loc = location.lower()
    for state in TARGET_STATES:
        if f", {state.lower()}" in loc or f" {state.lower()}" in loc:
            return True
    if any(name in loc for name in TARGET_STATE_NAMES):
        return True
    if location.strip().upper() in TARGET_STATES:
        return True
    return False

# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────
def load_seen_jobs() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen_jobs(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen)[-5000:], f)

def job_id(title: str, company: str, location: str) -> str:
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()

def add_job(all_jobs, seen_ids, title, company, location, link, posted, source):
    title   = title.strip()
    company = company.strip()
    if not is_good_job(title):
        return
    if not is_target_location(location):
        return
    jid = job_id(title, company, location)
    if jid in seen_ids or jid in all_jobs:
        return
    all_jobs[jid] = {
        "title": title, "company": company, "location": location,
        "link": link, "posted": posted, "source": source, "jid": jid,
    }

# ─────────────────────────────────────────────
# HELPER — safe URL fetch
# ─────────────────────────────────────────────
def safe_fetch(url, headers=None, timeout=10):
    try:
        headers = headers or {"User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None

# ─────────────────────────────────────────────
# SOURCE 1 — INDEED (RSS)
# ─────────────────────────────────────────────
def fetch_indeed(all_jobs, seen_ids):
    print("  Scanning Indeed...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"q": term, "l": f"{city}, {state}", "radius": "25",
                      "sort": "date", "limit": "25", "fromage": "1"}
            url = "https://www.indeed.com/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").split(" - ")[0].strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("indeed_city", city)
                    location += f", {entry.get('indeed_state', state)}"
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "Indeed")
                    count += 1
            except Exception as e:
                print(f"    Warning - Indeed {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 2 — LINKEDIN (with rate limit delay)
# ─────────────────────────────────────────────
def fetch_linkedin(all_jobs, seen_ids):
    print("  Scanning LinkedIn...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"keywords": term, "location": f"{city}, {state}",
                      "f_TPR": "r86400", "distance": "25", "start": "0"}
            url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(params)
            html = safe_fetch(url)
            if html:
                cards = re.findall(
                    r'href="(https://www\.linkedin\.com/jobs/view/[^"]+)".*?'
                    r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>.*?'
                    r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>.*?'
                    r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>',
                    html, re.DOTALL
                )
                for link, title, company, location in cards:
                    title    = re.sub(r'<[^>]+>', '', title).strip()
                    company  = re.sub(r'<[^>]+>', '', company).strip()
                    location = re.sub(r'<[^>]+>', '', location).strip()
                    add_job(all_jobs, seen_ids, title, company, location,
                            link.split("?")[0], "", "LinkedIn")
                    count += 1
            time.sleep(1)
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 3 — USAJOBS (official API)
# Searches by city rather than state to avoid
# returning jobs from Raleigh, DC, etc.
# ─────────────────────────────────────────────
def fetch_usajobs(all_jobs, seen_ids):
    print("  Scanning USAJobs...")
    if not USAJOBS_API_KEY:
        print("    Skipped - no API key")
        return
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"Keyword": term, "LocationName": f"{city}, {state}",
                      "Radius": "25", "DatePosted": "1",
                      "ResultsPerPage": "25", "Fields": "Min"}
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode(params)
            html = safe_fetch(url, headers={
                "Host": "data.usajobs.gov",
                "User-Agent": RECIPIENT_EMAIL,
                "Authorization-Key": USAJOBS_API_KEY,
            })
            if html:
                try:
                    data  = json.loads(html)
                    items = data.get("SearchResult", {}).get("SearchResultItems", [])
                    for item in items:
                        mv       = item.get("MatchedObjectDescriptor", {})
                        title    = mv.get("PositionTitle", "")
                        company  = mv.get("OrganizationName", "US Government")
                        locs     = mv.get("PositionLocation", [{}])
                        location = locs[0].get("LocationName", f"{city}, {state}") if locs else f"{city}, {state}"
                        add_job(all_jobs, seen_ids, title, company, location,
                                mv.get("PositionURI", ""), mv.get("PublicationStartDate", ""), "USAJobs")
                        count += 1
                except Exception as e:
                    print(f"    Warning - USAJobs parse {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 4 — DICE (IT focused, RSS)
# ─────────────────────────────────────────────
def fetch_dice(all_jobs, seen_ids):
    print("  Scanning Dice...")
    count = 0
    states = list(set(s for _, s in LOCATIONS))
    for term in SEARCH_TERMS:
        for state in states:
            params = {"q": term, "location": state, "radius": "30",
                      "radiusUnit": "mi", "pageSize": "20", "filters.postedDate": "ONE"}
            url = "https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search?" + urllib.parse.urlencode(params)
            html = safe_fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0)",
                "x-api-key":  "1YAt0R9wBg4WfsF9VB2778F5CHLAPMVW3WAZcKd8",
            })
            if html:
                try:
                    data = json.loads(html)
                    for job in data.get("data", []):
                        title    = job.get("title", "")
                        company  = job.get("advertiserName", "Unknown")
                        location = job.get("location", state)
                        link     = f"https://www.dice.com/job-detail/{job.get('id', '')}"
                        posted   = job.get("postedDate", "")
                        add_job(all_jobs, seen_ids, title, company, location,
                                link, posted, "Dice")
                        count += 1
                except Exception as e:
                    print(f"    Warning - Dice parse {state}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 5 — MONSTER (RSS)
# ─────────────────────────────────────────────
def fetch_monster(all_jobs, seen_ids):
    print("  Scanning Monster...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"q": term, "where": f"{city}, {state}", "rad": "25"}
            url = "https://www.monster.com/jobs/search/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("location", f"{city}, {state}")
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "Monster")
                    count += 1
            except Exception as e:
                print(f"    Warning - Monster {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 6 — SIMPLYHIRED (RSS)
# ─────────────────────────────────────────────
def fetch_simplyhired(all_jobs, seen_ids):
    print("  Scanning SimplyHired...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"q": term, "l": f"{city} {state}", "mi": "25", "fdb": "1"}
            url = "https://www.simplyhired.com/search/jobsrss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("location", f"{city}, {state}")
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "SimplyHired")
                    count += 1
            except Exception as e:
                print(f"    Warning - SimplyHired {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 7 — SECURITYJOBS.COM
# ─────────────────────────────────────────────
def fetch_securityjobs(all_jobs, seen_ids):
    print("  Scanning SecurityJobs...")
    count = 0
    states = list(set(s for _, s in LOCATIONS))
    for term in [t for t in SEARCH_TERMS if any(k in t.lower() for k in
                 ["security", "patrol", "surveillance", "loss prevention", "asset protection"])]:
        for state in states:
            params = {"keywords": term, "location": state, "radius": "50"}
            url = "https://www.securityjobs.com/jobs/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("location", state)
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "SecurityJobs")
                    count += 1
            except Exception as e:
                print(f"    Warning - SecurityJobs {state}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 8 — SNAGAJOB (good for hourly/shift security)
# ─────────────────────────────────────────────
def fetch_snagajob(all_jobs, seen_ids):
    print("  Scanning Snagajob...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"what": term, "where": f"{city}, {state}", "radius": "25"}
            url = "https://www.snagajob.com/jobs/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("location", f"{city}, {state}")
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "Snagajob")
                    count += 1
            except Exception as e:
                print(f"    Warning - Snagajob {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 9 — ZIPRECRUITER (RSS)
# ─────────────────────────────────────────────
def fetch_ziprecruiter(all_jobs, seen_ids):
    print("  Scanning ZipRecruiter...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"search": term, "location": f"{city}, {state}",
                      "radius": "25", "days": "1"}
            url = "https://www.ziprecruiter.com/jobs-search/feed?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "").strip()
                    company  = entry.get("author", entry.get("source", {}).get("title", "Unknown"))
                    location = entry.get("location", f"{city}, {state}")
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "ZipRecruiter")
                    count += 1
            except Exception as e:
                print(f"    Warning - ZipRecruiter {city}: {e}")
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# SOURCE 10 — GLASSDOOR
# ─────────────────────────────────────────────
def fetch_glassdoor(all_jobs, seen_ids):
    print("  Scanning Glassdoor...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {"searchKeyword": term, "searchLocation": f"{city}, {state}"}
            url = "https://www.glassdoor.com/Job/jobs.htm?" + urllib.parse.urlencode(params)
            html = safe_fetch(url)
            if html:
                cards = re.findall(
                    r'data-job-title="([^"]+)"[^>]*data-employer-name="([^"]+)"'
                    r'[^>]*data-job-location="([^"]+)"[^>]*data-job-emp-id="([^"]+)"',
                    html
                )
                for title, company, location, jid_val in cards:
                    link = f"https://www.glassdoor.com/job-listing/j?jl={jid_val}"
                    add_job(all_jobs, seen_ids, title, company, location,
                            link, "", "Glassdoor")
                    count += 1
    print(f"    Done: {count} raw entries scanned")

# ─────────────────────────────────────────────
# MAIN FETCHER
# ─────────────────────────────────────────────
def fetch_jobs() -> list[dict]:
    seen_ids = load_seen_jobs()
    all_jobs = {}

    print(f"Scanning {len(SEARCH_TERMS)} terms x {len(LOCATIONS)} locations across 10 sources...")
    fetch_indeed(all_jobs, seen_ids)
    fetch_linkedin(all_jobs, seen_ids)
    fetch_usajobs(all_jobs, seen_ids)
    fetch_dice(all_jobs, seen_ids)
    fetch_monster(all_jobs, seen_ids)
    fetch_simplyhired(all_jobs, seen_ids)
    fetch_securityjobs(all_jobs, seen_ids)
    fetch_snagajob(all_jobs, seen_ids)
    fetch_ziprecruiter(all_jobs, seen_ids)
    fetch_glassdoor(all_jobs, seen_ids)

    new_jobs = list(all_jobs.values())
    seen_ids.update(j["jid"] for j in new_jobs)
    save_seen_jobs(seen_ids)

    print(f"Found {len(new_jobs)} new unique jobs across all sources.")
    return new_jobs

# ─────────────────────────────────────────────
# EMAIL BUILDER
# ─────────────────────────────────────────────
def build_html_email(jobs: list[dict]) -> str:
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%A, %B %d, %Y")

    source_colors = {
        "Indeed":        "#2557a7",
        "LinkedIn":      "#0a66c2",
        "USAJobs":       "#1a6b3c",
        "Dice":          "#eb6534",
        "Monster":       "#6d4aff",
        "SimplyHired":   "#0e9e6e",
        "SecurityJobs":  "#c0392b",
        "Snagajob":      "#e67e22",
        "ZipRecruiter":  "#4a90d9",
        "Glassdoor":     "#0caa41",
    }

    if not jobs:
        body_content = """
        <div class="no-jobs">
            <p>No new job postings found today in your target region.</p>
            <p>Check back tomorrow - the bot is still watching!</p>
        </div>
        """
    else:
        by_source = {}
        for j in jobs:
            by_source.setdefault(j["source"], 0)
            by_source[j["source"]] += 1

        summary_badges = ""
        for src, cnt in sorted(by_source.items()):
            color = source_colors.get(src, "#666")
            summary_badges += f'<span class="src-badge" style="background:{color}">{src}: {cnt}</span> '

        rows = ""
        for j in sorted(jobs, key=lambda x: (x["source"], x["location"])):
            color   = source_colors.get(j["source"], "#666")
            src_tag = f'<span class="src-pill" style="background:{color}">{j["source"]}</span>'
            rows += f"""
            <tr>
                <td><a href="{j['link']}" target="_blank">{j['title']}</a></td>
                <td>{j['company']}</td>
                <td>{j['location']}</td>
                <td>{src_tag}</td>
                <td class="date">{j['posted'][:16] if j['posted'] else '-'}</td>
            </tr>"""

        body_content = f"""
        <p class="summary">Found <strong>{len(jobs)} new listing{'s' if len(jobs) != 1 else ''}</strong>
        across NE Georgia, Western NC, Colorado, Tennessee, and Alabama.</p>
        <p class="source-summary">{summary_badges}</p>
        <table>
            <thead>
                <tr>
                    <th>Job Title</th><th>Employer</th>
                    <th>Location</th><th>Source</th><th>Posted</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f4f8; color: #1a202c; }}
  .wrapper {{ max-width: 900px; margin: 30px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%); color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
  .header p {{ font-size: 14px; opacity: 0.85; }}
  .badge {{ display: inline-block; background: rgba(255,255,255,0.2); border-radius: 20px; padding: 3px 12px; font-size: 12px; margin-top: 10px; }}
  .body {{ padding: 32px 40px; }}
  .summary {{ margin-bottom: 12px; font-size: 15px; color: #4a5568; }}
  .source-summary {{ margin-bottom: 24px; }}
  .src-badge {{ display: inline-block; color: white; border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: 600; margin: 2px; }}
  .src-pill {{ display: inline-block; color: white; border-radius: 8px; padding: 2px 8px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  thead tr {{ background: #edf2f7; }}
  th {{ text-align: left; padding: 12px 14px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: #718096; border-bottom: 2px solid #e2e8f0; }}
  td {{ padding: 12px 14px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f7fafc; }}
  td a {{ color: #2b6cb0; text-decoration: none; font-weight: 500; }}
  td a:hover {{ text-decoration: underline; }}
  td.date {{ color: #718096; white-space: nowrap; font-size: 12px; }}
  .no-jobs {{ text-align: center; padding: 48px 24px; color: #718096; font-size: 15px; line-height: 1.8; }}
  .footer {{ background: #f7fafc; padding: 20px 40px; font-size: 12px; color: #a0aec0; text-align: center; border-top: 1px solid #e2e8f0; }}
  .region-tag {{ display: inline-block; background: #ebf8ff; color: #2b6cb0; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; margin: 2px; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>IT, Helpdesk and Security Job Alert</h1>
    <p>Daily digest - NE Georgia · Western NC · Colorado · Tennessee · Alabama</p>
    <span class="badge">Date: {now}</span>
  </div>
  <div class="body">{body_content}</div>
  <div class="footer">
    <p style="margin-bottom:10px; font-size:13px; color:#718096; background:#fffbeb; border:1px solid #f6e05e; border-radius:6px; padding:10px 16px; text-align:left;">
      <strong style="color:#b7791f;">Reminder:</strong> Degree requirements are not shown in this summary.
      Please click each job link to review the full description and verify education requirements before applying.
    </p>
    <p>Sources: Indeed · LinkedIn · USAJobs · Dice · Monster · SimplyHired · SecurityJobs · Snagajob · ZipRecruiter · Glassdoor</p>
    <p style="margin-top:6px;">
      <span class="region-tag">NE Georgia</span>
      <span class="region-tag">Western NC</span>
      <span class="region-tag">Colorado</span>
      <span class="region-tag">Tennessee</span>
      <span class="region-tag">Alabama</span>
    </p>
    <p style="margin-top:10px;">Automated daily at 7:00 AM ET</p>
  </div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# EMAIL SENDER (Gmail SMTP)
# ─────────────────────────────────────────────
def send_email(jobs: list[dict]):
    now_str = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
    subject = f"IT/Security Job Alert - {len(jobs)} New Listing{'s' if len(jobs) != 1 else ''} - {now_str}"
    if not jobs:
        subject = f"IT/Security Job Alert - No New Listings Today - {now_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(build_html_email(jobs), "html"))

    print(f"Sending email to {RECIPIENT_EMAIL} ...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print("Email sent successfully!")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  IT / Helpdesk / Security Job Alert Bot v3")
    print(f"  {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 55)
    jobs = fetch_jobs()
    send_email(jobs)
    print("Done.")
