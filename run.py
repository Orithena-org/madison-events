#!/usr/bin/env python3
"""
Madison Events Aggregator - Main Runner

Scrapes events from Madison sources, builds a website,
generates social media content, and creates a newsletter.

Usage:
    python run.py                  # Run full pipeline
    python run.py --scrape-only    # Only scrape events
    python run.py --build-only     # Only build site (uses cached data)
    python run.py --demo           # Run with sample data (no scraping)
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, OUTPUT_DIR
from models import Event, save_events, load_events
from categorizer import categorize_events
from scrapers import ALL_SCRAPERS
from website.build import build_site
from social.generator import generate_all_social_content, save_social_content
from newsletter.generator import generate_newsletter_html, save_newsletter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_sample_events() -> list[Event]:
    """Create sample events for demo/testing without scraping."""
    today = date.today()
    return [
        Event(
            title="Madison Symphony Orchestra: Winter Concert",
            date=today,
            source="eventbrite",
            url="https://www.overture.org/events",
            time_start="7:30 PM",
            venue="Overture Hall",
            description="Experience an evening of classical masterpieces performed by the Madison Symphony Orchestra, featuring works by Beethoven and Tchaikovsky.",
            category="Arts & Entertainment",
            price="$25-$85",
            is_featured=True,
        ),
        Event(
            title="Isthmus Beer & Cheese Fest",
            date=today,
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="12:00 PM",
            time_end="5:00 PM",
            venue="Alliant Energy Center",
            description="Sample craft beers and artisan cheeses from Wisconsin's finest producers. Over 50 breweries and 30 cheese makers.",
            category="Food & Drink",
            price="$45",
            is_featured=True,
        ),
        Event(
            title="UW Science Lecture: Climate Futures",
            date=today,
            source="uw_madison",
            url="https://today.wisc.edu/events",
            time_start="4:00 PM",
            venue="Discovery Building",
            description="Join leading climate researchers for a public lecture on Wisconsin's changing climate and what it means for our future.",
            category="Education",
        ),
        Event(
            title="Live Jazz at The Bur Oak",
            date=today + timedelta(days=1),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="8:00 PM",
            venue="The Bur Oak",
            description="An intimate evening of jazz featuring local and touring musicians.",
            category="Music",
            price="$15",
        ),
        Event(
            title="Children's Theater: The Wizard of Oz",
            date=today + timedelta(days=1),
            source="eventbrite",
            url="https://www.overture.org/events",
            time_start="2:00 PM",
            time_end="4:30 PM",
            venue="Capitol Theater",
            description="A magical retelling of the classic tale, perfect for the whole family.",
            category="Arts & Entertainment",
            price="$12-$35",
        ),
        Event(
            title="Farmers' Market on the Square",
            date=today + timedelta(days=2),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="6:00 AM",
            time_end="2:00 PM",
            venue="Capitol Square",
            description="Madison's legendary farmers' market featuring fresh produce, baked goods, flowers, and local crafts.",
            category="Community",
            is_featured=True,
        ),
        Event(
            title="Badger Basketball vs Michigan",
            date=today + timedelta(days=2),
            source="uw_madison",
            url="https://today.wisc.edu/events",
            time_start="12:00 PM",
            venue="Kohl Center",
            description="Wisconsin Badgers take on the Michigan Wolverines in Big Ten action.",
            category="Sports",
            price="$30-$120",
        ),
        Event(
            title="Comedy Night at Comedy on State",
            date=today + timedelta(days=2),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="9:00 PM",
            venue="Comedy on State",
            description="Featuring headliner comedians and local opening acts.",
            category="Comedy",
            price="$20",
        ),
        Event(
            title="Olbrich Gardens Winter Light Show",
            date=today + timedelta(days=3),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="5:00 PM",
            time_end="9:00 PM",
            venue="Olbrich Botanical Gardens",
            description="Walk through beautifully illuminated gardens featuring thousands of lights and holiday decorations.",
            category="Arts & Entertainment",
            price="$8",
        ),
        Event(
            title="Open Mic Night at Mother Fool's",
            date=today + timedelta(days=3),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="7:00 PM",
            venue="Mother Fool's Coffeehouse",
            description="Bring your poetry, music, or comedy for a supportive open mic night.",
            category="Music",
        ),
        Event(
            title="Gallery Night: MMoCA New Exhibits",
            date=today + timedelta(days=4),
            source="eventbrite",
            url="https://www.overture.org/events",
            time_start="6:00 PM",
            time_end="9:00 PM",
            venue="Madison Museum of Contemporary Art",
            description="Preview new exhibitions with artist talks, refreshments, and music.",
            category="Arts & Entertainment",
        ),
        Event(
            title="UW Astronomy Public Night",
            date=today + timedelta(days=5),
            source="uw_madison",
            url="https://today.wisc.edu/events",
            time_start="8:00 PM",
            venue="Washburn Observatory",
            description="Free stargazing through historic telescopes, weather permitting. Expert astronomers on hand.",
            category="Education",
        ),
        Event(
            title="Willy Street Co-op Cooking Class",
            date=today + timedelta(days=5),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="6:00 PM",
            time_end="8:00 PM",
            venue="Willy Street Co-op East",
            description="Learn to make seasonal Wisconsin dishes with local ingredients.",
            category="Food & Drink",
            price="$25",
        ),
        Event(
            title="Majestic Theatre: Indie Rock Showcase",
            date=today + timedelta(days=6),
            source="isthmus",
            url="https://isthmus.com/events/",
            time_start="8:00 PM",
            venue="Majestic Theatre",
            description="Three local indie bands perform original music in this monthly showcase.",
            category="Music",
            price="$12",
        ),
        Event(
            title="Forward Theater: New Play Reading",
            date=today + timedelta(days=6),
            source="eventbrite",
            url="https://www.overture.org/events",
            time_start="7:30 PM",
            venue="Overture Center - Playhouse",
            description="A staged reading of a new play by a Wisconsin playwright, followed by audience talkback.",
            category="Arts & Entertainment",
        ),
    ]


def _normalize_title(title: str) -> str:
    """Normalize event title for dedup comparison."""
    import re
    t = title.lower().strip()
    # Remove common prefixes that scrapers add
    for prefix in ("rsvp for ", "rsvp: "):
        if t.startswith(prefix):
            t = t[len(prefix):]
    # Remove punctuation and extra whitespace
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _titles_match(t1: str, t2: str) -> bool:
    """Check if two normalized titles are similar enough to be duplicates."""
    if t1 == t2:
        return True
    # Check if one title contains the other (handles "Event" vs "Event @ Venue")
    if len(t1) > 10 and len(t2) > 10:
        if t1 in t2 or t2 in t1:
            return True
    # Check word overlap for longer titles
    words1 = set(t1.split())
    words2 = set(t2.split())
    if len(words1) >= 4 and len(words2) >= 4:
        overlap = words1 & words2
        smaller = min(len(words1), len(words2))
        if len(overlap) / smaller >= 0.75:
            return True
    return False


def scrape_events() -> list[Event]:
    """Run all scrapers and return combined events."""
    all_events = []
    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        events = scraper.run()
        all_events.extend(events)

    # Deduplicate: exact title+date first, then fuzzy within same date
    seen_exact = set()
    unique = []
    for event in all_events:
        key = (event.title.lower().strip(), event.date)
        if key in seen_exact:
            continue
        seen_exact.add(key)

        # Check fuzzy match against existing events on same date
        norm = _normalize_title(event.title)
        is_dupe = False
        for existing in unique:
            if existing.date == event.date:
                if _titles_match(norm, _normalize_title(existing.title)):
                    is_dupe = True
                    # Keep the one with more info (longer description)
                    existing_desc_len = len(existing.description or "")
                    new_desc_len = len(event.description or "")
                    if new_desc_len > existing_desc_len:
                        # Replace with richer version
                        idx = unique.index(existing)
                        unique[idx] = event
                    break
        if not is_dupe:
            unique.append(event)

    return unique


def run_pipeline(scrape: bool = True, build: bool = True, demo: bool = False):
    """Run the full pipeline."""
    events_file = DATA_DIR / "events.json"

    # Step 1: Get events
    if demo:
        logger.info("Using sample event data (demo mode)")
        events = create_sample_events()
        save_events(events, str(events_file))
    elif scrape:
        logger.info("Scraping events from all sources...")
        events = scrape_events()
        if events:
            categorized = categorize_events(events)
            logger.info(f"Auto-categorized {categorized}/{len(events)} events")
            save_events(events, str(events_file))
            logger.info(f"Saved {len(events)} events to {events_file}")
        else:
            logger.warning("No events scraped. Using sample data as fallback.")
            events = create_sample_events()
            save_events(events, str(events_file))
    else:
        if events_file.exists():
            events = load_events(str(events_file))
            categorized = categorize_events(events)
            if categorized:
                logger.info(f"Auto-categorized {categorized} cached events")
            logger.info(f"Loaded {len(events)} cached events")
        else:
            logger.error("No cached events found. Run with --scrape or --demo first.")
            return

    if not build:
        logger.info("Scrape-only mode. Done.")
        return

    # Step 2: Generate newsletter
    logger.info("Generating newsletter...")
    newsletter_html = generate_newsletter_html(events)
    save_newsletter(events)

    # Step 3: Build website
    logger.info("Building website...")
    site_path = build_site(events, newsletter_html)

    # Step 4: Generate social content
    logger.info("Generating social media content...")
    social_content = generate_all_social_content(events)
    save_social_content(social_content)

    # Step 5: Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 50)
    logger.info(f"  Events:     {len(events)}")
    logger.info(f"  Website:    {site_path}/index.html")
    logger.info(f"  Newsletter: {OUTPUT_DIR}/newsletter/newsletter.html")
    logger.info(f"  Social:     {len(social_content)} posts generated")
    logger.info(f"  Sponsors:   {site_path}/sponsors.html")
    logger.info("")
    logger.info(f"Open the site: file://{site_path}/index.html")


def main():
    parser = argparse.ArgumentParser(description="Madison Events Aggregator")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape, don't build")
    parser.add_argument("--build-only", action="store_true", help="Only build from cached data")
    parser.add_argument("--demo", action="store_true", help="Use sample data (no scraping)")
    args = parser.parse_args()

    if args.scrape_only:
        run_pipeline(scrape=True, build=False)
    elif args.build_only:
        run_pipeline(scrape=False, build=True)
    elif args.demo:
        run_pipeline(scrape=False, build=True, demo=True)
    else:
        run_pipeline()


if __name__ == "__main__":
    main()
