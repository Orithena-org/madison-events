"""Scraper for Overture Center (overture.org/events)."""
from __future__ import annotations

import logging
from datetime import date
from dateutil import parser as dateparser

from config import SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)


class OvertureScraper(BaseScraper):
    source_id = "overture"
    source_name = "Overture Center"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES["overture"]
        soup = self.fetch_page(conf["events_url"])
        if not soup:
            return events

        # Overture Center uses event cards/listings
        event_elements = soup.select(
            ".event-card, .event-listing, .event-item, "
            ".performance-card, .show-card, article, "
            "div[class*='event'], div[class*='performance'], "
            "li[class*='event']"
        )

        # Fallback: links to event pages
        if not event_elements:
            event_elements = soup.select(
                "a[href*='/events/'], a[href*='/event/'], a[href*='/show']"
            )

        for el in event_elements[:30]:
            try:
                event = self._parse_element(el, conf["base_url"])
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Failed to parse Overture element: {e}")

        return events

    def _parse_element(self, el, base_url: str) -> Event | None:
        # Title
        title_el = el.select_one(
            "h2, h3, h4, .event-title, .title, .show-title, "
            ".performance-title"
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
            "time, .date, .event-date, .performance-date, "
            "span[class*='date']"
        )
        event_date = date.today()
        if date_el:
            date_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
            try:
                event_date = dateparser.parse(date_text).date()
            except (ValueError, TypeError):
                pass

        # Time
        time_el = el.select_one(".time, .event-time, span[class*='time']")
        time_start = time_el.get_text(strip=True) if time_el else None

        # Venue - default to Overture Center since most events are there
        venue_el = el.select_one(
            ".venue, .location, span[class*='venue'], "
            "span[class*='location'], .hall"
        )
        venue = venue_el.get_text(strip=True) if venue_el else "Overture Center"

        # Description
        desc_el = el.select_one(".description, .excerpt, .summary, p")
        description = desc_el.get_text(strip=True) if desc_el else None

        # Image
        img_el = el.select_one("img")
        image_url = None
        if img_el and img_el.get("src"):
            src = img_el["src"]
            image_url = src if src.startswith("http") else base_url + src

        # Price
        price_el = el.select_one(
            ".price, .ticket-price, span[class*='price']"
        )
        price = price_el.get_text(strip=True) if price_el else None

        return Event(
            title=title,
            date=event_date,
            source=self.source_id,
            url=url,
            time_start=time_start,
            venue=venue,
            description=description,
            price=price,
            image_url=image_url,
            category="Arts & Entertainment",
        )
