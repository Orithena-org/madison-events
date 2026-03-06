"""Event curation engine for Madison Events.

Scores events algorithmically to select "Editor's Picks" and generate
curated commentary. This transforms the generic event dump into an
editorial product with personality.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path
from models import Event

log = logging.getLogger(__name__)

# --- Module-level feedback state (set via configure_feedback) ---
_feedback_loader = None
_feedback_message_ids: dict[str, str] = {}  # event URL -> Discord message ID

# --- Module-level preferences (loaded once via load_preferences) ---
_preferences: dict[str, list[str]] | None = None
PREFERENCES_PATH = Path(__file__).resolve().parent / "preferences.md"


def configure_feedback(loader=None, message_ids: dict[str, str] | None = None):
    """Set the module-level feedback loader and message ID map.

    Call this before scoring/selecting to enable community feedback.
    Gracefully no-ops if loader is None (feedback unavailable).
    """
    global _feedback_loader, _feedback_message_ids
    _feedback_loader = loader
    _feedback_message_ids = message_ids or {}


def load_preferences(path: Path | str | None = None) -> dict[str, list[str]]:
    """Parse preferences.md and cache the result module-wide.

    Returns a dict with keys like 'like', 'avoid', 'venue_boost', 'venue_deprioritize'
    each mapping to a list of lowercase keyword strings extracted from the bullet points.
    """
    global _preferences
    p = Path(path) if path else PREFERENCES_PATH
    if not p.exists():
        log.warning("preferences.md not found at %s — using defaults", p)
        _preferences = {}
        return _preferences

    text = p.read_text()
    sections = _parse_preference_sections(text)
    _preferences = sections
    log.info("Loaded preferences: %s", {k: len(v) for k, v in sections.items()})
    return _preferences


def _parse_preference_sections(text: str) -> dict[str, list[str]]:
    """Extract bullet-point items from each section of preferences.md."""
    section_map = {
        "what we like": "like",
        "what we avoid": "avoid",
        "audience notes": "audience",
        "venue preferences": "venue_boost",
        "category preferences": "category",
    }
    result: dict[str, list[str]] = {}
    current_key = None
    in_deprioritize = False

    for line in text.splitlines():
        stripped = line.strip()
        # Detect section headers (## ...)
        if stripped.startswith("## "):
            header = stripped.lstrip("# ").strip().lower()
            matched = False
            for pattern, key in section_map.items():
                if pattern in header:
                    current_key = key
                    in_deprioritize = False
                    if key not in result:
                        result[key] = []
                    matched = True
                    break
            if not matched:
                current_key = None
            continue

        # Detect sub-headers for venue deprioritize
        if current_key == "venue_boost" and "deprioritize" in stripped.lower():
            in_deprioritize = True
            if "venue_deprioritize" not in result:
                result["venue_deprioritize"] = []
            continue

        # Extract bullet items (- or numbered 1.)
        if current_key and re.match(r"^[-*]\s+|^\d+\.\s+", stripped):
            item = re.sub(r"^[-*]\s+|^\d+\.\s+", "", stripped).strip()
            # Strip parenthetical qualifiers for cleaner matching
            clean = re.sub(r"\(.*?\)", "", item).strip().lower()
            if not clean:
                continue
            if in_deprioritize:
                result.setdefault("venue_deprioritize", []).append(clean)
            else:
                result[current_key].append(clean)

    return result


def get_preferences() -> dict[str, list[str]]:
    """Return cached preferences, loading from disk if needed."""
    global _preferences
    if _preferences is None:
        load_preferences()
    return _preferences or {}


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


def score_event(event: Event, feedback_loader=None, message_id: str | None = None,
                thread_context: list[str] | None = None) -> tuple[float, str]:
    """Score an event for curation. Higher = more likely to be picked.

    Returns (score, curation_reason) tuple. The reason is a 1-2 sentence
    human-readable explanation of the top signals that contributed to the score.

    If feedback_loader and message_id are provided, community feedback is applied:
      - Each 👍 from a unique user adds +5
      - Each 🔥 from a unique user adds +15
      - Any ❌ sets score to -999 (suppressed)

    thread_context: Optional list of thread feedback strings to check against this event.
    """
    score = 0.0
    signals = []  # track top scoring signals for curation reason

    # Apply community feedback if available (explicit params or module-level)
    fl = feedback_loader or _feedback_loader
    mid = message_id or _feedback_message_ids.get(event.url)
    if fl and mid:
        if fl.is_suppressed(mid):
            return -999.0, "Suppressed by community feedback."
        counts = fl.reaction_counts(mid)
        thumbs_count = counts["thumbs_up"]
        fire_count = counts["fire"]
        fb_score = thumbs_count * 5 + fire_count * 15
        score += fb_score
        if fire_count:
            signals.append(("community favorite", fb_score))
        elif thumbs_count:
            signals.append(("community upvoted", fb_score))

    # Category bonus
    if event.category in HIGH_VALUE_CATEGORIES:
        score += 3.0
        signals.append((f"{event.category.lower()} priority", 3.0))

    # Featured events get a boost
    if event.is_featured:
        score += 5.0
        signals.append(("featured event", 5.0))

    # Notable venue bonus
    if event.venue:
        venue_lower = event.venue.lower()
        for notable in NOTABLE_VENUES:
            if notable in venue_lower:
                score += 2.0
                signals.append((f"notable venue ({event.venue})", 2.0))
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
        signals.append(("happening soon", 2.0))
    elif 3 <= days_away <= 4:
        score += 1.0

    # --- Preference-based scoring ---
    prefs = get_preferences()
    if prefs:
        text = _event_text(event)

        # Boost for "like" preferences
        for pref in prefs.get("like", []):
            keywords = [w for w in pref.split() if len(w) > 3]
            if keywords and any(kw in text for kw in keywords):
                score += 1.5
                signals.append((f"matches preference: {pref[:40]}", 1.5))
                log.debug("Preference boost (+1.5) for %r matching like: %s", event.title, pref)
                break  # one boost per event from likes

        # Penalty for "avoid" preferences
        for pref in prefs.get("avoid", []):
            keywords = [w for w in pref.split() if len(w) > 3]
            if keywords and any(kw in text for kw in keywords):
                score -= 10.0
                log.info("Preference penalty (-10) for %r matching avoid: %s", event.title, pref)
                break  # one penalty per event from avoids

        # Venue deprioritize
        if event.venue:
            venue_lower = event.venue.lower()
            for vp in prefs.get("venue_deprioritize", []):
                keywords = [w for w in vp.split() if len(w) > 3]
                if keywords and any(kw in venue_lower for kw in keywords):
                    score -= 1.0
                    log.debug("Venue deprioritize (-1) for %r: %s", event.venue, vp)
                    break

    # --- Thread feedback scoring ---
    # Check if any thread feedback (from all events) contains signals relevant to this event
    _thread_ctx = thread_context
    if _thread_ctx is None and fl:
        _thread_ctx = _build_thread_context(fl)
    if _thread_ctx:
        text = _event_text(event)
        for fb_text in _thread_ctx:
            fb_lower = fb_text.lower()
            # Negative signals: "skip", "not interested", "don't like", "boring", "stop"
            is_negative = any(w in fb_lower for w in ("skip", "not interested", "don't like",
                                                       "boring", "stop", "hate", "avoid"))
            # Positive signals: "love", "more like this", "great", "want", "yes"
            is_positive = any(w in fb_lower for w in ("love", "more like this", "great",
                                                       "want", "yes", "amazing", "awesome"))
            # Extract topic keywords from feedback (words > 4 chars, skip common words)
            skip_words = {"this", "that", "these", "those", "would", "could", "should",
                          "about", "really", "there", "their", "where", "which", "being",
                          "other", "every", "after", "before", "because", "through"}
            topic_words = [w for w in re.findall(r"[a-z]{5,}", fb_lower) if w not in skip_words]

            if topic_words and any(tw in text for tw in topic_words):
                if is_negative:
                    score -= 5.0
                    log.info("Thread feedback penalty (-5) for %r: %s", event.title, fb_text[:60])
                elif is_positive:
                    score += 3.0
                    signals.append(("community thread feedback positive", 3.0))
                    log.info("Thread feedback boost (+3) for %r: %s", event.title, fb_text[:60])

    reason = _build_curation_reason(event, signals)
    return score, reason


def _build_curation_reason(event: Event, signals: list[tuple[str, float]]) -> str:
    """Build a concise 1-2 sentence curation reason from top scoring signals."""
    if not signals:
        return "Picked for upcoming date and complete event details."

    # Sort by score contribution, take top 2
    signals.sort(key=lambda x: x[1], reverse=True)
    top = signals[:2]
    parts = [s[0] for s in top]

    if len(parts) == 1:
        return f"Picked for: {parts[0]}."
    return f"Picked for: {parts[0]}. {parts[1].capitalize()}."


def generate_curation_reason(event: Event, feedback_loader=None,
                             message_id: str | None = None,
                             thread_context: list[str] | None = None) -> str:
    """Generate a curation reason for an event without needing the full score.

    Convenience wrapper around score_event that returns just the reason string.
    """
    _, reason = score_event(event, feedback_loader=feedback_loader,
                            message_id=message_id, thread_context=thread_context)
    return reason


def _build_thread_context(fl) -> list[str]:
    """Extract all thread feedback text from the feedback loader."""
    try:
        all_fb = fl.all_thread_feedback()
        return [fb["text"] for fb in all_fb if fb.get("text")]
    except AttributeError:
        return []


def _event_text(event: Event) -> str:
    """Build a lowercase searchable string from event fields."""
    parts = [event.title or "", event.description or "", event.venue or "",
             event.category or ""]
    return " ".join(parts).lower()


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

    # Pre-compute thread context once for all events
    fl = feedback_loader or _feedback_loader
    thread_ctx = _build_thread_context(fl) if fl else []

    # Score all events (feedback applied via explicit params or module-level state)
    scored = [
        (*score_event(e, feedback_loader=feedback_loader,
                      message_id=(message_ids or {}).get(e.url),
                      thread_context=thread_ctx),
         e)
        for e in upcoming
    ]

    # Filter out suppressed events
    scored = [(s, r, e) for s, r, e in scored if s > -999]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Select with source diversity
    picks = []
    sources_used = {}

    for _score, _reason, event in scored:
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
            "curation_reason": _reason,
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

    scored = [(*score_event(e), e) for e in weekend_events]
    scored.sort(key=lambda x: x[0], reverse=True)

    picks = []
    for _score, _reason, event in scored[:count]:
        picks.append({
            "event": event,
            "commentary": get_commentary(event),
            "score": _score,
            "curation_reason": _reason,
        })

    return picks
