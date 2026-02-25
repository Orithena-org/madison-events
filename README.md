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
