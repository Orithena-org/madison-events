"""Scraper for Visit Madison tourism events (visitmadison.com RSS feed).

Fetches the RSS feed for event listings, then hits each detail page to
extract venue name from JSON-LD structured data.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT, SOURCES
from models import Event
from .base import BaseScraper

logger = logging.getLogger(__name__)

# Map Visit Madison categories to our categories
CATEGORY_MAP = {
    "food & drink": "Food & Drink",
    "local libations": "Food & Drink",
    "entertainment & nightlife": "Nightlife",
    "music & concerts": "Music",
    "music": "Music",
    "theater & performing arts": "Arts",
    "performing arts": "Arts",
    "arts & culture": "Arts",
    "gallery & exhibitions": "Arts",
    "visual arts": "Arts",
    "education & lectures": "Education",
    "sports & recreation": "Sports",
    "nature & outdoors": "Outdoors",
    "outdoor recreation": "Outdoors",
    "tours & walks": "Outdoors",
    "health & wellness": "Health & Wellness",
    "general & community events": "Community",
    "kids & families": "Family",
    "family friendly": "Family",
    "festivals & fairs": "Festivals",
    "holiday": "Holidays",
    "shopping": "Shopping",
    "trivia": "Nightlife",
}

# Map JSON-LD @type to our categories (fallback when RSS tags miss)
JSONLD_TYPE_MAP = {
    "FoodEvent": "Food & Drink",
    "SocialEvent": "Community",
    "MusicEvent": "Music",
    "SportsEvent": "Sports",
    "EducationEvent": "Education",
    "DanceEvent": "Arts",
    "TheaterEvent": "Arts",
    "ScreeningEvent": "Arts & Entertainment",
    "Festival": "Festivals",
}


class VisitMadisonScraper(BaseScraper):
    source_id = "visitmadison"
    source_name = "Visit Madison"

    def scrape(self) -> list[Event]:
        events = []
        conf = SOURCES.get("visitmadison", {})
        url = conf.get("rss_url", "https://www.visitmadison.com/event/rss/")

        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[Visit Madison] Failed to fetch RSS: {e}")
            return events

        feed = feedparser.parse(resp.text)

        if not feed.entries:
            logger.warning("[Visit Madison] No entries in RSS feed")
            return events

        today = date.today()
        for entry in feed.entries:
            try:
                event = self._parse_entry(entry, today)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Failed to parse Visit Madison entry: {e}")

        # Enrich events with venue data from detail pages
        self._enrich_from_detail_pages(events)

        return events[:30]

    def _parse_entry(self, entry, today: date) -> Event | None:
        title = entry.get("title", "").strip()
        if not title or len(title) < 3:
            return None

        url = entry.get("link", "")
        if not url:
            return None

        # Parse date from pubDate (RFC 2822 format)
        event_date = today
        pub_date = entry.get("published", "")
        if pub_date:
            try:
                event_date = parsedate_to_datetime(pub_date).date()
            except (ValueError, TypeError):
                pass

        # Skip past events
        if event_date < today:
            return None

        # Extract categories
        categories = []
        for tag in entry.get("tags", []):
            term = tag.get("term", "").strip()
            if term:
                categories.append(term)

        # Map to our category system
        category = self._map_category(categories)

        # Check if free
        price = None
        if any("free" in c.lower().replace("&amp;", "&") for c in categories):
            price = "Free"

        # Parse description — extract image and text
        description_html = entry.get("summary", "") or entry.get("description", "")
        image_url = None
        description = None

        if description_html:
            soup = BeautifulSoup(description_html, "lxml")

            # Extract image
            img = soup.find("img")
            if img and img.get("src"):
                image_url = img["src"]

            # Extract text (strip HTML tags)
            text = soup.get_text(separator=" ").strip()
            # Remove date ranges like "02/05/2026 to 05/21/2026 -"
            text = re.sub(r'\d{2}/\d{2}/\d{4}\s+to\s+\d{2}/\d{2}/\d{4}\s*-?\s*', '', text).strip()
            if text and len(text) > 10:
                description = text[:500]

        return Event(
            title=title,
            date=event_date,
            source=self.source_id,
            url=url,
            description=description,
            image_url=image_url,
            category=category,
            price=price,
        )

    def _enrich_from_detail_pages(self, events: list[Event]) -> None:
        """Fetch each event's detail page to extract venue from JSON-LD."""
        enriched = 0
        for event in events:
            if not event.url:
                continue
            try:
                resp = requests.get(
                    event.url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                ld = self._extract_jsonld(resp.text)
                if not ld:
                    continue

                # Venue from location.name
                location = ld.get("location", {})
                if isinstance(location, dict):
                    venue_name = location.get("name", "").strip()
                    if venue_name:
                        event.venue = venue_name

                # Use JSON-LD @type as category fallback
                if not event.category:
                    ld_type = ld.get("@type", "")
                    if ld_type in JSONLD_TYPE_MAP:
                        event.category = JSONLD_TYPE_MAP[ld_type]

                enriched += 1
                time.sleep(0.2)  # polite delay between requests
            except Exception as e:
                logger.debug(f"[Visit Madison] Failed to enrich {event.title}: {e}")

        logger.info(f"[Visit Madison] Enriched {enriched}/{len(events)} events from detail pages")

    def _extract_jsonld(self, html: str) -> dict | None:
        """Extract first Event JSON-LD block from page HTML."""
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@context"):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _map_category(self, categories: list[str]) -> str | None:
        for cat in categories:
            # feedparser may leave &amp; as-is; normalize to &
            key = cat.lower().strip().replace("&amp;", "&")
            if key in CATEGORY_MAP:
                return CATEGORY_MAP[key]
        return None
