#!/usr/bin/env python3
"""Migrate n8n workflows from cloud instance to self-hosted n8n.

Migrates workflow JSON files (already pulled from cloud) into the self-hosted
n8n instance, remapping credential IDs to match the target environment.

Prerequisites:
  1. Pull latest workflows from cloud:  python sync_workflows.py pull
  2. Create credentials on self-hosted n8n UI (Settings > Credentials):
     - Airtable Personal Access Token
     - Perplexity API key
     - Anthropic API key
  3. Generate an API key on self-hosted n8n (Settings > API > Create API Key)
  4. Set env vars in .env:
     N8N_HOSTED_URL=https://vps.visionvolve.com/api/v1
     N8N_HOSTED_API_TOKEN=<your-hosted-api-key>

Usage:
    python migrate_to_hosted.py credentials     # List credentials on hosted instance
    python migrate_to_hosted.py migrate          # Migrate all workflows
    python migrate_to_hosted.py migrate --dry-run  # Preview without importing
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

WORKFLOWS_DIR = Path("workflows")

# Cloud instance (source)
CLOUD_URL = "https://visionvolve.app.n8n.cloud/api/v1"
CLOUD_TOKEN = os.getenv("N8N_API_TOKEN")

# Self-hosted instance (target)
HOSTED_URL = os.getenv("N8N_HOSTED_URL", "https://vps.visionvolve.com/api/v1")
HOSTED_TOKEN = os.getenv("N8N_HOSTED_API_TOKEN")

# Cloud credential IDs (from exported workflow files)
CLOUD_CREDENTIALS = {
    "OZgSzSQsVA0gjet3": {"name": "Airtable Personal Access Token account", "type": "airtableTokenApi"},
    "z8b8wRk0xGQbQgIc": {"name": "Perplexity account", "type": "perplexityApi"},
    "vGvebeysXQw7CHt8": {"name": "Anthropic account", "type": "anthropicApi"},
}

# Fields to strip from workflow JSON before importing
STRIP_FIELDS = {"shared", "activeVersion", "activeVersionId", "versionCounter",
                "versionId", "triggerCount", "tags", "meta", "staticData",
                "pinData", "isArchived", "description", "active"}


def hosted_headers() -> dict:
    return {"X-N8N-API-KEY": HOSTED_TOKEN, "Content-Type": "application/json"}


def cloud_headers() -> dict:
    return {"X-N8N-API-KEY": CLOUD_TOKEN, "Content-Type": "application/json"}


def list_hosted_credentials() -> list[dict]:
    """List credentials on the self-hosted instance.

    n8n v2 public API doesn't support GET /credentials, so we scan the
    workflow files on the target instance to discover credential IDs, or
    fall back to creating credentials via POST and caching the result.
    """
    # Try the API first (works on some n8n versions)
    resp = requests.get(f"{HOSTED_URL}/credentials", headers=hosted_headers())
    if resp.status_code == 200:
        return resp.json().get("data", [])

    # Fallback: use credential mapping file if it exists
    cred_map_file = Path("migration_credential_map.json")
    if cred_map_file.exists():
        return json.loads(cred_map_file.read_text())

    # Fallback: create credentials via POST API
    print("  GET /credentials not supported (n8n v2). Creating credentials via API...")
    created = []
    cred_configs = [
        {
            "name": "Airtable Personal Access Token account",
            "type": "airtableTokenApi",
            "data": {"accessToken": os.getenv("AIRTABLE_TOKEN", "placeholder-update-in-ui")},
        },
        {
            "name": "Perplexity account",
            "type": "perplexityApi",
            "data": {"apiKey": "pplx-placeholder-update-in-ui"},
        },
        {
            "name": "Anthropic account",
            "type": "anthropicApi",
            "data": {"apiKey": "placeholder", "headerName": "x-api-key", "headerValue": "placeholder"},
        },
    ]

    for config in cred_configs:
        try:
            r = requests.post(f"{HOSTED_URL}/credentials", headers=hosted_headers(), json=config)
            if r.status_code in (200, 201):
                cred = r.json()
                created.append({"id": cred["id"], "name": cred["name"], "type": cred["type"]})
                print(f"    Created: {cred['name']} -> {cred['id']}")
            elif "duplicate" in r.text.lower() or "already" in r.text.lower():
                print(f"    {config['name']}: already exists (skipped)")
            else:
                print(f"    {config['name']}: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"    {config['name']}: error - {e}")

    if created:
        cred_map_file.write_text(json.dumps(created, indent=2))
        print(f"  Saved credential map to {cred_map_file}")

    return created


def list_hosted_workflows() -> list[dict]:
    """List all workflows on the self-hosted instance."""
    resp = requests.get(f"{HOSTED_URL}/workflows", headers=hosted_headers())
    resp.raise_for_status()
    return resp.json().get("data", [])


def build_credential_map(hosted_creds: list[dict]) -> dict[str, str]:
    """Build cloud_id -> hosted_id credential mapping.

    Matches by credential type name (airtableTokenApi, perplexityApi, etc).
    """
    # Index hosted credentials by type
    hosted_by_type: dict[str, dict] = {}
    for cred in hosted_creds:
        hosted_by_type[cred["type"]] = cred

    cred_map: dict[str, str] = {}
    missing = []

    for cloud_id, info in CLOUD_CREDENTIALS.items():
        cred_type = info["type"]
        if cred_type in hosted_by_type:
            hosted = hosted_by_type[cred_type]
            cred_map[cloud_id] = hosted["id"]
            print(f"  Mapped {info['name']} ({cred_type}): {cloud_id} -> {hosted['id']}")
        else:
            missing.append(info)
            print(f"  MISSING {info['name']} ({cred_type}): not found on hosted instance")

    return cred_map, missing


def remap_workflow(workflow: dict, cred_map: dict[str, str]) -> dict:
    """Prepare a workflow for import: strip metadata, remap credentials."""
    # Strip cloud-specific fields
    cleaned = {k: v for k, v in workflow.items() if k not in STRIP_FIELDS}

    # Remove cloud ID (n8n will assign a new one)
    cleaned.pop("id", None)
    cleaned.pop("createdAt", None)
    cleaned.pop("updatedAt", None)

    # Remap credential IDs in all nodes
    for node in cleaned.get("nodes", []):
        creds = node.get("credentials", {})
        for cred_key, cred_val in creds.items():
            if isinstance(cred_val, dict) and cred_val.get("id") in cred_map:
                old_id = cred_val["id"]
                cred_val["id"] = cred_map[old_id]

    return cleaned


def import_workflow(workflow_data: dict) -> dict:
    """Create a workflow on the self-hosted instance."""
    resp = requests.post(
        f"{HOSTED_URL}/workflows",
        headers=hosted_headers(),
        json=workflow_data,
    )
    resp.raise_for_status()
    return resp.json()


def pull_cloud_workflow(workflow_id: str) -> Optional[dict]:
    """Pull a single workflow from the cloud instance."""
    resp = requests.get(
        f"{CLOUD_URL}/workflows/{workflow_id}",
        headers=cloud_headers(),
    )
    if resp.status_code == 200:
        return resp.json()
    print(f"  Failed to pull {workflow_id}: {resp.status_code}")
    return None


def cmd_credentials():
    """List credentials on the hosted instance and show mapping status."""
    print("Credentials on self-hosted n8n:")
    print("-" * 60)

    hosted_creds = list_hosted_credentials()
    if not hosted_creds:
        print("  No credentials found.")
        print()
        print("Create these credentials in the n8n UI first:")
        for info in CLOUD_CREDENTIALS.values():
            print(f"  - {info['name']} ({info['type']})")
        return

    for cred in hosted_creds:
        print(f"  [{cred['id']}] {cred['name']} ({cred['type']})")

    print()
    print("Credential mapping:")
    print("-" * 60)
    cred_map, missing = build_credential_map(hosted_creds)

    if missing:
        print()
        print("Create missing credentials in the n8n UI before migrating.")


def cmd_migrate(dry_run: bool = False, fresh: bool = False):
    """Migrate workflows to the self-hosted instance."""
    if not HOSTED_TOKEN:
        print("Error: N8N_HOSTED_API_TOKEN not set in .env")
        print("Generate an API key in self-hosted n8n: Settings > API")
        sys.exit(1)

    # Check for existing workflows on target
    existing = list_hosted_workflows()
    existing_names = {w["name"] for w in existing}
    if existing_names:
        print(f"Existing workflows on hosted instance: {', '.join(existing_names)}")
        print()

    # Build credential mapping
    print("Building credential mapping...")
    hosted_creds = list_hosted_credentials()
    cred_map, missing = build_credential_map(hosted_creds)

    if missing:
        print()
        print("ERROR: Missing credentials on hosted instance. Create them first:")
        for info in missing:
            print(f"  - {info['name']} ({info['type']})")
        print()
        print("Run: python migrate_to_hosted.py credentials")
        sys.exit(1)

    print()

    # Load workflow files (use fresh pull from cloud or local files)
    workflow_files = sorted(WORKFLOWS_DIR.glob("*.json"))
    if not workflow_files:
        print("No workflow files found in workflows/. Run: python sync_workflows.py pull")
        sys.exit(1)

    # Optionally pull fresh from cloud
    if fresh and CLOUD_TOKEN:
        synced_ids = os.getenv("N8N_SYNCED_PROJECTS", "").split(",")
        print("Pulling fresh workflows from cloud...")
        for wf_id in synced_ids:
            wf_id = wf_id.strip()
            if not wf_id:
                continue
            data = pull_cloud_workflow(wf_id)
            if data:
                print(f"  Pulled: {data['name']}")

    # Import workflows
    id_mapping: dict[str, str] = {}  # old cloud ID -> new hosted ID
    results = []

    for wf_file in workflow_files:
        workflow = json.loads(wf_file.read_text())
        name = workflow.get("name", wf_file.stem)
        cloud_id = workflow.get("id", "unknown")

        if name in existing_names:
            print(f"SKIP {name}: already exists on hosted instance")
            # Find the existing ID for the mapping
            for w in existing:
                if w["name"] == name:
                    id_mapping[cloud_id] = w["id"]
            continue

        cleaned = remap_workflow(workflow, cred_map)
        node_count = len(cleaned.get("nodes", []))

        if dry_run:
            print(f"DRY RUN {name}: {node_count} nodes, would import")
            results.append({"name": name, "cloud_id": cloud_id, "status": "dry_run"})
            continue

        print(f"Importing {name} ({node_count} nodes)...", end=" ")
        try:
            result = import_workflow(cleaned)
            new_id = result.get("id")
            id_mapping[cloud_id] = new_id
            print(f"OK -> {new_id}")
            results.append({"name": name, "cloud_id": cloud_id, "hosted_id": new_id, "status": "ok"})
        except requests.HTTPError as e:
            print(f"FAILED: {e.response.status_code} {e.response.text[:200]}")
            results.append({"name": name, "cloud_id": cloud_id, "status": "error", "error": str(e)})

    print()
    print("=" * 60)
    print("Migration summary")
    print("=" * 60)

    for r in results:
        status = r["status"].upper()
        hosted_id = r.get("hosted_id", "-")
        print(f"  {r['name']}: {status} (cloud: {r['cloud_id']} -> hosted: {hosted_id})")

    if id_mapping and not dry_run:
        print()
        print("Workflow ID mapping (cloud -> hosted):")
        for old, new in id_mapping.items():
            print(f"  {old} -> {new}")

        # Save mapping for reference
        mapping_file = Path("migration_id_mapping.json")
        mapping_file.write_text(json.dumps(id_mapping, indent=2))
        print(f"\nMapping saved to {mapping_file}")

        # Show env update suggestion
        new_synced = ",".join(id_mapping.values())
        print()
        print("Update .env for self-hosted sync:")
        print(f"  N8N_HOSTED_URL={HOSTED_URL}")
        print(f"  N8N_HOSTED_API_TOKEN=<keep-your-token>")
        print(f"  N8N_SYNCED_PROJECTS={new_synced}")
        print()
        print("Workflows imported as INACTIVE. Activate them in the n8n UI after verifying.")


def main():
    parser = argparse.ArgumentParser(description="Migrate n8n workflows to self-hosted instance")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("credentials", help="List credentials on hosted instance")

    migrate_p = sub.add_parser("migrate", help="Migrate workflows")
    migrate_p.add_argument("--dry-run", action="store_true", help="Preview without importing")
    migrate_p.add_argument("--fresh", action="store_true", help="Pull fresh from cloud before migrating")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "credentials":
        cmd_credentials()
    elif args.command == "migrate":
        cmd_migrate(dry_run=args.dry_run, fresh=args.fresh)


if __name__ == "__main__":
    main()
