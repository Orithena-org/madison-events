"""Event curation engine for Madison Events.

Scores events algorithmically to select "Editor's Picks" and generate
curated commentary. This transforms the generic event dump into an
editorial product with personality.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from models import Event


# --- Module-level feedback state (set via configure_feedback) ---
_feedback_loader = None
_feedback_message_ids: dict[str, str] = {}  # event URL -> Discord message ID


def configure_feedback(loader=None, message_ids: dict[str, str] | None = None):
    """Set the module-level feedback loader and message ID map.

    Call this before scoring/selecting to enable community feedback.
    Gracefully no-ops if loader is None (feedback unavailable).
    """
    global _feedback_loader, _feedback_message_ids
    _feedback_loader = loader
    _feedback_message_ids = message_ids or {}


# Categories we care most about (for scoring)
HIGH_VALUE_CATEGORIES = {
    "Arts & Entertainment", "Music", "Food & Drink", "Comedy",
    "Community", "Festival",
}

# Venues that signal quality/interest
NOTABLE_VENUES = {
    "overture", "majestic", "barrymore", "high noon", "sylvee",
    "memorial union", "terrace", "capitol square", "olbrich",
    "dane county", "alliant", "kohl center", "bur oak",
    "mother fool", "comedy on state", "forward theater",
    "bartell", "union south", "chazen", "mmoca",
}

# Commentary templates by category — gives the newsletter personality
COMMENTARY = {
    "Arts & Entertainment": [
        "Worth clearing your calendar for.",
        "This is the kind of thing that makes Madison special.",
        "Don't sleep on this one.",
        "A standout in a week of great options.",
    ],
    "Music": [
        "Your ears will thank you.",
        "One of those shows you'll be glad you didn't skip.",
        "The kind of night out Madison does best.",
        "Live music the way it should be.",
    ],
    "Food & Drink": [
        "Bring your appetite (and maybe a friend).",
        "Wisconsin knows food. This proves it.",
        "Your weekend plans just got tastier.",
    ],
    "Comedy": [
        "Laughter guaranteed (or your evening back).",
        "Just what the midweek blues ordered.",
    ],
    "Community": [
        "This is how community happens.",
        "Madison at its best — people showing up for each other.",
        "Free, fun, and good for the soul.",
    ],
    "Education": [
        "Feed your brain this week.",
        "The kind of free education you can't get on YouTube.",
    ],
    "Sports": [
        "On, Wisconsin!",
        "Bring your game-day energy.",
    ],
}

DEFAULT_COMMENTARY = [
    "One of our top picks this week.",
    "We think you'll like this one.",
    "Definitely worth checking out.",
    "A highlight of the week ahead.",
]


def score_event(event: Event, feedback_loader=None, message_id: str | None = None) -> float:
    """Score an event for curation. Higher = more likely to be picked.

    If feedback_loader and message_id are provided, community feedback is applied:
      - Each 👍 from a unique user adds +5
      - Each 🔥 from a unique user adds +15
      - Any ❌ sets score to -999 (suppressed)
    """
    score = 0.0

    # Apply community feedback if available (explicit params or module-level)
    fl = feedback_loader or _feedback_loader
    mid = message_id or _feedback_message_ids.get(event.url)
    if fl and mid:
        if fl.is_suppressed(mid):
            return -999.0
        data = fl._load()
        entry = data.get(str(mid), {})
        reactions = entry.get("reactions", {})
        thumbs = reactions.get("\U0001f44d", {})
        score += thumbs.get("count", 0) * 5
        fire = reactions.get("\U0001f525", {})
        score += fire.get("count", 0) * 15

    # Category bonus
    if event.category in HIGH_VALUE_CATEGORIES:
        score += 3.0

    # Featured events get a boost
    if event.is_featured:
        score += 5.0

    # Notable venue bonus
    if event.venue:
        venue_lower = event.venue.lower()
        for notable in NOTABLE_VENUES:
            if notable in venue_lower:
                score += 2.0
                break

    # Events with prices tend to be more "real" / production-quality
    if event.price:
        score += 1.0

    # Events with full info are better picks
    if event.description and len(event.description) > 50:
        score += 1.5
    if event.time_start:
        score += 0.5
    if event.venue:
        score += 0.5
    if event.image_url:
        score += 1.0

    # Slight variety bonus — prefer events from different sources
    # (handled at selection level, not scoring)

    # Time proximity bonus — closer events score higher
    days_away = (event.date - date.today()).days
    if 0 <= days_away <= 2:
        score += 2.0
    elif 3 <= days_away <= 4:
        score += 1.0

    return score


def get_commentary(event: Event) -> str:
    """Get a short editorial comment for an event."""
    category = event.category or ""
    options = COMMENTARY.get(category, DEFAULT_COMMENTARY)
    # Use event title hash for deterministic-ish selection
    idx = hash(event.title) % len(options)
    return options[idx]


def select_editors_picks(
    events: list[Event],
    count: int = 5,
    days_ahead: int = 7,
    feedback_loader=None,
    message_ids: dict[str, str] | None = None,
) -> list[dict]:
    """Select top events as Editor's Picks with commentary.

    Returns a list of dicts with 'event' and 'commentary' keys.
    Ensures source diversity in the picks.

    Args:
        feedback_loader: Optional FeedbackLoader for community scoring.
        message_ids: Optional mapping of event URL -> Discord message ID.
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    # Filter to upcoming events
    upcoming = [e for e in events if today <= e.date <= end]
    if not upcoming:
        return []

    # Score all events (feedback applied via explicit params or module-level state)
    scored = [
        (score_event(e, feedback_loader=feedback_loader,
                     message_id=(message_ids or {}).get(e.url)),
         e)
        for e in upcoming
    ]

    # Filter out suppressed events
    scored = [(s, e) for s, e in scored if s > -999]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Select with source diversity
    picks = []
    sources_used = {}

    for _score, event in scored:
        if len(picks) >= count:
            break

        # Allow max 2 events from same source in picks
        source_count = sources_used.get(event.source, 0)
        if source_count >= 2:
            continue

        picks.append({
            "event": event,
            "commentary": get_commentary(event),
            "score": _score,
        })
        sources_used[event.source] = source_count + 1

    return picks


def select_weekend_picks(
    events: list[Event],
    count: int = 3,
) -> list[dict]:
    """Select top weekend events specifically."""
    today = date.today()
    # Find next Friday-Sunday
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.weekday() > 4:
        days_until_friday = 7
    friday = today + timedelta(days=days_until_friday)
    sunday = friday + timedelta(days=2)

    weekend_events = [e for e in events if friday <= e.date <= sunday]
    if not weekend_events:
        return []

    scored = [(score_event(e), e) for e in weekend_events]
    scored.sort(key=lambda x: x[0], reverse=True)

    picks = []
    for _score, event in scored[:count]:
        picks.append({
            "event": event,
            "commentary": get_commentary(event),
            "score": _score,
        })

    return picks
