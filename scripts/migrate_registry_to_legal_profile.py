#!/usr/bin/env python3
"""Migrate data from company_registry_data + company_insolvency_data into
the unified company_legal_profile table.

Idempotent: uses ON CONFLICT DO UPDATE so re-runs are safe.
Also computes credibility scores and promotes core fields to companies.

Run from VPS after deploying migration 016 and the new code:
    python3 scripts/migrate_registry_to_legal_profile.py
"""

import json
import os
import sys
from datetime import date, datetime

import psycopg2
import psycopg2.extras

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL:
    print("ERROR: DATABASE_URL environment variable not set.")
    print("  export DATABASE_URL='postgresql://user:pass@host:5432/leadgen'")
    sys.exit(1)


# ---------- Credibility scorer (standalone copy to avoid app imports) ----------

def compute_credibility(profile):
    factors = {}
    factors["registration_verified"] = _score_reg(
        profile.get("registration_id"), profile.get("match_confidence"))
    factors["active_status"] = _score_status(profile.get("registration_status"))
    factors["no_insolvency"] = _score_insolvency(
        profile.get("insolvency_flag", False),
        profile.get("active_insolvency_count", 0),
        profile.get("insolvency_details", []))
    factors["business_history"] = _score_history(profile.get("date_established"))
    factors["data_completeness"] = _score_completeness(profile)
    factors["directors_known"] = _score_directors(profile.get("directors", []))
    score = min(sum(factors.values()), 100)
    return {"score": score, "factors": factors}


def _score_reg(reg_id, conf):
    if not reg_id:
        return 0
    if conf is None:
        return 10
    c = float(conf)
    return 25 if c >= 0.95 else 20 if c >= 0.85 else 10 if c >= 0.60 else 5


def _score_status(status):
    if not status:
        return 5
    s = str(status).lower()
    return 20 if s == "active" else 5 if s in ("unknown", "") else 0


def _score_insolvency(flag, active, details):
    if not flag and active == 0:
        return 20
    if active == 0 and details:
        return 10
    return 0


