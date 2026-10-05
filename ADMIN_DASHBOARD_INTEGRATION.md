# Next.js Admin Dashboard Integration Guide

This guide is specifically written for your existing **Next.js Admin Dashboard**. It outlines how to integrate with the **Lead Intelligence & Generation Backend REST API**, covering authentication, token handling, typed API clients, polling patterns, error handling, and recommended UI workflows.

---

## 1. Core Architecture & Mental Model

```text
┌─────────────────────────────────┐
│ Existing Next.js Admin Dashboard│
└────────────────┬────────────────┘
                 │
                 │ HTTPS (JSON over REST)
                 │ Bearer JWT Token
                 v
┌─────────────────────────────────┐
│    FastAPI Gateway (/api/v1)    │
└────────────────┬────────────────┘
                 │
                 │ Async Jobs / Events
                 v
┌─────────────────────────────────┐
│     Redis & Celery Workers      │
└────────────────┬────────────────┘
                 │
                 v
┌─────────────────────────────────┐
│ Supabase PostgreSQL DB & Sheets │
└─────────────────────────────────┘
```

1. **Backend Base URL**:
   In your Next.js project's `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   # In production:
   # NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

2. **Frontend Boundaries**:
   - The Next.js dashboard communicates **exclusively** with this FastAPI backend.
   - The frontend never connects directly to Apify, Apollo, OpenRouter, or Supabase service-role keys.

---

## 2. Authentication & Token Management

All non-public endpoints require an `Authorization: Bearer <access_token>` header.

### Secure Token Storage Pattern

> [!WARNING]
> Storing access tokens in `localStorage` exposes them to Cross-Site Scripting (XSS) attacks. For maximum security in your Next.js dashboard, adopt one of the following approaches:

1. **Recommended (Next.js Route Handlers / Cookies)**:
   - Your Next.js login page posts to a Next.js route handler (`app/api/auth/login/route.ts`).
   - The route handler calls the backend `POST /api/v1/auth/login`.
   - The route handler sets an `httpOnly`, `secure`, `sameSite=strict` cookie with the `access_token` and `refresh_token`.
   - Server components and proxy route handlers forward the Bearer token safely.
2. **Alternative (In-Memory Access Token + Refresh Token Rotation)**:
   - Store the short-lived access token in React state / memory.
   - On 401 response, call `POST /api/v1/auth/refresh` with the refresh token to get a fresh token.

---

## 3. Standard API Envelopes & Error Format

### Success Response Envelope
Paginated endpoints return:
```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 120,
  "total_pages": 3
}
```

### Standard Error Envelope
All error responses adhere to a uniform structure:
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid email or password.",
    "request_id": "7b3b9b41-2b0e-473d-8e6f-44da4cbf8a89",
    "details": {}
  }
}
```

---

## 4. Reusable TypeScript API Client (`lib/api.ts`)

Drop this file into your Next.js dashboard repository at `lib/api.ts`:

```typescript
// lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  requestId?: string;
  details?: Record<string, any>;
  statusCode: number;

  constructor(message: string, code: string, statusCode: number, requestId?: string, details?: Record<string, any>) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.statusCode = statusCode;
    this.requestId = requestId;
    this.details = details;
  }
}

let inMemoryToken: string | null = null;

export function setAccessToken(token: string | null) {
  inMemoryToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryToken;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null as unknown as T;
  }

  const data = await response.json();

  if (!response.ok) {
    const err = data.error || {};
    throw new ApiError(
      err.message || "API request failed",
      err.code || "UNKNOWN_ERROR",
      response.status,
      err.request_id,
      err.details
    );
  }

  return data as T;
}

// ==========================================
// TYPE DEFINITIONS
// ==========================================

