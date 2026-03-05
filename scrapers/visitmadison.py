"""Scraper for Visit Madison tourism events (visitmadison.com RSS feed)."""
from __future__ import annotations

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

    def _map_category(self, categories: list[str]) -> str | None:
        for cat in categories:
            # feedparser may leave &amp; as-is; normalize to &
            key = cat.lower().strip().replace("&amp;", "&")
            if key in CATEGORY_MAP:
                return CATEGORY_MAP[key]
        return None
