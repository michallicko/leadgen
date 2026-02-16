# Production Database Access

The production PostgreSQL database runs on AWS RDS and is **not publicly accessible**. Access requires an SSH tunnel through the VPS.

## Quick Start

### 1. Open the tunnel

```bash
bash scripts/db-tunnel.sh
```

This forwards `localhost:5433` to the RDS instance. Leave it running in a terminal.

### 2. Connect

With **psql**:
```bash
psql -h localhost -p 5433 -U dbmasteruser -d leadgen
```

With **TablePlus** or any GUI client, use these connection parameters:

| Parameter | Value |
|-----------|-------|
| Host | `localhost` |
| Port | `5433` |
| User | `dbmasteruser` |
| Database | `leadgen` |
| SSL Mode | `require` |

> Password is stored in 1Password / ask the team.

## TablePlus Setup (Recommended)

TablePlus has a free tier (2 open tabs) and is a native Mac app.

1. Install: `brew install --cask tableplus`
2. Create new PostgreSQL connection
3. Fill in the connection parameters from the table above
4. Alternatively, use TablePlus's built-in SSH tunnel tab instead of the script:
   - SSH Host: `52.58.119.191`
   - SSH User: `ec2-user`
   - SSH Key: `/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem`
   - DB Host: `ls-934f096d99ba4e98dd82196e6e7470f8a9e993bc.cz6y8ke6ynad.eu-central-1.rds.amazonaws.com`
   - DB Port: `5432`

## Optional: Password-Free psql

Add to `~/.pgpass` (create if it doesn't exist):

```
localhost:5433:leadgen:dbmasteruser:<password>
```

Then `chmod 600 ~/.pgpass`. After this, `psql` won't prompt for a password.

## Safety Notes

- **Prefer read-only queries** for browsing data
- **Use transactions** for any writes: `BEGIN; ... COMMIT;` (or `ROLLBACK;`)
- The dashboard API is the intended write path — direct DB writes bypass validation
- n8n workflows still write to Airtable; PG is currently a read-only mirror for the dashboard
