#!/usr/bin/env bash
# install_gico_email_enrichment.sh
# One-command installer for GICO Email Enrichment → Veza OAA integration
# Usage:
#   Interactive:       bash install_gico_email_enrichment.sh
#   Non-interactive:   VEZA_URL=... VEZA_API_KEY=... bash install_gico_email_enrichment.sh --non-interactive
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/gico-enrichment"
REPO_URL="https://github.com/YOUR_ORG/YOUR_REPO.git"
BRANCH="main"
NON_INTERACTIVE=false
OVERWRITE_ENV=false
SCRIPT_SUBDIR="integrations/gico-enrichment"

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --non-interactive) NON_INTERACTIVE=true ;;
        --overwrite-env)   OVERWRITE_ENV=true ;;
        --install-dir)     INSTALL_DIR="$2"; shift ;;
        --repo-url)        REPO_URL="$2"; shift ;;
        --branch)          BRANCH="$2"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

SCRIPTS_DIR="${INSTALL_DIR}/scripts"
LOGS_DIR="${INSTALL_DIR}/logs"
VENV_DIR="${SCRIPTS_DIR}/venv"
ENV_FILE="${SCRIPTS_DIR}/.env"

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

detect_pkg_manager() {
    if command -v dnf  &>/dev/null; then echo "dnf"
    elif command -v yum  &>/dev/null; then echo "yum"
    elif command -v apt-get &>/dev/null; then echo "apt"
    else error "Unsupported OS — install python3, python3-pip, python3-venv manually then re-run."; fi
}

require_python38() {
    local py
    py=$(command -v python3 2>/dev/null || true)
    [[ -z "$py" ]] && error "python3 not found. Install Python 3.8+ and re-run."
    local ver
    ver=$("$py" -c "import sys; print(sys.version_info >= (3,8))")
    [[ "$ver" != "True" ]] && error "Python 3.8+ required. Found: $("$py" --version)"
    info "Python version OK: $("$py" --version)"
}

# ─────────────────────────────────────────────────────────────────────────────
# System package installation
# ─────────────────────────────────────────────────────────────────────────────
PKG_MGR=$(detect_pkg_manager)
info "Using package manager: $PKG_MGR"

if [[ "$PKG_MGR" == "apt" ]]; then
    sudo apt-get update -qq
    sudo apt-get install -y git curl python3 python3-pip python3-venv
elif [[ "$PKG_MGR" == "dnf" ]]; then
    sudo dnf install -y git curl python3 python3-pip python3-venv
else
    sudo yum install -y git curl python3 python3-pip python3-venv
fi

require_python38

# ─────────────────────────────────────────────────────────────────────────────
# Directory setup
# ─────────────────────────────────────────────────────────────────────────────
info "Creating directory layout under ${INSTALL_DIR} ..."
sudo mkdir -p "${SCRIPTS_DIR}" "${LOGS_DIR}"

# ─────────────────────────────────────────────────────────────────────────────
# Clone or update repo
# ─────────────────────────────────────────────────────────────────────────────
REPO_CLONE_DIR="${INSTALL_DIR}/_repo"
if [[ -d "${REPO_CLONE_DIR}/.git" ]]; then
    info "Updating existing repository in ${REPO_CLONE_DIR} ..."
    git -C "${REPO_CLONE_DIR}" fetch origin
    git -C "${REPO_CLONE_DIR}" checkout "${BRANCH}"
    git -C "${REPO_CLONE_DIR}" pull origin "${BRANCH}"
else
    info "Cloning repository into ${REPO_CLONE_DIR} ..."
    sudo git clone --branch "${BRANCH}" "${REPO_URL}" "${REPO_CLONE_DIR}"
fi

# Copy integration files into scripts dir
sudo cp "${REPO_CLONE_DIR}/${SCRIPT_SUBDIR}/gico_email_enrichment.py" "${SCRIPTS_DIR}/"
sudo cp "${REPO_CLONE_DIR}/${SCRIPT_SUBDIR}/requirements.txt"          "${SCRIPTS_DIR}/"

