"""Automatic event categorization based on title, description, and venue keywords.

Events from most scrapers arrive without categories. This module assigns
categories using keyword matching so the curator and site filters work well.
"""
from __future__ import annotations

import re
from models import Event


# Category keyword maps — checked against title + description + venue (lowercased)
# Order matters: first match wins, so more specific categories come first.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Comedy", [
        "comedy", "improv", "standup", "stand-up", "comedian", "funny",
        "comedy on state", "laugh",
    ]),
    ("Music", [
        "concert", "live music", "jazz", "rock", "band", "orchestra",
        "symphony", "choir", "recital", "singer", "songwriter",
        "dj ", "open mic", "album", "majestic theatre", "high noon saloon",
        "bur oak", "sylvee", "frequency", "hip-hop", "hip hop",
        "folk music", "bluegrass", "acoustic", "karaoke",
        "cafe coda", "coda presents",
    ]),
    ("Sports", [
        "badger basketball", "badger football", "badger hockey",
        "kohl center", "camp randall", "game day", "gameday",
        "tournament", "5k run", "marathon", "triathlon", "race",
        "wrestling", "volleyball", "soccer", "tennis",
        "archery", "fencing", "combat", "rapier", "intramural",
    ]),
    ("Food & Drink", [
        "brunch", "beer", "wine", "food", "cooking class", "tasting",
        "dinner", "chef", "brewery", "distillery", "cocktail",
        "farmers market", "farmer's market", "farmers' market",
        "co-op", "cheese", "supper club",
    ]),
    ("Arts & Entertainment", [
        "gallery", "theater", "theatre", "exhibit", "exhibition",
        "museum", "art ", " art", "film", "cinema", "screening",
        "dance", "ballet", "opera", "play ", "musical",
        "overture", "chazen", "mmoca", "forward theater",
        "drag", "burlesque", "puppet", "magic show",
        "scavenger hunt", "game night", "puzzle", "reception",
    ]),
    ("Education", [
        "lecture", "workshop", "seminar", "class", "webinar",
        "discussion", "panel", "talk", "presentation", "symposium",
        "conference", "training", "certification", "learn",
        "science", "research", "discovery building",
        "career fair", "sat practice", "test prep",
    ]),
    ("Outdoors", [
        "hike", "hiking", "garden", "birding", "bird ", "nature",
        "trail", "paddle", "kayak", "canoe", "fishing",
        "arboretum", "olbrich", "park", "outdoor",
        "rain garden", "conservation",
    ]),
    ("Wellness", [
        "meditation", "yoga", "mindfulness", "zen", "exercise",
        "fitness", "health", "wellness", "tai chi", "qigong",
    ]),
    ("Family", [
        "kids", "children", "family", "storytime", "story time",
        "story hour", "puppet", "ages 3", "ages 5",
        "children's", "childrens",
    ]),
    ("Community", [
        "volunteer", "neighborhood", "civic", "meeting", "council",
        "fundraiser", "charity", "benefit", "rally", "protest",
        "democracy", "election", "voting", "voter", "political",
        "naturalization", "citizenship", "league of women",
    ]),
]


def categorize_event(event: Event) -> str | None:
    """Assign a category to an event based on keyword matching.

    Returns the category string or None if no match.
    Does not override existing categories.
    """
    if event.category:
        return event.category

    # Build searchable text from all available fields
    parts = [event.title or ""]
    if event.description:
        parts.append(event.description)
    if event.venue:
        parts.append(event.venue)
    text = " ".join(parts).lower()

    for category, keywords in CATEGORY_RULES:
        for keyword in keywords:
            if keyword in text:
                return category

    return None


def categorize_events(events: list[Event]) -> int:
    """Assign categories to all uncategorized events in-place.

    Returns the number of events that were categorized.
    """
    count = 0
    for event in events:
        if not event.category:
            cat = categorize_event(event)
            if cat:
                event.category = cat
                count += 1
    return count
