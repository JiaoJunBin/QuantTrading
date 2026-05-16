#!/usr/bin/env bash
# Show a cloud backtest's stats. Usage: bt_show.sh <backtest_id> [-p <project_id>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

usage() {
    cat <<EOF
usage: bt_show.sh <backtest_id> [-p <project_id>]
  backtest_id   QC backtest id (e.g. a3423b5b356ad811fca08df42e9b4e28)
  -p            override project id (defaults to QC_PROJECT_ID from .env)
EOF
    exit 1
}

[ $# -ge 1 ] || usage
BACKTEST_ID="$1"
shift || true

PROJECT_ID="${QC_PROJECT_ID:-}"
while [ $# -gt 0 ]; do
    case "$1" in
        -p) PROJECT_ID="$2"; shift 2;;
        -h|--help) usage;;
        *) echo "unknown arg: $1" >&2; usage;;
    esac
done
[ -n "$PROJECT_ID" ] || { echo "error: project id missing. Set QC_PROJECT_ID or pass -p." >&2; exit 1; }

RESP="$(qc_api backtests/read "$(jq -n --arg pid "$PROJECT_ID" --arg bid "$BACKTEST_ID" \
    '{projectId: ($pid | tonumber), backtestId: $bid}')")"

echo "$RESP" | jq -e '.success == true' >/dev/null || {
    echo "API error:" >&2
    echo "$RESP" | jq '.errors // .' >&2
    exit 1
}

echo "$RESP" | jq -r '
    .backtest as $b |
    "name:       \($b.name)",
    "status:     \($b.status)",
    "progress:   \($b.progress)",
    "url:        https://www.quantconnect.com/project/'"$PROJECT_ID"'/\($b.backtestId)",
    "",
    "── statistics ──",
    ($b.statistics | to_entries | sort_by(.key) | .[] | "  \(.key | . + ":" | ([., (28 - length) * " "] | join("")))\(.value)")
'
