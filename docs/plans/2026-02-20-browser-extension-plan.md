# Browser Extension Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port the LinkedIn Lead Uploader Chrome extension into leadgen-pipeline with TypeScript rewrite, JWT auth, PostgreSQL storage, and dual-environment builds (prod/staging).

**Architecture:** New `extension/` directory with TypeScript Chrome MV3 extension built with Vite. New Flask API routes (`/api/extension/*`) for lead import, activity sync, and status. New `activities` PostgreSQL table. React Preferences page accessed via user dropdown menu.

**Tech Stack:** TypeScript, Vite (extension build), Chrome Extension MV3, Flask/SQLAlchemy (API), React (Preferences page), PostgreSQL (activities table)

**Design Doc:** `docs/plans/2026-02-20-browser-extension-design.md`

**Source Material:**
- LinkedIn Lead Uploader: `~/git/linkedin-lead-uploader/` (existing Chrome extension, vanilla JS)
- Airtable LinkedIn Importer: `~/git/airtable-linkedin-importer/` (CSV import CLI, company matching logic)

---

## Task 1: Database Migration — Activities Table + Contacts Columns

**Files:**
- Create: `migrations/028_extension_activities.sql`
- Modify: `api/models.py` (add Activity model, extend Contact)
- Test: `tests/unit/test_extension_routes.py`

**Step 1: Write the migration SQL**

Create `migrations/028_extension_activities.sql`:

```sql
-- Migration 028: Extension activities table + contacts stub fields
-- Supports browser extension lead import and activity sync

-- New activities table
CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID REFERENCES contacts(id),
    owner_id UUID REFERENCES owners(id),
    event_type TEXT NOT NULL,
    activity_name TEXT,
    activity_detail TEXT,
    source TEXT NOT NULL DEFAULT 'linkedin_extension',
    external_id TEXT,
    timestamp TIMESTAMPTZ,
    payload JSONB DEFAULT '{}',
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Dedup index: external_id unique per tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_tenant_external_id
    ON activities(tenant_id, external_id) WHERE external_id IS NOT NULL;

-- Query indexes
CREATE INDEX IF NOT EXISTS idx_activities_tenant_contact
    ON activities(tenant_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_type_ts
    ON activities(tenant_id, event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_source
    ON activities(tenant_id, source);

-- Contact stub fields
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_stub BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS import_source TEXT;

-- Index for finding stub contacts
CREATE INDEX IF NOT EXISTS idx_contacts_is_stub
    ON contacts(tenant_id, is_stub) WHERE is_stub = true;
```

**Step 2: Add Activity model to SQLAlchemy**

Modify `api/models.py` — add after the `EnrichmentSchedule` class (or at end of models):

```python
class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.Text, db.ForeignKey("tenants.id"), nullable=False)
    contact_id = db.Column(db.Text, db.ForeignKey("contacts.id"), nullable=True)
    owner_id = db.Column(db.Text, db.ForeignKey("owners.id"), nullable=True)
    event_type = db.Column(db.Text, nullable=False)
    activity_name = db.Column(db.Text)
    activity_detail = db.Column(db.Text)
    source = db.Column(db.Text, nullable=False, default="linkedin_extension")
    external_id = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True))
    payload = db.Column(db.JSON, default=dict)
    processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    contact = db.relationship("Contact", foreign_keys=[contact_id])
    owner = db.relationship("Owner", foreign_keys=[owner_id])
```

**Step 3: Add stub fields to Contact model**

In `api/models.py`, find the `Contact` class and add these columns (after `processed_enrich`):

```python
    is_stub = db.Column(db.Boolean, default=False)
    import_source = db.Column(db.Text)
```

**Step 4: Verify migration format matches existing pattern**

Run: `ls migrations/` to confirm naming convention (NNN_name.sql).

**Step 5: Commit**

```bash
git add migrations/028_extension_activities.sql api/models.py
git commit -m "feat: add activities table and contact stub fields for extension integration"
```

---

## Task 2: Extension Routes — Lead Import (TDD)

**Files:**
- Create: `api/routes/extension_routes.py`
- Modify: `api/routes/__init__.py`
- Create: `tests/unit/test_extension_routes.py`

**Step 1: Write failing tests for lead import**

Create `tests/unit/test_extension_routes.py`:

```python
"""Tests for browser extension API routes."""
import pytest


class TestUploadLeads:
    """POST /api/extension/leads"""

    def test_creates_contacts_and_companies(self, client, seed_data, auth_header):
        """Given new leads, creates contacts and companies."""
        leads = [
            {
                "name": "Jane Smith",
                "job_title": "CTO",
                "company_name": "NewCorp Inc",
                "linkedin_url": "https://www.linkedin.com/in/janesmith",
                "company_website": "https://newcorp.com",
                "revenue": "$10M-50M",
                "headcount": "51-200",
                "industry": "Technology",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "test-import"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created_contacts"] == 1
        assert data["created_companies"] == 1
        assert data["skipped_duplicates"] == 0

    def test_deduplicates_by_linkedin_url(self, client, seed_data, auth_header):
        """Given duplicate linkedin_url, skips the duplicate."""
        leads = [
            {
                "name": "Jane Smith",
                "job_title": "CTO",
                "company_name": "NewCorp Inc",
                "linkedin_url": "https://www.linkedin.com/in/janesmith",
            }
        ]
        # First upload
        client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "import-1"},
            headers=auth_header,
        )
        # Second upload — same linkedin_url
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "import-2"},
            headers=auth_header,
        )
        data = resp.get_json()
        assert data["created_contacts"] == 0
        assert data["skipped_duplicates"] == 1

    def test_links_to_existing_company(self, client, seed_data, auth_header):
        """Given a lead whose company already exists, links to it without creating new."""
        # seed_data should have at least one company — check conftest.py
        # Use that company's name in the lead
        leads = [
            {
                "name": "New Person",
                "job_title": "Engineer",
                "company_name": "Test Company",  # matches seeded company
                "linkedin_url": "https://www.linkedin.com/in/newperson",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "test"},
            headers=auth_header,
        )
        data = resp.get_json()
        assert data["created_contacts"] == 1
        assert data["created_companies"] == 0  # reused existing

    def test_requires_auth(self, client):
        """Given no auth header, returns 401."""
        resp = client.post(
            "/api/extension/leads",
            json={"leads": [], "source": "test", "tag": "test"},
        )
        assert resp.status_code == 401

    def test_sets_owner_and_import_source(self, client, seed_data, auth_header):
        """Given leads, sets owner_id from user and import_source on contact."""
        leads = [
            {
                "name": "Tagged Person",
                "job_title": "PM",
                "company_name": "TagCorp",
                "linkedin_url": "https://www.linkedin.com/in/taggedperson",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "sn-import"},
            headers=auth_header,
        )
        assert resp.status_code == 200

        # Verify contact has import_source set
        from api.models import Contact
        contact = Contact.query.filter_by(
            linkedin_url="https://www.linkedin.com/in/taggedperson"
        ).first()
        assert contact is not None
        assert contact.import_source == "sales_navigator"
        assert contact.is_stub is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_extension_routes.py -v`
