# IT & Helpdesk Job Alert Bot

Scans Indeed daily for IT/Helpdesk roles across **NE Georgia and Western North Carolina**
and sends you a formatted HTML email digest every morning at 7:00 AM ET.

---

## 📍 Search Region

The bot covers a loop from **Suwanee, GA** north to **Clayton, GA**, across to
**Cherokee, NC**, west to **Murphy, NC**, and back — including all towns in between
with a 25-mile radius around each.

---

## 🔍 Job Titles Searched

- Help Desk Technician
- IT Support Specialist
- Desktop Support Technician
- Service Desk Analyst
- IT Technician
- Technical Support Specialist
- Entry Level IT Support
- Computer Support Technician
- Systems Support Technician
- Network Support Technician

---

## 🚀 Setup Guide (One-Time, ~15 minutes)

### Step 1 — Create a GitHub account
Go to [github.com](https://github.com) and sign up for a free account.

### Step 2 — Create a new repository
1. Click the **+** icon → **New repository**
2. Name it something like `it-job-alert`
3. Set it to **Private** (recommended)
4. Click **Create repository**

### Step 3 — Upload the files
Upload these files to the root of your repo:
- `job_scraper.py`
- `requirements.txt`

Then create this folder path and upload the workflow:
- `.github/workflows/daily_job_alert.yml`

> **Tip:** You can drag-and-drop files directly in the GitHub web interface.

### Step 4 — Set up an Outlook App Password
Because Outlook blocks basic passwords for automated apps, you need an **App Password**:

1. Go to [account.microsoft.com/security](https://account.microsoft.com/security)
2. Click **Advanced security options**
3. Under **App passwords**, click **Create a new app password**
4. Copy the generated password (you'll only see it once!)

> ⚠️ If you use two-factor authentication (you should!), App Passwords are required.
> If you don't have 2FA enabled, you may be able to use your regular password — but
> enabling 2FA is strongly recommended.

### Step 5 — Add your secrets to GitHub
In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**.

Add these three secrets:

| Secret Name       | Value                                      |
|-------------------|--------------------------------------------|
| `SENDER_EMAIL`    | your Outlook address (e.g. you@outlook.com)|
| `SENDER_PASSWORD` | the App Password from Step 4               |
| `RECIPIENT_EMAIL` | where you want alerts sent (can be same)   |

### Step 6 — Enable Actions
1. Click the **Actions** tab in your repo
2. Click **I understand my workflows, go ahead and enable them**

### Step 7 — Test it manually
1. Go to **Actions** tab
2. Click **IT Job Alert — Daily Run**
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — you should receive an email within a minute!

---

## ⏰ Schedule
The bot runs automatically every day at **7:00 AM Eastern Time**.
You can change this in `.github/workflows/daily_job_alert.yml` by editing the cron line:
```
- cron: "0 11 * * *"   ← 11:00 UTC = 7:00 AM ET
```

---

## 💡 Customization Tips

**Add more locations:** Edit the `LOCATIONS` list in `job_scraper.py`

**Add more search terms:** Edit the `SEARCH_TERMS` list in `job_scraper.py`

**Expand the search radius:** Change `"radius": "25"` to `"50"` for a 50-mile radius

**Run twice a day:** Add a second cron line:
```yaml
- cron: "0 11 * * *"   # 7 AM ET
- cron: "0 17 * * *"   # 1 PM ET
```

---

## 🆓 Cost
**Completely free.** GitHub Actions gives you 2,000 free minutes/month.
This bot uses about 2–3 minutes per run × 30 days = ~75 minutes/month.

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| No email received | Check GitHub Actions logs for errors; verify secrets are set correctly |
| "Authentication failed" | Re-generate your Outlook App Password |
| Getting duplicate jobs | The `seen_jobs.json` cache handles this — let it run for a day |
| Workflow not running | Make sure Actions are enabled in repo Settings |
