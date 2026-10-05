#!/usr/bin/env bash
# ==============================================================================
# Wake & Scrape: Low-Resource Cron Runner
# ==============================================================================
# This script is designed for VPS environments to:
# 1. Wake up the Docker stack if it is stopped / paused
# 2. Trigger the daily lead scraping & Google Sheets sync
# 3. Put worker and scheduler containers back to sleep when done
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================================"
echo "⏰ [$(date '+%Y-%m-%d %H:%M:%S')] WAKING UP DOCKER CONTAINERS..."
echo "======================================================================"

# Ensure core containers are running
docker compose up -d

# Wait briefly for services to be ready
echo "Waiting for services to be ready..."
sleep 5

echo "======================================================================"
echo "🚀 STARTING TODAY'S AUTOMATED SCRAPE & GOOGLE SHEETS SYNC..."
echo "======================================================================"

# Run the daily scraping and sync script inside the API container
docker exec leadgen_api python scripts/start_daily_pipeline.py

echo "======================================================================"
echo "💤 PUTTING BACKGROUND WORKERS BACK TO SLEEP (IDLE MODE)..."
echo "======================================================================"

# Optionally stop the heavy Celery worker until the next scheduled run
# to save RAM and CPU on low-memory VPS instances:
docker compose stop worker beat

echo "✅ [$(date '+%Y-%m-%d %H:%M:%S')] Daily job complete. Stack is now IDLE."
