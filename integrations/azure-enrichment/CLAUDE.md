# Azure Enrichment — Scoped Rules

These rules apply only when working inside `integrations/azure-enrichment/`. They narrow and extend the project-level `CLAUDE.md`.

## Integration Identity

| Field | Value |
|---|---|
| Script | `azure_oaa_enrichment.py` |
| Provider name | `Azure Email Enrichment` |
| Data source name | `Azure Email Enrichment` |
| Entity type | `AzureADUser` |
| Default IDP domain | `smurfitwestrock.com` |
| Venv path | `integrations/azure-enrichment/venv/` |

## What This Integration Does

Queries Azure AD users from Veza's Access Graph, transforms each user's `manager_principal_name` by replacing its domain with the configured IDP domain (`manager_OAA_idp`), and pushes the enriched attributes back to Veza as a single data source.

## Rules

- All users must be pushed to a **single data source** — do not batch into multiple data sources
- The `manager_OAA_idp` field format is `<local-part>@<IDP_DOMAIN>` (local part taken from `manager_principal_name` before the `@`)
- Skip entities missing `datasource_id` or `manager_principal_name` — log skip counts but do not error
- Use the `logging` module exclusively — no `print()` statements
- Do not hardcode the IDP domain — it must come from config (`.env` or `--idp-domain` CLI flag)

## Not Allowed

- Do not re-introduce `PUSH_BATCH_SIZE` batching or multiple data source names
- Do not add retry logic unless the Veza API explicitly returns a retryable status code
- Do not write to files outside `integrations/azure-enrichment/`

## CLI Reference

```bash
./venv/bin/python3 azure_oaa_enrichment.py \
  --veza-host <host> \
  --idp-domain <domain> \
  [--azure-datasource-name <name>]  # filter to a specific Azure datasource \
  [--dry-run] \
  [--save-json] \
  [--log-level DEBUG|INFO|WARNING|ERROR]
```

## Key Files

| File | Purpose |
|---|---|
| `azure_oaa_enrichment.py` | Main script |
| `.env` | Credentials (`VEZA_URL`, `VEZA_API_KEY`, `IDP_DOMAIN`) |
| `.env.example` | Credential template — commit this, never `.env` |
| `requirements.txt` | Python dependencies |
| `logs/` | Hourly-rotating log files (gitignored) |
