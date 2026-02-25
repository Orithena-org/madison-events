"""Social media content generator for Madison Events."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from config import OUTPUT_DIR, SITE_URL
from models import Event

logger = logging.getLogger(__name__)


def generate_daily_highlights(events: list[Event], target_date: date = None) -> dict:
    """Generate a daily highlights post for social media."""
    if target_date is None:
        target_date = date.today()

    day_events = [e for e in events if e.date == target_date]
    if not day_events:
        return {"text": "", "platform_variants": {}}

    day_name = target_date.strftime("%A")
    date_str = target_date.strftime("%B %-d")

    # Main post text
    header = f"What's happening in Madison today ({day_name}, {date_str}):\n\n"
    items = []
    for e in day_events[:8]:
        line = f"- {e.title}"
        if e.venue:
            line += f" @ {e.venue}"
        if e.time_start:
            line += f" ({e.time_start})"
        items.append(line)

    main_text = header + "\n".join(items)
    if len(day_events) > 8:
        main_text += f"\n\n...and {len(day_events) - 8} more events!"
    main_text += f"\n\nFull listings: {SITE_URL}"

    # Platform-specific variants
    twitter_text = f"Madison events today ({date_str}):\n\n"
    for e in day_events[:4]:
        twitter_text += f"- {e.title}"
        if e.venue:
            twitter_text += f" @ {e.venue}"
        twitter_text += "\n"
    if len(day_events) > 4:
        twitter_text += f"\n+{len(day_events) - 4} more at {SITE_URL}"
    twitter_text += "\n\n#MadisonWI #MadisonEvents #ThingsToDoMadison"

    instagram_text = f"Happy {day_name}, Madison! Here's what's happening today ({date_str}):\n\n"
    for i, e in enumerate(day_events[:6], 1):
        instagram_text += f"{i}. {e.title}"
        if e.venue:
            instagram_text += f" at {e.venue}"
        instagram_text += "\n"
    instagram_text += f"\nSee all {len(day_events)} events - link in bio!\n\n"
    instagram_text += "#MadisonWI #MadisonEvents #ExploreWisconsin #ThingsToDoMadison #MadCity #WisconsinEvents"

    return {
        "type": "daily_highlights",
        "date": target_date.isoformat(),
        "event_count": len(day_events),
        "text": main_text,
        "platform_variants": {
            "twitter": twitter_text,
            "instagram": instagram_text,
            "facebook": main_text,
        },
    }


def generate_weekend_roundup(events: list[Event]) -> dict:
    """Generate a weekend roundup post."""
    today = date.today()
    # Find next Friday-Sunday
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.weekday() > 4:
        days_until_friday = 7
    friday = today + timedelta(days=days_until_friday)
    saturday = friday + timedelta(days=1)
    sunday = friday + timedelta(days=2)
    weekend_dates = {friday, saturday, sunday}

    weekend_events = [e for e in events if e.date in weekend_dates]
    weekend_events.sort(key=lambda e: e.date)

    if not weekend_events:
        return {"text": "", "platform_variants": {}}

    friday_str = friday.strftime("%B %-d")
    sunday_str = sunday.strftime("%-d")

    header = f"WEEKEND ROUNDUP: Madison Events {friday_str}-{sunday_str}\n\n"
    body = ""
    for day in [friday, saturday, sunday]:
        day_events = [e for e in weekend_events if e.date == day]
        if day_events:
            body += f"{day.strftime('%A').upper()}:\n"
            for e in day_events[:5]:
                body += f"  - {e.title}"
                if e.venue:
                    body += f" @ {e.venue}"
                if e.time_start:
                    body += f" ({e.time_start})"
                body += "\n"
            body += "\n"

    main_text = header + body
    main_text += f"Plan your weekend: {SITE_URL}\n"

    twitter_text = f"Weekend in Madison ({friday_str}-{sunday_str}):\n\n"
    for e in weekend_events[:5]:
        twitter_text += f"- {e.title} ({e.date.strftime('%a')})\n"
    if len(weekend_events) > 5:
        twitter_text += f"\n+{len(weekend_events) - 5} more at {SITE_URL}"
    twitter_text += "\n\n#MadisonWI #WeekendPlans #MadisonEvents"

    return {
        "type": "weekend_roundup",
        "event_count": len(weekend_events),
        "text": main_text,
        "platform_variants": {
            "twitter": twitter_text,
            "facebook": main_text,
            "instagram": main_text + "\n#MadisonWI #WeekendVibes #MadisonEvents #ExploreWisconsin",
        },
    }


def generate_event_spotlight(event: Event) -> dict:
    """Generate a spotlight post for a single event."""
    text = f"EVENT SPOTLIGHT: {event.title}\n\n"
    text += f"When: {event.date_display}"
    if event.time_start:
        text += f" at {event.time_start}"
    text += "\n"
    if event.venue:
        text += f"Where: {event.venue}\n"
    if event.price:
        text += f"Price: {event.price}\n"
    if event.description:
        text += f"\n{event.description[:200]}\n"
    if event.url:
        text += f"\nMore info: {event.url}\n"

    twitter_text = f"Don't miss: {event.title}\n"
    twitter_text += f"{event.date_display}"
    if event.venue:
        twitter_text += f" @ {event.venue}"
    if event.url:
        twitter_text += f"\n\n{event.url}"
    twitter_text += "\n\n#MadisonWI #MadisonEvents"

    return {
        "type": "event_spotlight",
        "event_title": event.title,
        "text": text,
        "platform_variants": {
            "twitter": twitter_text,
            "facebook": text,
            "instagram": text + "\n\n#MadisonWI #MadisonEvents #LiveMusic #ArtsAndCulture",
        },
    }


def generate_all_social_content(events: list[Event]) -> list[dict]:
    """Generate all social media content for the current batch of events."""
    content = []

    # Daily highlights for today and next 2 days
    today = date.today()
    for i in range(3):
        target = today + timedelta(days=i)
        post = generate_daily_highlights(events, target)
        if post["text"]:
            content.append(post)

    # Weekend roundup
    roundup = generate_weekend_roundup(events)
    if roundup["text"]:
        content.append(roundup)

    # Spotlights for featured events
    featured = [e for e in events if e.is_featured][:3]
    if not featured:
        # Pick top events from each source
        by_source = {}
        for e in events:
            if e.source not in by_source:
                by_source[e.source] = e
        featured = list(by_source.values())[:3]

    for event in featured:
        content.append(generate_event_spotlight(event))

    return content


def save_social_content(content: list[dict]) -> Path:
    """Save generated social content to output directory."""
    output_file = OUTPUT_DIR / "social" / "social_posts.json"
    with open(output_file, "w") as f:
        json.dump(content, f, indent=2)
    logger.info(f"Saved {len(content)} social posts to {output_file}")

    # Also generate a human-readable summary
    summary_file = OUTPUT_DIR / "social" / "social_summary.txt"
    lines = [f"MADISON EVENTS - Social Media Content ({date.today().isoformat()})\n"]
    lines.append(f"Generated {len(content)} posts\n")
    lines.append("=" * 60 + "\n")
    for i, post in enumerate(content, 1):
        lines.append(f"\n--- Post {i}: {post['type']} ---\n")
        lines.append(post["text"])
        lines.append("\n")
        for platform, variant in post.get("platform_variants", {}).items():
            lines.append(f"\n[{platform.upper()}]:\n{variant}\n")
        lines.append("\n" + "=" * 60)

    summary_file.write_text("\n".join(lines))
    logger.info(f"Saved social summary to {summary_file}")

    return output_file