export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface Campaign {
  id: string;
  name: string;
  description?: string;
  locations: string[];
  categories: string[];
  max_leads: number;
  enrich_contacts: boolean;
  analyze_websites: boolean;
  ai_qualification: boolean;
  google_sheet_sync: boolean;
  status: string;
  leads_discovered: number;
  leads_enriched: number;
  leads_scored: number;
  leads_exported: number;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  business_name: string;
  category?: string;
  subcategory?: string;
  phone?: string | null;
  email?: string | null;
  owner_name?: string | null;
  website?: string | null;
  has_website: boolean;
  address?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  lead_score: number;
  opportunity: string;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface JobStatus {
  id: string;
  campaign_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number; // 0 to 100
  current_stage: "queued" | "discovering" | "normalizing" | "deduplicating" | "analyzing" | "qualifying" | "enriching" | "scoring" | "exporting" | "completed";
  processed: number;
  total: number;
  successful: number;
  failed: number;
  error_message?: string;
}

export interface PaginatedResult<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// ==========================================
// API CLIENT FUNCTIONS
// ==========================================

// Authentication
export async function login(email: string, password: string) {
  const result = await apiFetch<{ access_token: string; refresh_token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(result.access_token);
  return result;
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/v1/auth/me");
}

// Campaigns
export async function createCampaign(data: {
  name: string;
  description?: string;
  locations: string[];
  categories: string[];
  max_leads?: number;
  enrich_contacts?: boolean;
  analyze_websites?: boolean;
  ai_qualification?: boolean;
  google_sheet_sync?: boolean;
}): Promise<Campaign> {
  return apiFetch<Campaign>("/api/v1/campaigns", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getCampaigns(page = 1, pageSize = 20): Promise<PaginatedResult<Campaign>> {
  return apiFetch<PaginatedResult<Campaign>>(`/api/v1/campaigns?page=${page}&page_size=${pageSize}`);
}

export async function getCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/api/v1/campaigns/${id}`);
}

export async function runCampaign(id: string): Promise<{ job_id: string; campaign_id: string; status: string }> {
  return apiFetch<{ job_id: string; campaign_id: string; status: string }>(`/api/v1/campaigns/${id}/run`, {
    method: "POST",
  });
}

export async function pauseCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/api/v1/campaigns/${id}/pause`, { method: "POST" });
}

export async function resumeCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/api/v1/campaigns/${id}/resume`, { method: "POST" });
}

export async function getCampaignStats(id: string): Promise<any> {
  return apiFetch<any>(`/api/v1/campaigns/${id}/stats`);
}

// Jobs Polling
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/v1/jobs/${jobId}`);
}

// Leads
export async function getLeads(params: {
  page?: number;
  pageSize?: number;
  location?: string;
  category?: string;
  hasWebsite?: boolean;
  hasEmail?: boolean;
  hasPhone?: boolean;
  scoreMin?: number;
  scoreMax?: number;
  opportunity?: string;
  status?: string;
  campaignId?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}): Promise<PaginatedResult<Lead>> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", params.page.toString());
  if (params.pageSize) query.set("page_size", params.pageSize.toString());
  if (params.location) query.set("location", params.location);
  if (params.category) query.set("category", params.category);
  if (params.hasWebsite !== undefined) query.set("has_website", params.hasWebsite.toString());
  if (params.hasEmail !== undefined) query.set("has_email", params.hasEmail.toString());
  if (params.hasPhone !== undefined) query.set("has_phone", params.hasPhone.toString());
  if (params.scoreMin !== undefined) query.set("score_min", params.scoreMin.toString());
  if (params.scoreMax !== undefined) query.set("score_max", params.scoreMax.toString());
  if (params.opportunity) query.set("opportunity", params.opportunity);
  if (params.status) query.set("status", params.status);
  if (params.campaignId) query.set("campaign_id", params.campaignId);
  if (params.sortBy) query.set("sort_by", params.sortBy);
  if (params.sortOrder) query.set("sort_order", params.sortOrder);

  return apiFetch<PaginatedResult<Lead>>(`/api/v1/leads?${query.toString()}`);
}

export async function getLead(id: string): Promise<Lead> {
  return apiFetch<Lead>(`/api/v1/leads/${id}`);
}

