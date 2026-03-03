# Namespace Setup: unitedarts

## Date
2026-03-02

## Tenant Details
- **Name**: United Arts
- **Slug**: unitedarts
- **Tenant ID**: 4c0960ea-553d-4fba-808f-c7f9419f389e
- **Created via**: POST /api/tenants (API endpoint, super_admin auth)
- **Status**: Active

## User Assignment
- **User**: test@staging.local (Staging Test User)
- **User ID**: 00000000-0000-0000-0000-000000000099
- **Role**: admin (on unitedarts tenant)
- **Assigned via**: Direct INSERT into user_tenant_roles table (no API endpoint for user-tenant assignment)

## Verification Results

### JWT Roles (after re-login)
```json
{
  "unitedarts": "admin",
  "visionvolve": "admin"
}
```

### Namespace URL
- `https://leadgen-staging.visionvolve.com/unitedarts/` → HTTP 200

### API Access
- `GET /api/batches` with `X-Namespace: unitedarts` → `{"error": "Not found"}` (expected — empty namespace)
- `GET /api/health` → `{"status": "ok"}`

## Login Credentials
- **URL**: https://leadgen-staging.visionvolve.com/
- **Email**: test@staging.local
- **Password**: staging123
- **Post-login redirect**: /unitedarts/ (if unitedarts is first namespace in roles)

## Notes
- A pre-existing "United Arts" tenant with slug `united-arts` (hyphenated) already existed (id: 19071805-7533-4e7c-b95b-9084040790e2). The new `unitedarts` (no hyphen) is a separate tenant.
- No Docker postgres container on staging VPS — database is on RDS (`leadgen_staging` database).
- Database access goes through the `leadgen-api-rev-latest` container which has the DATABASE_URL environment variable.
- The namespace is empty (no batches, contacts, companies, or messages). Data would need to be seeded separately for testing.