Expected: FAIL (import errors, route not found)

**Step 3: Create extension routes blueprint**

Create `api/routes/extension_routes.py`:

```python
"""Browser extension API routes for lead import, activity sync, and status."""
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import Activity, Company, Contact, Owner, Tag, db

extension_bp = Blueprint("extension", __name__, url_prefix="/api/extension")


@extension_bp.before_request
@require_auth
def before_request():
    resolve_tenant()


@extension_bp.route("/leads", methods=["POST"])
def upload_leads():
    """Import leads from browser extension (Sales Navigator extraction)."""
    data = request.get_json()
    if not data or "leads" not in data:
        return jsonify({"error": "Missing 'leads' in request body"}), 400

    leads = data["leads"]
    source = data.get("source", "sales_navigator")
    tag_name = data.get("tag")
    tenant_id = g.tenant_id
    owner_id = getattr(g.current_user, "owner_id", None)

    created_contacts = 0
    created_companies = 0
    skipped_duplicates = 0

    # Resolve or create tag
    tag = None
    if tag_name:
        tag = Tag.query.filter_by(tenant_id=tenant_id, name=tag_name).first()
        if not tag:
            tag = Tag(tenant_id=tenant_id, name=tag_name)
            db.session.add(tag)
            db.session.flush()

    for lead in leads:
        linkedin_url = (lead.get("linkedin_url") or "").strip()

        # Dedup by LinkedIn URL
        if linkedin_url:
            existing = Contact.query.filter_by(
                tenant_id=tenant_id, linkedin_url=linkedin_url
            ).first()
            if existing:
                skipped_duplicates += 1
                continue

        # Find or create company
        company = None
        company_name = (lead.get("company_name") or "").strip()
        if company_name:
            company = Company.query.filter(
                Company.tenant_id == tenant_id,
                db.func.lower(Company.name) == company_name.lower(),
            ).first()
            if not company:
                company = Company(
                    tenant_id=tenant_id,
                    name=company_name,
                    website=lead.get("company_website"),
                    industry=lead.get("industry"),
                    headcount=lead.get("headcount"),
                    revenue=lead.get("revenue"),
                    status="new",
                    owner_id=owner_id,
                )
                db.session.add(company)
                db.session.flush()
                created_companies += 1

        # Parse name
        full_name = (lead.get("name") or "").strip()
        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Create contact
        contact = Contact(
            tenant_id=tenant_id,
            first_name=first_name,
            last_name=last_name,
            job_title=lead.get("job_title"),
            linkedin_url=linkedin_url or None,
            company_id=company.id if company else None,
            owner_id=owner_id,
            import_source=source,
            is_stub=False,
        )
        db.session.add(contact)
        db.session.flush()

        # Link tag
        if tag:
            contact.tags.append(tag)

        created_contacts += 1

    db.session.commit()

    return jsonify(
        {
            "created_contacts": created_contacts,
            "created_companies": created_companies,
            "skipped_duplicates": skipped_duplicates,
        }
    )
```

NOTE: The exact column names on Company and Contact models need to be verified against `api/models.py`. The exploration found:
- Contact has: first_name, last_name, job_title, linkedin_url, company_id, owner_id, tags (relationship)
- Company has: name, website, industry, status, owner_id
- Check if headcount/revenue columns exist on Company — if not, store in a JSON field or skip

**Step 4: Register the blueprint**

In `api/routes/__init__.py`, add:

```python
from .extension_routes import extension_bp
```

And in the `register_routes(app)` function, add:

```python
    app.register_blueprint(extension_bp)
```

