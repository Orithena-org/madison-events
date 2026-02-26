"""Scraper for UW-Madison Events (today.wisc.edu/events)."""
from __future__ import annotations

import logging
from datetime import date
from dateutil import parser as dateparser

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class UWMadisonScraper(BaseScraper):
    source_id = "uw_madison"
    source_name = "UW-Madison"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["uw_madison"]

        # UW-Madison today.wisc.edu provides an RSS/JSON feed
        # Try the events page first
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # today.wisc.edu uses li.event-row for each event listing
        event_elements = soup.select("li.event-row")

        # Fallback: broader search
        if not event_elements:
            event_elements = soup.select(
                ".event-listing, .event-card, .event-item, "
                "article[class*='event'], div[class*='event-row']"
            )

        for el in event_elements[:30]:
            try:
                event = self._parse_element(el, conf["base_url"])
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Failed to parse UW-Madison element: {e}")

        return events

    def _parse_element(self, el, base_url: str) -> Event | None:
        # Title
        title_el = el.select_one(
            "h2, h3, h4, .event-title, .title, .field-title"
        )
        if title_el:
            title = title_el.get_text(strip=True)
        elif el.name == "a":
            title = el.get_text(strip=True)
        else:
            title = el.get_text(strip=True)[:100]

        if not title or len(title) < 3:
            return None

        # URL
        link = el.select_one("a[href]")
        if el.name == "a":
            link = el
        url = ""
        if link and link.get("href"):
            href = link["href"]
            url = href if href.startswith("http") else base_url + href

        # Date
        date_el = el.select_one(
            "time, .date, .event-date, .field-date, "
            "span[class*='date'], div[class*='date']"
        )
        event_date = date.today()
        if date_el:
            date_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
            try:
                event_date = dateparser.parse(date_text).date()
            except (ValueError, TypeError):
                pass

        # Time — today.wisc.edu uses p.event-time with span.time-hm children
        time_el = el.select_one(".event-time")
        time_start = None
        if time_el:
            time_start = time_el.get_text(strip=True)

        # Venue — today.wisc.edu uses p.event-location
        venue_el = el.select_one(".event-location")
        venue = venue_el.get_text(strip=True) if venue_el else None

        # Description — UW event rows don't have description text in the listing,
        # so avoid the generic p fallback which grabs time/sponsor text
        desc_el = el.select_one(
            ".description, .excerpt, .summary, .field-body"
        )
        description = desc_el.get_text(strip=True) if desc_el else None

        # Image
        img_el = el.select_one("img")
        image_url = None
        if img_el and img_el.get("src"):
            src = img_el["src"]
            image_url = src if src.startswith("http") else base_url + src

        # Category
        cat_el = el.select_one(
            ".category, .event-type, .field-type, "
            "span[class*='category'], span[class*='type']"
        )
        category = cat_el.get_text(strip=True) if cat_el else None

        return Event(
            title=title,
            date=event_date,
            source=self.source_id,
            url=url,
            time_start=time_start,
            venue=venue,
            description=description,
            category=category,
            image_url=image_url,
        )
