"""Static site builder for Madison Events."""
from __future__ import annotations

import shutil
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from jinja2 import Environment, FileSystemLoader

from config import (
    SITE_TITLE, SITE_TAGLINE, SITE_URL, OUTPUT_DIR, SOURCES,
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


def generate_rss(events: list[Event]) -> str:
    """Generate an RSS 2.0 feed from events."""
    rss = Element("rss", version="2.0", attrib={"xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = SITE_TITLE
    SubElement(channel, "link").text = SITE_URL
    SubElement(channel, "description").text = f"{SITE_TAGLINE}. Updated daily."
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", f"{SITE_URL}/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for event in sorted(events, key=lambda e: e.date, reverse=True)[:50]:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = event.title
        SubElement(item, "link").text = event.display_url or SITE_URL
        desc_parts = []
        if event.venue:
            desc_parts.append(f"@ {event.venue}")
        desc_parts.append(f"{event.date_display} {event.time_display}")
        if event.description:
            desc_parts.append(event.description[:300])
        SubElement(item, "description").text = " | ".join(desc_parts)
        SubElement(item, "pubDate").text = event.date.strftime("%a, %d %b %Y 00:00:00 +0000")
        if event.category:
            SubElement(item, "category").text = event.category
        guid = SubElement(item, "guid")
        guid.text = event.display_url or f"{SITE_URL}/#event-{hash(event.title)}"
        guid.set("isPermaLink", "true" if event.url else "false")

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")


def generate_sitemap(events: list[Event]) -> str:
    """Generate a sitemap.xml."""
    now = datetime.utcnow().strftime("%Y-%m-%d")
    urls = [
        (f"{SITE_URL}/", "daily", "1.0"),
        (f"{SITE_URL}/newsletter.html", "weekly", "0.8"),
        (f"{SITE_URL}/sponsors.html", "monthly", "0.5"),
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url, freq, priority in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{url}</loc>")
        lines.append(f"    <lastmod>{now}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def generate_robots_txt() -> str:
    """Generate robots.txt."""
    return f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
"""


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
        "site_url": SITE_URL,
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

    # Generate RSS feed
    rss_xml = generate_rss(events)
    (SITE_OUTPUT / "feed.xml").write_text(rss_xml)
    logger.info("Built feed.xml (RSS)")

    # Generate sitemap
    sitemap_xml = generate_sitemap(events)
    (SITE_OUTPUT / "sitemap.xml").write_text(sitemap_xml)
    logger.info("Built sitemap.xml")

    # Generate robots.txt
    robots = generate_robots_txt()
    (SITE_OUTPUT / "robots.txt").write_text(robots)
    logger.info("Built robots.txt")

    # Copy static assets
    static_output = SITE_OUTPUT / "static"
    if static_output.exists():
        shutil.rmtree(static_output)
    shutil.copytree(str(STATIC_DIR), str(static_output))
    logger.info("Copied static assets")

    logger.info(f"Site built at: {SITE_OUTPUT}")
    return SITE_OUTPUT