**Step 5: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_extension_routes.py -v`
Expected: Tests pass (may need fixture adjustments — see conftest.py for `seed_data` and `auth_header` fixture names)

**Step 6: Commit**

```bash
git add api/routes/extension_routes.py api/routes/__init__.py tests/unit/test_extension_routes.py
git commit -m "feat: add POST /api/extension/leads endpoint with dedup and company matching"
```

---

## Task 3: Extension Routes — Activity Sync (TDD)

**Files:**
- Modify: `api/routes/extension_routes.py`
- Modify: `tests/unit/test_extension_routes.py`

**Step 1: Write failing tests for activity sync**

Add to `tests/unit/test_extension_routes.py`:

```python
class TestUploadActivities:
    """POST /api/extension/activities"""

    def test_creates_activities(self, client, seed_data, auth_header):
        """Given new events, creates activity records."""
        events = [
            {
                "event_type": "message",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/existing-contact",
                "external_id": "ext_001",
                "payload": {
                    "contact_name": "Existing Contact",
                    "message": "Hey, interested in your product",
                    "direction": "received",
                },
            }
        ]
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created"] == 1
        assert data["skipped_duplicates"] == 0

    def test_deduplicates_by_external_id(self, client, seed_data, auth_header):
        """Given duplicate external_id, skips the duplicate."""
        events = [
            {
                "event_type": "message",
                "external_id": "ext_dedup",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/someone",
                "payload": {"contact_name": "Someone", "message": "Hi"},
            }
        ]
        client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=auth_header,
        )
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=auth_header,
        )
        data = resp.get_json()
        assert data["created"] == 0
        assert data["skipped_duplicates"] == 1

    def test_creates_stub_contact_for_unknown_linkedin_url(
        self, client, seed_data, auth_header
    ):
        """Given activity with unknown linkedin_url, creates stub contact."""
        events = [
            {
                "event_type": "message",
                "external_id": "ext_stub",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/unknown-person",
                "payload": {"contact_name": "Unknown Person", "message": "Hello"},
            }
        ]
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=auth_header,
        )
        assert resp.status_code == 200

        from api.models import Contact
        stub = Contact.query.filter_by(
            linkedin_url="https://www.linkedin.com/in/unknown-person"
        ).first()
        assert stub is not None
        assert stub.is_stub is True
        assert stub.import_source == "activity_stub"
        assert stub.first_name == "Unknown"
        assert stub.last_name == "Person"

    def test_requires_auth(self, client):
        """Given no auth header, returns 401."""
        resp = client.post(
            "/api/extension/activities",
            json={"events": []},
        )
        assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_extension_routes.py::TestUploadActivities -v`
Expected: FAIL

**Step 3: Implement activity sync endpoint**

Add to `api/routes/extension_routes.py`:

```python
@extension_bp.route("/activities", methods=["POST"])
def upload_activities():
    """Sync activity events from browser extension."""
    data = request.get_json()
    if not data or "events" not in data:
        return jsonify({"error": "Missing 'events' in request body"}), 400

    events = data["events"]
    tenant_id = g.tenant_id
    owner_id = getattr(g.current_user, "owner_id", None)

    created = 0
    skipped_duplicates = 0

    for event in events:
        external_id = event.get("external_id")

        # Dedup by external_id
        if external_id:
            existing = Activity.query.filter_by(
                tenant_id=tenant_id, external_id=external_id
            ).first()
            if existing:
                skipped_duplicates += 1
                continue

        # Resolve contact by LinkedIn URL
        contact_id = None
        linkedin_url = (event.get("contact_linkedin_url") or "").strip()
        if linkedin_url:
            contact = Contact.query.filter_by(
                tenant_id=tenant_id, linkedin_url=linkedin_url
            ).first()
            if not contact:
                # Create stub contact
                payload = event.get("payload", {})
                contact_name = (payload.get("contact_name") or "").strip()
                parts = contact_name.split(None, 1)
                contact = Contact(
                    tenant_id=tenant_id,
                    first_name=parts[0] if parts else "Unknown",
                    last_name=parts[1] if len(parts) > 1 else "",
                    linkedin_url=linkedin_url,
                    is_stub=True,
                    import_source="activity_stub",
                    owner_id=owner_id,
                )
                db.session.add(contact)
                db.session.flush()
            contact_id = contact.id

        # Parse timestamp
        ts = event.get("timestamp")
        timestamp = None
        if ts:
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

        # Extract display fields from payload
        payload = event.get("payload", {})

        activity = Activity(
            tenant_id=tenant_id,
            contact_id=contact_id,
            owner_id=owner_id,
            event_type=event.get("event_type", "event"),
            activity_name=payload.get("contact_name", ""),
            activity_detail=payload.get("message", ""),
            source="linkedin_extension",
            external_id=external_id,
            timestamp=timestamp,
            payload=payload,
        )
        db.session.add(activity)
        created += 1

    db.session.commit()

    return jsonify({"created": created, "skipped_duplicates": skipped_duplicates})
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/test_extension_routes.py::TestUploadActivities -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/routes/extension_routes.py tests/unit/test_extension_routes.py
git commit -m "feat: add POST /api/extension/activities endpoint with dedup and stub contacts"
```

---

## Task 4: Extension Routes — Status Endpoint (TDD)

**Files:**
- Modify: `api/routes/extension_routes.py`
- Modify: `tests/unit/test_extension_routes.py`

**Step 1: Write failing tests**

Add to `tests/unit/test_extension_routes.py`:

```python
class TestExtensionStatus:
    """GET /api/extension/status"""

    def test_returns_status_when_no_data(self, client, seed_data, auth_header):
        """Given no extension data, returns zeroed status."""
        resp = client.get("/api/extension/status", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False
        assert data["total_leads_imported"] == 0
        assert data["total_activities_synced"] == 0
        assert data["last_lead_sync"] is None
        assert data["last_activity_sync"] is None

    def test_returns_stats_after_imports(self, client, seed_data, auth_header):
        """Given prior imports, returns correct counts and timestamps."""
        # Upload some leads
        client.post(
            "/api/extension/leads",
            json={
                "leads": [
                    {
                        "name": "Status Test",
                        "linkedin_url": "https://linkedin.com/in/statustest",
                        "company_name": "StatusCorp",
                    }
                ],
                "source": "sales_navigator",
                "tag": "status-test",
            },
            headers=auth_header,
        )
        # Upload some activities
        client.post(
            "/api/extension/activities",
            json={
                "events": [
                    {
                        "event_type": "message",
                        "external_id": "status_ext_001",
                        "timestamp": "2026-02-20T10:30:00Z",
                        "contact_linkedin_url": "https://linkedin.com/in/statustest",
                        "payload": {"contact_name": "Status Test", "message": "Hi"},
                    }
                ]
            },
            headers=auth_header,
        )

        resp = client.get("/api/extension/status", headers=auth_header)
        data = resp.get_json()
        assert data["connected"] is True
        assert data["total_leads_imported"] == 1
        assert data["total_activities_synced"] == 1
        assert data["last_lead_sync"] is not None
        assert data["last_activity_sync"] is not None

    def test_requires_auth(self, client):
        resp = client.get("/api/extension/status")
        assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_extension_routes.py::TestExtensionStatus -v`

**Step 3: Implement status endpoint**

Add to `api/routes/extension_routes.py`:

```python
@extension_bp.route("/status", methods=["GET"])
def extension_status():
    """Get extension connection status and sync stats for current user."""
    tenant_id = g.tenant_id
    user_id = g.current_user.id
    owner_id = getattr(g.current_user, "owner_id", None)

    # Count leads imported by this user (via owner_id + import_source)
    lead_count = 0
    last_lead_sync = None
    if owner_id:
        lead_query = (
            db.session.query(
                db.func.count(Contact.id),
                db.func.max(Contact.created_at),
            )
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.owner_id == owner_id,
                Contact.import_source.isnot(None),
                Contact.is_stub.is_(False),
            )
            .first()
        )
        lead_count = lead_query[0] or 0
        last_lead_sync = lead_query[1]

    # Count activities synced by this user
    activity_count = 0
    last_activity_sync = None
    if owner_id:
        activity_query = (
            db.session.query(
                db.func.count(Activity.id),
                db.func.max(Activity.created_at),
            )
            .filter(
                Activity.tenant_id == tenant_id,
                Activity.owner_id == owner_id,
            )
            .first()
        )
        activity_count = activity_query[0] or 0
        last_activity_sync = activity_query[1]

    connected = lead_count > 0 or activity_count > 0

    return jsonify(
        {
            "connected": connected,
            "last_lead_sync": last_lead_sync.isoformat() if last_lead_sync else None,
            "last_activity_sync": (
                last_activity_sync.isoformat() if last_activity_sync else None
            ),
            "total_leads_imported": lead_count,
            "total_activities_synced": activity_count,
        }
    )
```

**Step 4: Run all extension tests**

Run: `python -m pytest tests/unit/test_extension_routes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add api/routes/extension_routes.py tests/unit/test_extension_routes.py
git commit -m "feat: add GET /api/extension/status endpoint"
```

---

## Task 5: Frontend — User Dropdown Menu

**Files:**
- Modify: `frontend/src/components/layout/AppNav.tsx`

**Context:** Currently the user's name is displayed as a static span at lines ~189-199 of AppNav.tsx. We need to convert this into a clickable dropdown with "Preferences" and "Logout" options.

**Step 1: Read current AppNav.tsx**

Read the file to understand the exact current structure of the user name display and logout button.

**Step 2: Add user dropdown**

Replace the static user name display with a dropdown menu component. Use Headless UI `Menu` (already likely available via Tailwind) or a simple custom dropdown with state.

```tsx
// Add state for dropdown
const [userMenuOpen, setUserMenuOpen] = useState(false);
const userMenuRef = useRef<HTMLDivElement>(null);

