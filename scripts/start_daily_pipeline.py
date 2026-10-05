import os
import sys
import time
import httpx
from dotenv import dotenv_values

config = dotenv_values(".env")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = config.get("ADMIN_EMAIL", "admin@codesec.me")
ADMIN_PASSWORD = config.get("ADMIN_PASSWORD", "hMLkFYY!4VV2sy")

print("=" * 70)
print("🚀 INITIALIZING DAILY 50+ LEADS AUTOMATION PIPELINE (TODAY'S RUN)")
print(f"API Base: {BASE_URL}")
print(f"Admin:    {ADMIN_EMAIL}")
print("=" * 70)

client = httpx.Client(base_url=BASE_URL, timeout=360.0)

# Step 1: Authenticate
login_res = client.post(
    "/api/v1/auth/login",
    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
)
if login_res.status_code != 200:
    print(f"❌ Login failed: {login_res.status_code} - {login_res.text}")
    sys.exit(1)

token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Authenticated successfully.")

# Step 2: Check or create the Daily 50+ Leads Campaign
list_res = client.get("/api/v1/campaigns?limit=50", headers=headers)
campaigns = list_res.json().get("items", []) if list_res.status_code == 200 else []

daily_campaign = None
for c in campaigns:
    if "Daily 50+ Leads" in c.get("name", ""):
        daily_campaign = c
        break

if daily_campaign:
    campaign_id = daily_campaign["id"]
    print(f"ℹ️ Found existing Daily Campaign: '{daily_campaign['name']}' ({campaign_id})")
else:
    campaign_payload = {
        "name": "Daily 50+ Leads Auto-Pipeline",
        "description": "Daily automated scraping, Jev qualification, Apollo enrichment, and Google Sheets sync for at least 50 leads/day",
        "locations": ["Bangalore, India", "Whitefield, Bangalore", "Indiranagar, Bangalore", "Koramangala, Bangalore"],
        "categories": ["Dental Clinic", "Healthcare Clinic", "Software Development", "Digital Marketing"],
        "max_leads": 60,
        "enrich_contacts": True,
        "analyze_websites": True,
        "ai_qualification": True,
        "google_sheet_sync": True,
        "max_apollo_credits": 60,
        "max_ai_requests": 60,
    }
    create_res = client.post("/api/v1/campaigns", headers=headers, json=campaign_payload)
    if create_res.status_code not in (200, 201):
        print(f"❌ Failed to create daily campaign: {create_res.status_code} - {create_res.text}")
        sys.exit(1)
    daily_campaign = create_res.json()
    campaign_id = daily_campaign["id"]
    print(f"✅ Created Daily Campaign: '{daily_campaign['name']}' ({campaign_id})")

# Ensure campaign is ACTIVE
client.put(f"/api/v1/campaigns/{campaign_id}", headers=headers, json={"status": "ACTIVE"})

# Step 3: Trigger today's live discovery run
print("\n" + "=" * 70)
print("📡 STARTING TODAY'S LIVE SCRAPE & GOOGLE SHEETS SYNC (AT LEAST 50 LEADS)...")
print("=" * 70)

run_res = client.post(f"/api/v1/campaigns/{campaign_id}/run", headers=headers)
if run_res.status_code not in (200, 201, 202):
    print(f"❌ Run trigger failed: {run_res.status_code} - {run_res.text}")
    sys.exit(1)

job_data = run_res.json()
job_id = job_data["job_id"]
print(f"✅ Job triggered with ID: {job_id} | Status: {job_data.get('status')}")

# Step 4: Monitor progress
start_time = time.time()
while True:
    time.sleep(10)
    elapsed = int(time.time() - start_time)
    job_status_res = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    if job_status_res.status_code != 200:
        print(f"[{elapsed}s] Waiting for job {job_id}...")
        continue
    j = job_status_res.json()
    stage = j.get("current_stage", "unknown")
    status = j.get("status", "unknown")
    progress = j.get("progress", 0)
    total = j.get("total", 0)
    successful = j.get("successful", 0)
    print(f"[{elapsed}s] Stage: {stage:<15} | Status: {status:<10} | Progress: {progress}% ({successful}/{total} leads)")

    if status in ("completed", "failed"):
        if status == "completed":
            print(f"\n🎉 Discovery job completed successfully in {elapsed}s!")
            print(f"Total leads processed: {successful}")
        else:
            print(f"\n❌ Discovery job failed: {j.get('error_message')}")
        break

print("\nFinished checking today's run.")
