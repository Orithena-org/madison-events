# Madison Events Aggregator

A complete events aggregation system for Madison, WI. Scrapes events from local sources, builds a clean website, generates social media content, and creates weekly newsletters.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with sample data (no scraping needed)
python run.py --demo

# Open the generated site
open output/site/index.html
```

## Commands

```bash
python run.py              # Full pipeline: scrape + build + social + newsletter
python run.py --demo       # Use sample data (no network requests)
python run.py --scrape-only # Only scrape and save events
python run.py --build-only  # Build from cached data
```

## Architecture

```
madison-events/
├── run.py                  # Main pipeline runner
├── config.py               # Configuration and settings
├── models.py               # Event data model
├── scrapers/               # Event source scrapers
│   ├── base.py             # Base scraper class
│   ├── isthmus.py          # Isthmus (isthmus.com/events)
│   ├── overture.py         # Overture Center (overture.org)
│   └── uw_madison.py       # UW-Madison (today.wisc.edu)
├── website/                # Static site generator
│   ├── build.py            # Site builder
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # CSS and JavaScript
├── social/                 # Social media content
│   └── generator.py        # Multi-platform post generator
├── newsletter/             # Email newsletter
│   └── generator.py        # HTML + plain text newsletter
├── data/                   # Scraped event data (JSON)
└── output/                 # Generated outputs
    ├── site/               # Static website files
    ├── social/             # Social media posts
    └── newsletter/         # Newsletter HTML + text
```

## Features

### Event Sources
- **Isthmus** - Madison's alt-weekly events calendar
- **Overture Center** - Performing arts venue listings
- **UW-Madison** - University events via today.wisc.edu

### Website
- Responsive design with list and calendar views
- Source filtering (Isthmus, Overture, UW-Madison)
- Ad placement slots (header, sidebar, in-feed)
- Newsletter signup form
- Sponsor showcase

### Social Media
- Daily event highlights (Twitter, Instagram, Facebook)
- Weekend roundup posts
- Individual event spotlights
- Platform-specific formatting and hashtags

### Newsletter
- Weekly HTML email digest with event highlights
- Plain text fallback version
- Sponsor placement slots
- Category-based event grouping

### Monetization
- **Ad slots**: Header banner (728x90), sidebar (300x250), in-feed sponsored
- **Sponsor tiers**: Presenting ($500/mo), Supporting ($200/mo), Community ($50/mo)
- **Featured events**: Premium placement for paying venues/organizers

## Deployment

The site is deployed to GitHub Pages automatically via GitHub Actions.

**Live site:** https://orithena-org.github.io/madison-events

### How it works

1. Every push to `main` triggers a build via `.github/workflows/deploy.yml`
2. The workflow installs Python dependencies, runs `python run.py --demo`, and deploys `output/site/` to GitHub Pages
3. A daily scheduled build (6 AM Central) keeps the demo dates current

### Setup (one-time)

1. Go to the repo's **Settings > Pages**
2. Set **Source** to "GitHub Actions"
3. Push to `main` — the workflow handles the rest

### Custom domain (optional)

To use a custom domain, add a `CNAME` file to `website/static/` containing your domain (it gets copied to `output/site/` during build), and update the `SITE_URL` env var in the workflow.

## Feedback

Found an issue or want to suggest a new event source? Use our [feedback form](https://github.com/Orithena-org/madison-events/issues/new/choose) on GitHub.
