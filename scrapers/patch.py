"""Scraper for Patch.com Madison events (patch.com/wisconsin/madison-wi/calendar)."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PatchScraper(BaseScraper):
    source_id = "patch"
    source_name = "Patch.com"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["patch"]
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # Patch.com embeds all event data in __NEXT_DATA__ JSON
        script = soup.select_one("script#__NEXT_DATA__")
        if not script or not script.string:
            logger.warning("[Patch.com] No __NEXT_DATA__ found")
            return events

        try:
            data = json.loads(script.string)
        except json.JSONDecodeError as e:
            logger.error(f"[Patch.com] Failed to parse JSON: {e}")
            return events

        # Events are in props.pageProps.mainContent.allEvents
        # keyed by Unix timestamp, each containing a list of events
        try:
            all_events = data["props"]["pageProps"]["mainContent"]["allEvents"]
        except (KeyError, TypeError):
            logger.warning("[Patch.com] Could not find allEvents in JSON")
            return events

        for timestamp, event_list in all_events.items():
            if not isinstance(event_list, list):
                continue
            for evt in event_list:
                try:
                    event = self._parse_event(evt, conf["base_url"])
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.debug(f"Failed to parse Patch event: {e}")

        return events[:30]

    def _parse_event(self, evt: dict, base_url: str) -> Event | None:
        title = evt.get("title", "").strip()
        if not title or len(title) < 3:
            return None

        # Date from displayDate (ISO format: 2026-02-28T00:00:00.000Z)
        event_date = date.today()
        display_date = evt.get("displayDate", "")
        if display_date:
            try:
                event_date = datetime.fromisoformat(
                    display_date.replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                pass

        # URL from canonicalUrl or itemAlias
        url = evt.get("canonicalUrl", "")
        if not url:
            alias = evt.get("itemAlias", "")
            if alias:
                url = f"https://patch.com{alias}"
        if url and not url.startswith("http"):
            url = f"https://patch.com{url}"

        # Venue from address
        venue = None
        address = evt.get("address")
        if isinstance(address, dict):
            venue = address.get("name", "").strip() or None

        # Description from summary
        description = evt.get("summary", "").strip() or None

        # Image
        image_url = None
        images = evt.get("images", [])
        if isinstance(images, list) and images:
            image_url = images[0].get("url") if isinstance(images[0], dict) else None
        if not image_url:
            image_url = evt.get("ogImageUrl")

        # Price hint from eventType
        price = None
        event_type = evt.get("eventType", "")
        if event_type == "free":
            price = "Free"

        return Event(
            title=title,
            date=event_date,
            source=self.source_id,
            url=url,
            venue=venue,
            description=description,
            image_url=image_url,
            price=price,
        )
