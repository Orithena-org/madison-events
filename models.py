"""Data models for Madison Events Aggregator."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional
import json


@dataclass
class Event:
    title: str
    date: date
    source: str  # isthmus, overture, uw_madison
    url: str
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[str] = None
    is_featured: bool = False
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        d = d.copy()
        d["date"] = date.fromisoformat(d["date"])
        return cls(**d)

    @property
    def display_url(self) -> str:
        """URL with affiliate tracking appended where applicable."""
        from config import EVENTBRITE_AFFILIATE_ID
        if not self.url:
            return ""
        if EVENTBRITE_AFFILIATE_ID and "eventbrite.com" in self.url:
            sep = "&" if "?" in self.url else "?"
            return f"{self.url}{sep}aff={EVENTBRITE_AFFILIATE_ID}"
        return self.url

    @property
    def date_display(self) -> str:
        return self.date.strftime("%A, %B %-d, %Y")

    @property
    def time_display(self) -> str:
        if not self.time_start:
            return "Time TBA"
        if self.time_end:
            return f"{self.time_start} - {self.time_end}"
        return self.time_start

    @property
    def source_display(self) -> str:
        names = {
            "isthmus": "Isthmus",
            "eventbrite": "Eventbrite",
            "uw_madison": "UW-Madison",
        }
        return names.get(self.source, self.source)


def save_events(events: list[Event], filepath: str) -> None:
    with open(filepath, "w") as f:
        json.dump([e.to_dict() for e in events], f, indent=2)


def load_events(filepath: str) -> list[Event]:
    with open(filepath) as f:
        return [Event.from_dict(d) for d in json.load(f)]