// Close on outside click
useEffect(() => {
  const handleClickOutside = (e: MouseEvent) => {
    if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
      setUserMenuOpen(false);
    }
  };
  document.addEventListener('mousedown', handleClickOutside);
  return () => document.removeEventListener('mousedown', handleClickOutside);
}, []);

// In the JSX where user name is displayed:
<div className="relative" ref={userMenuRef}>
  <button
    onClick={() => setUserMenuOpen(!userMenuOpen)}
    className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-gray-100 text-sm"
  >
    <span>{user?.display_name || user?.email}</span>
    <ChevronDownIcon className="w-4 h-4" />
  </button>
  {userMenuOpen && (
    <div className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-50">
      <Link
        to={`/${namespace}/preferences`}
        className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
        onClick={() => setUserMenuOpen(false)}
      >
        Preferences
      </Link>
      <hr className="my-1 border-gray-200" />
      <button
        onClick={handleLogout}
        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
      >
        Logout
      </button>
    </div>
  )}
</div>
```

NOTE: Adjust class names and imports to match existing patterns in the codebase. Check what icon library is used (Heroicons, Lucide, etc.).

**Step 3: Run frontend dev server and verify visually**

Run: `cd /Users/michal/git/leadgen-pipeline && make dev` (or `DEV_SLOT=N make dev` in worktree)
Navigate to the dashboard, verify the user dropdown appears and opens correctly.

**Step 4: Commit**

```bash
git add frontend/src/components/layout/AppNav.tsx
git commit -m "feat: add user dropdown menu with Preferences link"
```

---

## Task 6: Frontend — Preferences Page

**Files:**
- Create: `frontend/src/pages/preferences/PreferencesPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

**Step 1: Create PreferencesPage component**

Create `frontend/src/pages/preferences/PreferencesPage.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { apiFetch } from '../../api/client';

interface ExtensionStatus {
  connected: boolean;
  last_lead_sync: string | null;
  last_activity_sync: string | null;
  total_leads_imported: number;
  total_activities_synced: number;
}

export default function PreferencesPage() {
  const [status, setStatus] = useState<ExtensionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ExtensionStatus>('/api/extension/status')
      .then(setStatus)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-semibold mb-6">Preferences</h1>
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-semibold mb-6">Preferences</h1>
        <p className="text-red-500">Failed to load extension status: {error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-semibold mb-6">Preferences</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium mb-4">Browser Extension</h2>

        <div className="flex items-center gap-2 mb-4">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${
              status?.connected ? 'bg-green-500' : 'bg-gray-400'
            }`}
          />
          <span className="text-sm text-gray-700">
            {status?.connected ? 'Connected' : 'Not connected'}
          </span>
          {status?.connected && status.last_lead_sync && (
            <span className="text-xs text-gray-400 ml-2">
              Last sync {formatRelative(status.last_lead_sync)}
            </span>
          )}
        </div>

        {status?.connected && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Leads imported</dt>
              <dd className="text-lg font-medium">{status.total_leads_imported}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Activities synced</dt>
              <dd className="text-lg font-medium">{status.total_activities_synced}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Last lead sync</dt>
              <dd>{status.last_lead_sync ? formatDate(status.last_lead_sync) : '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Last activity sync</dt>
              <dd>{status.last_activity_sync ? formatDate(status.last_activity_sync) : '—'}</dd>
            </div>
          </div>
        )}

        {!status?.connected && (
          <p className="text-sm text-gray-500">
            Install the VisionVolve Leads browser extension and log in to connect.
          </p>
        )}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

**Step 2: Add route in App.tsx**

In `frontend/src/App.tsx`, add the route inside the authenticated namespace routes (look for the pattern with other pages like `messages`, `contacts`, etc.):

```tsx
import PreferencesPage from './pages/preferences/PreferencesPage';

// Inside routes:
<Route path="preferences" element={<PreferencesPage />} />
```

**Step 3: Verify in browser**

Navigate to `http://localhost:5173/{namespace}/preferences` — should show "Not connected" state.

**Step 4: Commit**

```bash
git add frontend/src/pages/preferences/PreferencesPage.tsx frontend/src/App.tsx
git commit -m "feat: add Preferences page with extension connection status"
```

---

## Task 7: Extension Scaffolding

**Files:**
- Create: `extension/package.json`
- Create: `extension/tsconfig.json`
- Create: `extension/vite.config.ts`
- Create: `extension/manifests/base.json`
- Create: `extension/manifests/prod.json`
- Create: `extension/manifests/staging.json`
- Create: `extension/src/common/types.ts`
- Create: `extension/src/common/config.ts`

**Step 1: Create package.json**

Create `extension/package.json`:

```json
{
  "name": "visionvolve-leads-extension",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev:prod": "vite build --watch --mode production",
    "dev:staging": "vite build --watch --mode staging",
    "build:prod": "vite build --mode production",
    "build:staging": "vite build --mode staging",
    "build:all": "npm run build:prod && npm run build:staging",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {},
  "devDependencies": {
    "@crxjs/vite-plugin": "^2.0.0-beta.28",
    "typescript": "~5.9.0",
    "vite": "^7.3.0"
  }
}
```

NOTE: Check if `@crxjs/vite-plugin` supports Vite 7. If not, use `@nicedoc/vite-plugin-crx` or manual manifest generation. An alternative approach without CRXJS:

```typescript
// vite.config.ts — manual MV3 build (no CRXJS dependency)
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const env = mode === 'production' ? 'prod' : 'staging';

  return {
    build: {
      outDir: `dist/${env}`,
      emptyOutDir: true,
      rollupOptions: {
        input: {
          'service-worker': resolve(__dirname, 'src/background/service-worker.ts'),
          'sales-navigator': resolve(__dirname, 'src/content/sales-navigator.ts'),
          'activity-monitor': resolve(__dirname, 'src/content/activity-monitor.ts'),
          'popup': resolve(__dirname, 'src/popup/popup.html'),
        },
        output: {
          entryFileNames: '[name].js',
          chunkFileNames: 'chunks/[name].js',
        },
      },
    },
    define: {
      __API_BASE__: JSON.stringify(
        mode === 'production'
          ? 'https://leadgen.visionvolve.com'
          : 'https://leadgen-staging.visionvolve.com'
      ),
      __EXT_ENV__: JSON.stringify(env),
    },
  };
});
```

