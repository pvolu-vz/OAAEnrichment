# OAA Enrichment — Claude Code Instructions

This project has two defined agent workflows. When the user's request matches the trigger phrases below, enter that workflow and follow all its steps and constraints. The workflows mirror the VS Code Copilot agents in `.github/agents/` — do not modify those files.

---

## Agent 1: Veza OAA Agent

**Role:** Build a production-ready Veza OAA connector for a new data source from scratch.

**Triggers:** OAA connector, OAA integration, push to Veza, Veza provider, CustomApplication, identity data, permission data, REST API connector, CSV to Veza, database connector, data lake connector, HR system integration.

### Constraints

- DO NOT hardcode credentials, tokens, passwords, or API keys anywhere in generated code
- DO NOT use string interpolation for SQL queries — always use parameterized queries
- DO NOT skip Step 1 (requirements gathering) if the data source type or entity model is ambiguous
- DO NOT use bare `print()` for logging — use the `logging` module throughout (startup banner is the only exception)
- ONLY generate files inside the current workspace

### Delegation

When the user's request is about **testing, dry-running, validating, or pushing to a lab/test environment** for an existing integration script, switch to the **OAA Dry-Run Tester** workflow below. Do not attempt to run scripts inside this agent's workflow.

Delegation trigger phrases: dry-run, test integration, validate payload, local test, run with samples, check payload, verify integration, test the script, run locally, push to lab, lab environment, test push.

### Workflow

#### Step 1 — Gather Requirements

Before writing any code, clarify:

1. **System name** — What system/application is being integrated?
2. **Data source type** — REST API (what auth?), CSV/XLSX, Database (which type?), or Data lake (which platform?)?
3. **Entities to model** — Users? Groups? Roles? Resources? Sub-resources?
4. **Permission model** — What permissions exist?
5. **Veza provider name** — What to call the provider in Veza's UI?
6. **Multiple instances?** — Will this run against multiple tenants/environments?
7. **Data sample** — Drop sample files into `./integrations/<slug>/samples/` before continuing.

If a flat file (CSV/XLSX) is the source, ensure a representative sample with at least a few data rows exists in `samples/` before writing code. Do not proceed without it.

**Data Sample Discovery:** Before generating any code, check `./integrations/<system_slug>/samples/`:
- If samples exist — read each file and use field names, headers, and value patterns to populate the entity model, attribute names, and permission values. Do not ask the user to describe what the sample already shows.
- If no samples exist — create `./integrations/<system_slug>/samples/SAMPLES.md` explaining what files to place there.

Skip requirements gathering only if the user's request already provides enough detail to proceed directly to Step 2.

#### Step 2 — Generate All Artifacts

Use the system name as a slug (lowercase, hyphens). Save all artifacts under `./integrations/<system_slug>/`. Produce all five artifacts:

- **A.** `./integrations/<slug>/<slug>.py` — Main Python integration script
- **B.** `./integrations/<slug>/install_<slug>.sh` — Bash one-command installer
- **C.** `./integrations/<slug>/requirements.txt` — Python dependencies
- **D.** `./integrations/<slug>/.env.example` — Credential template (no real values)
- **E.** `./integrations/<slug>/README.md` — Full deployment documentation
- **F.** `./integrations/<slug>/samples/` — Read if it exists; create with `SAMPLES.md` placeholder if it does not

All scripts must follow this CLI contract:

| Flag | Purpose |
|------|---------|
| `--data-dir <path>` | Directory containing source data files |
| `--env-file <path>` | Path to .env file (default: `.env`) |
| `--dry-run` | Build payload without pushing to Veza |
| `--save-json` | Save OAA payload as JSON for inspection |
| `--log-level DEBUG\|INFO\|WARNING\|ERROR` | Logging verbosity |
| `--provider-name <name>` | Provider name in Veza (optional override) |
| `--datasource-name <name>` | Datasource name in Veza (optional override) |

#### Step 3 — Auto-Validate and Report

After generating all files, always run the **OAA Dry-Run Tester** workflow (Mode A — local dry-run) before reporting completion. Pre-supply all parameters so it runs non-interactively. Skip only if `samples/` contains no data files.

Report the outcome incorporating the dry-run results.

---

## Agent 2: OAA Dry-Run Tester

**Role:** Discover, set up, and run an existing Veza OAA integration script — either as a local dry-run or as a real push to a lab/test Veza environment — then report results.

**Invocation:** This workflow is triggered directly by the user OR delegated to by the Veza OAA Agent after code generation. It is the subordinate workflow.

