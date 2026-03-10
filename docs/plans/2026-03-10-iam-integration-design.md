# IAM Integration Design — Leadgen Pipeline

**Date**: 2026-03-10
**Status**: Draft
**Approach**: Hybrid (IAM for auth, local users for tenant data)

---

## 1. Overview

Integrate leadgen-pipeline with VisionVolve IAM (`iam.visionvolve.com`) for authentication while keeping app-specific user data (OAuth connections, tenant roles, owner assignments) in the local PostgreSQL database.

**Why hybrid?** Leadgen has deep tenant-scoped data that IAM does not own — Google OAuth tokens per user per tenant, owner assignments, tenant-specific settings. IAM handles identity and authentication; leadgen owns the application layer.

### Current State

| Concern | Current | After |
|---------|---------|-------|
| Login | Local email/password, HS256 JWT | IAM login, RS256 JWT from IAM |
| Password mgmt | Local bcrypt hash | IAM (delegated) |
| Token validation | Symmetric HS256 via `JWT_SECRET_KEY` | Asymmetric RS256 via JWKS public key |
| User data | `users` table (password_hash, display_name) | `users` table (password_hash nullable, `iam_user_id` added) |
| Roles | `user_tenant_roles` (local only) | Local + synced from IAM permissions on login |
| OAuth connections | Local (Google API tokens) | Unchanged — stays local |
| Tenant resolution | X-Namespace header | Unchanged |

---

## 2. Auth Flow Changes

### 2.1 Frontend Login Flow (Recommended: Proxy Approach)

Use a **backend proxy** rather than a browser redirect to IAM. This avoids CORS complexity and keeps the existing LoginPage UX intact.

```
User enters email/password in LoginPage
    ↓
Frontend POST /api/auth/login {email, password}
    ↓
Backend proxies credentials to IAM:
    POST https://iam.visionvolve.com/api/auth/login
    Body: {email, password, app: "leadgen"}
    ↓
IAM returns: {access_token (RS256), refresh_token, user: {id, email, name, permissions}}
    ↓
Backend:
    1. Validates IAM access_token via JWKS
    2. Find-or-create local user by iam_user_id (fall back to email match)
    3. Sync IAM permissions → user_tenant_roles
    4. Mint a LOCAL access token (RS256 or HS256) with local user ID + roles
       OR pass through IAM token directly
    5. Return tokens + local user object to frontend
    ↓
Frontend stores tokens in localStorage (same keys: lg_access_token, lg_refresh_token)
```

**Decision: Pass-through vs. local token?**

**Recommended: Pass-through IAM tokens.** The backend validates IAM RS256 tokens on every request via JWKS. This eliminates dual token management and means token revocation at IAM level takes effect immediately.

### 2.2 Token Refresh Flow

```
Frontend POST /api/auth/refresh {refresh_token}
    ↓
Backend proxies to IAM:
    POST https://iam.visionvolve.com/api/auth/refresh
    Body: {refresh_token}
    ↓
IAM returns new access_token
    ↓
Backend validates, syncs roles (lightweight — skip if last sync < 5 min), returns token
```

### 2.3 Fallback: Direct IAM Login (Future)

For SSO scenarios, IAM can redirect back to leadgen with an auth code. Not needed for v1 since leadgen has a single login page.

---

## 3. Backend Middleware Changes

### 3.1 JWKS-Based Token Validation

Replace symmetric HS256 decoding with RS256 validation using IAM's public key.

**File: `api/auth.py`**

```python
# New: JWKS client for RS256 validation
import requests
from jwt import PyJWKClient

_jwks_client = None

def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            current_app.config["IAM_JWKS_URL"],
            cache_keys=True,
            max_cached_keys=4,
        )
    return _jwks_client

def decode_token(token):
    """Decode IAM RS256 token via JWKS, falling back to local HS256 for migration period."""
    # Try RS256 (IAM) first
    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=current_app.config.get("IAM_AUDIENCE", "leadgen"),
        )
    except Exception:
        pass

    # Fallback: local HS256 (migration period only — remove after full cutover)
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
    )
```

