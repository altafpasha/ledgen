-- ==============================================================================
-- SUPABASE POSTGRESQL SCHEMA — LEAD INTELLIGENCE & GENERATION PLATFORM
-- Run this script directly in your Supabase SQL Editor
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 2. USERS, AUTHENTICATION & AUDIT LOGS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    hashed_key VARCHAR(64) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS ix_api_keys_hash ON api_keys(hashed_key);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);

-- ==============================================================================
-- 3. BUSINESSES & LEAD REPOSITORY
-- ==============================================================================

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name TEXT NOT NULL,
    normalized_business_name TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),

    phone VARCHAR(50),
    normalized_phone VARCHAR(50),

    email VARCHAR(255),
    normalized_email VARCHAR(255),

    owner_name VARCHAR(255),

    website TEXT,
    website_domain VARCHAR(255),
    has_website BOOLEAN NOT NULL DEFAULT FALSE,

    address TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) DEFAULT 'India',
    pincode VARCHAR(20),

    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),

    source VARCHAR(50) NOT NULL DEFAULT 'apify',
    source_business_id VARCHAR(255),
    google_maps_url TEXT,
    description TEXT,

    last_enriched_at TIMESTAMPTZ,
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_businesses_name ON businesses(business_name);
CREATE INDEX IF NOT EXISTS ix_businesses_norm_name ON businesses(normalized_business_name);
CREATE INDEX IF NOT EXISTS ix_businesses_phone ON businesses(normalized_phone);
CREATE INDEX IF NOT EXISTS ix_businesses_email ON businesses(normalized_email);
CREATE INDEX IF NOT EXISTS ix_businesses_domain ON businesses(website_domain);
CREATE INDEX IF NOT EXISTS ix_businesses_has_website ON businesses(has_website);
CREATE INDEX IF NOT EXISTS ix_businesses_city_cat ON businesses(city, category);
CREATE INDEX IF NOT EXISTS ix_businesses_district ON businesses(district);
CREATE INDEX IF NOT EXISTS ix_businesses_state ON businesses(state);
CREATE INDEX IF NOT EXISTS ix_businesses_pincode ON businesses(pincode);
CREATE INDEX IF NOT EXISTS ix_businesses_source_id ON businesses(source, source_business_id);

CREATE TABLE IF NOT EXISTS business_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name VARCHAR(255),
    title VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    linkedin_url TEXT,
    source VARCHAR(50) NOT NULL DEFAULT 'apollo',
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_business_contacts_bid ON business_contacts(business_id);
CREATE INDEX IF NOT EXISTS ix_business_contacts_email ON business_contacts(email);
CREATE INDEX IF NOT EXISTS ix_business_contacts_phone ON business_contacts(phone);

CREATE TABLE IF NOT EXISTS business_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    address TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) DEFAULT 'India',
    pincode VARCHAR(20),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    is_primary BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_business_locations_bid ON business_locations(business_id);

CREATE TABLE IF NOT EXISTS business_websites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    status_code INTEGER,
    is_alive BOOLEAN DEFAULT TRUE,
    is_https BOOLEAN DEFAULT FALSE,
    title TEXT,
    technology_stack JSONB,
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_business_websites_bid ON business_websites(business_id);
CREATE INDEX IF NOT EXISTS ix_business_websites_domain ON business_websites(domain);

CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==============================================================================
-- 4. CAMPAIGNS & CAMPAIGN LEADS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_leads INTEGER NOT NULL DEFAULT 500,
    enrich_contacts BOOLEAN NOT NULL DEFAULT TRUE,
    analyze_websites BOOLEAN NOT NULL DEFAULT TRUE,
    ai_qualification BOOLEAN NOT NULL DEFAULT TRUE,
    google_sheet_sync BOOLEAN NOT NULL DEFAULT TRUE,

    max_apify_cost NUMERIC(10, 2),
    max_apollo_credits INTEGER NOT NULL DEFAULT 100,
    max_ai_requests INTEGER NOT NULL DEFAULT 500,

    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',

    leads_discovered INTEGER NOT NULL DEFAULT 0,
    leads_enriched INTEGER NOT NULL DEFAULT 0,
    leads_scored INTEGER NOT NULL DEFAULT 0,
    leads_exported INTEGER NOT NULL DEFAULT 0,

    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS ix_campaigns_created_by ON campaigns(created_by_id);

