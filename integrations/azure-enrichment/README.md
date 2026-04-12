# Azure OAA Enrichment — Veza OAA Integration

## Overview

This script enriches **AzureADUser** entities already present in your Veza tenant with a new custom attribute called `OAA_idp`. The value is derived entirely from data already in Veza — no external API calls are required.

The enrichment is pushed as a **separate enrichment provider** (using the `entity_enrichment` template), distinct from the Azure AD integration. You can optionally supply an existing provider ID to skip name-based lookup/creation.

| Step | Action |
|------|--------|
| 1 | Query all `AzureADUser` nodes from Veza via the Assessment Query API |
| 2 | For each user, read the `principal_name` property |
| 3 | Construct `OAA_idp = local_part(principal_name) + @IDP_DOMAIN` |
| 4 | Push the enriched attribute back to Veza using the OAA Enrichment template |

After a successful run the `OAA_idp` attribute will be visible on each AzureADUser node in the Veza Access Graph and available in queries, reports, and access reviews.

### OAA Entity Mapping

| Veza Node Type       | Enriched Attribute | Source Field       | Derived Value                    |
|----------------------|--------------------|--------------------|----------------------------------|
| `AzureADUser`        | `OAA_idp`          | `principal_name`   | `<local_part>@smurfitwestrock.com` |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.8 | `python3 --version` |
| Network access | Outbound HTTPS to your Veza tenant |
| Veza API key | Must have OAA read + write permissions |
| Enrichment provider | Created automatically, or supply an existing provider ID via `ENRICHMENT_PROVIDER_ID` |

---

## Quick Start

```bash
# 1. Clone or navigate to the integration directory
cd integrations/azure-enrichment

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
chmod 600 .env
# Edit .env — fill in VEZA_URL, VEZA_API_KEY, and optionally other settings

# 5. Dry-run first (no write to Veza)
python3 azure_oaa_enrichment.py --dry-run

# 6. Push enrichment to Veza
python3 azure_oaa_enrichment.py
```

---

## Installation (Linux / macOS)

### RHEL / CentOS / Fedora

```bash
sudo dnf install -y python3 python3-pip python3-venv
python3 -m venv /opt/azure-oaa-enrichment/venv
source /opt/azure-oaa-enrichment/venv/bin/activate
pip install -r requirements.txt
```

### Ubuntu / Debian

```bash
sudo apt-get install -y python3 python3-pip python3-venv
python3 -m venv /opt/azure-oaa-enrichment/venv
source /opt/azure-oaa-enrichment/venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

```
python3 azure_oaa_enrichment.py [OPTIONS]
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--veza-host HOST` | No* | `VEZA_URL` env var | Veza tenant hostname (e.g. `acme.veza.com`) |
| `--idp-domain DOMAIN` | No | `IDP_DOMAIN` env var or `smurfitwestrock.com` | IDP domain to replace the existing domain in `principal_name` |
| `--entity-type TYPE` | No | `ENTITY_TYPE` env var or `AzureADUser` | Veza entity type to enrich |
| `--provider-name NAME` | No | `ENRICHMENT_PROVIDER_NAME` env var or `Azure Email Enrichment` | Name for the enrichment provider (`entity_enrichment` template) |
| `--provider-id ID` | No | `ENRICHMENT_PROVIDER_ID` env var | Existing provider ID — skips name-based lookup/creation |
| `--data-source-name NAME` | No | `ENRICHMENT_DATA_SOURCE_NAME` env var or `Azure Email Enrichment` | Data source name for the enrichment payload |
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
| `IDP_DOMAIN` | IDP domain for principal_name replacement (default: `smurfitwestrock.com`) |
| `ENTITY_TYPE` | Veza entity type to enrich (default: `AzureADUser`) |
| `ENRICHMENT_PROVIDER_NAME` | Enrichment provider name (default: `Azure Email Enrichment`) |
| `ENRICHMENT_PROVIDER_ID` | Existing provider ID — set to skip name-based lookup/creation |
| `ENRICHMENT_DATA_SOURCE_NAME` | Data source name under the provider (default: `Azure Email Enrichment`) |

### Example Commands

```bash
# Standard run using .env file
python3 azure_oaa_enrichment.py

# Explicit host, debug logging
python3 azure_oaa_enrichment.py --veza-host acme.veza.com --log-level DEBUG

# Dry-run with JSON payload saved to disk
python3 azure_oaa_enrichment.py --dry-run --save-json