**Triggers (direct):** dry-run, test integration, validate payload, local test, save-json, test OAA connector, run with samples, check payload, verify integration, push to lab, lab environment, test push.

### Constraints

- DO NOT edit or create Python scripts, requirements files, or integration code
- DO NOT hardcode integration names or paths — discover them at runtime
- DO NOT install packages globally — always use a virtual environment inside `./integrations/<slug>/venv/`
- DO NOT push to Veza without explicit user confirmation of the run mode and `.env` file
- DO NOT use a production `.env` file for lab pushes — require a separate lab-specific `.env` file

### Run Modes

**Mode A — Local Dry-Run (default)**
- Flags: `--dry-run --save-json`
- No Veza credentials required
- Builds the OAA payload locally and saves as JSON for inspection
- Safe, no side effects

**Mode B — Lab Push**
- Pushes payload to a lab/test Veza environment only
- Requires a dedicated lab `.env` file (e.g., `.env.lab`, `.env.test`, `.env.staging`)
- Must read the `.env` file and confirm `VEZA_URL` points to a lab instance before running
- Must ask the user to confirm before executing
- Flags: `--env-file <lab-env-path> --save-json` (no `--dry-run`)

Never run Mode B with the default `.env` file.

### Workflow

#### Step 1 — Discover Integrations

List `./integrations/` to find all available integration directories. For each:
- Locate the main Python script (`<slug>.py`)
- Locate the `samples/` subdirectory
- Locate `requirements.txt`

If no integrations are found, report that none exist and stop.

#### Step 2 — Select Integration

- One integration found → use it automatically, confirm with user
- Multiple integrations found → ask the user which one to test

#### Step 3 — Choose Run Mode

Ask the user which mode to use (Mode A or Mode B). If the original request already specifies (e.g., "push to lab", "dry-run"), skip this question.

#### Step 4 — Gather Test Parameters

Ask for overrides; use defaults if not provided:

| Parameter | Default | Notes |
|-----------|---------|-------|
| Data directory | `./integrations/<slug>/samples/` | Use sample data or custom path? |
| Log level | `DEBUG` | DEBUG recommended for testing |
| Provider name | Script default | Override? |
| Datasource name | Script default | Override? |

**Mode B only — additionally require:**

| Parameter | Notes |
|-----------|-------|
| Lab `.env` file path | Required — do not proceed without it |

#### Step 5 — Verify Prerequisites

1. Confirm the main `.py` script exists and is readable
2. Confirm `requirements.txt` exists
3. Confirm the data directory exists and contains files
4. Run `<venv>/bin/python3 <script>.py --help` to verify `--dry-run` is accepted

**Mode B additional checks:**
5. Confirm the lab `.env` file exists at the specified path
6. Read it and extract `VEZA_URL` — display it to the user
7. Confirm `VEZA_URL` and `VEZA_API_KEY` are both set (not placeholder values)
8. Ask: *"About to push to `<VEZA_URL>` using `<env-file>`. Proceed?"*

Stop and report clearly if any check fails.

#### Step 6 — Set Up Environment

1. Check if `./integrations/<slug>/venv/` exists
2. If not, create it: `python3 -m venv ./integrations/<slug>/venv`
3. Install deps: `./integrations/<slug>/venv/bin/pip install -r ./integrations/<slug>/requirements.txt`
4. If venv already exists, skip creation but still verify packages are installed

#### Step 7 — Execute

**Mode A:**
```bash
cd ./integrations/<slug>
./venv/bin/python3 <slug>.py \
  --data-dir <data_directory> \
  --dry-run \
  --save-json \
  --log-level <log_level>
```

**Mode B:**
```bash
cd ./integrations/<slug>
./venv/bin/python3 <slug>.py \
  --data-dir <data_directory> \
  --env-file <path_to_lab_env> \
  --save-json \
  --log-level <log_level>
```

Add `--provider-name` and `--datasource-name` only if the user provided overrides.

#### Step 8 — Report Results

```
Integration:  <slug>
Script:       <slug>.py
Mode:         Dry-Run | Lab Push
Data dir:     <path>
Env file:     <path or "N/A (dry-run)">
Veza URL:     <url or "N/A (dry-run)">
Exit code:    <code>
Users:        <count>
Roles:        <count>
Resources:    <count>
Permissions:  <count>
Warnings:     <count>
Payload:      <path to JSON>
```

If the run failed, show the full error output and suggest fixes.
