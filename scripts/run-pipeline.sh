#!/usr/bin/env bash
# Wrapper script for launchd — loads .env, runs the Madison Events pipeline,
# then commits and pushes site output so GitHub Pages deploys automatically.
set -euo pipefail

MADISON_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORE_ROOT="$(cd "$MADISON_ROOT/../orithena-org/infrastructure" && pwd)"

# launchd starts with a minimal PATH — add common tool locations
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

# Source .env (contains DISCORD_WEBHOOK_MADISON_EVENTS)
if [[ -f "$CORE_ROOT/.env" ]]; then
    set -a
    source "$CORE_ROOT/.env"
    set +a
fi

AGENT_ROOT="$(cd "$MADISON_ROOT/../agent-01" && pwd)"
ORG_ROOT="$(cd "$MADISON_ROOT/../orithena-org" && pwd)"

# --- Branch guard: must be on main before any writes ---
cd "$MADISON_ROOT"
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "main" ]]; then
    echo "[deploy] WARNING: was on branch '$current_branch', switching to main"
    git checkout main
fi
# Pull latest — tolerate network failures so the pipeline still runs with local state
git pull origin main 2>/dev/null || echo "[deploy] WARNING: git pull failed (network?), continuing with local main"

cd "$ORG_ROOT"
python3 -u -m content.pipeline --domain madison_events

# --- Generate curated picks page ---
if [[ -f "$AGENT_ROOT/tools/generate_picks_page.py" ]]; then
    echo "[picks] Generating curated picks page..."
    python3 "$AGENT_ROOT/tools/generate_picks_page.py" \
        --output "$MADISON_ROOT/output/site/picks" || true
fi

# --- Generate iCal subscription feed ---
if [[ -f "$AGENT_ROOT/tools/generate_ical_feed.py" ]]; then
    echo "[ical] Generating iCal subscription feed..."
    python3 "$AGENT_ROOT/tools/generate_ical_feed.py" \
        --output "$MADISON_ROOT/output/site/feeds" || true
fi

# --- Deploy: commit and push site output if changed ---
cd "$MADISON_ROOT"

if ! git diff --quiet output/ 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard output/)" ]; then
    git add output/data/ output/site/
    git commit -m "chore(site): update generated site output $(date +%Y-%m-%d)"
    if git push origin main; then
        echo "[deploy] Site output committed and pushed."
        # Notify search engines about the update
        python3 "$MADISON_ROOT/scripts/notify_search_engines.py" || true
    else
        echo "[deploy] WARNING: git push failed (network?), commit is local — will push on next run"
    fi
else
    echo "[deploy] No site changes to commit."
fi
