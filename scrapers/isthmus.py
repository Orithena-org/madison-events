"""Scraper for Isthmus (isthmus.com/events)."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from dateutil import parser as dateparser

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class IsthmusScraper(BaseScraper):
    source_id = "isthmus"
    source_name = "Isthmus"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["isthmus"]
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # Isthmus uses various event listing structures.
        # Look for event cards/articles in the events page.
        event_elements = soup.select(
            "article.event, .event-card, .listing-item, "
            ".event-listing, .tribe-events-calendar-list__event-row, "
            "div[class*='event'], article[class*='event']"
        )

        # Fallback: look for links that appear to be event detail pages
        if not event_elements:
            event_elements = soup.select("a[href*='/events/']")

        for el in event_elements[:30]:  # Cap at 30
            try:
                event = self._parse_element(el, conf["base_url"])
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Failed to parse Isthmus element: {e}")

        return events

    def _parse_element(self, el, base_url: str) -> Event | None:
        # Try to extract title
        title_el = el.select_one("h2, h3, h4, .event-title, .title")
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
            "time, .event-date, .date, span[class*='date'], "
            "div[class*='date']"
        )
        event_date = date.today()
        if date_el:
            date_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
            try:
                event_date = dateparser.parse(date_text).date()
            except (ValueError, TypeError):
                pass

        # Time
        time_el = el.select_one(".event-time, .time, span[class*='time']")
        time_start = None
        if time_el:
            time_start = time_el.get_text(strip=True)

        # Venue
        venue_el = el.select_one(
            ".event-venue, .venue, .location, span[class*='venue'], "
            "span[class*='location']"
        )
        venue = venue_el.get_text(strip=True) if venue_el else None

        # Description
        desc_el = el.select_one(".event-description, .description, .excerpt, p")
        description = desc_el.get_text(strip=True) if desc_el else None

        # Image
        img_el = el.select_one("img")
        image_url = None
        if img_el and img_el.get("src"):
            src = img_el["src"]
            image_url = src if src.startswith("http") else base_url + src

        # Category
        cat_el = el.select_one(
            ".category, .event-category, span[class*='category']"
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
