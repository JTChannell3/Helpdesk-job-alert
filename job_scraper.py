"""
IT/Helpdesk Job Alert Bot — Multi-Source Edition
Sources: Indeed, LinkedIn, USAJobs, ZipRecruiter, CareerBuilder
Sends daily HTML email digest via Gmail SMTP
"""

import feedparser
import smtplib
import json
import os
import hashlib
import urllib.request
import urllib.parse
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
# IT TITLE FILTER
# Two-stage filter:
# 1. Title must contain at least one IT keyword
# 2. Title must NOT contain any exclusion word
# This blocks false matches like "diesel technician"
# and "patient care tech" from slipping through.
# ─────────────────────────────────────────────
IT_KEYWORDS = [
    # IT / Helpdesk keywords
    "it support",
    "it technician",
    "it specialist",
    "it analyst",
    "it help",
    "it coordinator",
    "it administrator",
    "it manager",
    "helpdesk",
    "help desk",
    "help-desk",
    "desktop support",
    "desktop technician",
    "service desk",
    "deskside",
    "end user support",
    "end-user support",
    "support specialist",
    "support analyst",
    "support engineer",
    "support technician",
    "field technician",
    "field tech",
    "pc technician",
    "pc support",
    "pc tech",
    "computer support",
    "computer technician",
    "network support",
    "network technician",
    "network administrator",
    "systems administrator",
    "systems analyst",
    "sysadmin",
    "sys admin",
    "infrastructure",
    "information technology",
    "information systems",
    "software support",
    "hardware support",
    "hardware technician",
    "technical support",
    # Security keywords
    "security guard",
    "security officer",
    "security professional",
    "security specialist",
    "security patrol",
    "site security",
    "unarmed security",
    "armed security",
    "loss prevention",
    "patrol officer",
]

# Jobs containing ANY of these words are excluded
# even if they matched an IT keyword above
IT_EXCLUSIONS = [
    "diesel",
    "automotive",
    "auto body",
    "auto tech",
    "mechanic",
    "patient care",
    "patient tech",
    "dental",
    "medical",
    "clinical",
    "culinary",
    "food",
    "hvac",
    "plumbing",
    "electrical",
    "construction",
    "nursing",
    "pharmacy",
    "radiology",
    "surgical",
    "veterinary",
    "childcare",
    "custodial",
    "janitorial",
    "welding",
    "forklift",
    "warehouse",
    "housing",
    "case manager",
]

# Target states — jobs outside these are rejected
TARGET_STATES = {"GA", "NC", "CO"}

# Full state names that may appear in location strings
TARGET_STATE_NAMES = {
    "georgia", "north carolina", "colorado"
}

def is_it_job(title: str) -> bool:
    """Return True if title matches IT keywords and has no exclusion words."""
    title_lower = title.lower()
    if not any(keyword in title_lower for keyword in IT_KEYWORDS):
        return False
    if any(excl in title_lower for excl in IT_EXCLUSIONS):
        return False
    return True

def is_target_location(location: str) -> bool:
    """Return True if the job location is in one of our target states."""
    loc_lower = location.lower()
    # Check for state abbreviations (e.g. ", GA" or "GA,")
    for state in TARGET_STATES:
        if f", {state.lower()}" in loc_lower or f" {state.lower()}" in loc_lower:
            return True
    # Check for full state names
    if any(name in loc_lower for name in TARGET_STATE_NAMES):
        return True
    # USAJobs sometimes returns just the state abbreviation
    if location.strip().upper() in TARGET_STATES:
        return True
    return False


# ─────────────────────────────────────────────
# TARGET LOCATIONS
# ─────────────────────────────────────────────
LOCATIONS = [
    # Georgia corridor
    ("Suwanee",          "GA"),
    ("Lawrenceville",    "GA"),
    ("Gainesville",      "GA"),
    ("Cumming",          "GA"),
    ("Dahlonega",        "GA"),
    ("Cleveland",        "GA"),
    ("Toccoa",           "GA"),
    ("Cornelia",         "GA"),
    ("Clayton",          "GA"),
    ("Blue Ridge",       "GA"),
    ("Ellijay",          "GA"),
    ("Jasper",           "GA"),
    ("Canton",           "GA"),
    ("Ball Ground",      "GA"),
    ("Athens",           "GA"),
    ("Alpharetta",       "GA"),
    ("Kennesaw",         "GA"),
    ("Marietta",         "GA"),
    ("Rome",             "GA"),
    ("Dalton",           "GA"),
    # North Carolina corridor
    ("Murphy",           "NC"),
    ("Andrews",          "NC"),
    ("Robbinsville",     "NC"),
    ("Hayesville",       "NC"),
    ("Brasstown",        "NC"),
    ("Cherokee",         "NC"),
    ("Sylva",            "NC"),
    ("Franklin",         "NC"),
    ("Highlands",        "NC"),
    ("Asheville",        "NC"),
    ("Waynesville",      "NC"),
    ("Brevard",          "NC"),
    ("Hendersonville",   "NC"),
    # Colorado corridor
    ("Nederland",        "CO"),
    ("Glenwood Springs", "CO"),
    ("Golden",           "CO"),
    ("Boulder",          "CO"),
    ("Blackhawk",        "CO"),
    ("Idaho Springs",    "CO"),
    ("Vail",             "CO"),
    ("Evergreen",        "CO"),
    ("Conifer",          "CO"),
    ("Morrison",         "CO"),
    ("Dillon",           "CO"),
    ("Frisco",           "CO"),
    ("Silverthorne",     "CO"),
    ("Breckenridge",     "CO"),
    ("Avon",             "CO"),
    ("Eagle",            "CO"),
    ("Gypsum",           "CO"),
    ("Lakewood",         "CO"),
    ("Arvada",           "CO"),
    ("Central City",     "CO"),
]

