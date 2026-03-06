-- Migration 043: Company news table for news & PR enrichment (BL-231)
--
-- Stores news research results per company: media mentions, press releases,
-- sentiment analysis, and AI-generated summary.

CREATE TABLE IF NOT EXISTS company_news (
    company_id UUID PRIMARY KEY REFERENCES companies(id),
    media_mentions JSONB DEFAULT '[]'::jsonb,
    press_releases JSONB DEFAULT '[]'::jsonb,
    sentiment_score NUMERIC(5,2),
    thought_leadership TEXT,
    news_summary TEXT,
    enriched_at TIMESTAMPTZ,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