### 3.2 Updated `require_auth` Decorator

The decorator stays structurally the same. Key change: after decoding the IAM token, resolve the local user via `iam_user_id` instead of local `sub`.

```python
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        if payload.get("type") == "refresh":
            return jsonify({"error": "Cannot use refresh token for API access"}), 401

        # Resolve local user: try iam_user_id first, then legacy local ID
        iam_user_id = payload.get("sub")  # IAM tokens use sub = IAM user UUID
        user = User.query.filter_by(iam_user_id=iam_user_id).first()

        if not user:
            # Legacy fallback: local token with local user ID
            user = db.session.get(User, payload.get("sub"))

        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        g.token_payload = payload
        return f(*args, **kwargs)

    return decorated
```

### 3.3 `require_role` Decorator

**No changes needed.** It reads from `user.roles` (the local `user_tenant_roles` relationship), which gets synced on login. The role hierarchy (`admin: 3, editor: 2, viewer: 1`) stays identical.

### 3.4 `resolve_tenant`

**No changes needed.** It reads `X-Namespace` header and checks `g.token_payload.roles` or `user.is_super_admin`. After migration, `g.token_payload` will contain IAM permissions instead of locally-minted role claims, but the backend resolves roles from the DB relationship anyway.

---

## 4. User Model Changes

### 4.1 Add `iam_user_id` Column

**File: `api/models.py`** — `User` model

```python
class User(db.Model):
    __tablename__ = "users"

    # ... existing columns ...
    iam_user_id = db.Column(db.Text, unique=True, nullable=True, index=True)
    password_hash = db.Column(db.Text, nullable=True)  # WAS: nullable=False
    auth_provider = db.Column(db.Text, default="local")  # "local" | "iam"
```

