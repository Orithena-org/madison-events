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
STATE_FILE = DATA_DIR / "discord_state.json"
MESSAGE_IDS_FILE = DATA_DIR / "discord_message_ids.json"
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


def load_message_ids() -> dict[str, str]:
    """Load mapping of event URL -> Discord message ID."""
    if MESSAGE_IDS_FILE.exists():
        try:
            return json.loads(MESSAGE_IDS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def save_message_ids(msg_ids: dict[str, str]) -> None:
    """Persist event URL -> Discord message ID mapping."""
    MESSAGE_IDS_FILE.write_text(
        json.dumps(msg_ids, indent=2),
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

    # Prepend curation reason in italics if present
    desc = event.get("description") or ""
    if len(desc) > 150:
        desc = desc[:147] + "..."
    curation_reason = event.get("curation_reason")
    if curation_reason:
        desc = f"*{curation_reason}*\n\n{desc}" if desc else f"*{curation_reason}*"

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


def load_state() -> dict:
    """Load discord posting state (last_message_id, etc.)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def save_state(state: dict) -> None:
    """Persist discord posting state."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_last_post_reactions(state: dict) -> bool:
    """Check if the last posted message has at least 1 reaction."""
    last_msg_id = state.get("last_message_id")
    channel_id = os.environ.get("DISCORD_CHANNEL_MADISON_EVENTS")
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")

    if not all([last_msg_id, channel_id, bot_token]):
        logger.warning("Missing last_message_id, DISCORD_CHANNEL_MADISON_EVENTS, or DISCORD_BOT_TOKEN for reaction check")
        return False

    try:
        resp = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{last_msg_id}",
            headers={"Authorization": f"Bot {bot_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("Failed to fetch last message: HTTP %d", resp.status_code)
            return False
        msg = resp.json()
        reactions = msg.get("reactions", [])
        total = sum(r.get("count", 0) for r in reactions)
        return total >= 1
    except requests.RequestException as e:
        logger.warning("Error checking reactions: %s", e)
        return False


def _enrich_with_curation_reasons(events: list[dict]) -> None:
    """Score events and attach curation_reason to each event dict in-place."""
    try:
        from models import Event
        from curator import generate_curation_reason
        for event in events:
            if event.get("curation_reason"):
                continue
            try:
                ev = Event.from_dict(event)
                event["curation_reason"] = generate_curation_reason(ev)
            except Exception:
                pass
    except ImportError:
        logger.debug("Curator not available, skipping curation reasons")


def post_events(webhook_url: str, top_n: int = 5, dry_run: bool = False) -> int:
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

    # Sort by date ascending (most upcoming first)
    new_events.sort(key=lambda e: e.get("date", ""))

    # Enrich events with curation reasons before posting
    _enrich_with_curation_reasons(new_events)

    # Limit to top N
    to_post = new_events[:top_n]

    logger.info("Found %d new events, posting top %d", len(new_events), len(to_post))

    state = load_state()
    msg_ids = load_message_ids()
    last_message_id = None
    count = 0
    for event in to_post:
        embed = build_embed(event)

        if dry_run:
            logger.info("[DRY RUN] Would post: %s", event.get("title"))
            count += 1
            continue

        payload = {"embeds": [embed]}
        try:
            resp = requests.post(f"{webhook_url}?wait=true", json=payload, timeout=10)
            if resp.status_code in (200, 204):
                posted.add(event["url"])
                count += 1
                logger.info("Posted: %s", event.get("title"))
                try:
                    msg_data = resp.json()
                    msg_id = msg_data.get("id")
                    if msg_id:
                        msg_ids[event["url"]] = msg_id
                        last_message_id = msg_id
                except (ValueError, KeyError):
                    pass
            elif resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                logger.warning("Rate limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                resp = requests.post(f"{webhook_url}?wait=true", json=payload, timeout=10)
                if resp.status_code in (200, 204):
                    posted.add(event["url"])
                    count += 1
                    try:
                        msg_data = resp.json()
                        msg_id = msg_data.get("id")
                        if msg_id:
                            msg_ids[event["url"]] = msg_id
                            last_message_id = msg_id
                    except (ValueError, KeyError):
                        pass
            else:
                logger.error("Failed to post %s: HTTP %d", event.get("title"), resp.status_code)
        except requests.RequestException as e:
            logger.error("Error posting %s: %s", event.get("title"), e)

        time.sleep(0.5)

    if not dry_run:
        save_posted(posted)
        save_message_ids(msg_ids)
        if last_message_id:
            state["last_message_id"] = last_message_id
            save_state(state)

    logger.info("Posted %d/%d new events", count, len(to_post))
    return count


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Post events to Discord")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--top", type=int, default=5, help="Number of top events to post (default: 5)")
    parser.add_argument("--more", action="store_true", help="Post next batch only if last post got reactions")
    args = parser.parse_args()

    webhook_url = os.environ.get("DISCORD_WEBHOOK_MADISON_EVENTS")
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_MADISON_EVENTS not set, skipping Discord posting")
        return

    if args.more:
        state = load_state()
        if not state.get("last_message_id"):
            logger.info("No previous post found — run without --more first")
            return
        if not check_last_post_reactions(state):
            logger.info("No reactions yet on last post — skipping.")
            return
        logger.info("Last post has reactions, posting next batch")

    post_events(webhook_url, top_n=args.top, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
