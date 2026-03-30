# msndo — Events Aggregator for Madison, WI

Madison WI events aggregator. GitHub Pages shell — templates, static assets, and output live here. Pipeline code lives in `orithena-org/content/`.

For system-wide context, see `../CLAUDE.md`. For the org mission, see `../orithena-org/NORTH_STAR.md`.

## Key Commands

| Command | What it does |
|---|---|
| `make run` | Full pipeline (scrape + build + post) |
| `make scrape` | Scrape events only |
| `make build` | Build site from cached events |
| `make demo` | Run with sample data (no network) |

## Architecture

This repo is a **product shell**. All pipeline logic is in `orithena-org/content/`:
- Adapters, scoring, dedup, categorization → `content/adapters/`, `content/curation/`
- Discord posting → `content/discord/`
- Newsletter, social → `content/output/`
- Site builder → `content/sitegen/madison_build.py`
- Domain config → `content/domains/madison_events.yaml`

This repo contains only:
- `website/templates/` — Jinja2 templates (product identity)
- `website/static/` — CSS, JS, images
- `output/` — Generated site (gitignored)
- `Makefile` — Delegates to unified pipeline

## Git Rules

Check `ORITHENA_AGENT_RUN` to determine workflow:

- **Agent run** (`ORITHENA_AGENT_RUN` is set): use `scout/<name>` branches and PRs — never push to main
- **Human session** (`ORITHENA_AGENT_RUN` is not set): push directly to main

### Forbidden

- `git push --force` — never, on any branch, for any reason
- `git reset --hard` — never discard work
