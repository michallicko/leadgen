#!/usr/bin/env python3
"""
Ingest LinkedIn connections CSV into PostgreSQL.

Parses LinkedIn export CSV, creates owner/batch if needed,
deduplicates companies by name, and inserts contacts with
linkedin_url as dedup key.

Usage (run from VPS where DB is accessible):
  python3 ingest_linkedin_csv.py <csv_path> --owner "Bara" --batch "linkedin-bara-2026-02"

Prerequisites:
  - DATABASE_URL env var or .env file
  - pip install psycopg2-binary python-dotenv
"""

import argparse
import csv
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

TENANT_SLUG = "visionvolve"


def parse_csv(path):
    """Parse LinkedIn connections CSV, skipping the 3-line header preamble."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        # Skip first 3 lines (LinkedIn notes)
        for _ in range(3):
            next(f)
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_tenant_id(cur):
    cur.execute("SELECT id FROM tenants WHERE slug = %s", (TENANT_SLUG,))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: tenant '{TENANT_SLUG}' not found.")
        sys.exit(1)
    return row[0]


def ensure_owner(cur, tenant_id, owner_name):
    """Create owner if not exists, return owner_id."""
    cur.execute(
        "SELECT id FROM owners WHERE tenant_id = %s AND name = %s",
        (tenant_id, owner_name),
    )
    row = cur.fetchone()
    if row:
        print(f"  Owner '{owner_name}' exists: {row[0]}")
        return row[0]
    cur.execute(
        "INSERT INTO owners (tenant_id, name) VALUES (%s, %s) RETURNING id",
        (tenant_id, owner_name),
    )
    owner_id = cur.fetchone()[0]
    print(f"  Owner '{owner_name}' created: {owner_id}")
    return owner_id


def ensure_batch(cur, tenant_id, batch_name):
    """Create batch if not exists, return batch_id."""
    cur.execute(
        "SELECT id FROM batches WHERE tenant_id = %s AND name = %s",
        (tenant_id, batch_name),
    )
    row = cur.fetchone()
    if row:
        print(f"  Batch '{batch_name}' exists: {row[0]}")
        return row[0]
    cur.execute(
        "INSERT INTO batches (tenant_id, name) VALUES (%s, %s) RETURNING id",
        (tenant_id, batch_name),
    )
    batch_id = cur.fetchone()[0]
    print(f"  Batch '{batch_name}' created: {batch_id}")
    return batch_id


def ingest(csv_path, owner_name, batch_name):
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    rows = parse_csv(csv_path)
    print(f"Parsed {len(rows)} contacts from CSV")

    # Extract unique company names
    company_names = set()
    for r in rows:
        name = (r.get("Company") or "").strip()
        if name:
            company_names.add(name)
    print(f"Found {len(company_names)} unique company names")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        tenant_id = get_tenant_id(cur)
        print(f"Tenant: {tenant_id}")

        owner_id = ensure_owner(cur, tenant_id, owner_name)
        batch_id = ensure_batch(cur, tenant_id, batch_name)

        # --- Companies ---
        print(f"\n=== Inserting companies ===")

        # Load existing companies for this tenant (name → id)
        cur.execute(
            "SELECT name, id FROM companies WHERE tenant_id = %s",
            (tenant_id,),
        )
        existing_companies = {row[0]: row[1] for row in cur.fetchall()}
        print(f"  {len(existing_companies)} existing companies in tenant")

        company_lookup = dict(existing_companies)  # name → uuid
        new_company_count = 0
        skipped_company_count = 0

        for name in sorted(company_names):
            if name in company_lookup:
                skipped_company_count += 1
                continue
            cur.execute(
                """INSERT INTO companies (tenant_id, name, batch_id, owner_id, status)
                   VALUES (%s, %s, %s, %s, 'new') RETURNING id""",
                (tenant_id, name, batch_id, owner_id),
            )
            company_lookup[name] = cur.fetchone()[0]
            new_company_count += 1

        print(f"  Inserted {new_company_count} new companies")
        print(f"  Skipped {skipped_company_count} already existing")

        # --- Contacts ---
        print(f"\n=== Inserting contacts ===")

        # Load existing contacts by linkedin_url for dedup
        cur.execute(
            "SELECT linkedin_url, id FROM contacts WHERE tenant_id = %s AND linkedin_url IS NOT NULL",
            (tenant_id,),
        )
        existing_contacts = {row[0]: row[1] for row in cur.fetchall()}
        print(f"  {len(existing_contacts)} existing contacts with linkedin_url")

        new_contact_count = 0
        updated_contact_count = 0
        skipped_no_name = 0

        for r in rows:
            first = (r.get("First Name") or "").strip()
            last = (r.get("Last Name") or "").strip()
            full_name = f"{first} {last}".strip()
            if not full_name:
                skipped_no_name += 1
                continue

            linkedin_url = (r.get("URL") or "").strip() or None
            email = (r.get("Email Address") or "").strip() or None
            company_name = (r.get("Company") or "").strip()
            position = (r.get("Position") or "").strip() or None

            company_id = company_lookup.get(company_name) if company_name else None

            if linkedin_url and linkedin_url in existing_contacts:
                # Update existing contact (add owner/batch if not set, update company link)
                cur.execute(
                    """UPDATE contacts SET
                         company_id = COALESCE(company_id, %s),
                         owner_id = COALESCE(owner_id, %s),
                         batch_id = COALESCE(batch_id, %s),
                         job_title = COALESCE(job_title, %s),
                         email_address = COALESCE(email_address, %s)
                       WHERE id = %s""",
                    (company_id, owner_id, batch_id, position, email,
                     existing_contacts[linkedin_url]),
                )
                updated_contact_count += 1
            else:
                cur.execute(
                    """INSERT INTO contacts (
                         tenant_id, company_id, owner_id, batch_id,
                         full_name, job_title, email_address, linkedin_url,
                         contact_source
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'social')""",
                    (tenant_id, company_id, owner_id, batch_id,
                     full_name, position, email, linkedin_url),
                )
                new_contact_count += 1
                if linkedin_url:
                    existing_contacts[linkedin_url] = None  # prevent dups within file

        print(f"  Inserted {new_contact_count} new contacts")
        print(f"  Updated {updated_contact_count} existing contacts")
        if skipped_no_name:
            print(f"  Skipped {skipped_no_name} rows with no name")

        conn.commit()
        print(f"\nDone! Committed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest LinkedIn CSV into PostgreSQL")
    parser.add_argument("csv_path", help="Path to LinkedIn connections CSV")
    parser.add_argument("--owner", required=True, help="Owner name (e.g. 'Bara')")
    parser.add_argument("--batch", required=True, help="Batch name (e.g. 'linkedin-bara-2026-02')")
    args = parser.parse_args()

    print("LinkedIn CSV → PostgreSQL Ingestion")
    print("=" * 50)
    ingest(args.csv_path, args.owner, args.batch)
