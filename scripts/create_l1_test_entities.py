#!/usr/bin/env python3
"""Create test entities for L1 enrichment E2E validation.

Inserts 10 companies with varied field coverage into a dedicated test batch.
Run from VPS or via SSH tunnel to reach RDS.

Usage:
    python scripts/create_l1_test_entities.py

Environment:
    DATABASE_URL  — PostgreSQL connection string
"""
import os
import sys
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

TENANT_ID = "8f7d2027-3e09-4db7-b607-6c1424038a54"  # visionvolve
BATCH_NAME = "l1-e2e-test"

TEST_COMPANIES = [
    # 1. Full data — expect clean enrichment
    {
        "name": "SAP SE",
        "domain": "sap.com",
        "hq_country": "Germany",
        "industry": None,
    },
    # 2. Domain only, no country — tests country resolution
    {
        "name": "Spotify Technology",
        "domain": "spotify.com",
        "hq_country": None,
        "industry": None,
    },
    # 3. No domain, country only — limited data
    {
        "name": "Skoda Auto",
        "domain": None,
        "hq_country": "Czech Republic",
        "industry": None,
    },
    # 4. Free-mail domain — tests free-mail detection
    {
        "name": "John Smith Consulting",
        "domain": "gmail.com",
        "hq_country": "UK",
        "industry": None,
    },
    # 5. Non-existent domain — tests error handling
    {
        "name": "Nonexistent Corp XYZ",
        "domain": "this-domain-does-not-exist-12345.com",
        "hq_country": "US",
        "industry": None,
    },
    # 6. Minimal data (name only)
    {
        "name": "Kiwi.com",
        "domain": None,
        "hq_country": None,
        "industry": None,
    },
    # 7. Czech company — tests registry follow-up eligibility
    {
        "name": "Avast Software",
        "domain": "avast.com",
        "hq_country": "Czech Republic",
        "industry": None,
    },
    # 8. Norwegian company — tests Nordic path
    {
        "name": "Telenor ASA",
        "domain": "telenor.com",
        "hq_country": "Norway",
        "industry": None,
    },
    # 9. Large known enterprise — tests data quality
    {
        "name": "Siemens AG",
        "domain": "siemens.com",
        "hq_country": "Germany",
        "industry": None,
    },
    # 10. Duplicate name, different domain — tests dedup handling
    {
        "name": "SAP SE",
        "domain": "sap.de",
        "hq_country": "Germany",
        "industry": None,
    },
]


def main():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        # Get or create batch
        row = conn.execute(
            text("SELECT id FROM batches WHERE tenant_id = :tid AND name = :name"),
            {"tid": TENANT_ID, "name": BATCH_NAME},
        ).fetchone()

        if row:
            batch_id = str(row[0])
            print(f"Using existing batch: {batch_id}")
            # Delete existing test companies
            conn.execute(
                text("DELETE FROM companies WHERE batch_id = :bid AND tenant_id = :tid"),
                {"bid": batch_id, "tid": TENANT_ID},
            )
            print("Cleared existing test companies")
        else:
            batch_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO batches (id, tenant_id, name, is_active) "
                    "VALUES (:id, :tid, :name, true)"
                ),
                {"id": batch_id, "tid": TENANT_ID, "name": BATCH_NAME},
            )
            print(f"Created batch: {batch_id}")

        # Get first owner
        owner_row = conn.execute(
            text("SELECT id FROM owners WHERE tenant_id = :tid LIMIT 1"),
            {"tid": TENANT_ID},
        ).fetchone()
        owner_id = str(owner_row[0]) if owner_row else None

        # Insert test companies
        for i, c in enumerate(TEST_COMPANIES, 1):
            cid = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO companies (id, tenant_id, batch_id, owner_id, "
                    "name, domain, hq_country, industry, status) "
                    "VALUES (:id, :tid, :bid, :oid, :name, :domain, :country, :industry, 'new')"
                ),
                {
                    "id": cid,
                    "tid": TENANT_ID,
                    "bid": batch_id,
                    "oid": owner_id,
                    "name": c["name"],
                    "domain": c["domain"],
                    "country": c["hq_country"],
                    "industry": c["industry"],
                },
            )
            print(f"  [{i:2d}] {c['name']} ({c.get('domain', '-')}) → {cid}")

        print(f"\nInserted {len(TEST_COMPANIES)} test companies in batch '{BATCH_NAME}'")
        print("Ready for L1 enrichment via: POST /api/pipeline/dag-run")


if __name__ == "__main__":
    main()