Changes:
- `iam_user_id`: UUID from IAM, used for user lookup on IAM-authenticated requests. Nullable during migration (legacy users won't have it until they log in via IAM).
- `password_hash`: Made nullable. IAM users won't have a local password. Legacy users keep theirs during migration.
- `auth_provider`: Track whether user authenticates via IAM or legacy local auth. Useful for migration tracking and eventual cleanup.

### 4.2 Migration SQL

```sql
-- Migration: add IAM integration columns
ALTER TABLE users ADD COLUMN iam_user_id TEXT UNIQUE;
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local';
CREATE INDEX ix_users_iam_user_id ON users (iam_user_id) WHERE iam_user_id IS NOT NULL;
```

---

## 5. Role Sync Strategy

### 5.1 IAM Permission Model

IAM stores permissions as:
```json
{
  "app": "leadgen",
  "role": "admin",
  "scope": "my-namespace-slug"
}
```

Each permission maps to one `user_tenant_roles` row.

### 5.2 Sync Logic (On Login)

**New file: `api/services/iam_sync.py`**

```python
def sync_iam_roles(local_user, iam_permissions):
    """
    Sync IAM permissions to local user_tenant_roles.

    Strategy: IAM is authoritative for role grants. Local roles not in IAM
    are preserved (they may be app-specific grants by a local admin).
    IAM roles are upserted — if IAM says admin, local gets admin.
    """
    leadgen_perms = [p for p in iam_permissions if p.get("app") == "leadgen"]

    for perm in leadgen_perms:
        scope = perm.get("scope")  # namespace slug
        role = perm.get("role")    # admin/editor/viewer
        if not scope or not role:
            continue

        tenant = Tenant.query.filter_by(slug=scope, is_active=True).first()
        if not tenant:
            continue  # IAM has a scope for a namespace that doesn't exist locally

        existing = UserTenantRole.query.filter_by(
            user_id=local_user.id, tenant_id=tenant.id
        ).first()

        if existing:
            if existing.role != role:
                existing.role = role  # IAM wins
        else:
            db.session.add(UserTenantRole(
                user_id=local_user.id,
                tenant_id=tenant.id,
                role=role,
            ))

    db.session.commit()
```

### 5.3 Sync Rules

| Scenario | Behavior |
|----------|----------|
| IAM has `admin` for scope X, local has `viewer` | Upgrade to `admin` (IAM wins) |
| IAM has `viewer` for scope X, local has `admin` | Downgrade to `viewer` (IAM wins) |
| IAM has scope X, local doesn't | Create local role |
| Local has scope Y, IAM doesn't | **Keep local role** (app-specific grant) |
| IAM removes a scope entirely | Keep local role until explicit revocation (conservative) |

**Rationale for keeping local-only roles**: A local admin may grant temporary access to a namespace. Deleting it on every login because IAM doesn't have it would be disruptive. A separate "strict sync" flag can be added later if needed.

### 5.4 `is_super_admin` Mapping

IAM admin role without a scope (or with a wildcard scope `*`) maps to `is_super_admin = True`. This sync happens in the login proxy handler:

```python
if any(p.get("role") == "admin" and p.get("scope") in (None, "*") for p in leadgen_perms):
    local_user.is_super_admin = True
```

---

## 6. Tenant Resolution

**No changes.** The existing flow works:

1. Frontend sends `X-Namespace: my-namespace` header
2. `resolve_tenant()` looks up `Tenant` by slug
3. Validates user has access via `g.token_payload.roles` or `user.is_super_admin`
4. Returns `tenant_id`

The only nuance: during the pass-through token period, the IAM JWT payload won't have the `roles` dict in the same format. Fix: `resolve_tenant()` should read roles from the DB (`g.current_user.roles`) rather than from `g.token_payload`. This is a minor refactor:

```python
def resolve_tenant():
    slug = request.headers.get("X-Namespace", "").strip().lower()
    if not slug:
        # Fallback to first accessible namespace
        user_roles = {r.tenant.slug: r.role for r in g.current_user.roles if r.tenant}
        slug = next(iter(user_roles), None)
    if not slug:
        return None
    tenant = Tenant.query.filter_by(slug=slug, is_active=True).first()
    if not tenant:
        return None
    if not g.current_user.is_super_admin:
        user_roles = {r.tenant.slug: r.role for r in g.current_user.roles if r.tenant}
        if slug not in user_roles:
            return None
    return tenant.id
```

---

## 7. OAuth Connections (Google API Tokens)

**No changes.** The `oauth_connections` table stores Google Contacts/Gmail API tokens, not authentication tokens. These are:

- Scoped to `(user_id, tenant_id, provider)`
- Encrypted with Fernet (`OAUTH_ENCRYPTION_KEY`)
- Used for data import (contacts, emails), not login

The `user_id` FK still points to the local `users.id`, which remains the primary key. IAM integration doesn't affect this relationship.

---

## 8. Frontend Changes

### 8.1 LoginPage (`frontend/src/components/layout/LoginPage.tsx`)

**Minimal changes.** The form still collects email + password. The `login()` function still calls `POST /api/auth/login`. The backend proxies to IAM transparently.

Only change: error messages may need mapping from IAM error codes to user-friendly strings.

### 8.2 Auth Library (`frontend/src/lib/auth.ts`)

**Token storage**: Unchanged (`lg_access_token`, `lg_refresh_token` in localStorage).

**`StoredUser` interface**: Add optional `iam_user_id` field:

```typescript
export interface StoredUser {
  id: string
  email: string
  display_name: string
  is_super_admin: boolean
  roles: UserRoles
  iam_user_id?: string    // NEW
  auth_provider?: string  // NEW: "local" | "iam"
}
```

**`isTokenExpired`**: Works with both HS256 and RS256 tokens (only reads the payload, doesn't verify signature — that's the backend's job).

**`decodeJWT`**: No changes needed — base64 payload decoding is algorithm-agnostic.

### 8.3 Auth Hook (`frontend/src/hooks/useAuth.ts`)

**No structural changes.** The `login` callback calls `apiLogin()` which hits `/api/auth/login`. The backend response shape stays the same:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": { "id": "...", "email": "...", "display_name": "...", "roles": {...} }
}
```

### 8.4 API Client (`frontend/src/api/client.ts`)

**Token refresh**: The `refreshAccessToken()` function hits `/api/auth/refresh`, which the backend proxies to IAM. No client-side changes.

### 8.5 Logout

Add IAM session invalidation on logout:

```typescript
const logout = useCallback(() => {
  // Optionally notify IAM to revoke the refresh token
  const refreshToken = getRefreshToken()
  if (refreshToken) {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => {}) // fire and forget
  }
  clearTokens()
  setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
  window.location.href = '/'
}, [])
```

Backend `/api/auth/logout` proxies to `POST https://iam.visionvolve.com/api/auth/revoke`.