export async function updateLead(id: string, data: Partial<Lead>): Promise<Lead> {
  return apiFetch<Lead>(`/api/v1/leads/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function markLeadContacted(id: string): Promise<any> {
  return apiFetch<any>(`/api/v1/leads/${id}/contacted`, { method: "POST" });
}

export async function updateLeadNotes(id: string, notes: string): Promise<any> {
  return apiFetch<any>(`/api/v1/leads/${id}/notes`, {
    method: "POST",
    body: JSON.stringify({ contact_notes: notes }),
  });
}

export async function enrichLead(id: string): Promise<{ job_id: string; lead_id: string; status: string }> {
  return apiFetch<{ job_id: string; lead_id: string; status: string }>(`/api/v1/leads/${id}/enrich`, {
    method: "POST",
  });
}

// Google Sheets
export async function exportCampaignToSheets(campaignId: string, sheetName = "Leads"): Promise<any> {
  return apiFetch<any>(`/api/v1/google-sheets/export/campaign/${campaignId}`, {
    method: "POST",
    body: JSON.stringify({ sheet_name: sheetName }),
  });
}

export async function exportSelectedLeadsToSheets(leadIds: string[], sheetName = "Exported Leads"): Promise<any> {
  return apiFetch<any>("/api/v1/google-sheets/export/leads", {
    method: "POST",
    body: JSON.stringify({ lead_ids: leadIds, sheet_name: sheetName }),
  });
}

// Providers & Usage
export async function getProvidersStatus(): Promise<any> {
  return apiFetch<any>("/api/v1/providers/status");
}

export async function getUsageSummary(): Promise<any> {
  return apiFetch<any>("/api/v1/usage");
}
```

---

## 5. Complete API Endpoint Reference

### 5.1 Authentication

#### `POST /api/v1/auth/login`
- **Auth**: None
- **Request Body**:
  ```json
  {
    "email": "admin@yourdomain.com",
    "password": "YourPassword123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 86400,
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **cURL Example**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@yourdomain.com","password":"YourPassword123!"}'
  ```

#### `GET /api/v1/auth/me`
- **Auth**: Bearer Token
- **Response `200 OK`**:
  ```json
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "admin@yourdomain.com",
    "full_name": "Platform Administrator",
    "is_active": true,
    "is_superuser": true,
    "created_at": "2026-10-05T12:00:00Z"
  }
  ```

---

### 5.2 Campaigns

#### `POST /api/v1/campaigns`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "name": "KGF No Website Outreach",
    "description": "Restaurants and retail without web presence",
    "locations": ["KGF", "Bangarapet"],
    "categories": ["restaurants", "hotels", "retail"],
    "max_leads": 500,
    "enrich_contacts": true,
    "analyze_websites": true,
    "ai_qualification": true,
    "google_sheet_sync": true
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "c1a9f1b0-4e3a-493b-8fa4-123456789abc",
    "name": "KGF No Website Outreach",
    "locations": ["KGF", "Bangarapet"],
    "categories": ["restaurants", "hotels", "retail"],
    "status": "DRAFT",
    "leads_discovered": 0,
    "created_at": "2026-10-05T12:30:00Z"
  }
  ```

#### `POST /api/v1/campaigns/{id}/run`
- **Auth**: Bearer Token
- **Response `200 OK`**:
  ```json
  {
    "job_id": "8f9a2b10-6c7d-4e5f-9a1b-9876543210fe",
    "campaign_id": "c1a9f1b0-4e3a-493b-8fa4-123456789abc",
    "status": "queued",
    "message": "Campaign queued for execution. Poll /api/v1/jobs/{job_id} for live progress."
  }
  ```

---

### 5.3 Jobs & Polling

#### `GET /api/v1/jobs/{job_id}`
- **Auth**: Bearer Token
- **Response `200 OK`**:
  ```json
  {
    "id": "8f9a2b10-6c7d-4e5f-9a1b-9876543210fe",
    "campaign_id": "c1a9f1b0-4e3a-493b-8fa4-123456789abc",
    "status": "running",
    "progress": 64,
    "current_stage": "enriching",
    "processed": 64,
    "total": 100,
    "successful": 60,
    "failed": 4,
    "error_message": null,
    "started_at": "2026-10-05T12:31:00Z",
    "completed_at": null
  }
  ```

---

### 5.4 Leads

#### `GET /api/v1/leads`
- **Auth**: Bearer Token
- **Query Parameters**:
  - `page` (default 1)
  - `page_size` (default 50, max 100)
  - `location` (e.g. `KGF` or `Bangalore`)
  - `has_website` (`true` / `false`)
  - `has_email` (`true` / `false`)
  - `has_phone` (`true` / `false`)
  - `score_min` (0-100)
  - `score_max` (0-100)
  - `opportunity` (`NO_WEBSITE`, `WEBSITE_REBUILD`, `ECOMMERCE_OPPORTUNITY`, `WEBSITE_SECURITY`)
  - `status` (`NEW`, `CONTACTED`, `INTERESTED`, `FOLLOW_UP`, `PROPOSAL`, `WON`, `LOST`)
  - `sort_by` (`lead_score`, `created_at`, `business_name`)
  - `sort_order` (`asc`, `desc`)
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "b9c8d7e6-f5a4-3b2c-1d0e-abcdef123456",
        "business_name": "Bangarapet Sri Krishna Grand Hotel",
        "category": "hotels",
        "phone": "+918153255678",
        "email": null,
        "owner_name": null,
        "website": null,
        "has_website": false,
        "city": "Bangarapet",
        "district": "Kolar",
        "state": "Karnataka",
        "lead_score": 88,
        "opportunity": "NO_WEBSITE",
        "status": "NEW",
        "source": "apify",
        "created_at": "2026-10-05T12:35:00Z"
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 1,
    "total_pages": 1
  }
  ```

#### `POST /api/v1/leads/{id}/contacted`
- **Auth**: Bearer Token
- **Response `200 OK`**:
  ```json
  {
    "status": "CONTACTED",
    "last_contacted_at": "2026-10-05T12:40:00Z",
    "contact_notes": null
  }
  ```

#### `POST /api/v1/leads/{id}/notes`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "contact_notes": "Owner interested in a mobile-responsive landing page. Follow up on Thursday."
  }
  ```

---

### 5.5 Google Sheets Synchronization

#### `POST /api/v1/google-sheets/export/campaign/{campaign_id}`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "sheet_name": "KGF Leads"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "export_id": "e1f2a3b4-...",
    "campaign_id": "c1a9f1b0-...",
    "spreadsheet_id": "1BxiMVs0XRA5...",
    "sheet_name": "KGF Leads",
    "total_rows_exported": 60,
    "status": "completed",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5.../edit",
    "message": "Successfully exported 60 leads to Google Sheets."
  }
  ```