# ─────────────────────────────────────────────
# DEDUPLICATION HELPERS
# ─────────────────────────────────────────────
def load_seen_jobs() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen: set):
    seen_list = list(seen)[-5000:]
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_list, f)


def job_id(title: str, company: str, location: str) -> str:
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def add_job(all_jobs: dict, seen_ids: set, title: str, company: str,
            location: str, link: str, posted: str, source: str):
    title   = title.strip()
    company = company.strip()
    # Skip jobs that don't match IT-related keywords
    if not is_it_job(title):
        return
    # Skip jobs outside our target states
    if not is_target_location(location):
        return
    jid     = job_id(title, company, location)
    if jid in seen_ids or jid in all_jobs:
        return
    all_jobs[jid] = {
        "title":    title,
        "company":  company,
        "location": location,
        "link":     link,
        "posted":   posted,
        "source":   source,
        "jid":      jid,
    }


# ─────────────────────────────────────────────
# SOURCE 1 — INDEED  (RSS)
# ─────────────────────────────────────────────
def fetch_indeed(all_jobs: dict, seen_ids: set):
    print("  Scanning Indeed...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {
                "q":       term,
                "l":       f"{city}, {state}",
                "radius":  "25",
                "sort":    "date",
                "limit":   "25",
                "fromage": "1",
            }
            url = "https://www.indeed.com/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "Unknown Title").split(" - ")[0].strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("indeed_city", city)
                    if entry.get("indeed_state"):
                        location += f", {entry['indeed_state']}"
                    else:
                        location += f", {state}"
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "Indeed")
                    count += 1
            except Exception as e:
                print(f"    Warning - Indeed {term}/{city}: {e}")
    print(f"    Done: {count} raw entries scanned")


# ─────────────────────────────────────────────
# SOURCE 2 — LINKEDIN  (public jobs feed)
# ─────────────────────────────────────────────
def fetch_linkedin(all_jobs: dict, seen_ids: set):
    print("  Scanning LinkedIn...")
    count = 0
    import re
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {
                "keywords": term,
                "location": f"{city}, {state}",
                "f_TPR":    "r86400",
                "distance": "25",
                "start":    "0",
            }
            url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(params)
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0)"
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                cards = re.findall(
                    r'<li[^>]*>.*?<a[^>]+href="(https://www\.linkedin\.com/jobs/view/[^"]+)"[^>]*>.*?'
                    r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>.*?'
                    r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>.*?'
                    r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>',
                    html, re.DOTALL
                )
                for link, title, company, location in cards:
                    title    = re.sub(r'<[^>]+>', '', title).strip()
                    company  = re.sub(r'<[^>]+>', '', company).strip()
                    location = re.sub(r'<[^>]+>', '', location).strip()
                    add_job(all_jobs, seen_ids, title, company, location,
                            link.split("?")[0], "", "LinkedIn")
                    count += 1
            except Exception as e:
                print(f"    Warning - LinkedIn {term}/{city}: {e}")
    print(f"    Done: {count} raw entries scanned")