**Step 2: Create tsconfig.json**

Create `extension/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "outDir": "dist",
    "rootDir": "src",
    "types": ["chrome"]
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

Add `@types/chrome` to devDependencies in package.json.

**Step 3: Create manifest files**

Create `extension/manifests/base.json`:

```json
{
  "manifest_version": 3,
  "version": "1.0.0",
  "permissions": ["activeTab", "scripting", "storage", "alarms", "tabs"],
  "host_permissions": [
    "https://www.linkedin.com/*"
  ],
  "background": {
    "service_worker": "service-worker.js",
    "type": "module"
  },
  "action": {
    "default_popup": "popup.html"
  },
  "content_scripts": [
    {
      "matches": ["https://www.linkedin.com/sales/*"],
      "js": ["sales-navigator.js"],
      "run_at": "document_idle"
    },
    {
      "matches": [
        "https://www.linkedin.com/messaging/*",
        "https://www.linkedin.com/mynetwork/*"
      ],
      "js": ["activity-monitor.js"],
      "run_at": "document_idle"
    }
  ]
}
```

Create `extension/manifests/prod.json`:

```json
{
  "name": "VisionVolve Leads",
  "description": "Lead extraction and activity monitoring for VisionVolve",
  "icons": {
    "16": "icons/prod/16.png",
    "48": "icons/prod/48.png",
    "128": "icons/prod/128.png"
  },
  "host_permissions": [
    "https://www.linkedin.com/*",
    "https://leadgen.visionvolve.com/*"
  ]
}
```

Create `extension/manifests/staging.json`:

```json
{
  "name": "VisionVolve Leads [STAGING]",
  "description": "Lead extraction and activity monitoring (STAGING)",
  "icons": {
    "16": "icons/staging/16.png",
    "48": "icons/staging/48.png",
    "128": "icons/staging/128.png"
  },
  "host_permissions": [
    "https://www.linkedin.com/*",
    "https://leadgen-staging.visionvolve.com/*"
  ]
}
```

NOTE: The build script needs to merge base.json + environment.json into the final manifest.json in each dist folder. Add a small merge script or handle in vite.config.ts.

**Step 4: Create types.ts**

Create `extension/src/common/types.ts`:

```typescript
export interface Lead {
  name: string;
  job_title?: string;
  company_name?: string;
  linkedin_url?: string;
  company_website?: string;
  revenue?: string;
  headcount?: string;
  industry?: string;
}

export interface ActivityEvent {
  event_type: 'message' | 'event';
  timestamp: string;
  contact_linkedin_url: string;
  external_id: string;
  payload: {
    contact_name: string;
    message?: string;
    conversation_id?: string;
    message_id?: string;
    sender_id?: string;
    direction?: 'sent' | 'received';
  };
}

export interface AuthState {
  access_token: string;
  refresh_token: string;
  namespace: string;
  user: {
    id: string;
    email: string;
    display_name: string;
    owner_id: string | null;
    roles: Record<string, string>;
  };
  token_stored_at: number;
}

export interface UploadLeadsResponse {
  created_contacts: number;
  created_companies: number;
  skipped_duplicates: number;
}

export interface UploadActivitiesResponse {
  created: number;
  skipped_duplicates: number;
}

export interface ExtensionStatus {
  connected: boolean;
  last_lead_sync: string | null;
  last_activity_sync: string | null;
  total_leads_imported: number;
  total_activities_synced: number;
}
```

**Step 5: Create config.ts**

Create `extension/src/common/config.ts`:

```typescript
declare const __API_BASE__: string;
declare const __EXT_ENV__: string;

export const config = {
  apiBase: __API_BASE__,
  environment: __EXT_ENV__ as 'prod' | 'staging',
  tokenRefreshBuffer: 60_000, // refresh 1 min before expiry
  activitySyncInterval: 30, // minutes
  activityBatchSize: 50,
  leadEnrichDelay: 500, // ms between LinkedIn API calls
};
```

**Step 6: Commit**

```bash
git add extension/
git commit -m "feat: scaffold extension with TypeScript config, manifests, and types"
```

---

## Task 8: Extension Auth Module

**Files:**
- Create: `extension/src/common/auth.ts`
- Create: `extension/src/common/api-client.ts`

**Step 1: Create auth.ts**

Create `extension/src/common/auth.ts`:

```typescript
import type { AuthState } from './types';
import { config } from './config';

const STORAGE_KEY = 'auth_state';

export async function getAuthState(): Promise<AuthState | null> {
  const result = await chrome.storage.local.get(STORAGE_KEY);
  return result[STORAGE_KEY] ?? null;
}

export async function storeAuthState(state: AuthState): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
}

export async function clearAuthState(): Promise<void> {
  await chrome.storage.local.remove(STORAGE_KEY);
}

export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const expiresAt = payload.exp * 1000;
    return Date.now() > expiresAt - config.tokenRefreshBuffer;
  } catch {
    return true;
  }
}

export async function login(
  email: string,
  password: string
): Promise<AuthState> {
  const resp = await fetch(`${config.apiBase}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: 'Login failed' }));
    throw new Error(err.error || `Login failed (${resp.status})`);
  }

  const data = await resp.json();
  const roles = data.user.roles || {};
  const namespaces = Object.keys(roles);

  // Auto-select namespace if only one
  const namespace = namespaces.length === 1 ? namespaces[0] : '';

  const state: AuthState = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    namespace,
    user: {
      id: data.user.id,
      email: data.user.email,
      display_name: data.user.display_name,
      owner_id: data.user.owner_id,
      roles,
    },
    token_stored_at: Date.now(),
  };

  await storeAuthState(state);
  return state;
}

export async function refreshToken(): Promise<string> {
  const state = await getAuthState();
  if (!state) throw new Error('Not authenticated');

  const resp = await fetch(`${config.apiBase}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: state.refresh_token }),
  });

  if (!resp.ok) {
    await clearAuthState();
    throw new Error('Session expired — please log in again');
  }

  const data = await resp.json();
  const updated: AuthState = {
    ...state,
    access_token: data.access_token,
    token_stored_at: Date.now(),
  };
  await storeAuthState(updated);
  return data.access_token;
}

export async function logout(): Promise<void> {
  await clearAuthState();
}
```

**Step 2: Create api-client.ts**

Create `extension/src/common/api-client.ts`:

```typescript
import type {
  ExtensionStatus,
  Lead,
  ActivityEvent,
  UploadLeadsResponse,
  UploadActivitiesResponse,
} from './types';
import { config } from './config';
import { getAuthState, isTokenExpired, refreshToken } from './auth';

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function getValidToken(): Promise<string> {
  const state = await getAuthState();
  if (!state) throw new ApiError(401, 'Not authenticated');

  if (isTokenExpired(state.access_token)) {
    return refreshToken();
  }
  return state.access_token;
}

