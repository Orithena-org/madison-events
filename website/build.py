"""Static site builder for Madison Events."""
from __future__ import annotations

import shutil
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import (
    SITE_TITLE, SITE_TAGLINE, OUTPUT_DIR, SOURCES,
    AD_SLOTS, SPONSOR_TIERS,
)
from models import Event
from curator import select_editors_picks

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
SITE_OUTPUT = OUTPUT_DIR / "site"


def group_events_by_date(events: list[Event]) -> OrderedDict:
    """Group events by date string, sorted chronologically."""
    grouped = {}
    for event in sorted(events, key=lambda e: e.date):
        key = event.date.isoformat()
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(event)
    return OrderedDict(sorted(grouped.items()))


def build_site(events: list[Event], newsletter_html: str = "") -> Path:
    """Build the full static site from events data."""
    logger.info(f"Building site with {len(events)} events...")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    events_by_date = group_events_by_date(events)
    sources = {sid: s["name"] for sid, s in SOURCES.items()}
    current_year = datetime.now().year
    editors_picks = select_editors_picks(events, count=5)

    common_context = {
        "site_title": SITE_TITLE,
        "site_tagline": SITE_TAGLINE,
        "sources": sources,
        "total_events": len(events),
        "current_year": current_year,
        "last_updated": datetime.now().strftime("%B %-d, %Y at %-I:%M %p"),
    }

    # Build landing page (main entry point)
    landing_tmpl = env.get_template("landing.html")
    landing_html = landing_tmpl.render(
        editors_picks=editors_picks,
        **common_context,
    )
    (SITE_OUTPUT / "landing.html").write_text(landing_html)
    logger.info("Built landing.html")

    # Build index page (full events listing)
    index_tmpl = env.get_template("index.html")
    index_html = index_tmpl.render(
        events_by_date=events_by_date,
        **common_context,
    )
    (SITE_OUTPUT / "index.html").write_text(index_html)
    logger.info("Built index.html")

    # Build sponsors page
    sponsors_tmpl = env.get_template("sponsors.html")
    sponsors_html = sponsors_tmpl.render(
        ad_slots=AD_SLOTS,
        sponsor_tiers=SPONSOR_TIERS,
        **common_context,
    )
    (SITE_OUTPUT / "sponsors.html").write_text(sponsors_html)
    logger.info("Built sponsors.html")

    # Build newsletter page
    newsletter_tmpl = env.get_template("newsletter_page.html")
    newsletter_page_html = newsletter_tmpl.render(
        newsletter_preview=newsletter_html,
        **common_context,
    )
    (SITE_OUTPUT / "newsletter.html").write_text(newsletter_page_html)
    logger.info("Built newsletter.html")

    # Copy static assets
    static_output = SITE_OUTPUT / "static"
    if static_output.exists():
        shutil.rmtree(static_output)
    shutil.copytree(str(STATIC_DIR), str(static_output))
    logger.info("Copied static assets")

    logger.info(f"Site built at: {SITE_OUTPUT}")
    return SITE_OUTPUT
