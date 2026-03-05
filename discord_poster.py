#!/usr/bin/env python3
"""Post new events to Discord via webhook as rich embeds.

Usage:
    python discord_poster.py              # Post new events
    python discord_poster.py --dry-run    # Preview without posting

Requires DISCORD_WEBHOOK_MADISON_EVENTS env var to be set.
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests

from config import DATA_DIR

logger = logging.getLogger(__name__)

POSTED_FILE = DATA_DIR / "discord_posted.json"
EVENTS_FILE = DATA_DIR / "events.json"

# Category -> embed color (Discord int format)
CATEGORY_COLORS = {
    "Music": 0x9B59B6,
    "Arts & Entertainment": 0xE74C3C,
    "Food & Drink": 0xE67E22,
    "Community": 0x2ECC71,
    "Education": 0x3498DB,
    "Sports": 0x1ABC9C,
    "Family": 0xF1C40F,
    "Comedy": 0xE91E63,
    "Wellness": 0x00BCD4,
    "Outdoors": 0x4CAF50,
}
DEFAULT_COLOR = 0x95A5A6


def load_posted() -> set[str]:
    """Load the set of already-posted event URLs."""
    if POSTED_FILE.exists():
        try:
            data = json.loads(POSTED_FILE.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_posted(posted: set[str]) -> None:
    """Persist the set of posted event URLs."""
    POSTED_FILE.write_text(
        json.dumps(sorted(posted), indent=2),
        encoding="utf-8",
    )


def load_events() -> list[dict]:
    """Load events from data/events.json."""
    if not EVENTS_FILE.exists():
        logger.warning("Events file not found: %s", EVENTS_FILE)
        return []
    return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))


def build_embed(event: dict) -> dict:
    """Build a Discord embed dict from an event."""
    category = event.get("category") or "Uncategorized"
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)

    # Truncate description
    desc = event.get("description") or ""
    if len(desc) > 150:
        desc = desc[:147] + "..."

    # Build time string
    time_str = event.get("time_start") or ""
    if event.get("time_end") and event["time_end"] != event.get("time_start"):
        time_str += f" - {event['time_end']}"

    fields = []
    if event.get("date"):
        fields.append({"name": "Date", "value": event["date"], "inline": True})
    if time_str:
        fields.append({"name": "Time", "value": time_str, "inline": True})
    if event.get("venue"):
        fields.append({"name": "Venue", "value": event["venue"], "inline": True})
    if event.get("price"):
        fields.append({"name": "Price", "value": event["price"], "inline": True})
    if category != "Uncategorized":
        fields.append({"name": "Category", "value": category, "inline": True})

    embed = {
        "title": event.get("title", "Untitled Event"),
        "url": event.get("url"),
        "description": desc,
        "color": color,
        "fields": fields,
        "footer": {"text": f"Source: {event.get('source', 'unknown')}"},
    }

    if event.get("image_url"):
        embed["thumbnail"] = {"url": event["image_url"]}

    return embed


def post_events(webhook_url: str, dry_run: bool = False) -> int:
    """Post new events to Discord. Returns count of events posted."""
    events = load_events()
    if not events:
        logger.info("No events to post")
        return 0

    posted = load_posted()
    new_events = [e for e in events if e.get("url") and e["url"] not in posted]

    if not new_events:
        logger.info("No new events to post (%d already posted)", len(posted))
        return 0

    logger.info("Found %d new events to post", len(new_events))

    count = 0
    for event in new_events:
        embed = build_embed(event)

        if dry_run:
            logger.info("[DRY RUN] Would post: %s", event.get("title"))
            count += 1
            continue

        payload = {"embeds": [embed]}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                posted.add(event["url"])
                count += 1
                logger.info("Posted: %s", event.get("title"))
            elif resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                logger.warning("Rate limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                # Retry once
                resp = requests.post(webhook_url, json=payload, timeout=10)
                if resp.status_code in (200, 204):
                    posted.add(event["url"])
                    count += 1
            else:
                logger.error("Failed to post %s: HTTP %d", event.get("title"), resp.status_code)
        except requests.RequestException as e:
            logger.error("Error posting %s: %s", event.get("title"), e)

        time.sleep(0.5)  # Small delay between posts

    if not dry_run:
        save_posted(posted)

    logger.info("Posted %d/%d new events", count, len(new_events))
    return count


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Post events to Discord")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    args = parser.parse_args()

    webhook_url = os.environ.get("DISCORD_WEBHOOK_MADISON_EVENTS")
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_MADISON_EVENTS not set, skipping Discord posting")
        return

    post_events(webhook_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
