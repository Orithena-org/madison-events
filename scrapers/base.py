"""Base scraper class for Madison Events sources."""
from __future__ import annotations

import logging
import time
import requests
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT
from models import Event

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 3  # seconds


class BaseScraper(ABC):
    """Base class for all event scrapers."""

    source_id: str = ""
    source_name: str = ""

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as e:
                if attempt < MAX_RETRIES:
                    logger.warning(f"[{self.source_name}] Attempt {attempt} failed for {url}: {e}. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"[{self.source_name}] Failed to fetch {url} after {MAX_RETRIES} attempts: {e}")
                    return None

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Scrape events from this source. Returns list of Event objects."""
        ...

    def run(self) -> list[Event]:
        logger.info(f"[{self.source_name}] Starting scrape...")
        try:
            events = self.scrape()
            if not events:
                logger.warning(f"[{self.source_name}] Got 0 events, retrying once...")
                time.sleep(RETRY_DELAY)
                events = self.scrape()
            logger.info(f"[{self.source_name}] Found {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"[{self.source_name}] Scrape failed: {e}")
            return []