---

## 6. Recommended Next.js UI Flows

### Flow 1: Create & Monitor a Lead Campaign

```text
Dashboard UI: Campaign Form
             |
             | 1. Submit form (locations, categories, max_leads)
             v
      createCampaign()
             |
             | 2. Receives campaign_id
             v
       runCampaign()
             |
             | 3. Receives job_id
             v
   Poll getJobStatus() every 2500ms
             |
             | 4. Update UI progress bar & badge:
             |    - Stage: "discovering" -> "normalizing" -> "enriching" -> "scoring"
             |    - Progress: 10% -> 45% -> 80% -> 100%
             v
     Job Status = 'completed'
             |
             v
    Refresh Leads Table & Stats
```

**React Hook Example (`useCampaignRunner.ts`):**

```typescript
// hooks/useCampaignRunner.ts
import { useState } from "react";
import { runCampaign, getJobStatus, JobStatus } from "@/lib/api";

export function useCampaignRunner() {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const startCampaign = async (campaignId: string, onComplete?: () => void) => {
    try {
      setIsRunning(true);
      const { job_id } = await runCampaign(campaignId);

      const interval = setInterval(async () => {
        const status = await getJobStatus(job_id);
        setJob(status);

        if (status.status === "completed" || status.status === "failed") {
          clearInterval(interval);
          setIsRunning(false);
          if (status.status === "completed" && onComplete) {
            onComplete();
          }
        }
      }, 2000);
    } catch (err) {
      setIsRunning(false);
      throw err;
    }
  };

  return { startCampaign, job, isRunning };
}
```

---

### Flow 2: Qualified Leads Table with Filter Badges

```tsx
// components/LeadsTable.tsx
import React, { useEffect, useState } from "react";
import { getLeads, Lead } from "@/lib/api";

export function LeadsTable() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [filterNoWebsite, setFilterNoWebsite] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getLeads({
      page: 1,
      pageSize: 50,
      hasWebsite: filterNoWebsite ? false : undefined,
      sortBy: "lead_score",
      sortOrder: "desc",
    })
      .then((res) => setLeads(res.items))
      .finally(() => setLoading(false));
  }, [filterNoWebsite]);

  return (
    <div>
      <div className="flex gap-4 mb-4">
        <button
          onClick={() => setFilterNoWebsite(!filterNoWebsite)}
          className={`px-3 py-1.5 rounded ${filterNoWebsite ? "bg-amber-600 text-white" : "bg-gray-200"}`}
        >
          {filterNoWebsite ? "Showing: No Website Only" : "Filter: No Website"}
        </button>
      </div>

      {loading ? (
        <p>Loading leads...</p>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Business Name</th>
              <th>Location</th>
              <th>Phone</th>
              <th>Website</th>
              <th>Score</th>
              <th>Opportunity</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((l) => (
              <tr key={l.id} className="border-b hover:bg-gray-50">
                <td className="py-2 font-medium">{l.business_name}</td>
                <td>{l.city || "N/A"}</td>
                <td>{l.phone || <span className="text-gray-400">None</span>}</td>
                <td>
                  {l.has_website && l.website ? (
                    <a href={l.website} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                      Visit
                    </a>
                  ) : (
                    <span className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded font-semibold">
                      NO WEBSITE
                    </span>
                  )}
                </td>
                <td className="font-bold text-emerald-600">{l.lead_score}</td>
                <td>
                  <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                    {l.opportunity}
                  </span>
                </td>
                <td>{l.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

---

## 7. Error Handling Guide

| Error Code | HTTP Status | Action for Next.js Dashboard |
| :--- | :--- | :--- |
| `AUTHENTICATION_FAILED` | `401` | Clear token state and redirect user to `/login`. |
| `PERMISSION_DENIED` | `403` | Render "Access Denied: Admin required" alert modal. |
| `RESOURCE_NOT_FOUND` | `404` | Display Next.js `notFound()` or empty state placeholder. |
| `RATE_LIMIT_EXCEEDED` | `429` | Show countdown toast: "Too many requests. Please wait 60s." |
| `VALIDATION_ERROR` | `422` | Display inline form field error messages from `details.errors`. |
| `PROVIDER_ERROR` | `502` | Show warning banner: Provider temporary outage. |
| `BUDGET_LIMIT_REACHED`| `400` | Alert user: "Campaign reached max Apollo credits or AI quota." |
