# ServiceNow Incident Daily Reporter

## 1. Setup

```bash
git clone <repo-url> servicenow_reporter
cd servicenow_reporter
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env       # edit SMTP credentials
```

Edit `config/config.yaml` to set folders, recipients, and thresholds.

## 2. Run on demand

```bash
python -m src.main
```

## 3. Run as scheduled daemon

```bash
python -m src.scheduler_runner
```

## 4. Schedule with Windows Task Scheduler

1. Open Task Scheduler → **Create Basic Task**.
2. Trigger: Daily at `08:30`.
3. Action: **Start a Program**
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `-m src.main`
   - Start in: `C:\path\to\servicenow_reporter`
4. Check **Run whether user is logged on or not** and **Run with highest privileges**.

## 5. Schedule with Linux cron

```bash
crontab -e
# Run daily at 08:30
30 8 * * * cd /opt/servicenow_reporter && /opt/servicenow_reporter/.venv/bin/python -m src.main >> logs/cron.log 2>&1
```

## 6. Logs

Rotating logs are written to `logs/reporter.log` (kept 14 days by default).
Failure notifications are emailed automatically to the configured recipients.

## 7. Folder Conventions

- `input/`  – drop the latest ServiceNow Excel export here.
- `output/` – generated HTML + XLSX reports.
- `logs/`   – rotated log files.
