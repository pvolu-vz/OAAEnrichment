# GICO Email Enrichment — Veza OAA Integration

## Overview

This script enriches **OAA.GICO.User** entities already present in your Veza tenant with a new custom attribute called `new_email`. The value is derived entirely from data already in Veza — no external API calls to the GICO system are required.

| Step | Action |
|------|--------|
| 1 | Query all `OAA.GICO.User` nodes from Veza via the Assessment Query API |
| 2 | For each user, read the `native_id` property |
| 3 | Construct `new_email = native_id + @smurfitwestrock.com` |
| 4 | Push the enriched attribute back to Veza using the OAA Enrichment template |

After a successful run the `new_email` attribute will be visible on each GICO User node in the Veza Access Graph and available in queries, reports, and access reviews.

### OAA Entity Mapping

| Veza Node Type     | Enriched Attribute | Source Field | Derived Value                    |
|--------------------|--------------------|--------------|----------------------------------|
| `OAA.GICO.User`    | `new_email`        | `native_id`  | `<native_id>@smurfitwestrock.com` |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.8 | `python3 --version` |
| Network access | Outbound HTTPS to your Veza tenant |
| Veza API key | Must have OAA read + write (provider/datasource create) permissions |
| GICO OAA provider | The `OAA.GICO` data source must already exist in your Veza tenant |

---

## Quick Start

```bash
# 1. Clone or navigate to the integration directory
cd integrations/gico-enrichment

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
chmod 600 .env
# Edit .env — fill in VEZA_URL and VEZA_API_KEY

# 5. Dry-run first (no write to Veza)
python3 gico_email_enrichment.py --dry-run

# 6. Push enrichment to Veza
python3 gico_email_enrichment.py
```

---

## Installation (Linux / macOS)

### RHEL / CentOS / Fedora

```bash
sudo dnf install -y python3 python3-pip python3-venv
python3 -m venv /opt/gico-enrichment/venv
source /opt/gico-enrichment/venv/bin/activate
pip install -r requirements.txt
```

### Ubuntu / Debian

```bash
sudo apt-get install -y python3 python3-pip python3-venv
python3 -m venv /opt/gico-enrichment/venv
source /opt/gico-enrichment/venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

```
python3 gico_email_enrichment.py [OPTIONS]
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--veza-host HOST` | No* | `VEZA_URL` env var | Veza tenant hostname (e.g. `acme.veza.com`) |
| `--email-domain DOMAIN` | No | `@smurfitwestrock.com` | Domain suffix appended to `native_id` |
| `--provider-name NAME` | No | `GICO Email Enrichment` | OAA provider name in the Veza UI |
| `--env-file PATH` | No | `.env` | Path to a dotenv credentials file |
| `--dry-run` | No | `False` | Preview payload without pushing to Veza |
| `--save-json` | No | `False` | Save enrichment payload to a local JSON file |
| `--log-level LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

\* Required via CLI or `VEZA_URL` environment variable.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `VEZA_URL` | Veza tenant hostname |
| `VEZA_API_KEY` | Veza API key (always required) |

### Example Commands

```bash
# Standard run using .env file
python3 gico_email_enrichment.py

# Explicit host, debug logging
python3 gico_email_enrichment.py --veza-host acme.veza.com --log-level DEBUG

# Dry-run with JSON payload saved to disk
python3 gico_email_enrichment.py --dry-run --save-json

# Override the email domain
python3 gico_email_enrichment.py --email-domain @example.com

# Use a non-default .env file
python3 gico_email_enrichment.py --env-file /etc/gico-enrichment/prod.env
```

---

## Deployment on Linux

### Service Account Setup

```bash
sudo useradd -r -s /bin/bash -m -d /opt/gico-enrichment gico-enrichment
sudo mkdir -p /opt/gico-enrichment/{scripts,logs}
sudo chown -R gico-enrichment:gico-enrichment /opt/gico-enrichment
```

### File Permissions

```bash
chmod 600 /opt/gico-enrichment/scripts/.env
chmod 700 /opt/gico-enrichment/scripts
```

### SELinux (RHEL)

```bash
getenforce   # check status
# If Enforcing, restore context after placing files:
restorecon -Rv /opt/gico-enrichment/
```

### Cron Schedule

Create `/etc/cron.d/gico-enrichment`:

```cron
# Run GICO email enrichment daily at 02:00
0 2 * * * gico-enrichment /opt/gico-enrichment/scripts/run.sh >> /opt/gico-enrichment/logs/gico-enrichment.log 2>&1
```

Wrapper script `/opt/gico-enrichment/scripts/run.sh`:

```bash
#!/bin/bash
set -euo pipefail
source /opt/gico-enrichment/venv/bin/activate
python3 /opt/gico-enrichment/scripts/gico_email_enrichment.py \
  --env-file /opt/gico-enrichment/scripts/.env
```

### Log Rotation

Create `/etc/logrotate.d/gico-enrichment`:

```
/opt/gico-enrichment/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 640 gico-enrichment gico-enrichment
}
```

---

## Security Considerations

- Store `VEZA_API_KEY` only in the `.env` file; never commit it to source control.
- Use `chmod 600 .env` to restrict read access to the service account only.
- Rotate the Veza API key regularly and update `.env` accordingly.
- The script performs only write operations to the enrichment provider — it does not modify existing GICO user records or permissions.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Missing required configuration: VEZA_API_KEY` | Env var not set | Set `VEZA_API_KEY` in `.env` or shell |
| `Missing required configuration: --veza-host / VEZA_URL` | Host not provided | Set `VEZA_URL` in `.env` or pass `--veza-host` |
| `Received 0 OAA.GICO.User entities` | GICO datasource not in Veza | Confirm GICO OAA integration has run successfully |
| `Skipped N entities with no native_id` | GICO users missing native_id | Check GICO OAA connector — native_id must be populated |
| `Veza push_metadata failed: 401` | Invalid or expired API key | Regenerate the Veza API key |
| `Veza push_metadata failed: 403` | Insufficient permissions | Ensure the API key has OAA provider create/write permissions |
| `ModuleNotFoundError: oaaclient` | venv not activated or deps not installed | `source venv/bin/activate && pip install -r requirements.txt` |

---

## Changelog

### v1.0 — 2026-04-10
- Initial release: query `OAA.GICO.User` entities, enrich with `new_email = native_id + @smurfitwestrock.com`
- Supports `--dry-run`, `--save-json`, `--log-level`, `--email-domain` override
- Credentials via `.env` file or environment variables