def _score_history(dt):
    if not dt:
        return 0
    if isinstance(dt, str):
        try:
            est = datetime.strptime(dt[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return 0
    elif isinstance(dt, datetime):
        est = dt.date()
    elif isinstance(dt, date):
        est = dt
    else:
        return 0
    years = (date.today() - est).days / 365.25
    return 15 if years >= 10 else 12 if years >= 5 else 8 if years >= 2 else 5 if years >= 1 else 2


def _score_completeness(p):
    fields = ["official_name", "legal_form", "registered_address",
              "nace_codes", "registered_capital", "date_established"]
    filled = sum(1 for f in fields if p.get(f) not in (None, "", []))
    return round(filled / len(fields) * 10)


def _score_directors(dirs):
    return 10 if dirs and isinstance(dirs, list) and len(dirs) > 0 else 0


# ---------- Migration ----------

def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Check that company_legal_profile table exists
    cur.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'company_legal_profile'
    """)
    if not cur.fetchone():
        print("ERROR: company_legal_profile table does not exist.")
        print("  Run migration 016 first.")
        conn.close()
        sys.exit(1)

    # 2. Read all company_registry_data rows
    cur.execute("""
        SELECT company_id, ico, dic, official_name, legal_form, legal_form_name,
               date_established, date_dissolved, registered_address, address_city,
               address_postal_code, nace_codes, registration_court, registration_number,
               registered_capital, directors, registration_status, insolvency_flag,
               match_confidence, match_method, enriched_at, registry_country,
               raw_response, raw_vr_response
        FROM company_registry_data
    """)
    registry_rows = cur.fetchall()
    print(f"Found {len(registry_rows)} company_registry_data rows")

    # 3. Read all company_insolvency_data rows (keyed by company_id)
    cur.execute("""
        SELECT company_id, has_insolvency, proceedings, total_proceedings,
               active_proceedings, raw_response
        FROM company_insolvency_data
    """)
    insolvency_map = {}
    for row in cur.fetchall():
        insolvency_map[str(row["company_id"])] = row
    print(f"Found {len(insolvency_map)} company_insolvency_data rows")

    # 4. Merge into company_legal_profile
    inserted = 0
    updated = 0

    for reg in registry_rows:
        cid = str(reg["company_id"])
        country = reg["registry_country"] or "CZ"

        # Parse JSONB fields
        nace = reg["nace_codes"]
        if isinstance(nace, str):
            nace = json.loads(nace)
        directors = reg["directors"]
        if isinstance(directors, str):
            directors = json.loads(directors)

        # Merge insolvency data
        insol = insolvency_map.get(cid)
        insolvency_flag = reg.get("insolvency_flag", False)
        insolvency_details = []
        active_insolvency_count = 0

        if insol:
            insolvency_flag = insolvency_flag or insol.get("has_insolvency", False)
            procs = insol.get("proceedings", [])
            if isinstance(procs, str):
                procs = json.loads(procs)
            insolvency_details = procs
            active_insolvency_count = insol.get("active_proceedings", 0)

        # Build source_data
        source_data = {}
        raw_main = reg.get("raw_response")
        if raw_main:
            if isinstance(raw_main, str):
                raw_main = json.loads(raw_main)
            source_data[country + "_main"] = raw_main
        raw_vr = reg.get("raw_vr_response")
        if raw_vr and raw_vr != "{}":
            if isinstance(raw_vr, str):
                raw_vr = json.loads(raw_vr)
            source_data[country + "_vr"] = raw_vr
        if insol and insol.get("raw_response"):
            raw_isir = insol["raw_response"]
            if isinstance(raw_isir, str):
                raw_isir = json.loads(raw_isir)
            source_data["CZ_ISIR"] = raw_isir

        # Build profile for credibility scoring
        profile = {
            "registration_id": reg["ico"],
            "match_confidence": float(reg["match_confidence"]) if reg["match_confidence"] is not None else None,
            "registration_status": reg["registration_status"],
            "insolvency_flag": insolvency_flag,
            "active_insolvency_count": active_insolvency_count,
            "insolvency_details": insolvency_details,
            "date_established": reg["date_established"],
            "official_name": reg["official_name"],
            "legal_form": reg["legal_form"],
            "registered_address": reg["registered_address"],
            "nace_codes": nace or [],
            "registered_capital": reg["registered_capital"],
            "directors": directors or [],
        }
        cred = compute_credibility(profile)

        # Upsert into company_legal_profile
        cur.execute("""
            INSERT INTO company_legal_profile (
                company_id, registration_id, registration_country,
                tax_id, official_name, legal_form, legal_form_name,
                registration_status, date_established, date_dissolved,
                registered_address, address_city, address_postal_code,
                nace_codes, directors, registered_capital,
                registration_court, registration_number,
                insolvency_flag, insolvency_details, active_insolvency_count,
                match_confidence, match_method,
                credibility_score, credibility_factors,
                source_data, enriched_at, enrichment_cost_usd
            ) VALUES (
                %(company_id)s, %(registration_id)s, %(registration_country)s,
                %(tax_id)s, %(official_name)s, %(legal_form)s, %(legal_form_name)s,
                %(registration_status)s, %(date_established)s, %(date_dissolved)s,
                %(registered_address)s, %(address_city)s, %(address_postal_code)s,
                %(nace_codes)s, %(directors)s, %(registered_capital)s,
                %(registration_court)s, %(registration_number)s,
                %(insolvency_flag)s, %(insolvency_details)s, %(active_insolvency_count)s,
                %(match_confidence)s, %(match_method)s,
                %(credibility_score)s, %(credibility_factors)s,
                %(source_data)s, %(enriched_at)s, 0
            )
            ON CONFLICT (company_id) DO UPDATE SET
                registration_id = EXCLUDED.registration_id,
                registration_country = EXCLUDED.registration_country,
                tax_id = EXCLUDED.tax_id,
                official_name = EXCLUDED.official_name,
                legal_form = EXCLUDED.legal_form,
                legal_form_name = EXCLUDED.legal_form_name,
                registration_status = EXCLUDED.registration_status,
                date_established = EXCLUDED.date_established,
                date_dissolved = EXCLUDED.date_dissolved,
                registered_address = EXCLUDED.registered_address,
                address_city = EXCLUDED.address_city,
                address_postal_code = EXCLUDED.address_postal_code,
                nace_codes = EXCLUDED.nace_codes,
                directors = EXCLUDED.directors,
                registered_capital = EXCLUDED.registered_capital,
                registration_court = EXCLUDED.registration_court,
                registration_number = EXCLUDED.registration_number,
                insolvency_flag = EXCLUDED.insolvency_flag,
                insolvency_details = EXCLUDED.insolvency_details,
                active_insolvency_count = EXCLUDED.active_insolvency_count,
                match_confidence = EXCLUDED.match_confidence,
                match_method = EXCLUDED.match_method,
                credibility_score = EXCLUDED.credibility_score,
                credibility_factors = EXCLUDED.credibility_factors,
                source_data = EXCLUDED.source_data,
                enriched_at = EXCLUDED.enriched_at,
                updated_at = now()
        """, {
            "company_id": cid,
            "registration_id": reg["ico"],
            "registration_country": country,
            "tax_id": reg["dic"],
            "official_name": reg["official_name"],
            "legal_form": reg["legal_form"],
            "legal_form_name": reg["legal_form_name"],
            "registration_status": reg["registration_status"],
            "date_established": reg["date_established"],
            "date_dissolved": reg["date_dissolved"],
            "registered_address": reg["registered_address"],
            "address_city": reg["address_city"],
            "address_postal_code": reg["address_postal_code"],
            "nace_codes": json.dumps(nace or []),
            "directors": json.dumps(directors or []),
            "registered_capital": reg["registered_capital"],
            "registration_court": reg["registration_court"],
            "registration_number": reg["registration_number"],
            "insolvency_flag": insolvency_flag,
            "insolvency_details": json.dumps(insolvency_details, default=str),
            "active_insolvency_count": active_insolvency_count,
            "match_confidence": reg["match_confidence"],
            "match_method": reg["match_method"],
            "credibility_score": cred["score"],
            "credibility_factors": json.dumps(cred["factors"]),
            "source_data": json.dumps(source_data, default=str),
            "enriched_at": reg["enriched_at"],
        })

        # 5. Promote core fields to companies table
        cur.execute("""
            UPDATE companies SET
                official_name = %(official_name)s,
                tax_id = %(tax_id)s,
                legal_form = %(legal_form)s,
                registration_status = %(registration_status)s,
                date_established = %(date_established)s,
                has_insolvency = %(has_insolvency)s,
                credibility_score = %(credibility_score)s,
                credibility_factors = %(credibility_factors)s
            WHERE id = %(company_id)s
        """, {
            "company_id": cid,
            "official_name": reg["official_name"],
            "tax_id": reg["dic"],
            "legal_form": reg["legal_form"],
            "registration_status": reg["registration_status"],
            "date_established": reg["date_established"],
            "has_insolvency": insolvency_flag,
            "credibility_score": cred["score"],
            "credibility_factors": json.dumps(cred["factors"]),
        })

        inserted += 1
        if inserted % 100 == 0:
            print(f"  Processed {inserted}/{len(registry_rows)}...")

    conn.commit()
    print(f"\nDone. {inserted} rows migrated to company_legal_profile.")

    # 6. Handle insolvency-only rows (ISIR data without registry data)
    orphan_count = 0
    for cid, insol in insolvency_map.items():
        # Check if already migrated via registry data
        cur.execute(
            "SELECT 1 FROM company_legal_profile WHERE company_id = %s",
            (cid,),
        )
        if cur.fetchone():
            continue

        # Insolvency-only entry — need to look up company country
        cur.execute(
            "SELECT hq_country, domain FROM companies WHERE id = %s",
            (cid,),
        )
        comp = cur.fetchone()
        country = "CZ"  # ISIR is CZ-only

        procs = insol.get("proceedings", [])
        if isinstance(procs, str):
            procs = json.loads(procs)

        profile = {
            "registration_id": None,
            "match_confidence": None,
            "registration_status": None,
            "insolvency_flag": insol.get("has_insolvency", False),
            "active_insolvency_count": insol.get("active_proceedings", 0),
            "insolvency_details": procs,
            "date_established": None,
            "directors": [],
        }
        cred = compute_credibility(profile)

        cur.execute("""
            INSERT INTO company_legal_profile (
                company_id, registration_country,
                insolvency_flag, insolvency_details, active_insolvency_count,
                credibility_score, credibility_factors, enrichment_cost_usd
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            ON CONFLICT (company_id) DO NOTHING
        """, (
            cid, country, insol.get("has_insolvency", False),
            json.dumps(procs, default=str), insol.get("active_proceedings", 0),
            cred["score"], json.dumps(cred["factors"]),
        ))

        cur.execute("""
            UPDATE companies SET
                has_insolvency = %s,
                credibility_score = %s,
                credibility_factors = %s
            WHERE id = %s
        """, (
            insol.get("has_insolvency", False),
            cred["score"], json.dumps(cred["factors"]),
            cid,
        ))

        orphan_count += 1

    conn.commit()
    if orphan_count:
        print(f"Migrated {orphan_count} insolvency-only rows (no registry data).")

    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
