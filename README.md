# 🚀 AI-Powered Daily Lead Generation & Scraping Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Celery](https://img.shields.io/badge/Celery-Distributed%20Queue-37814A.svg)](https://docs.celeryq.dev/)

A production-grade, self-hosted, open-source lead generation and qualification platform. Designed to continuously discover local and global businesses on **Google Places / Google Maps**, inspect their web infrastructure safely, score service opportunities using **AI Decision Intelligence**, and automatically synchronize 50+ qualified leads daily to your **Google Sheet**.

---

## 🌟 Key Features

- **Automated Daily Discovery**: Automatically crawls Google Places daily at 02:00 UTC via Celery Beat or on-demand via REST API.
- **Configurable Locations & Categories in `.env`**: Easily specify your target cities (e.g., `KGF, Bangarapet, Bangalore, London, New York`) and business categories directly in `.env`.
- **Frontend API & CORS Controls**: Toggle API access for external frontends or admin dashboards on/off (`ENABLE_FRONTEND_API=true/false`) with strict CORS origin whitelisting.
- **Documentation Toggle**: Enable or disable interactive Swagger UI (`/docs`) in production via `.env` (`ENABLE_API_DOCS=true/false`).
- **Safe Web Infrastructure Inspection**: Analyzes websites for SSL/HTTPS, responsiveness, security headers, technology stack, and public contact information (with strict SSRF defense).
- **Jev AI Qualification Engine**: Evaluates service gaps (`NO_WEBSITE`, `WEBSITE_SECURITY`, `WEBSITE_REBUILD`, `ECOMMERCE_OPPORTUNITY`) and calculates deterministic + AI hybrid lead scores.
- **6-Tier Deduplication**: Guarantees zero duplicate leads across runs (deduplicating by Place ID, phone, domain, normalized name + address, and fuzzy matching).
- **Google Sheets Cumulative Sync**: Automatically appends new leads daily with verified phone numbers, scores, matching opportunity dropdowns, and **clickable Google Maps search links**.
- **Offline / Mock Mode**: Fully testable offline without spending external API credits (`MOCK_PROVIDERS=true`).

---

## 🏗️ Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│        Frontend / Admin Dashboard (Next.js / Vite / React)    │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTPS REST API (JWT / API Key)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI API Gateway                       │
│    (CORS Control, SSRF Protection, JWT Auth & Rate Limiter)  │
└──────────────────────────────┬───────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌───────────────────────┐             ┌────────────────────────┐
│ PostgreSQL / Supabase │             │   Redis & Celery Queue │
│ (Relational Storage)  │             │ (Background Discovery) │
└───────────────────────┘             └───────────┬────────────┘
                                                  │
            ┌───────────────────┬─────────────────┴─────────────────┬──────────────────┐
            ▼                   ▼                                   ▼                  ▼
┌─────────────────────┐ ┌───────────────┐                 ┌───────────────────┐ ┌───────────────┐
│ Apify Google Places │ │ Apollo.io     │                 │ typesafe/jev      │ │ Google Sheets │
│ Discovery Crawler   │ │ Contact Enrich│                 │ AI Decision Layer │ │ Daily Sync    │
└─────────────────────┘ └───────────────┘                 └───────────────────┘ └───────────────┘
```

---

## 🚀 Quick Start (Docker - Recommended)

The fastest way to deploy the entire stack (PostgreSQL, Redis, FastAPI, Celery Worker, Celery Beat scheduler, and Caddy with automatic HTTPS) is using Docker:

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/leadgen-platform.git
cd leadgen-platform
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
nano .env   # Or open in your favorite code editor
```

