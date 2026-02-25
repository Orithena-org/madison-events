"""Base scraper class for Madison Events sources."""
from __future__ import annotations

import logging
import requests
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT
from models import Event

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all event scrapers."""

    source_id: str = ""
    source_name: str = ""

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Scrape events from this source. Returns list of Event objects."""
        ...

    def run(self) -> list[Event]:
        logger.info(f"[{self.source_name}] Starting scrape...")
        try:
            events = self.scrape()
            logger.info(f"[{self.source_name}] Found {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"[{self.source_name}] Scrape failed: {e}")
            return []
