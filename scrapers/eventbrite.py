"""Scraper for Eventbrite Madison events using JSON-LD structured data."""
from __future__ import annotations

import json
import logging
from datetime import date
from dateutil import parser as dateparser

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class EventbriteScraper(BaseScraper):
    source_id = "eventbrite"
    source_name = "Eventbrite"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["eventbrite"]
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # Eventbrite embeds an ItemList JSON-LD with all events
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(data, dict):
                continue

            # The ItemList contains ListItem entries wrapping Event objects
            if data.get("@type") == "ItemList":
                for list_item in data.get("itemListElement", []):
                    item = list_item.get("item", {})
                    if item.get("@type") != "Event":
                        continue
                    try:
                        event = self._parse_jsonld(item)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.debug(f"Failed to parse Eventbrite event: {e}")

        return events[:30]

    def _parse_jsonld(self, data: dict) -> Event | None:
        name = (data.get("name") or "").strip()
        if not name or len(name) < 3:
            return None

        url = data.get("url", "")

        # Parse date
        event_date = date.today()
        start_str = data.get("startDate", "")
        if start_str:
            try:
                event_date = dateparser.parse(start_str).date()
            except (ValueError, TypeError):
                pass

        # Location / venue
        venue = None
        location = data.get("location")
        if isinstance(location, dict):
            venue = location.get("name")

        # Description
        description = (data.get("description") or "").strip() or None

        # Image
        image_url = data.get("image") or None

        return Event(
            title=name,
            date=event_date,
            source=self.source_id,
            url=url,
            venue=venue,
            description=description,
            image_url=image_url,
        )