CREATE TABLE IF NOT EXISTS campaign_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'DISCOVERED',
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_campaign_lead UNIQUE (campaign_id, business_id)
);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_camp_id ON campaign_leads(campaign_id);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_biz_id ON campaign_leads(business_id);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_status ON campaign_leads(status);

-- ==============================================================================
-- 5. BACKGROUND JOBS (DISCOVERY & ENRICHMENT)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS discovery_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    celery_task_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    current_stage VARCHAR(50) NOT NULL DEFAULT 'queued',
    total INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    successful INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata_json JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_discovery_jobs_camp_id ON discovery_jobs(campaign_id);
CREATE INDEX IF NOT EXISTS ix_discovery_jobs_status ON discovery_jobs(status);
CREATE INDEX IF NOT EXISTS ix_discovery_jobs_task_id ON discovery_jobs(celery_task_id);

CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    celery_task_id VARCHAR(255),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    error_message TEXT,
    result_summary JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_enrichment_jobs_lead_id ON enrichment_jobs(lead_id);
CREATE INDEX IF NOT EXISTS ix_enrichment_jobs_status ON enrichment_jobs(status);

-- ==============================================================================
-- 6. AI QUALIFICATION, SCORING & WEBSITE INTELLIGENCE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS ai_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    model_name VARCHAR(100) NOT NULL,
    lead_quality VARCHAR(50) NOT NULL,
    score INTEGER NOT NULL,
    recommended_service VARCHAR(100) NOT NULL,
    opportunity VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    needs_enrichment BOOLEAN NOT NULL DEFAULT FALSE,
    confidence REAL NOT NULL DEFAULT 1.0,
    raw_prompt TEXT,
    raw_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ai_decisions_biz_id ON ai_decisions(business_id);
CREATE INDEX IF NOT EXISTS ix_ai_decisions_opp ON ai_decisions(opportunity);

CREATE TABLE IF NOT EXISTS lead_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    deterministic_score INTEGER NOT NULL DEFAULT 0,
    ai_score INTEGER,
    final_score INTEGER NOT NULL DEFAULT 0,
    scoring_breakdown JSONB,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_lead_scores_biz_id ON lead_scores(business_id);
CREATE INDEX IF NOT EXISTS ix_lead_scores_final ON lead_scores(final_score);

CREATE TABLE IF NOT EXISTS website_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    website_url TEXT NOT NULL,
    is_https BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    response_time_ms INTEGER,
    title TEXT,
    meta_description TEXT,
    technologies JSONB DEFAULT '{}'::jsonb,
    security_headers JSONB DEFAULT '{}'::jsonb,
    performance_indicators JSONB DEFAULT '{}'::jsonb,
    emails_found JSONB NOT NULL DEFAULT '[]'::jsonb,
    phones_found JSONB NOT NULL DEFAULT '[]'::jsonb,
    analysis_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_website_analysis_biz_id ON website_analysis(business_id);

-- ==============================================================================
-- 7. CRM OUTREACH STATUS & GOOGLE SHEETS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS outreach_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID UNIQUE NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'NEW',
    last_contacted_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ,
    contact_notes TEXT,
    assigned_to_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_outreach_status_biz_id ON outreach_status(business_id);
CREATE INDEX IF NOT EXISTS ix_outreach_status_status ON outreach_status(status);

CREATE TABLE IF NOT EXISTS google_sheet_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    spreadsheet_id VARCHAR(255) NOT NULL,
    sheet_name VARCHAR(100) NOT NULL DEFAULT 'Leads',
    total_rows_exported INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'completed',
    last_synced_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_sheet_exports_camp_id ON google_sheet_exports(campaign_id);

-- ==============================================================================
-- 8. PROVIDER USAGE & COST TRACKING
-- ==============================================================================

CREATE TABLE IF NOT EXISTS provider_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    campaign_id UUID,
    job_id UUID,
    requests INTEGER NOT NULL DEFAULT 1,
    credits_used DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    estimated_cost NUMERIC(10, 4) NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_provider_usage_provider ON provider_usage(provider);
CREATE INDEX IF NOT EXISTS ix_provider_usage_op ON provider_usage(operation);
CREATE INDEX IF NOT EXISTS ix_provider_usage_camp ON provider_usage(campaign_id);
CREATE INDEX IF NOT EXISTS ix_provider_usage_created ON provider_usage(created_at);