---

## 9. Files to Change

### Backend

| File | Change |
|------|--------|
| `api/models.py` | Add `iam_user_id`, `auth_provider` columns; make `password_hash` nullable |
| `api/auth.py` | Add JWKS client, dual-mode `decode_token` (RS256 + HS256 fallback), update `require_auth` to resolve by `iam_user_id`, update `resolve_tenant` to read roles from DB |
| `api/config.py` | Add `IAM_BASE_URL`, `IAM_JWKS_URL`, `IAM_AUDIENCE` config vars |
| `api/routes/auth_routes.py` | Rewrite `login()` to proxy to IAM, add find-or-create + role sync, rewrite `refresh()` to proxy, add `logout()` endpoint |
| `api/services/iam_sync.py` | **New file** — role sync logic, user find-or-create |
| `api/routes/oauth_routes.py` | No changes (Google OAuth state tokens can keep using local HS256) |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/lib/auth.ts` | Add `iam_user_id`, `auth_provider` to `StoredUser` interface |
| `frontend/src/hooks/useAuth.ts` | Add IAM logout call in `logout` callback |
| `frontend/src/components/layout/LoginPage.tsx` | Map IAM error codes to messages (minor) |

### Config / Deploy

| File | Change |
|------|--------|
| `docker-compose*.yml` or `.env` | Add `IAM_BASE_URL`, `IAM_JWKS_URL`, `IAM_AUDIENCE` env vars |
| Migration script (new) | Add `iam_user_id`, `auth_provider` columns, alter `password_hash` nullable |

---

## 10. Migration Strategy

### Phase 1: Dual-Mode (Week 1)

1. Deploy schema migration (add columns, alter nullable).
2. Deploy dual-mode `decode_token` — accepts both HS256 (legacy) and RS256 (IAM).
3. Keep existing login working (local passwords still accepted).
4. Add IAM proxy login as an alternative path.

### Phase 2: Link Existing Users (Week 1-2)

On first IAM login, match by email:

```python
def find_or_create_local_user(iam_user):
    """Find local user by iam_user_id, then by email. Create if neither exists."""
    # Try iam_user_id
    user = User.query.filter_by(iam_user_id=iam_user["id"]).first()
    if user:
        return user

    # Try email match (one-time migration link)
    user = User.query.filter_by(email=iam_user["email"]).first()
    if user:
        user.iam_user_id = iam_user["id"]
        user.auth_provider = "iam"
        db.session.commit()
        return user

    # Create new user (no local password needed)
    user = User(
        email=iam_user["email"],
        display_name=iam_user.get("name", iam_user["email"]),
        iam_user_id=iam_user["id"],
        auth_provider="iam",
        password_hash=None,
    )
    db.session.add(user)
    db.session.commit()
    return user
```

### Phase 3: Cutover (Week 3+)

1. Verify all active users have `iam_user_id` set.
2. Remove HS256 fallback from `decode_token`.
3. Remove local `login()` password validation path.
4. Remove `JWT_SECRET_KEY` from config (no longer needed for auth tokens; keep if used for OAuth state).
5. Optionally null out `password_hash` for all IAM-linked users.

### Rollback Plan

- Revert to HS256-only `decode_token` (one-line change).
- Local passwords are still in the DB — users can log in with old flow.
- `iam_user_id` column is additive, doesn't break anything if unused.

---

## 11. Deploy Config Changes

### Environment Variables (New)

```bash
# IAM integration
IAM_BASE_URL=https://iam.visionvolve.com
IAM_JWKS_URL=https://iam.visionvolve.com/.well-known/jwks.json
IAM_AUDIENCE=leadgen

