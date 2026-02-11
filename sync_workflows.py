#!/usr/bin/env python3
"""Sync n8n workflows between local files and n8n cloud.

Usage:
    python sync_workflows.py pull              # Download all workflows
    python sync_workflows.py push              # Push changed workflows (pulls first)
    python sync_workflows.py push <name>       # Push specific workflow by name
    python sync_workflows.py status            # Show sync status
"""

import argparse
import json
import os
import re
import sys
from typing import Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

N8N_BASE_URL = "https://visionvolve.app.n8n.cloud/api/v1"
N8N_API_TOKEN = os.getenv("N8N_API_TOKEN")
N8N_SYNCED_PROJECTS = os.getenv("N8N_SYNCED_PROJECTS", "").split(",")

OUTPUT_DIR = "workflows"


def sanitize_filename(name: str) -> str:
    """Convert workflow name to safe filename."""
    return re.sub(r'[^\w\-_]', '_', name)


def get_headers() -> dict:
    """Get API headers."""
    return {"X-N8N-API-KEY": N8N_API_TOKEN, "Content-Type": "application/json"}


def download_workflow(workflow_id: str) -> Optional[dict]:
    """Download a single workflow by ID."""
    response = requests.get(
        f"{N8N_BASE_URL}/workflows/{workflow_id}",
        headers=get_headers()
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to download {workflow_id}: {response.status_code} {response.text}")
        return None


def upload_workflow(workflow_id: str, workflow_data: dict) -> bool:
    """Upload/update a workflow by ID."""
    # Only include fields that n8n API accepts for updates
    # See: https://docs.n8n.io/api/api-reference/#tag/Workflow/paths/~1workflows~1%7Bid%7D/put
    payload = {
        'name': workflow_data.get('name'),
        'nodes': workflow_data.get('nodes', []),
        'connections': workflow_data.get('connections', {}),
        'settings': workflow_data.get('settings', {}),
    }

    response = requests.put(
        f"{N8N_BASE_URL}/workflows/{workflow_id}",
        headers=get_headers(),
        json=payload
    )

    if response.status_code == 200:
        return True
    else:
        print(f"Failed to upload {workflow_id}: {response.status_code} {response.text}")
        return False


def get_local_workflow(workflow_id: str) -> Optional[Tuple[str, dict]]:
    """Find and load local workflow file by ID."""
    if not os.path.exists(OUTPUT_DIR):
        return None

    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(OUTPUT_DIR, filename)
        try:
            with open(filepath) as f:
                data = json.load(f)
                if data.get('id') == workflow_id:
                    return filepath, data
        except (json.JSONDecodeError, IOError):
            continue

    return None


def normalize_workflow(workflow: dict) -> dict:
    """Normalize workflow for comparison (remove volatile fields)."""
    exclude_keys = {'id', 'createdAt', 'updatedAt', 'versionId'}
    return {k: v for k, v in workflow.items() if k not in exclude_keys}


def workflows_differ(local: dict, remote: dict) -> bool:
    """Check if local and remote workflows differ."""
    local_norm = normalize_workflow(local)
    remote_norm = normalize_workflow(remote)
    return json.dumps(local_norm, sort_keys=True) != json.dumps(remote_norm, sort_keys=True)


def pull_workflows() -> dict:
    """Pull all workflows from n8n. Returns dict of workflow_id -> workflow_data."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    workflows = {}

    for workflow_id in N8N_SYNCED_PROJECTS:
        workflow_id = workflow_id.strip()
        if not workflow_id:
            continue

        print(f"Pulling {workflow_id}...")
        workflow = download_workflow(workflow_id)

        if workflow:
            workflows[workflow_id] = workflow
            name = workflow.get("name", workflow_id)
            filename = f"{OUTPUT_DIR}/{sanitize_filename(name)}.json"

            with open(filename, "w") as f:
                json.dump(workflow, f, indent=2)

            print(f"  Saved: {filename}")

    return workflows


def push_workflows(specific_name: Optional[str] = None) -> None:
    """Push changed workflows to n8n. Always pulls first to detect conflicts."""

    # First, load all local workflows
    local_workflows = {}
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(OUTPUT_DIR, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    wf_id = data.get('id')
                    if wf_id:
                        local_workflows[wf_id] = (filepath, data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {filepath}: {e}")

    # Filter by name if specified
    if specific_name:
        local_workflows = {
            wf_id: (path, data)
            for wf_id, (path, data) in local_workflows.items()
            if specific_name.lower() in data.get('name', '').lower()
        }
        if not local_workflows:
            print(f"No workflow found matching '{specific_name}'")
            return

    # Pull remote workflows to compare
    print("Pulling remote workflows to check for changes...")
    remote_workflows = {}
    for workflow_id in local_workflows.keys():
        remote = download_workflow(workflow_id)
        if remote:
            remote_workflows[workflow_id] = remote

    # Compare and push changed workflows
    pushed = 0
    skipped = 0

    for wf_id, (filepath, local_data) in local_workflows.items():
        name = local_data.get('name', wf_id)

        if wf_id not in remote_workflows:
            print(f"  {name}: Remote not found, skipping")
            skipped += 1
            continue

        remote_data = remote_workflows[wf_id]

        if not workflows_differ(local_data, remote_data):
            print(f"  {name}: No changes")
            skipped += 1
            continue

        print(f"  {name}: Pushing changes...")
        if upload_workflow(wf_id, local_data):
            print(f"    ✓ Updated successfully")
            pushed += 1
            # Pull updated version to sync metadata
            updated = download_workflow(wf_id)
            if updated:
                with open(filepath, 'w') as f:
                    json.dump(updated, f, indent=2)
        else:
            print(f"    ✗ Failed to update")

    print(f"\nSummary: {pushed} pushed, {skipped} unchanged")


def show_status() -> None:
    """Show sync status of all workflows."""

    # Load local workflows
    local_workflows = {}
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(OUTPUT_DIR, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    wf_id = data.get('id')
                    if wf_id:
                        local_workflows[wf_id] = (filepath, data)
            except (json.JSONDecodeError, IOError):
                continue

    print("Checking sync status...\n")

    for workflow_id in N8N_SYNCED_PROJECTS:
        workflow_id = workflow_id.strip()
        if not workflow_id:
            continue

        remote = download_workflow(workflow_id)
        if not remote:
            print(f"  {workflow_id}: ✗ Could not fetch remote")
            continue

        name = remote.get('name', workflow_id)

        if workflow_id not in local_workflows:
            print(f"  {name}: ⬇ Remote only (needs pull)")
            continue

        _, local_data = local_workflows[workflow_id]

        if workflows_differ(local_data, remote):
            print(f"  {name}: ⬆ Local changes (needs push)")
        else:
            print(f"  {name}: ✓ In sync")


def main():
    parser = argparse.ArgumentParser(description="Sync n8n workflows")
    parser.add_argument(
        'command',
        choices=['pull', 'push', 'status'],
        help='Command to execute'
    )
    parser.add_argument(
        'name',
        nargs='?',
        help='Workflow name filter (for push command)'
    )

    args = parser.parse_args()

    if not N8N_API_TOKEN:
        print("Error: N8N_API_TOKEN not set in environment")
        sys.exit(1)

    if args.command == 'pull':
        pull_workflows()
    elif args.command == 'push':
        push_workflows(args.name)
    elif args.command == 'status':
        show_status()


if __name__ == "__main__":
    main()
