#!/usr/bin/env bash
# Wrapper script for launchd — loads .env and runs the Madison Events pipeline.
set -euo pipefail

MADISON_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORE_ROOT="$(cd "$MADISON_ROOT/../orithena-core" && pwd)"

# launchd starts with a minimal PATH — add common tool locations
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

# Source .env (contains DISCORD_WEBHOOK_MADISON_EVENTS)
if [[ -f "$CORE_ROOT/.env" ]]; then
    set -a
    source "$CORE_ROOT/.env"
    set +a
fi

cd "$MADISON_ROOT"
exec python3 -u run.py