# Existing (keep during migration, remove in Phase 3)
JWT_SECRET_KEY=<existing-value>
```

### Config Class Update

**File: `api/config.py`**

```python
class Config:
    # ... existing ...

    # IAM integration
    IAM_BASE_URL = os.environ.get("IAM_BASE_URL", "https://iam.visionvolve.com")
    IAM_JWKS_URL = os.environ.get("IAM_JWKS_URL", f"{IAM_BASE_URL}/.well-known/jwks.json")
    IAM_AUDIENCE = os.environ.get("IAM_AUDIENCE", "leadgen")
```

### Docker Compose

Add env vars to `docker-compose.backlog.yml` (or the leadgen overlay):

```yaml
environment:
  - IAM_BASE_URL=https://iam.visionvolve.com
  - IAM_JWKS_URL=https://iam.visionvolve.com/.well-known/jwks.json
  - IAM_AUDIENCE=leadgen
```

### Caddy / Networking

No Caddy changes needed. The leadgen backend makes outbound HTTPS requests to `iam.visionvolve.com`. The container needs outbound internet access (already has it).

---

## 12. Security Considerations

- **JWKS key rotation**: `PyJWKClient` with `cache_keys=True` handles rotation automatically — it refetches on cache miss.
- **Token validation**: Always verify `aud` (audience) claim matches `"leadgen"` to prevent cross-app token reuse.
- **Local password retention**: During migration, local passwords remain valid. This is intentional for rollback safety. Remove in Phase 3.
- **IAM availability**: If IAM is down, new logins fail but existing tokens (not yet expired) continue to validate via cached JWKS keys. Consider caching the last-known JWKS key set to disk for extended outages.
- **Email matching**: The one-time email match in Phase 2 assumes email addresses are consistent between IAM and local DB. Verify before migration with a dry-run query.

---

## 13. Testing Plan

| Test | Scope |
|------|-------|
| Unit: `decode_token` with RS256 mock key | `tests/test_auth.py` |
| Unit: `decode_token` HS256 fallback | `tests/test_auth.py` |
| Unit: `find_or_create_local_user` — email match | `tests/test_iam_sync.py` (new) |
| Unit: `find_or_create_local_user` — create new | `tests/test_iam_sync.py` |
| Unit: `sync_iam_roles` — upsert, upgrade, downgrade | `tests/test_iam_sync.py` |
| Integration: login proxy → IAM → local user creation | `tests/test_auth_routes.py` |
| Integration: refresh proxy → IAM | `tests/test_auth_routes.py` |
| Integration: existing endpoints with IAM token | `tests/test_auth.py` |
| E2E: LoginPage → backend → IAM → dashboard | Manual / Playwright |

---

## 14. Sequence Diagram

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│ Frontend  │     │ Leadgen API  │     │     IAM     │
└─────┬────┘     └──────┬───────┘     └──────┬──────┘
      │  POST /api/auth/login          │             │
      │  {email, password}             │             │
      │──────────────────────────────→ │             │
      │                                │  POST /api/auth/login
      │                                │  {email, password, app: "leadgen"}
      │                                │────────────────────→│
      │                                │                     │
      │                                │  {access_token (RS256),
      │                                │   refresh_token, user, permissions}
      │                                │←────────────────────│
      │                                │                     │
      │                   find_or_create_local_user()        │
      │                   sync_iam_roles()                   │
      │                                │                     │
      │  {access_token, refresh_token, │                     │
      │   user (local enriched)}       │                     │
      │←─────────────────────────────  │                     │
      │                                │                     │
      │  GET /api/contacts             │                     │
      │  Authorization: Bearer <IAM token>                   │
      │──────────────────────────────→ │                     │
      │                   decode_token (RS256 via JWKS)      │
      │                   resolve local user by iam_user_id  │
      │  {contacts: [...]}             │                     │
      │←─────────────────────────────  │                     │
```
