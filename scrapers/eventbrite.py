"""Scraper for Eventbrite Madison events using JSON-LD structured data.

NOTE: Eventbrite is a React SPA that renders event data client-side.
This scraper only works if JSON-LD is present in the initial HTML response,
which is unreliable. A proper fix requires a headless browser (e.g. Playwright)
to render the page before scraping.
"""
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

    def _is_madison_event(self, data: dict) -> bool:
        """Check if an event is actually in or relevant to Madison, WI."""
        location = data.get("location")
        name = (data.get("name") or "").lower()

        # Events with Madison in the title are likely relevant
        if "madison" in name:
            return True

        if isinstance(location, dict):
            venue_name = (location.get("name") or "").lower()
            address = location.get("address")

            # Check venue name for Madison indicators
            if "madison" in venue_name or "wisconsin" in venue_name:
                return True

            if isinstance(address, dict):
                locality = (address.get("addressLocality") or "").lower()
                region = (address.get("addressRegion") or "").upper()
                # Accept Madison and nearby cities
                madison_area = {"madison", "sun prairie", "middleton", "fitchburg",
                                "verona", "monona", "mcfarland", "waunakee", "deforest",
                                "cottage grove", "stoughton", "oregon"}
                if locality in madison_area:
                    return True
                if region == "WI" and locality:
                    return True

            # Has a named venue (not just "Online") — likely local
            if venue_name and "online" not in venue_name and "virtual" not in venue_name:
                return True

        # No location info and no Madison reference — skip
        return False

    def _parse_jsonld(self, data: dict) -> Event | None:
        name = (data.get("name") or "").strip()
        if not name or len(name) < 3:
            return None

        # Filter out non-Madison events
        if not self._is_madison_event(data):
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