# ─────────────────────────────────────────────────────────────────────────────
# Python virtual environment
# ─────────────────────────────────────────────────────────────────────────────
info "Creating Python virtual environment at ${VENV_DIR} ..."
sudo python3 -m venv "${VENV_DIR}"
sudo "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
sudo "${VENV_DIR}/bin/pip" install --quiet -r "${SCRIPTS_DIR}/requirements.txt"
info "Python dependencies installed."

# ─────────────────────────────────────────────────────────────────────────────
# Credentials / .env
# ─────────────────────────────────────────────────────────────────────────────
if [[ -f "${ENV_FILE}" && "${OVERWRITE_ENV}" == "false" ]]; then
    info ".env file already exists at ${ENV_FILE} — skipping credential prompts (use --overwrite-env to replace)."
else
    if [[ "${NON_INTERACTIVE}" == "true" ]]; then
        # Non-interactive: require env vars to be pre-set
        [[ -z "${VEZA_URL:-}"     ]] && error "VEZA_URL env var required in non-interactive mode."
        [[ -z "${VEZA_API_KEY:-}" ]] && error "VEZA_API_KEY env var required in non-interactive mode."
        _VEZA_URL="${VEZA_URL}"
        _VEZA_API_KEY="${VEZA_API_KEY}"
        _EMAIL_DOMAIN="${EMAIL_DOMAIN:-@smurfitwestrock.com}"
    else
        echo ""
        echo "Enter Veza credentials (input is hidden for secrets):"
        read -rp "  Veza tenant hostname (e.g. acme.veza.com): " _VEZA_URL
        read -rsp "  Veza API key: " _VEZA_API_KEY; echo
        read -rp "  Email domain suffix [default: @smurfitwestrock.com]: " _EMAIL_DOMAIN
        _EMAIL_DOMAIN="${_EMAIL_DOMAIN:-@smurfitwestrock.com}"
    fi

    sudo tee "${ENV_FILE}" > /dev/null <<EOF
# GICO Email Enrichment — Veza credentials
# Generated by installer on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
VEZA_URL=${_VEZA_URL}
VEZA_API_KEY=${_VEZA_API_KEY}
# EMAIL_DOMAIN=${_EMAIL_DOMAIN}
EOF

    sudo chmod 600 "${ENV_FILE}"
    info ".env file written to ${ENV_FILE} (permissions: 600)."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Cron wrapper script
# ─────────────────────────────────────────────────────────────────────────────
WRAPPER="${SCRIPTS_DIR}/run.sh"
sudo tee "${WRAPPER}" > /dev/null <<'WRAPPER_EOF'
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/venv/bin/activate"
python3 "${SCRIPT_DIR}/gico_email_enrichment.py" \
    --env-file "${SCRIPT_DIR}/.env"
WRAPPER_EOF
sudo chmod 755 "${WRAPPER}"

# ─────────────────────────────────────────────────────────────────────────────
# Final summary
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   GICO Email Enrichment — Installation Complete              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Install directory : ${INSTALL_DIR}"
echo "  Script            : ${SCRIPTS_DIR}/gico_email_enrichment.py"
echo "  Credentials file  : ${ENV_FILE}"
echo "  Cron wrapper      : ${WRAPPER}"
echo ""
echo "  Next steps:"
echo "  1. Review and confirm credentials in ${ENV_FILE}"
echo "  2. Dry-run:"
echo "       ${VENV_DIR}/bin/python3 ${SCRIPTS_DIR}/gico_email_enrichment.py --dry-run"
echo "  3. Push enrichment:"
echo "       ${VENV_DIR}/bin/python3 ${SCRIPTS_DIR}/gico_email_enrichment.py"
echo "  4. Optionally schedule via cron:"
echo "       echo '0 2 * * * root ${WRAPPER} >> ${LOGS_DIR}/gico-enrichment.log 2>&1' \\"
echo "           | sudo tee /etc/cron.d/gico-enrichment"
echo ""
