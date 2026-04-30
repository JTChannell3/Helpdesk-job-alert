"""
IT/Helpdesk Job Alert Bot
Scrapes Indeed RSS feeds for IT roles in NE Georgia / Western North Carolina region
Sends daily HTML email digest via Outlook SMTP
"""

import feedparser
import smtplib
import json
import os
import hashlib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# CONFIGURATION  (override via environment vars)
# ─────────────────────────────────────────────
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", "your_email@outlook.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "your_app_password")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_email@outlook.com")

# File to track already-seen job IDs (persisted between runs via GitHub Actions cache)
SEEN_JOBS_FILE  = "seen_jobs.json"

# ─────────────────────────────────────────────
# SEARCH TERMS
# ─────────────────────────────────────────────
SEARCH_TERMS = [
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
]

# ─────────────────────────────────────────────
# TARGET LOCATIONS  (city, state pairs)
# Covers the loop: Suwanee GA → Clayton GA → Cherokee NC → Murphy NC → back
# ─────────────────────────────────────────────
LOCATIONS = [
    # Georgia corridor
    ("Suwanee",       "GA"),
    ("Lawrenceville", "GA"),
    ("Gainesville",   "GA"),
    ("Cumming",       "GA"),
    ("Dahlonega",     "GA"),
    ("Cleveland",     "GA"),
    ("Toccoa",        "GA"),
    ("Cornelia",      "GA"),
    ("Clayton",       "GA"),
    ("Blue Ridge",    "GA"),
    ("Ellijay",       "GA"),
    ("Jasper",        "GA"),
    ("Canton",        "GA"),
    ("Ball Ground",   "GA"),
    ("Athens",        "GA"),
    ("Alpharetta",    "GA"),
    ("Kennesaw",      "GA"),
    ("Marietta",      "GA"),
    ("Rome",          "GA"),
    ("Dalton",        "GA"),
    # North Carolina corridor
    ("Murphy",        "NC"),
    ("Andrews",       "NC"),
    ("Robbinsville",  "NC"),
    ("Hayesville",    "NC"),
    ("Brasstown",     "NC"),
    ("Cherokee",      "NC"),
    ("Sylva",         "NC"),
    ("Franklin",      "NC"),
    ("Highlands",     "NC"),
    ("Asheville",     "NC"),
    ("Waynesville",   "NC"),
    ("Brevard",       "NC"),
    ("Hendersonville","NC"),
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
]

# ─────────────────────────────────────────────
# RSS FEED BUILDER
# ─────────────────────────────────────────────
def build_indeed_rss_url(query: str, city: str, state: str) -> str:
    """Build an Indeed RSS feed URL for a given query and location."""
    import urllib.parse
    params = {
        "q":      query,
        "l":      f"{city}, {state}",
        "radius": "25",          # 25-mile radius around each city
        "sort":   "date",
        "limit":  "25",
        "fromage": "1",          # Posted in last 1 day
    }
    base = "https://www.indeed.com/rss?"
    return base + urllib.parse.urlencode(params)


# ─────────────────────────────────────────────
# DEDUPLICATION HELPERS
# ─────────────────────────────────────────────
def load_seen_jobs() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen: set):
    # Keep only the last 5000 IDs to prevent unbounded growth
    seen_list = list(seen)[-5000:]
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_list, f)


def job_id(title: str, company: str, location: str) -> str:
    """Stable hash used as a unique job identifier."""
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


# ─────────────────────────────────────────────
# FEED FETCHER
# ─────────────────────────────────────────────
def fetch_jobs() -> list[dict]:
    """Fetch all jobs from Indeed RSS feeds, deduplicated by title+company+location."""
    seen_ids   = load_seen_jobs()
    all_jobs   = {}   # jid → job dict  (dedup within this run)

    print(f"🔍 Scanning {len(SEARCH_TERMS)} search terms × {len(LOCATIONS)} locations …")

    for term in SEARCH_TERMS:
        for city, state in LOCATIONS:
            url = build_indeed_rss_url(term, city, state)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title    = entry.get("title",   "Unknown Title").split(" - ")[0].strip()
                    company  = entry.get("author",  "Unknown Company").strip()
                    location = entry.get("indeed_city", "") or city
                    if entry.get("indeed_state"):
                        location += f", {entry['indeed_state']}"
                    else:
                        location += f", {state}"
                    link     = entry.get("link", "")
                    posted   = entry.get("published", "")

                    jid = job_id(title, company, location)

                    # Skip if we've seen this job in a previous run
                    if jid in seen_ids:
                        continue

                    # Deduplicate within this run
                    if jid not in all_jobs:
                        all_jobs[jid] = {
                            "title":    title,
                            "company":  company,
                            "location": location,
                            "link":     link,
                            "posted":   posted,
                            "jid":      jid,
                        }
            except Exception as e:
                print(f"  ⚠️  Error fetching {term} / {city}, {state}: {e}")

    new_jobs = list(all_jobs.values())

    # Mark all found jobs as seen
    seen_ids.update(j["jid"] for j in new_jobs)
    save_seen_jobs(seen_ids)

    print(f"✅ Found {len(new_jobs)} new jobs.")
    return new_jobs


