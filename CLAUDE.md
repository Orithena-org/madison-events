# Madison Events — Events Aggregator

Madison WI events aggregator. Scrapes local event sources, builds a static site, and generates newsletter/social content.

For system-wide context, see `../CLAUDE.md`. For the org mission, see `../orithena-org/NORTH_STAR.md`.

## Key Commands

| Command | What it does |
|---|---|
| `make run` | Full pipeline (scrape + build) |
| `make scrape` | Scrape events only |
| `make build` | Build site from cached events |
| `make demo` | Run with sample data (no network) |

## Pipeline

Scrapers -> event models -> site / social / newsletter (output in `output/`)

## Git Rules

Check `ORITHENA_AGENT_RUN` to determine workflow:

- **Agent run** (`ORITHENA_AGENT_RUN` is set): use `scout/<name>` branches and PRs — never push to main
- **Human session** (`ORITHENA_AGENT_RUN` is not set): push directly to main

### Forbidden

- `git push --force` — never, on any branch, for any reason
- `git reset --hard` — never discard work
