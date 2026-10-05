import json
import os
import sys
import time
import httpx
from dotenv import dotenv_values

config = dotenv_values(".env")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = config.get("ADMIN_EMAIL", "admin@codesec.me")
ADMIN_PASSWORD = config.get("ADMIN_PASSWORD", "changeme-admin-password")

print(f"================================================================")
print(f"🚀 RUNNING END-TO-END REST API TESTS AGAINST LIVE DOCKER STACK")
print(f"Target URL: {BASE_URL}")
print(f"Admin User: {ADMIN_EMAIL}")
print(f"================================================================")

client = httpx.Client(base_url=BASE_URL, timeout=30.0)

passed = 0
failed = 0

def test(name, func):
    global passed, failed
    print(f"\n[TEST] {name} ...", end=" ", flush=True)
    try:
        func()
        print("✅ PASSED")
        passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1

token = None
headers = {}
created_campaign_id = None
created_lead_id = None
created_api_key_id = None
discovery_job_id = None

# 1. Health Endpoints
def test_health():
    res = client.get("/health")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
test("1.1 GET /health (Health & DB/Redis status)", test_health)

def test_health_live():
    res = client.get("/health/live")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert res.json()["status"] == "alive"
test("1.2 GET /health/live (Liveness probe)", test_health_live)

def test_health_ready():
    res = client.get("/health/ready")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert res.json()["status"] == "ready"
test("1.3 GET /health/ready (Readiness probe)", test_health_ready)

def test_openapi():
    res = client.get("/openapi.json")
    assert res.status_code == 200
    data = res.json()
    assert "paths" in data
    assert len(data["paths"]) >= 20
test("1.4 GET /openapi.json (OpenAPI 3.1 Schema)", test_openapi)

# 2. Authentication
def test_login():
    global token, headers
    res = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
test("2.1 POST /api/v1/auth/login (JWT Token Issuance)", test_login)

def test_auth_me():
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["email"] == ADMIN_EMAIL
    assert data["is_superuser"] is True
test("2.2 GET /api/v1/auth/me (Read User Profile)", test_auth_me)

def test_api_keys():
    global created_api_key_id
    # Create
    res = client.post("/api/v1/auth/api-keys", headers=headers, json={"name": "Docker CI Key"})
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert "api_key" in data
    assert data["name"] == "Docker CI Key"
    created_api_key_id = data["id"]

    # List
    res = client.get("/api/v1/auth/api-keys", headers=headers)
    assert res.status_code == 200
    keys = res.json()
    assert any(k["id"] == created_api_key_id for k in keys)

    # Delete
    res = client.delete(f"/api/v1/auth/api-keys/{created_api_key_id}", headers=headers)
    assert res.status_code == 204
test("2.3 API Key Lifecycle (POST / GET / DELETE)", test_api_keys)