# ─────────────────────────────────────────────
# EMAIL BUILDER
# ─────────────────────────────────────────────
def build_html_email(jobs: list[dict]) -> str:
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%A, %B %d, %Y")

    if not jobs:
        body_content = """
        <div class="no-jobs">
            <p>🔍 No new IT/Helpdesk job postings found today in your target region.</p>
            <p>Check back tomorrow — the bot is still watching!</p>
        </div>
        """
    else:
        rows = ""
        for j in sorted(jobs, key=lambda x: x["location"]):
            rows += f"""
            <tr>
                <td><a href="{j['link']}" target="_blank">{j['title']}</a></td>
                <td>{j['company']}</td>
                <td>{j['location']}</td>
                <td class="date">{j['posted'][:16] if j['posted'] else '—'}</td>
            </tr>"""

        body_content = f"""
        <p class="summary">Found <strong>{len(jobs)} new listing{'s' if len(jobs) != 1 else ''}</strong> 
        matching your search across NE Georgia and Western North Carolina.</p>

        <table>
            <thead>
                <tr>
                    <th>Job Title</th>
                    <th>Employer</th>
                    <th>Location</th>
                    <th>Posted</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f4f8;
    color: #1a202c;
  }}
  .wrapper {{
    max-width: 860px;
    margin: 30px auto;
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }}
  .header {{
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    color: white;
    padding: 32px 40px;
  }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
  .header p  {{ font-size: 14px; opacity: 0.85; }}
  .badge {{
    display: inline-block;
    background: rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    margin-top: 10px;
    letter-spacing: 0.5px;
  }}
  .body {{ padding: 32px 40px; }}
  .summary {{ margin-bottom: 24px; font-size: 15px; color: #4a5568; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }}
  thead tr {{
    background: #edf2f7;
  }}
  th {{
    text-align: left;
    padding: 12px 14px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #718096;
    border-bottom: 2px solid #e2e8f0;
  }}
  td {{
    padding: 12px 14px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f7fafc; }}
  td a {{
    color: #2b6cb0;
    text-decoration: none;
    font-weight: 500;
  }}
  td a:hover {{ text-decoration: underline; }}
  td.date {{ color: #718096; white-space: nowrap; font-size: 12px; }}
  .no-jobs {{
    text-align: center;
    padding: 48px 24px;
    color: #718096;
    font-size: 15px;
    line-height: 1.8;
  }}
  .footer {{
    background: #f7fafc;
    padding: 20px 40px;
    font-size: 12px;
    color: #a0aec0;
    text-align: center;
    border-top: 1px solid #e2e8f0;
  }}
  .region-tag {{
    display: inline-block;
    background: #ebf8ff;
    color: #2b6cb0;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    margin: 2px;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>🖥️ IT &amp; Helpdesk Job Alert</h1>
    <p>Daily digest for NE Georgia &amp; Western North Carolina</p>
    <span class="badge">📅 {now}</span>
  </div>
  <div class="body">
    {body_content}
  </div>
  <div class="footer">
    <p>Search region: 
      <span class="region-tag">Suwanee, GA</span>
      <span class="region-tag">Gainesville, GA</span>
      <span class="region-tag">Clayton, GA</span>
      <span class="region-tag">Blue Ridge, GA</span>
      <span class="region-tag">Murphy, NC</span>
      <span class="region-tag">Cherokee, NC</span>
      + surrounding areas
    </p>
    <p style="margin-top:10px;">Powered by Indeed RSS feeds · Automated daily at 7:00 AM ET</p>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# EMAIL SENDER  (Gmail SMTP)
# ─────────────────────────────────────────────
def send_email(jobs: list[dict]):
    now_str = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
    subject = f"IT Job Alert — {len(jobs)} New Listing{'s' if len(jobs) != 1 else ''} · {now_str}"
    if not jobs:
        subject = f"IT Job Alert — No New Listings Today · {now_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    html_part = MIMEText(build_html_email(jobs), "html")
    msg.attach(html_part)

    print(f"📧 Sending email to {RECIPIENT_EMAIL} …")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print("✅ Email sent successfully!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  IT / Helpdesk Job Alert Bot")
    print(f"  {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 55)
    jobs = fetch_jobs()
    send_email(jobs)
    print("Done.")