# ─────────────────────────────────────────────
# SOURCE 3 — USAJOBS  (official free API)
# ─────────────────────────────────────────────
def fetch_usajobs(all_jobs: dict, seen_ids: set):
    print("  Scanning USAJobs...")
    count = 0
    states = list(set(state for _, state in LOCATIONS))
    for term in SEARCH_TERMS:
        for state in states:
            params = {
                "Keyword":        term,
                "LocationName":   state,
                "DatePosted":     "1",
                "ResultsPerPage": "25",
                "Fields":         "Min",
            }
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode(params)
            try:
                req = urllib.request.Request(url, headers={
                    "Host":       "data.usajobs.gov",
                    "User-Agent": "JobAlertBot/1.0",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                items = data.get("SearchResult", {}).get("SearchResultItems", [])
                for item in items:
                    mv       = item.get("MatchedObjectDescriptor", {})
                    title    = mv.get("PositionTitle", "Unknown Title")
                    company  = mv.get("OrganizationName", "US Government")
                    locs     = mv.get("PositionLocation", [{}])
                    location = locs[0].get("LocationName", state) if locs else state
                    link     = mv.get("PositionURI", "")
                    posted   = mv.get("PublicationStartDate", "")
                    add_job(all_jobs, seen_ids, title, company, location,
                            link, posted, "USAJobs")
                    count += 1
            except Exception as e:
                print(f"    Warning - USAJobs {term}/{state}: {e}")
    print(f"    Done: {count} raw entries scanned")


# ─────────────────────────────────────────────
# SOURCE 4 — ZIPRECRUITER  (RSS)
# ─────────────────────────────────────────────
def fetch_ziprecruiter(all_jobs: dict, seen_ids: set):
    print("  Scanning ZipRecruiter...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {
                "search":   term,
                "location": f"{city}, {state}",
                "radius":   "25",
                "days":     "1",
            }
            url = "https://www.ziprecruiter.com/jobs-search/feed?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "Unknown Title").strip()
                    company  = entry.get("author", entry.get("source", {}).get("title", "Unknown Company"))
                    location = entry.get("location", f"{city}, {state}")
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "ZipRecruiter")
                    count += 1
            except Exception as e:
                print(f"    Warning - ZipRecruiter {term}/{city}: {e}")
    print(f"    Done: {count} raw entries scanned")


# ─────────────────────────────────────────────
# SOURCE 5 — CAREERBUILDER  (RSS)
# ─────────────────────────────────────────────
def fetch_careerbuilder(all_jobs: dict, seen_ids: set):
    print("  Scanning CareerBuilder...")
    count = 0
    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            params = {
                "keywords": term,
                "location": f"{city}, {state}",
                "radius":   "25",
            }
            url = "https://www.careerbuilder.com/jobs/rss?" + urllib.parse.urlencode(params)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title", "Unknown Title").strip()
                    company  = entry.get("author", "Unknown Company")
                    location = entry.get("cb_city", city)
                    if entry.get("cb_state"):
                        location += f", {entry['cb_state']}"
                    else:
                        location += f", {state}"
                    add_job(all_jobs, seen_ids, title, company, location,
                            entry.get("link", ""), entry.get("published", ""), "CareerBuilder")
                    count += 1
            except Exception as e:
                print(f"    Warning - CareerBuilder {term}/{city}: {e}")
    print(f"    Done: {count} raw entries scanned")


# ─────────────────────────────────────────────
# MAIN FETCHER
# ─────────────────────────────────────────────
def fetch_jobs() -> list[dict]:
    seen_ids = load_seen_jobs()
    all_jobs = {}

    print(f"Scanning {len(SEARCH_TERMS)} terms x {len(LOCATIONS)} locations across 5 sources...")
    fetch_indeed(all_jobs, seen_ids)
    fetch_linkedin(all_jobs, seen_ids)
    fetch_usajobs(all_jobs, seen_ids)
    fetch_ziprecruiter(all_jobs, seen_ids)
    fetch_careerbuilder(all_jobs, seen_ids)

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
        "ZipRecruiter":  "#4a90d9",
        "CareerBuilder": "#e8432d",
    }

    if not jobs:
        body_content = """
        <div class="no-jobs">
            <p>No new IT/Helpdesk job postings found today in your target region.</p>
            <p>Check back tomorrow — the bot is still watching!</p>
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
        across NE Georgia, Western North Carolina, and Colorado.</p>
        <p class="source-summary">{summary_badges}</p>
        <table>
            <thead>
                <tr>
                    <th>Job Title</th>
                    <th>Employer</th>
                    <th>Location</th>
                    <th>Source</th>
                    <th>Posted</th>
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
    <p>Daily digest — NE Georgia · Western North Carolina · Colorado</p>
    <span class="badge">Date: {now}</span>
  </div>
  <div class="body">{body_content}</div>
  <div class="footer">
    <p style="margin-bottom:10px; font-size:13px; color:#718096; background:#fffbeb; border:1px solid #f6e05e; border-radius:6px; padding:10px 16px; text-align:left;">
      <strong style="color:#b7791f;">&#9432; Reminder:</strong> Degree requirements are not shown in this summary.
      Please click each job link to review the full description and verify education requirements before applying.
    </p>
    <p>Sources: Indeed · LinkedIn · USAJobs · ZipRecruiter · CareerBuilder</p>
    <p style="margin-top:6px;">
      <span class="region-tag">NE Georgia</span>
      <span class="region-tag">Western NC</span>
      <span class="region-tag">Colorado Mountains</span>
    </p>
    <p style="margin-top:10px;">Automated daily at 7:00 AM ET</p>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# EMAIL SENDER  (Gmail SMTP)
# ─────────────────────────────────────────────
def send_email(jobs: list[dict]):
    now_str = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
    subject = f"IT Job Alert - {len(jobs)} New Listing{'s' if len(jobs) != 1 else ''} - {now_str}"
    if not jobs:
        subject = f"IT Job Alert - No New Listings Today - {now_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    html_part = MIMEText(build_html_email(jobs), "html")
    msg.attach(html_part)

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
    print("  IT / Helpdesk Job Alert Bot - Multi-Source")
    print(f"  {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 55)
    jobs = fetch_jobs()
    send_email(jobs)
    print("Done.")