async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const token = await getValidToken();
  const state = await getAuthState();

  const resp = await fetch(`${config.apiBase}${path}`, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      'X-Namespace': state?.namespace || '',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (resp.status === 401) {
    // One retry after refresh
    const newToken = await refreshToken();
    const retry = await fetch(`${config.apiBase}${path}`, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${newToken}`,
        'X-Namespace': state?.namespace || '',
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    if (!retry.ok) {
      throw new ApiError(retry.status, `API error: ${retry.statusText}`);
    }
    return retry.json();
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new ApiError(resp.status, err.error || `API error: ${resp.status}`);
  }

  return resp.json();
}

export async function uploadLeads(
  leads: Lead[],
  source: string,
  tag: string
): Promise<UploadLeadsResponse> {
  return apiFetch('/api/extension/leads', {
    method: 'POST',
    body: { leads, source, tag },
  });
}

export async function uploadActivities(
  events: ActivityEvent[]
): Promise<UploadActivitiesResponse> {
  return apiFetch('/api/extension/activities', {
    method: 'POST',
    body: { events },
  });
}

export async function getStatus(): Promise<ExtensionStatus> {
  return apiFetch('/api/extension/status');
}
```

**Step 3: Commit**

```bash
git add extension/src/common/auth.ts extension/src/common/api-client.ts
git commit -m "feat: add extension auth and API client modules"
```

---

## Task 9: Extension Popup

**Files:**
- Create: `extension/src/popup/popup.html`
- Create: `extension/src/popup/popup.ts`

**Step 1: Create popup.html**

Create `extension/src/popup/popup.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      width: 320px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      color: #1a1a1a;
      background: #fff;
    }
    .header {
      padding: 16px;
      background: linear-gradient(135deg, #6E2C8B 0%, #4A1D6B 100%);
      color: white;
    }
    .header h1 { font-size: 16px; font-weight: 600; }
    .header .env-badge {
      display: inline-block;
      font-size: 10px;
      background: rgba(255,255,255,0.2);
      padding: 2px 6px;
      border-radius: 4px;
      margin-left: 8px;
    }
    .content { padding: 16px; }
    .login-form { display: flex; flex-direction: column; gap: 12px; }
    .login-form input {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 14px;
    }
    .login-form input:focus { outline: none; border-color: #6E2C8B; }
    .btn {
      padding: 8px 16px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
    }
    .btn-primary { background: #6E2C8B; color: white; }
    .btn-primary:hover { background: #5a2474; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary {
      background: transparent;
      color: #666;
      border: 1px solid #ddd;
    }
    .btn-sync { background: #059669; color: white; }
    .btn-sync:hover { background: #047857; }
    .error { color: #dc2626; font-size: 12px; margin-top: 4px; }
    .status { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .status-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #22c55e;
    }
    .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }
    .stat { text-align: center; padding: 8px; background: #f9fafb; border-radius: 6px; }
    .stat-value { font-size: 20px; font-weight: 600; color: #6E2C8B; }
    .stat-label { font-size: 11px; color: #666; }
    .actions { display: flex; gap: 8px; margin-top: 12px; }
    .actions .btn { flex: 1; }
    .namespace-picker select {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 14px;
    }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="header">
    <h1>VisionVolve Leads <span id="env-badge" class="env-badge"></span></h1>
  </div>

  <!-- Login View -->
  <div id="login-view" class="content">
    <form class="login-form" id="login-form">
      <input type="email" id="email" placeholder="Email" required />
      <input type="password" id="password" placeholder="Password" required />
      <button type="submit" class="btn btn-primary" id="login-btn">Log In</button>
      <div id="login-error" class="error hidden"></div>
    </form>
  </div>

  <!-- Namespace Picker (shown when multiple namespaces) -->
  <div id="namespace-view" class="content hidden">
    <p style="margin-bottom: 8px;">Select workspace:</p>
    <div class="namespace-picker">
      <select id="namespace-select"></select>
    </div>
    <button class="btn btn-primary" id="namespace-confirm" style="margin-top: 12px; width: 100%;">
      Continue
    </button>
  </div>

  <!-- Connected View -->
  <div id="connected-view" class="content hidden">
    <div class="status">
      <span class="status-dot"></span>
      <span id="user-email"></span>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-value" id="lead-count">0</div>
        <div class="stat-label">Leads</div>
      </div>
      <div class="stat">
        <div class="stat-value" id="activity-count">0</div>
        <div class="stat-label">Activities</div>
      </div>
    </div>
    <div class="actions">
      <button class="btn btn-sync" id="sync-btn">Sync Now</button>
      <button class="btn btn-secondary" id="logout-btn">Logout</button>
    </div>
    <div id="sync-status" style="margin-top: 8px; font-size: 12px; color: #666;"></div>
  </div>

  <script type="module" src="./popup.ts"></script>
</body>
</html>
```

**Step 2: Create popup.ts**

Create `extension/src/popup/popup.ts`:

```typescript
import { login, logout, getAuthState } from '../common/auth';
import { getStatus } from '../common/api-client';
import { config } from '../common/config';
import type { AuthState } from '../common/types';

// DOM elements
const loginView = document.getElementById('login-view')!;
const namespaceView = document.getElementById('namespace-view')!;
const connectedView = document.getElementById('connected-view')!;
const loginForm = document.getElementById('login-form') as HTMLFormElement;
const emailInput = document.getElementById('email') as HTMLInputElement;
const passwordInput = document.getElementById('password') as HTMLInputElement;
const loginBtn = document.getElementById('login-btn') as HTMLButtonElement;
const loginError = document.getElementById('login-error')!;
const envBadge = document.getElementById('env-badge')!;
const namespaceSelect = document.getElementById('namespace-select') as HTMLSelectElement;
const namespaceConfirm = document.getElementById('namespace-confirm')!;
const userEmail = document.getElementById('user-email')!;
const leadCount = document.getElementById('lead-count')!;
const activityCount = document.getElementById('activity-count')!;
const syncBtn = document.getElementById('sync-btn')!;
const logoutBtn = document.getElementById('logout-btn')!;
const syncStatus = document.getElementById('sync-status')!;

// Show environment badge
if (config.environment === 'staging') {
  envBadge.textContent = 'STAGING';
  envBadge.style.background = 'rgba(249, 115, 22, 0.3)';
}

function showView(view: 'login' | 'namespace' | 'connected') {
  loginView.classList.toggle('hidden', view !== 'login');
  namespaceView.classList.toggle('hidden', view !== 'namespace');
  connectedView.classList.toggle('hidden', view !== 'connected');
}

async function showConnected(state: AuthState) {
  userEmail.textContent = state.user.email;
  showView('connected');

  try {
    const status = await getStatus();
    leadCount.textContent = String(status.total_leads_imported);
    activityCount.textContent = String(status.total_activities_synced);
  } catch {
    leadCount.textContent = '\u2014';
    activityCount.textContent = '\u2014';
  }
}

// Init: check if already logged in
async function init() {
  const state = await getAuthState();
  if (state && state.namespace) {
    await showConnected(state);
  } else if (state && !state.namespace) {
    // Need namespace selection
    showNamespacePicker(state);
  } else {
    showView('login');
  }
}

function showNamespacePicker(state: AuthState) {
  // Clear existing options safely
  while (namespaceSelect.firstChild) {
    namespaceSelect.removeChild(namespaceSelect.firstChild);
  }
  for (const ns of Object.keys(state.user.roles)) {
    const opt = document.createElement('option');
    opt.value = ns;
    opt.textContent = ns;
    namespaceSelect.appendChild(opt);
  }
  showView('namespace');
}

// Login handler
loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  loginBtn.disabled = true;
  loginError.classList.add('hidden');

  try {
    const state = await login(emailInput.value, passwordInput.value);
    if (!state.namespace) {
      showNamespacePicker(state);
    } else {
      await showConnected(state);
    }
  } catch (err) {
    loginError.textContent = err instanceof Error ? err.message : 'Login failed';
    loginError.classList.remove('hidden');
  } finally {
    loginBtn.disabled = false;
  }
});

// Namespace confirm
namespaceConfirm.addEventListener('click', async () => {
  const state = await getAuthState();
  if (!state) return;
  const updated = { ...state, namespace: namespaceSelect.value };
  const { storeAuthState } = await import('../common/auth');
  await storeAuthState(updated);
  await showConnected(updated);
});

// Sync button
syncBtn.addEventListener('click', async () => {
  syncStatus.textContent = 'Syncing activities...';
  try {
    // Send message to service worker to trigger sync
    chrome.runtime.sendMessage({ type: 'sync_activities' }, (response) => {
      if (response?.success) {
        syncStatus.textContent = `Synced: ${response.created} new activities`;
      } else {
        syncStatus.textContent = response?.error || 'Sync failed';
      }
    });
  } catch {
    syncStatus.textContent = 'Sync failed';
  }
});

// Logout button
logoutBtn.addEventListener('click', async () => {
  await logout();
  showView('login');
});

init();
```

**Step 3: Commit**

```bash
git add extension/src/popup/
git commit -m "feat: add extension popup with login, namespace picker, and status display"
```

---

## Task 10: Extension Content Scripts

**Files:**
- Create: `extension/src/content/sales-navigator.ts`
- Create: `extension/src/content/activity-monitor.ts`

**Context:** Port from `~/git/linkedin-lead-uploader/content.js` (21KB) and `~/git/linkedin-lead-uploader/activity-monitor.js` (30KB). Rewrite in TypeScript, extract hardcoded URLs, use message passing to service worker instead of direct API calls.

**Step 1: Create sales-navigator.ts**

Port the Sales Navigator extraction logic from `~/git/linkedin-lead-uploader/content.js`. Key changes:
- TypeScript with proper types
- Send extracted leads to service worker via `chrome.runtime.sendMessage` instead of direct Supabase upload
- Remove hardcoded URLs (use config via service worker relay)
- Keep LinkedIn CSRF token extraction and Sales API calls (these run in content script context)
- Keep rate limiting logic (500ms base, exponential backoff)
- Keep multi-page detection (background handles orchestration)

The content script should:
1. Detect Sales Navigator list page (`/sales/lists/people/` URL pattern)
2. Extract CSRF token from cookies
3. Parse lead rows from DOM (`<tr data-row-id>`)
4. Enrich each lead with LinkedIn Sales API calls (profile URL, company data)
5. Send enriched leads to service worker: `chrome.runtime.sendMessage({ type: 'leads_extracted', leads: [...] })`

Read `~/git/linkedin-lead-uploader/content.js` for the exact extraction logic and API endpoints to port.

**Step 2: Create activity-monitor.ts**

Port from `~/git/linkedin-lead-uploader/activity-monitor.js`. Key changes:
- TypeScript with ActivityEvent type
- Send events to service worker instead of direct n8n webhook calls
- Keep deterministic external_id generation
- Keep conversation scraping logic for messaging pages
- Keep rate limiting (max 15 API calls per sync, 2s between requests)

The content script should:
1. Detect LinkedIn messaging page (`/messaging/` URL pattern)
2. Scrape visible conversations
3. Extract message data (sender, content, timestamp, direction)
4. Generate deterministic external_id per message
5. Send to service worker: `chrome.runtime.sendMessage({ type: 'activities_scraped', events: [...] })`

Read `~/git/linkedin-lead-uploader/activity-monitor.js` for the exact scraping logic.

NOTE: These are the largest files and require careful porting. The implementer should read the original source files and rewrite in TypeScript while preserving the core logic.

**Step 3: Commit**

```bash
git add extension/src/content/
git commit -m "feat: add content scripts for Sales Navigator extraction and activity monitoring"
```

---

## Task 11: Extension Service Worker

**Files:**
- Create: `extension/src/background/service-worker.ts`

**Step 1: Create service-worker.ts**

Port from `~/git/linkedin-lead-uploader/background.js`. Key changes:
- TypeScript
- Route lead uploads and activity syncs through API client (not direct webhook calls)
- Handle multi-page orchestration state
- Schedule periodic activity sync via chrome.alarms

```typescript
import { uploadLeads, uploadActivities } from '../common/api-client';
import { getAuthState } from '../common/auth';
import { config } from '../common/config';
import type { Lead, ActivityEvent } from '../common/types';

// Activity buffer — accumulates events between syncs
let activityBuffer: ActivityEvent[] = [];

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'leads_extracted') {
    handleLeadUpload(message.leads, message.source, message.tag)
      .then((resp) => sendResponse({ success: true, ...resp }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }

  if (message.type === 'activities_scraped') {
    activityBuffer.push(...message.events);
    sendResponse({ success: true, buffered: activityBuffer.length });
    return false;
  }

  if (message.type === 'sync_activities') {
    syncActivitiesBatch()
      .then((resp) => sendResponse({ success: true, ...resp }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'get_auth_state') {
    getAuthState().then((state) => sendResponse(state));
    return true;
  }
});

async function handleLeadUpload(leads: Lead[], source: string, tag: string) {
  const state = await getAuthState();
  if (!state) throw new Error('Not authenticated');
  return uploadLeads(leads, source, tag);
}

async function syncActivitiesBatch() {
  if (activityBuffer.length === 0) return { created: 0, skipped_duplicates: 0 };

  const batch = activityBuffer.splice(0, config.activityBatchSize);
  try {
    const result = await uploadActivities(batch);
    // Store last sync time
    await chrome.storage.local.set({ last_activity_sync: Date.now() });
    return result;
  } catch (err) {
    // Put events back in buffer on failure
    activityBuffer.unshift(...batch);
    throw err;
  }
}

// Schedule periodic activity sync
chrome.alarms.create('sync_activities', {
  periodInMinutes: config.activitySyncInterval,
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'sync_activities') {
    const state = await getAuthState();
    if (!state) return; // not logged in
    try {
      await syncActivitiesBatch();
    } catch {
      // Silent fail on scheduled sync — will retry next interval
    }
  }
});

// Multi-page orchestration (for Sales Navigator pagination)
// Port from ~/git/linkedin-lead-uploader/background.js — tab navigation detection
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;
  if (!tab.url?.includes('linkedin.com/sales/lists/people')) return;

  // Check if multi-page process is active
  const { multiPageProcess } = await chrome.storage.local.get('multiPageProcess');
  if (multiPageProcess?.active && multiPageProcess.tabId === tabId) {
    // Delay to let page render, then inject extraction
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { type: 'extract_page' });
    }, 5000);
  }
});
```

**Step 2: Commit**

```bash
git add extension/src/background/service-worker.ts
git commit -m "feat: add extension service worker with lead upload, activity sync, and multi-page orchestration"
```

---

## Task 12: Extension Icons

**Files:**
- Create: `extension/src/icons/prod/16.png`
- Create: `extension/src/icons/prod/48.png`
- Create: `extension/src/icons/prod/128.png`
- Create: `extension/src/icons/staging/16.png`
- Create: `extension/src/icons/staging/48.png`
- Create: `extension/src/icons/staging/128.png`

**Step 1: Generate icons**

Option A: Copy existing icons from `~/git/linkedin-lead-uploader/icons/` and create color variants.
Option B: Generate simple SVG -> PNG icons programmatically.

For prod: Purple (#6E2C8B) "V" logo or similar VisionVolve branding.
For staging: Orange (#F97316) version of the same icon.

If no design tool is available, create minimal placeholder icons:
- Use a simple colored square with a "V" letter
- Can be replaced later with proper branded icons

**Step 2: Commit**

```bash
git add extension/src/icons/
git commit -m "feat: add extension icons for prod (purple) and staging (orange)"
```

---

## Task 13: Extension Build & Test

**Step 1: Install dependencies**

```bash
cd /Users/michal/git/leadgen-pipeline/extension
npm install
```

**Step 2: Build both extensions**

```bash
npm run build:prod
npm run build:staging
```

Verify: `dist/prod/manifest.json` contains "VisionVolve Leads" and `dist/staging/manifest.json` contains "[STAGING]".

**Step 3: Type check**

```bash
npm run typecheck
```

Fix any TypeScript errors.

**Step 4: Manual test in Chrome**

1. Open `chrome://extensions/`
2. Enable Developer Mode
3. "Load unpacked" -> select `extension/dist/staging/`
4. Click extension icon -> login form appears
5. Enter staging credentials -> connected view
6. Navigate to LinkedIn Sales Navigator -> extraction should work
7. Load the prod extension separately to verify both can coexist

**Step 5: Commit**

```bash
git add extension/
git commit -m "feat: complete extension build system with prod and staging targets"
```

---

## Task 14: Run All Tests

**Step 1: Run backend tests**

```bash
cd /Users/michal/git/leadgen-pipeline
python -m pytest tests/unit/test_extension_routes.py -v
```

**Step 2: Run full test suite**

```bash
make test-all
```

**Step 3: Run lint**

```bash
make lint
```

Fix any issues.

**Step 4: Commit fixes if needed**

```bash
git add -A
git commit -m "fix: address lint and test issues"
```

---

## Task 15: Documentation Updates

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `CHANGELOG.md`
- Modify: `BACKLOG.md`

**Step 1: Update ARCHITECTURE.md**

Add a "Browser Extension" section describing:
- Extension architecture (popup + content scripts + service worker)
- Auth flow (login -> JWT -> chrome.storage -> auto-refresh)
- Data flow (leads -> POST /api/extension/leads, activities -> POST /api/extension/activities)
- Dual environment setup (prod/staging builds)

**Step 2: Update CHANGELOG.md**

Add entry:
```markdown
## [Unreleased]
### Added
- Browser extension for LinkedIn lead extraction and activity monitoring
- Extension auth via email/password login (reuses existing JWT system)
- POST /api/extension/leads — import leads with dedup by LinkedIn URL
- POST /api/extension/activities — sync activity events with dedup by external_id
- GET /api/extension/status — extension connection status for dashboard
- Activities table in PostgreSQL (migration 028)
- Stub contact creation for activities referencing unknown contacts
- User dropdown menu with Preferences link
- Preferences page showing extension connection status
- Dual-build system: purple (prod) and orange (staging) extensions
```

**Step 3: Update BACKLOG.md**

Mark BL-020 (Personal LinkedIn Connections Import) as partially addressed. Add new backlog item if needed for Chrome Web Store distribution.

**Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md CHANGELOG.md BACKLOG.md
git commit -m "docs: add browser extension architecture and changelog"
```

---

## Task Summary

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 1 | Database migration + models | S | None |
| 2 | Lead import endpoint (TDD) | M | Task 1 |
| 3 | Activity sync endpoint (TDD) | M | Task 1 |
| 4 | Status endpoint (TDD) | S | Tasks 2, 3 |
| 5 | User dropdown menu | S | None |
| 6 | Preferences page | S | Task 4 |
| 7 | Extension scaffolding | M | None |
| 8 | Extension auth + API client | M | Task 7 |
| 9 | Extension popup | M | Task 8 |
| 10 | Extension content scripts | L | Task 8 |
| 11 | Extension service worker | M | Tasks 8, 10 |
| 12 | Extension icons | S | None |
| 13 | Build & manual test | M | All extension tasks |
| 14 | Full test suite | S | All tasks |
| 15 | Documentation | S | All tasks |

**Parallel work possible:**
- Tasks 1-4 (backend) can run in parallel with Tasks 5-6 (frontend) and Tasks 7-12 (extension)
- Task 13 requires all extension tasks
- Tasks 14-15 require everything

**Total estimated effort:** XL (15 tasks, ~2400 lines new code)
