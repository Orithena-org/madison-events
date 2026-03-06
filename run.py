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
import os
import sys
from datetime import date, datetime, timedelta
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


def _normalize_venue(venue: str) -> str:
    """Normalize venue name for dedup comparison."""
    import re
    v = venue.lower().strip()
    # Remove common suffixes/prefixes
    for suffix in (" - madison", ", madison", " madison wi", ", madison, wi"):
        if v.endswith(suffix):
            v = v[:-len(suffix)]
    # Remove "the " prefix
    if v.startswith("the "):
        v = v[4:]
    v = re.sub(r'[^\w\s]', ' ', v)
    v = re.sub(r'\s+', ' ', v).strip()
    return v


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


def _venues_match(v1: str, v2: str) -> bool:
    """Check if two venue names refer to the same place."""
    if not v1 or not v2:
        return False
    n1 = _normalize_venue(v1)
    n2 = _normalize_venue(v2)
    if n1 == n2:
        return True
    # Check if one contains the other (e.g. "Overture Center" vs "Overture Center for the Arts")
    if len(n1) > 5 and len(n2) > 5:
        if n1 in n2 or n2 in n1:
            return True
    return False


def _is_duplicate(event: Event, existing: Event) -> bool:
    """Check if two events on the same date are duplicates."""
    norm_new = _normalize_title(event.title)
    norm_existing = _normalize_title(existing.title)

    # Title match is strong signal
    if _titles_match(norm_new, norm_existing):
        return True

    # Venue+date+time match catches renamed/reformatted events from different sources
    if (event.venue and existing.venue and event.time_start and existing.time_start
            and _venues_match(event.venue, existing.venue)
            and event.time_start == existing.time_start):
        # Same venue + same time + same date — very likely a dupe
        # Require at least some title word overlap to avoid false positives
        words_new = set(norm_new.split())
        words_existing = set(norm_existing.split())
        overlap = words_new & words_existing
        if overlap:
            return True

    return False


def _pick_richer(event: Event, existing: Event) -> Event:
    """Return the event with more complete data."""
    new_score = sum([
        len(event.description or ""),
        10 if event.venue else 0,
        5 if event.time_start else 0,
        5 if event.category else 0,
        5 if event.price else 0,
        5 if event.image_url else 0,
    ])
    existing_score = sum([
        len(existing.description or ""),
        10 if existing.venue else 0,
        5 if existing.time_start else 0,
        5 if existing.category else 0,
        5 if existing.price else 0,
        5 if existing.image_url else 0,
    ])
    return event if new_score > existing_score else existing


def scrape_events() -> list[Event]:
    """Run all scrapers and return combined events with health tracking."""
    all_events = []
    health = {
        "timestamp": datetime.now().isoformat(),
        "scrapers": {},
        "total_raw": 0,
        "total_unique": 0,
        "dupes_removed": 0,
    }

    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        scraper_health = {"status": "ok", "events": 0, "error": None}
        try:
            events = scraper.run()
            scraper_health["events"] = len(events)
            if not events:
                scraper_health["status"] = "empty"
            all_events.extend(events)
        except Exception as e:
            scraper_health["status"] = "error"
            scraper_health["error"] = str(e)
            logger.error(f"[{scraper.source_name}] Unexpected error: {e}")
        health["scrapers"][scraper.source_id] = scraper_health

    health["total_raw"] = len(all_events)

    # Deduplicate: exact title+date first, then fuzzy/venue within same date
    seen_exact = set()
    unique = []
    dupes_removed = 0
    for event in all_events:
        key = (event.title.lower().strip(), event.date)
        if key in seen_exact:
            dupes_removed += 1
            continue
        seen_exact.add(key)

        # Check fuzzy/venue match against existing events on same date
        is_dupe = False
        for i, existing in enumerate(unique):
            if existing.date == event.date and _is_duplicate(event, existing):
                is_dupe = True
                dupes_removed += 1
                unique[i] = _pick_richer(event, existing)
                break
        if not is_dupe:
            unique.append(event)

    if dupes_removed:
        logger.info(f"Deduplication removed {dupes_removed} duplicate events ({len(all_events)} raw → {len(unique)} unique)")

    health["total_unique"] = len(unique)
    health["dupes_removed"] = dupes_removed

    # Write health report
    health_file = DATA_DIR / "scraper_health.json"
    with open(health_file, "w") as f:
        json.dump(health, f, indent=2)
    logger.info(f"Scraper health report: {sum(1 for s in health['scrapers'].values() if s['status'] == 'ok')}/{len(health['scrapers'])} sources OK, {health['total_unique']} unique events")

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
        elif events_file.exists():
            logger.warning("No events scraped. Using previously cached events.")
            events = load_events(str(events_file))
            logger.info(f"Loaded {len(events)} cached events as fallback")
        else:
            logger.error("No events scraped and no cached data available. Using sample data.")
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

    # Post new events to Discord (if webhook is configured)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_MADISON_EVENTS")
    if webhook_url:
        from discord_poster import post_events
        logger.info("Posting new events to Discord...")
        post_events(webhook_url)

    # Load community feedback to influence curation (suppressed events, score boosts)
    try:
        from feedback_loader import FeedbackLoader
        from discord_poster import load_message_ids
        from curator import configure_feedback

        fl = FeedbackLoader()
        msg_ids = load_message_ids()
        if msg_ids:
            configure_feedback(loader=fl, message_ids=msg_ids)
            summary = fl.summary()
            logger.info(
                f"Feedback loaded: {summary['total_messages']} messages, "
                f"{summary['thumbs_up']} boosted, {summary['suppressed']} suppressed, "
                f"{summary['community_picks']} community picks"
            )
    except Exception as e:
        logger.warning(f"Could not load feedback (skipping): {e}")

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