Configure your target cities, categories, and provider keys (see [Configuration Guide](#-configuration-guide) below).

### 3. Build & Launch the Containers
```bash
docker-compose up -d --build
```

### 4. Verify Stack Status
```bash
docker ps
```
You should see 6 healthy containers running:
- `leadgen_caddy` (Ports `80` & `443`)
- `leadgen_api` (Port `8000`)
- `leadgen_worker` (Celery background processor)
- `leadgen_beat` (Celery scheduler)
- `leadgen_postgres` (PostgreSQL 16)
- `leadgen_redis` (Redis 7)

Check the API health:
```bash
curl http://localhost:8000/health
```

---

## ⚙️ Configuration Guide

### 1. Target Cities & Business Categories in `.env`
Specify the locations and categories you want the system to scrape daily:

```env
# Comma-separated list of target cities / regions
DEFAULT_SCRAPE_LOCATIONS=KGF, Bangarapet, Bangalore

# Comma-separated list of target business niches
DEFAULT_SCRAPE_CATEGORIES=Dental Clinic, Healthcare Clinic, Software Company, Digital Marketing, Retail

# Daily target lead quota
DEFAULT_DAILY_LEAD_LIMIT=50
```

> 💡 **Tip:** You can enter any locations (e.g. `New York, San Francisco`, `London, Manchester`, `Mumbai, Pune, Bangalore`) and any categories (e.g. `Real Estate Agency`, `Restaurants`, `Gym`, `Accounting Firm`).

---

### 2. Frontend API & CORS Controls
Control whether external frontends can access the API, and toggle documentation endpoints:

```env
# Enable or disable API access for external frontends (true/false)
ENABLE_FRONTEND_API=true

# Allowed frontend origins (comma-separated, no trailing slashes)
CORS_ORIGINS=http://localhost:3000,https://admin.yourdomain.com

# Enable or disable interactive Swagger UI (/docs) and ReDoc (/redoc)
ENABLE_API_DOCS=true
```

- When `ENABLE_FRONTEND_API=false`, cross-origin requests are blocked, securing the API for backend/cron use only.
- When `ENABLE_API_DOCS=false`, Swagger documentation routes (`/docs`, `/redoc`, `/openapi.json`) are disabled for production hardening.

---

### 3. Google Sheets Integration Setup
To synchronize qualified leads to your Google Sheet:

1. **Google Cloud Console**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project and enable the **Google Sheets API**.
   - Create an **OAuth 2.0 Client ID** (Application type: *Web application*).
   - Set Authorized Redirect URIs to `https://developers.google.com/oauthplayground`.
2. **Obtain Refresh Token**:
   - Open [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground).
   - Click the gear icon (Settings) -> check **Use your own OAuth credentials** and enter your Client ID & Secret.
   - Authorize scope: `https://www.googleapis.com/auth/spreadsheets`.
   - Exchange authorization code for a **Refresh Token**.
3. **Configure `.env`**:
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
   GOOGLE_REFRESH_TOKEN=1//04...
   GOOGLE_SHEETS_SPREADSHEET_ID=your-google-sheet-id
   ```
4. **Google Sheet Columns Layout**:
   Your Google Sheet tab `Leads` will automatically be formatted with these exact columns:
   | Col | Header | Description |
   | :--- | :--- | :--- |
   | **A** | Business Name | Name of discovered business |
   | **B** | Owner Name | Verified decision maker / owner (if found) |
   | **C** | Email | Cleaned business email |
   | **D** | Phone | E.164 normalized phone (`+91...`) |
   | **E** | Location | City, District, State |
   | **F** | Website | Verified company website |
   | **G** | Category | Business industry / niche |
   | **H** | Lead Score | Calculated lead score (0–100) |
   | **I** | Opportunity | Dropdown: `NO_WEBSITE`, `WEBSITE_SECURITY`, `WEBSITE_REBUILD`, `ECOMMERCE_OPPORTUNITY` |
   | **J** | Lead Status | Dropdown: `NEW`, `CONTACTED`, `QUALIFIED`, `CLOSED` |
   | **K** | Source | Discovery source (`apify`) |
   | **L** | Created At | ISO 8601 Timestamp |
   | **M** | Google Maps / Source Link | Clickable direct Google Maps search link |

---

### 4. Apify (Google Places Scraper) Setup
1. Create a free account at [Apify.com](https://apify.com/) (includes $5 monthly free credits).
2. Go to **Settings -> Integrations** and copy your **Personal API Token**.
3. Add to `.env`:
   ```env
   APIFY_API_TOKEN=apify_api_...
   APIFY_ACTOR_ID=compass~crawler-google-places
   MOCK_PROVIDERS=false
   ```

---

## 🏃 Running the Daily Scraping Pipeline

### Automatic Daily Execution (Celery Beat)
The background scheduler runs every day automatically at **02:00 AM UTC**:
1. Pulls the locations and categories configured in `.env`.
2. Crawls fresh places from Google Maps via Apify.
3. Performs 6-tier deduplication against existing database records.
4. Analyzes website performance, technology stack, and SSL security.
5. Scores and qualifies opportunities via `typesafe/jev-latest`.
6. Appends fresh leads to your Google Sheet without overwriting previous entries.

### Manual Execution on Demand
You can trigger today's scrape at any time using:

**Option A: REST API**
```bash
curl -X POST http://localhost:8000/api/v1/campaigns/daily-sync \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Option B: Python Runner Script**
```bash
python3 scripts/start_daily_pipeline.py
```

**Option C: Wake, Scrape & Sleep Script (Lowest VPS Resource Usage)**
```bash
./scripts/run_and_sleep.sh
```

---

## 💤 Low-Resource Idle Mode & VPS Crontab Setup

To prevent Docker containers from constantly consuming RAM and CPU on your VPS between scraping runs, you can choose between two idle optimization methods:

### Method 1: Automatic Autoscaling (Zero Configuration)
The Celery worker in `docker-compose.yml` is configured with `--autoscale=4,1` and memory limits:
- **Idle (No tasks)**: Automatically scales down to **1 idle process** sleeping on Redis BRPOP (~0.0% CPU, ~99MB RAM).
- **Active (When scraping)**: Instantly wakes up, scales up to **4 worker threads**, completes discovery and Google Sheets sync, and immediately scales back down to idle mode.

---

### Method 2: Wake, Scrape & Sleep via Linux Crontab (0% CPU / 0 MB RAM Between Runs)

If you want the background workers to be **completely stopped** between runs so that your VPS remains 100% idle until scraping time, use the provided [scripts/run_and_sleep.sh](scripts/run_and_sleep.sh).

#### What the script does:
1. Wakes up the Docker containers (`docker compose up -d`).
2. Scrapes fresh leads from Google Places, scores them, and appends them to your Google Sheet.
3. Automatically shuts down the heavy worker and beat containers (`docker compose stop worker beat`) until the next scheduled run.

#### How to Set Up in VPS Crontab:

1. Open your VPS crontab editor:
   ```bash
   crontab -e
   ```

2. If prompted, select your preferred editor (e.g. `1` for nano).

3. Add one of the following cron schedules at the bottom of the file (replace `/home/codesec/ledgen` with your actual repository path):

   **Example: Run every night at 02:00 AM:**
   ```cron
   0 2 * * * /home/codesec/ledgen/scripts/run_and_sleep.sh >> /home/codesec/ledgen/daily_scrape.log 2>&1
   ```

   **Example: Run every morning at 09:00 AM:**
   ```cron
   0 9 * * * /home/codesec/ledgen/scripts/run_and_sleep.sh >> /home/codesec/ledgen/daily_scrape.log 2>&1
   ```

   **Example: Run twice a day (09:00 AM and 09:00 PM):**
   ```cron
   0 9,21 * * * /home/codesec/ledgen/scripts/run_and_sleep.sh >> /home/codesec/ledgen/daily_scrape.log 2>&1
   ```

4. Save and exit (in nano: press `Ctrl+O`, `Enter`, then `Ctrl+X`).

5. Verify that your cron job is active:
   ```bash
   crontab -l
   ```

6. To monitor the live log output during a run:
   ```bash
   tail -f /home/codesec/ledgen/daily_scrape.log
   ```

---

## 🛠️ Local Development (Without Docker)

### 1. Prerequisites
- Python 3.12+
- PostgreSQL & Redis running locally

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Migrations & Seed Admin User
```bash
alembic upgrade head
python3 scripts/seed_admin.py
```

### 4. Run API Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger UI will be available at `http://localhost:8000/docs`.

### 5. Run Celery Worker & Scheduler
In two separate terminal windows:
```bash
# Terminal 1: Worker
celery -A app.workers.celery_app.celery_app worker --loglevel=info

# Terminal 2: Scheduler
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

---

## 🧪 Testing Suite

Run the unit and integration test suite:

```bash
# Run all unit tests
pytest -v

# Run live endpoint verification against Docker stack
python3 scripts/test_live_endpoints.py
```

---

## 📚 Complete `.env` Reference

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DEFAULT_SCRAPE_LOCATIONS` | Target cities / areas | `KGF, Bangarapet, Bangalore` |
| `DEFAULT_SCRAPE_CATEGORIES` | Target industries / niches | `Dental Clinic, Software Company` |
| `DEFAULT_DAILY_LEAD_LIMIT` | Target daily lead quota | `50` |
| `ENABLE_FRONTEND_API` | Allow external frontends to connect | `true` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `http://localhost:3000` |
| `ENABLE_API_DOCS` | Toggle `/docs` and `/redoc` | `true` |
| `MOCK_PROVIDERS` | Toggle offline mock testing mode | `false` |
| `APIFY_API_TOKEN` | Apify Personal API token | `apify_api_...` |
| `APIFY_ACTOR_ID` | Actor used for Google Places crawl | `compass~crawler-google-places` |
| `APOLLO_API_KEY` | Apollo.io API key for contact enrichment | `your-apollo-key` |
| `OPENROUTER_API_KEY` | OpenRouter API Key for Jev LLM | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | Decision model ID | `typesafe/jev-latest` |
| `GOOGLE_CLIENT_ID` | Google OAuth2 Client ID | `*.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 Client Secret | `GOCSPX-...` |
| `GOOGLE_REFRESH_TOKEN` | Google OAuth2 Refresh Token | `1//04...` |
| `GOOGLE_SHEETS_SPREADSHEET_ID`| Destination Google Sheet ID | `1jrpFDTL2cmQ6nAYPj...` |
| `ADMIN_EMAIL` | Initial admin account email | `admin@codesec.me` |
| `ADMIN_PASSWORD` | Initial admin account password | `YourSecurePassword!` |
| `JWT_SECRET` | 32+ char secret for JWT tokens | `7e8fabce7d9a...` |

---

## 🔒 Security Best Practices

- **Strict SSRF Mitigation**: The website crawler validates all domains and blocks loopback, private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and AWS/GCP metadata endpoints (`169.254.169.254`).
- **Secret Masking in Logs**: API keys and tokens are automatically redacted from console logs.
- **Isolated Network Architecture**: Redis and PostgreSQL are hosted in private Docker bridge networks and never exposed publicly.
- **Zero Hallucination Guarantee**: Fields that cannot be verified remain empty (`NULL`), preserving data integrity.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to your branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