# Override the IDP domain
python3 azure_oaa_enrichment.py --idp-domain example.com

# Use an existing provider ID (skips name lookup)
python3 azure_oaa_enrichment.py --provider-id abc123-def456

# Use a non-default .env file
python3 azure_oaa_enrichment.py --env-file /etc/azure-oaa-enrichment/prod.env
```

---

## Deployment on Linux

### Service Account Setup

```bash
sudo useradd -r -s /bin/bash -m -d /opt/azure-oaa-enrichment azure-oaa-enrichment
sudo mkdir -p /opt/azure-oaa-enrichment/{scripts,logs}
sudo chown -R azure-oaa-enrichment:azure-oaa-enrichment /opt/azure-oaa-enrichment
```

### File Permissions

```bash
chmod 600 /opt/azure-oaa-enrichment/scripts/.env
chmod 700 /opt/azure-oaa-enrichment/scripts
```

### SELinux (RHEL)

```bash
getenforce   # check status
# If Enforcing, restore context after placing files:
restorecon -Rv /opt/azure-oaa-enrichment/
```

### Cron Schedule

Create `/etc/cron.d/azure-oaa-enrichment`:

```cron
# Run Azure OAA enrichment daily at 02:00
0 2 * * * azure-oaa-enrichment /opt/azure-oaa-enrichment/scripts/run.sh >> /opt/azure-oaa-enrichment/logs/azure-oaa-enrichment.log 2>&1
```

Wrapper script `/opt/azure-oaa-enrichment/scripts/run.sh`:

```bash
#!/bin/bash
set -euo pipefail
source /opt/azure-oaa-enrichment/venv/bin/activate
python3 /opt/azure-oaa-enrichment/scripts/azure_oaa_enrichment.py \
  --env-file /opt/azure-oaa-enrichment/scripts/.env
```

### Log Rotation

Create `/etc/logrotate.d/azure-oaa-enrichment`:

```
/opt/azure-oaa-enrichment/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 640 azure-oaa-enrichment azure-oaa-enrichment
}
```

---

## Security Considerations

- Store `VEZA_API_KEY` only in the `.env` file; never commit it to source control.
- Use `chmod 600 .env` to restrict read access to the service account only.
- Rotate the Veza API key regularly and update `.env` accordingly.
- The script performs only write operations to the enrichment provider — it does not modify existing AzureADUser records or permissions.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Missing required configuration: VEZA_API_KEY` | Env var not set | Set `VEZA_API_KEY` in `.env` or shell |
| `Missing required configuration: --veza-host / VEZA_URL` | Host not provided | Set `VEZA_URL` in `.env` or pass `--veza-host` |
| `Received 0 AzureADUser entities` | Azure AD datasource not in Veza | Confirm Azure AD integration has run successfully |
| `Skipped N entities with no principal_name` | Users missing principal_name | Check Azure AD connector — principal_name must be populated |
| `Veza push_metadata failed: 401` | Invalid or expired API key | Regenerate the Veza API key |
| `Veza push_metadata failed: 403` | Insufficient permissions | Ensure the API key has OAA provider create/write permissions |
| `ModuleNotFoundError: oaaclient` | venv not activated or deps not installed | `source venv/bin/activate && pip install -r requirements.txt` |

---

## Changelog

### v1.2 — 2026-04-12
- Renamed script from `gico_email_enrichment.py` to `azure_oaa_enrichment.py`
- All configuration now driven by `.env` variables (with CLI overrides)
- Added `ENRICHMENT_PROVIDER_ID` to skip name-based provider lookup/creation
- Added `ENTITY_TYPE` and `ENRICHMENT_PROVIDER_NAME` / `ENRICHMENT_DATA_SOURCE_NAME` env vars
- Fixed entity type documentation to match implementation (`AzureADUser`)

### v1.1 — 2026-04-12
- Renamed enrichment attribute from `new_email` to `OAA_idp`
- Changed source field from `name` to `principal_name` with domain replacement
- Added `IDP_DOMAIN` environment variable for configurable domain
- CLI flag changed from `--email-domain` to `--idp-domain`

### v1.0 — 2026-04-10
- Initial release: query `OAA.GICO.User` entities, enrich with `new_email = native_id + @smurfitwestrock.com`
- Supports `--dry-run`, `--save-json`, `--log-level`, `--email-domain` override
- Credentials via `.env` file or environment variables
