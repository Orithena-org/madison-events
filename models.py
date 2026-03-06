"""Data models for Madison Events Aggregator."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional
import json
import re
import hashlib


@dataclass
class Event:
    title: str
    date: date
    source: str  # isthmus, overture, uw_madison, city_madison, patch
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
    def slug(self) -> str:
        """Generate a URL-safe slug from title and date."""
        text = re.sub(r'[^\w\s-]', '', self.title.lower())
        text = re.sub(r'[\s_]+', '-', text).strip('-')
        text = re.sub(r'-+', '-', text)
        # Truncate long slugs and add date for uniqueness
        text = text[:60].rstrip('-')
        date_str = self.date.isoformat()
        # Add short hash for uniqueness when titles collide
        unique = hashlib.md5(f"{self.title}{date_str}{self.venue or ''}".encode()).hexdigest()[:6]
        return f"{text}-{date_str}-{unique}"

    @property
    def detail_url(self) -> str:
        """URL path to this event's detail page on our site."""
        return f"events/{self.slug}/"

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
            "city_madison": "City of Madison",
            "patch": "Patch.com",
            "visitmadison": "Visit Madison",
        }
        return names.get(self.source, self.source)


def save_events(events: list[Event], filepath: str) -> None:
    with open(filepath, "w") as f:
        json.dump([e.to_dict() for e in events], f, indent=2)


def load_events(filepath: str) -> list[Event]:
    with open(filepath) as f:
        return [Event.from_dict(d) for d in json.load(f)]
