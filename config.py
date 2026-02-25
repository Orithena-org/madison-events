"""Configuration for Madison Events Aggregator."""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
WEBSITE_DIR = PROJECT_ROOT / "website"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "site").mkdir(exist_ok=True)
(OUTPUT_DIR / "social").mkdir(exist_ok=True)
(OUTPUT_DIR / "newsletter").mkdir(exist_ok=True)

# Scraper settings
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": "MadisonEventsAggregator/1.0 (community events calendar)"
}

# Event sources
SOURCES = {
    "isthmus": {
        "name": "Isthmus",
        "base_url": "https://isthmus.com",
        "events_url": "https://isthmus.com/events/",
    },
    "overture": {
        "name": "Overture Center",
        "base_url": "https://www.overture.org",
        "events_url": "https://www.overture.org/events",
    },
    "uw_madison": {
        "name": "UW-Madison",
        "base_url": "https://today.wisc.edu",
        "events_url": "https://today.wisc.edu/events",
    },
}

# Website settings
SITE_TITLE = "Madison Events"
SITE_TAGLINE = "Your guide to everything happening in Madison, WI"
SITE_URL = os.getenv("SITE_URL", "https://madison-events.example.com")

# Monetization
AD_SLOTS = {
    "header_banner": {"width": 728, "height": 90, "label": "Header Banner"},
    "sidebar": {"width": 300, "height": 250, "label": "Sidebar Ad"},
    "in_feed": {"width": 600, "height": 100, "label": "In-Feed Sponsored"},
}

SPONSOR_TIERS = {
    "presenting": {"price": 500, "perks": ["logo on all pages", "featured events", "newsletter mention"]},
    "supporting": {"price": 200, "perks": ["logo on homepage", "newsletter mention"]},
    "community": {"price": 50, "perks": ["listing in sponsors page"]},
}
