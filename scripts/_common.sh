#!/usr/bin/env bash
# Sourced by other scripts. Loads QC credentials and exposes qc_api().

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

if [ -z "${QC_USER_ID:-}" ] || [ -z "${QC_API_TOKEN:-}" ]; then
    if [ -f "$HOME/.lean/credentials" ]; then
        QC_USER_ID="$(jq -r '."user-id"' "$HOME/.lean/credentials")"
        QC_API_TOKEN="$(jq -r '."api-token"' "$HOME/.lean/credentials")"
    else
        echo "error: no QC credentials. Fill .env or run 'lean login'." >&2
        exit 1
    fi
fi

QC_API_BASE="${QC_API_BASE:-https://www.quantconnect.com/api/v2}"

# qc_api <endpoint> <json-body>
# Example: qc_api backtests/read '{"projectId":1,"backtestId":"abc"}'
qc_api() {
    local endpoint="$1"
    local body="${2:-{\}}"
    local ts hash
    ts="$(date +%s)"
    hash="$(printf '%s:%s' "$QC_API_TOKEN" "$ts" | sha256sum | awk '{print $1}')"
    curl -sS -u "${QC_USER_ID}:${hash}" \
        -H "Timestamp: ${ts}" \
        -H 'Content-Type: application/json' \
        -X POST "${QC_API_BASE}/${endpoint}" \
        -d "$body"
}