# 3. Provider Status
def test_provider_status():
    res = client.get("/api/v1/providers/status", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    providers = {p["provider"]: p for p in data["providers"]}
    assert "apify" in providers
    assert "apollo" in providers
    assert "openrouter" in providers
    assert "google_sheets" in providers
test("3.1 GET /api/v1/providers/status (Apify, Apollo, OpenRouter, Sheets)", test_provider_status)

# 4. Campaigns
def test_create_campaign():
    global created_campaign_id
    payload = {
        "name": f"Live Docker Verification Campaign {int(time.time())}",
        "description": "Automated verification test run against PostgreSQL & Redis",
        "locations": ["Bangalore, India"],
        "categories": ["Software Company"],
        "max_leads": 10,
        "enrich_contacts": True,
        "analyze_websites": True,
        "ai_qualification": True,
        "google_sheet_sync": False,
        "max_apollo_credits": 20,
        "max_ai_requests": 20
    }
    res = client.post("/api/v1/campaigns", headers=headers, json=payload)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "DRAFT"
    created_campaign_id = data["id"]
test("4.1 POST /api/v1/campaigns (Create Campaign)", test_create_campaign)

def test_get_campaign():
    res = client.get(f"/api/v1/campaigns/{created_campaign_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == created_campaign_id
test("4.2 GET /api/v1/campaigns/{id} (Retrieve Campaign)", test_get_campaign)

def test_list_campaigns():
    res = client.get("/api/v1/campaigns", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert any(c["id"] == created_campaign_id for c in data["items"])
test("4.3 GET /api/v1/campaigns (List Campaigns)", test_list_campaigns)

def test_update_campaign():
    res = client.patch(
        f"/api/v1/campaigns/{created_campaign_id}",
        headers=headers,
        json={"description": "Updated description by Docker test"}
    )
    assert res.status_code == 200
    assert res.json()["description"] == "Updated description by Docker test"
test("4.4 PATCH /api/v1/campaigns/{id} (Update Campaign)", test_update_campaign)

# 5. Start Campaign & Background Pipeline Execution
def test_start_campaign():
    global discovery_job_id
    res = client.post(f"/api/v1/campaigns/{created_campaign_id}/run", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "job_id" in data
    discovery_job_id = data["job_id"]
test("5.1 POST /api/v1/campaigns/{id}/run (Trigger Celery Pipeline)", test_start_campaign)

def test_poll_discovery_job():
    print("(Polling Celery discovery job...", end=" ", flush=True)
    max_wait = 90
    start = time.time()
    completed = False
    while time.time() - start < max_wait:
        res = client.get(f"/api/v1/jobs/{discovery_job_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        if data["status"] in ("completed", "failed"):
            completed = True
            assert data["status"] == "completed", f"Job failed: {data.get('error_message')}"
            assert data["successful"] > 0, "Expected at least 1 discovered lead"
            print(f"Finished: {data['successful']} leads in {time.time()-start:.1f}s)", end=" ", flush=True)
            break
        time.sleep(1.0)
    assert completed, f"Job did not finish within {max_wait}s"
test("5.2 GET /api/v1/jobs/{job_id} (Poll Discovery Progress)", test_poll_discovery_job)

def test_campaign_stats():
    res = client.get(f"/api/v1/campaigns/{created_campaign_id}/stats", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_leads" in data
    assert data["total_leads"] > 0
    assert "average_score" in data
test("5.3 GET /api/v1/campaigns/{id}/stats (Campaign Metrics & Analytics)", test_campaign_stats)

def test_campaign_pause_resume():
    res = client.post(f"/api/v1/campaigns/{created_campaign_id}/pause", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "PAUSED"

    res = client.post(f"/api/v1/campaigns/{created_campaign_id}/resume", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "QUEUED"
test("5.4 POST /api/v1/campaigns/{id}/(pause|resume)", test_campaign_pause_resume)

# 6. Leads Intelligence Endpoints
def test_list_leads():
    global created_lead_id
    res = client.get(f"/api/v1/leads?campaign_id={created_campaign_id}", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0, "Expected leads in campaign"
    created_lead_id = data["items"][0]["id"]
test("6.1 GET /api/v1/leads (Filter Leads by Campaign)", test_list_leads)

def test_get_campaign_leads():
    res = client.get(f"/api/v1/campaigns/{created_campaign_id}/leads", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) > 0
test("6.2 GET /api/v1/campaigns/{id}/leads (Campaign Leads Sub-resource)", test_get_campaign_leads)

def test_get_lead_detail():
    res = client.get(f"/api/v1/leads/{created_lead_id}", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["id"] == created_lead_id
    assert "business_name" in data
test("6.3 GET /api/v1/leads/{id} (Detailed Lead Intelligence Profile)", test_get_lead_detail)

def test_update_lead():
    res = client.patch(
        f"/api/v1/leads/{created_lead_id}",
        headers=headers,
        json={"category": "Enterprise Software"}
    )
    assert res.status_code == 200
    assert res.json()["category"] == "Enterprise Software"
test("6.4 PATCH /api/v1/leads/{id} (Update Lead Record)", test_update_lead)

def test_update_outreach_notes():
    res = client.post(
        f"/api/v1/leads/{created_lead_id}/notes",
        headers=headers,
        json={"contact_notes": "Outreach initiated via phone"}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["contact_notes"] == "Outreach initiated via phone"
test("6.5 POST /api/v1/leads/{id}/notes (CRM Notes Update)", test_update_outreach_notes)

def test_mark_contacted():
    res = client.post(f"/api/v1/leads/{created_lead_id}/contacted", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert res.json()["status"] == "CONTACTED"
test("6.6 POST /api/v1/leads/{id}/contacted (CRM Mark Contacted)", test_mark_contacted)

# 7. Intelligence & Enrichment Trigger Endpoints
def test_enrich_lead():
    res = client.post(f"/api/v1/leads/{created_lead_id}/enrich", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert "job_id" in res.json()
test("7.1 POST /api/v1/leads/{id}/enrich (Trigger Apollo Enrichment Job)", test_enrich_lead)

def test_ai_analysis():
    res = client.post(f"/api/v1/leads/{created_lead_id}/ai-analysis", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert "job_id" in res.json()
test("7.2 POST /api/v1/leads/{id}/ai-analysis (Trigger Jev AI Qualification)", test_ai_analysis)

# 8. Jobs List
def test_jobs_list():
    res = client.get("/api/v1/jobs", headers=headers)
    assert res.status_code == 200
    assert "items" in res.json()
    assert res.json()["total"] > 0
test("8.1 GET /api/v1/jobs (List Background Pipeline Jobs)", test_jobs_list)

# 9. Provider Usage Tracking
def test_usage_summary():
    res = client.get("/api/v1/usage", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "total_requests" in data
    assert "total_estimated_cost" in data
test("9.1 GET /api/v1/usage (Cost & Credit Aggregates)", test_usage_summary)

def test_usage_provider_logs():
    res = client.get("/api/v1/usage/apify", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
test("9.2 GET /api/v1/usage/{provider_name} (Itemized Provider Logs)", test_usage_provider_logs)

# 10. Google Sheets Sync
def test_sheets_status():
    res = client.get("/api/v1/google-sheets/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "status" in data
test("10.1 GET /api/v1/google-sheets/status (Sheets Integration Status)", test_sheets_status)

def test_sheets_export_campaign():
    res = client.post(
        f"/api/v1/google-sheets/export/campaign/{created_campaign_id}",
        headers=headers,
        json={"sheet_name": "Docker_Test_Leads"}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "export_id" in data
    assert data["status"] in ("completed", "pending")
test("10.2 POST /api/v1/google-sheets/export/campaign/{id} (Export Campaign to Sheets)", test_sheets_export_campaign)

print(f"\n================================================================")
print(f"🏁 ALL TESTS FINISHED: {passed} PASSED, {failed} FAILED")
print(f"================================================================")

if failed > 0:
    sys.exit(1)
