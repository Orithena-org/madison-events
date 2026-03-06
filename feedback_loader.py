"""
Load community reaction feedback from the Orithena Discord bot.

Reads event_reactions.json produced by orithena-core's feedback store
and provides scoring adjustments for the Madison Events pipeline.

Usage:
    from feedback_loader import FeedbackLoader

    loader = FeedbackLoader()
    boost = loader.score_boost(message_id)     # +N for thumbs up, 0 otherwise
    suppress = loader.is_suppressed(message_id) # True if event got X reactions
    picks = loader.community_picks()            # List of message IDs with fire reactions
"""

import json
import os
from pathlib import Path

# Default path to the shared feedback store
DEFAULT_STORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "orithena-core"
    / "feedback"
    / "event_reactions.json"
)
STORE_PATH = Path(os.environ.get("FEEDBACK_STORE_PATH", str(DEFAULT_STORE_PATH)))


class FeedbackLoader:
    """Load and query community reaction feedback for event scoring."""

    def __init__(self, store_path: Path | str | None = None):
        self._path = Path(store_path) if store_path else STORE_PATH
        self._data: dict | None = None

    def _load(self) -> dict:
        """Load feedback data (cached per instance)."""
        if self._data is None:
            if self._path.exists():
                try:
                    self._data = json.loads(self._path.read_text())
                except (json.JSONDecodeError, OSError):
                    self._data = {}
            else:
                self._data = {}
        return self._data

    def reload(self):
        """Force reload from disk."""
        self._data = None
        return self._load()

    def score_boost(self, message_id: str) -> int:
        """Return a scoring boost based on thumbs-up reactions.

        Each thumbs-up adds +1 to the score. Fire reactions add +3 each.
        """
        data = self._load()
        entry = data.get(str(message_id), {})
        reactions = entry.get("reactions", {})

        boost = 0
        thumbs = reactions.get("\U0001f44d", {})
        boost += thumbs.get("count", 0)

        fire = reactions.get("\U0001f525", {})
        boost += fire.get("count", 0) * 3

        return boost

    def is_suppressed(self, message_id: str) -> bool:
        """Return True if the event has been marked for suppression (X reactions)."""
        data = self._load()
        entry = data.get(str(message_id), {})
        reactions = entry.get("reactions", {})
        x_reactions = reactions.get("\u274c", {})
        return x_reactions.get("count", 0) > 0

    def community_picks(self) -> list[dict]:
        """Return entries that have fire reactions (community picks).

        Returns list of dicts with message_id, content, and fire count.
        """
        data = self._load()
        picks = []
        for msg_id, entry in data.items():
            reactions = entry.get("reactions", {})
            fire = reactions.get("\U0001f525", {})
            if fire.get("count", 0) > 0:
                picks.append({
                    "message_id": msg_id,
                    "channel": entry.get("channel", ""),
                    "content": entry.get("content", ""),
                    "fire_count": fire["count"],
                    "fire_users": fire.get("users", []),
                })
        picks.sort(key=lambda p: p["fire_count"], reverse=True)
        return picks

    def suppressed_message_ids(self) -> set[str]:
        """Return set of message IDs that should be suppressed."""
        data = self._load()
        suppressed = set()
        for msg_id, entry in data.items():
            reactions = entry.get("reactions", {})
            x_reactions = reactions.get("\u274c", {})
            if x_reactions.get("count", 0) > 0:
                suppressed.add(msg_id)
        return suppressed

    def thread_feedback(self, message_id: str) -> list[dict]:
        """Return thread feedback entries for a specific message.

        Each entry has: author, author_id, text, timestamp.
        Returns empty list if no thread feedback exists.
        """
        data = self._load()
        entry = data.get(str(message_id), {})
        return entry.get("thread_feedback", [])

    def all_thread_feedback(self) -> list[dict]:
        """Return all thread feedback across all messages.

        Each entry includes the parent message_id plus the feedback fields.
        Useful for building aggregate context for the curator.
        """
        data = self._load()
        all_fb = []
        for msg_id, entry in data.items():
            for fb in entry.get("thread_feedback", []):
                all_fb.append({"message_id": msg_id, **fb})
        return all_fb

    def summary(self) -> dict:
        """Return a summary of all feedback for logging/debugging."""
        data = self._load()
        thread_fb_count = sum(
            len(e.get("thread_feedback", [])) for e in data.values()
        )
        return {
            "total_messages": len(data),
            "thumbs_up": sum(
                1 for e in data.values()
                if e.get("reactions", {}).get("\U0001f44d", {}).get("count", 0) > 0
            ),
            "suppressed": sum(
                1 for e in data.values()
                if e.get("reactions", {}).get("\u274c", {}).get("count", 0) > 0
            ),
            "community_picks": sum(
                1 for e in data.values()
                if e.get("reactions", {}).get("\U0001f525", {}).get("count", 0) > 0
            ),
            "thread_feedback": thread_fb_count,
        }
