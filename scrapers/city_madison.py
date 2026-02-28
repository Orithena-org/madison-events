"""Scraper for City of Madison events (cityofmadison.com/events)."""
from __future__ import annotations

import logging
from datetime import date, datetime
from dateutil import parser as dateparser

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CityMadisonScraper(BaseScraper):
    source_id = "city_madison"
    source_name = "City of Madison"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["city_madison"]
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # City of Madison uses a Drupal views list with .view-content > ol > li
        event_items = soup.select(".view-content ol.list--items > li")

        if not event_items:
            # Fallback: try broader selectors
            event_items = soup.select(".view-content li")

        for el in event_items[:30]:
            try:
                event = self._parse_element(el, conf["base_url"])
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Failed to parse City of Madison element: {e}")

        return events

    def _parse_element(self, el, base_url: str) -> Event | None:
        # Title from .event-heading > a
        heading = el.select_one(".event-heading a")
        if not heading:
            heading = el.select_one("a[href]")
        if not heading:
            return None

        title = heading.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # URL
        href = heading.get("href", "")
        url = href if href.startswith("http") else base_url + href

        # Date from <time class="start-date" datetime="2026-02-28 10:00">
        event_date = date.today()
        time_start = None

        time_el = el.select_one("time.start-date")
        if time_el:
            dt_str = time_el.get("datetime", "")
            if dt_str:
                try:
                    dt = dateparser.parse(dt_str)
                    event_date = dt.date()
                    # Extract time if present (format: "2026-02-28 10:00")
                    if " " in dt_str and ":" in dt_str:
                        time_start = dt.strftime("%-I:%M %p")
                except (ValueError, TypeError):
                    pass

            # Fallback: parse from span.month + span.day
            if event_date == date.today() and not dt_str:
                month_el = time_el.select_one(".month")
                day_el = time_el.select_one(".day")
                if month_el and day_el:
                    try:
                        month_text = month_el.get_text(strip=True)
                        day_text = day_el.get_text(strip=True)
                        dt = dateparser.parse(f"{month_text} {day_text}")
                        event_date = dt.date()
                    except (ValueError, TypeError):
                        pass

        # Venue from .event-venue
        venue = None
        venue_el = el.select_one(".event-venue strong")
        if venue_el:
            venue = venue_el.get_text(strip=True)
        elif el.select_one(".event-venue"):
            venue = el.select_one(".event-venue").get_text(strip=True)

        # Category from URL path (e.g., /parks/events/... -> Parks)
        category = None
        if href:
            parts = href.strip("/").split("/")
            if len(parts) >= 2 and parts[1] == "events":
                cat_map = {
                    "parks": "Parks & Recreation",
                    "senior-center": "Community",
                    "library": "Education",
                    "arts-commission": "Arts & Entertainment",
                    "engineering": "Community",
                    "streets": "Community",
                }
                category = cat_map.get(parts[0], "Community")

        return Event(
            title=title,
            date=event_date,
            source=self.source_id,
            url=url,
            time_start=time_start,
            venue=venue,
            category=category,
        )
