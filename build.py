#!/usr/bin/env python3
"""Standalone site builder for Madison Events.

Reads output/data/events.json (written by the orithena-org content pipeline)
and renders the site using Jinja2 templates. No dependency on orithena-org.

Usage:
    python build.py
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from collections import OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "output" / "data" / "events.json"
TEMPLATES_DIR = ROOT / "website" / "templates"
STATIC_DIR = ROOT / "website" / "static"
SITE_DIR = ROOT / "_site"


class AttrDict(dict):
    """Dict subclass that supports attribute access (for Jinja2 templates)."""
    def __getattr__(self, key):
        try:
            val = self[key]
        except KeyError:
            return ""
        if isinstance(val, dict) and not isinstance(val, AttrDict):
            val = AttrDict(val)
            self[key] = val
        return val


def _wrap(d: dict) -> AttrDict:
    """Recursively wrap a dict for attribute access, converting date strings."""
    ad = AttrDict(d)
    # Convert date string to a real date object for strftime/isoformat in templates
    if "date" in ad and isinstance(ad["date"], str):
        try:
            ad["date"] = date.fromisoformat(ad["date"])
        except ValueError:
            pass
    return ad


def _load_data() -> dict:
    """Load the events data JSON."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _time_to_iso(time_str: str) -> str:
    """Convert human-readable time like '7:00 PM' to ISO 24h format like '19:00'."""
    if not time_str:
        return ""
    # Match patterns like "7:00 PM", "10:30 AM", "12:00 PM"
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', time_str.strip())
    if not m:
        return ""
    hour, minute, ampm = int(m.group(1)), m.group(2), m.group(3).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _group_events_by_date(events: list[AttrDict]) -> OrderedDict:
    grouped: dict[str, list[AttrDict]] = {}
    for event in sorted(events, key=lambda e: e["date"]):
        key = e["date"].isoformat() if isinstance((e := event)["date"], date) else str(e["date"])
        grouped.setdefault(key, []).append(event)
    return OrderedDict(sorted(grouped.items()))


def _generate_rss(events: list[AttrDict], site_title: str, site_url: str,
                  tagline: str) -> str:
    rss = Element("rss", version="2.0",
                  attrib={"xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = site_title
    SubElement(channel, "link").text = site_url
    SubElement(channel, "description").text = f"{tagline}. Updated daily."
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
        "%a, %d %b %Y %H:%M:%S +0000")

    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", f"{site_url}/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    sorted_events = sorted(events, key=lambda e: str(e["date"]), reverse=True)[:50]
    for event in sorted_events:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = event.title
        detail_link = f"{site_url}/{event.detail_url}"
        SubElement(item, "link").text = detail_link
        desc_parts = []
        if event.venue:
            desc_parts.append(f"@ {event.venue}")
        desc_parts.append(f"{event.date_display} {event.time_display}")
        if event.description:
            desc_parts.append(str(event.description)[:300])
        SubElement(item, "description").text = " | ".join(desc_parts)
        d = event["date"]
        if isinstance(d, date):
            SubElement(item, "pubDate").text = d.strftime("%a, %d %b %Y 00:00:00 +0000")
        if event.category:
            SubElement(item, "category").text = event.category
        guid = SubElement(item, "guid")
        guid.text = detail_link
        guid.set("isPermaLink", "true")

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        rss, encoding="unicode")


def _generate_sitemap(events: list[AttrDict], site_url: str,
                      category_slugs: list[str] | None = None) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    today = datetime.utcnow().date()
    urls = [
        (f"{site_url}/", "daily", "1.0"),
        (f"{site_url}/index.html", "daily", "0.9"),
    ]
    for slug in (category_slugs or []):
        urls.append((f"{site_url}/category/{slug}/", "daily", "0.8"))
    for event in events:
        d = event["date"]
        if isinstance(d, date):
            days_away = (d - today).days
        else:
            days_away = 0
        priority = "0.7" if days_away >= 0 else "0.4"
        freq = "daily" if days_away >= 0 else "weekly"
        urls.append((f"{site_url}/{event.detail_url}", freq, priority))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, freq, priority in urls:
        lines.extend([
            "  <url>",
            f"    <loc>{url}</loc>",
            f"    <lastmod>{now}</lastmod>",
            f"    <changefreq>{freq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ])
    lines.append("</urlset>")
    return "\n".join(lines)


def _ical_escape(text: str) -> str:
    """Escape text for iCalendar format (RFC 5545)."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _generate_ical(events: list[AttrDict], cal_name: str, site_url: str,
                   category: str | None = None) -> str:
    """Generate an iCalendar (.ics) feed from events.

    Args:
        events: List of event dicts.
        cal_name: Display name for the calendar.
        site_url: Base URL for event links.
        category: If set, filter to this category only.
    """
    if category:
        events = [e for e in events if e.category == category]

    # Only include future/today events
    today = date.today()
    events = [e for e in events if isinstance(e["date"], date) and e["date"] >= today]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//Madison Events//orithena//EN",
        f"X-WR-CALNAME:{_ical_escape(cal_name)}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for event in sorted(events, key=lambda e: e["date"]):
        d = event["date"]
        start_time = _time_to_iso(event.time_display.split(" - ")[0] if event.time_display else "")
        uid = f"{event.url_slug}@madison-events.orithena.org"

        lines.append("BEGIN:VEVENT")
        if start_time:
            dtstart = f"{d.strftime('%Y%m%d')}T{start_time.replace(':', '')}00"
            lines.append(f"DTSTART:{dtstart}")
            # Parse end time if available
            end_time = ""
            if event.time_display and " - " in event.time_display:
                end_time = _time_to_iso(event.time_display.split(" - ")[1])
            if end_time:
                dtend = f"{d.strftime('%Y%m%d')}T{end_time.replace(':', '')}00"
            else:
                # Default 2 hour duration
                h, m = start_time.split(":")
                end_h = int(h) + 2
                dtend = f"{d.strftime('%Y%m%d')}T{end_h:02d}{m}00"
            lines.append(f"DTEND:{dtend}")
        else:
            # All-day event
            lines.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
            next_day = d + timedelta(days=1)
            lines.append(f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}")

        lines.append(f"SUMMARY:{_ical_escape(event.title)}")
        lines.append(f"UID:{uid}")
        lines.append(f"URL:{site_url}/{event.detail_url}")

        if event.venue:
            lines.append(f"LOCATION:{_ical_escape(event.venue)}")
        if event.description:
            desc = str(event.description)[:500]
            lines.append(f"DESCRIPTION:{_ical_escape(desc)}")
        if event.category:
            lines.append(f"CATEGORIES:{_ical_escape(event.category)}")

        lines.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def build() -> None:
    """Build the Madison Events static site from JSON data."""
    data = _load_data()
    events = [_wrap(e) for e in data["events"]]
    editors_picks = [AttrDict({"event": _wrap(p["event"]), "commentary": p["commentary"]})
                     for p in data.get("editors_picks", [])]

    print(f"Building site from {len(events)} events...")

    # Prepare output directory
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True)

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["time_to_iso"] = _time_to_iso

    site_title = "Madison Events"
    site_url = "https://orithena-org.github.io/madison-events"
    tagline = "Your guide to everything happening in Madison, WI"
    goatcounter_site = "georgeauto"

    events_by_date = _group_events_by_date(events)
    categories = sorted(set(e.category for e in events if e.category))
    sources = {e.source: e.source_display for e in events if e.source}

    # Build category slug map for calendar URLs
    category_slugs_map = {
        cat: re.sub(r'[^a-z0-9]+', '-', cat.lower()).strip('-')
        for cat in categories
    }

    common_context = {
        "site_title": site_title,
        "site_tagline": tagline,
        "site_url": site_url,
        "categories": categories,
        "category_slugs": category_slugs_map,
        "sources": sources,
        "total_events": len(events),
        "current_year": datetime.now().year,
        "last_updated": datetime.now().strftime("%B %-d, %Y at %-I:%M %p"),
        "goatcounter_site": goatcounter_site,
    }

    # Sponsor tiers and ad slots for sponsors page
    sponsor_tiers = {
        "community": {
            "price": 50,
            "perks": [
                "Logo on website sidebar",
                "Mention in weekly newsletter",
                "Listed on sponsors page",
            ],
        },
        "featured": {
            "price": 150,
            "perks": [
                "Everything in Community",
                "Featured event placement",
                "Social media mentions",
                "Banner ad on homepage",
            ],
        },
        "premier": {
            "price": 500,
            "perks": [
                "Everything in Featured",
                "Dedicated newsletter section",
                "Custom event category page",
                "Priority event listing",
                "Monthly analytics report",
            ],
        },
    }

    ad_slots = {
        "sidebar": {"label": "Sidebar Banner", "width": 300, "height": 250},
        "newsletter_header": {"label": "Newsletter Header", "width": 600, "height": 100},
        "homepage_banner": {"label": "Homepage Banner", "width": 728, "height": 90},
    }

    # Render main templates
    template_renders = [
        ("landing.html", "landing.html", {"editors_picks": editors_picks}),
        ("index.html", "index.html", {"events_by_date": events_by_date}),
        ("newsletter_page.html", "newsletter.html", {"newsletter_preview": ""}),
        ("sponsors.html", "sponsors.html", {
            "sponsor_tiers": sponsor_tiers,
            "ad_slots": ad_slots,
        }),
    ]

    for tmpl_name, out_name, extra in template_renders:
        try:
            tmpl = env.get_template(tmpl_name)
        except TemplateNotFound:
            print(f"  Template {tmpl_name} not found, skipping")
            continue
        html = tmpl.render(**common_context, **extra)
        (SITE_DIR / out_name).write_text(html, encoding="utf-8")
        print(f"  Wrote {out_name}")

    # Event detail pages
    try:
        detail_tmpl = env.get_template("event_detail.html")
    except TemplateNotFound:
        detail_tmpl = None

    if detail_tmpl:
        events_dir = SITE_DIR / "events"
        events_dir.mkdir(exist_ok=True)
        for event in events:
            same_day = [e for e in events
                        if e["date"] == event["date"] and e.title != event.title][:4]
            event_dir = events_dir / event.url_slug
            event_dir.mkdir(parents=True, exist_ok=True)
            html = detail_tmpl.render(event=event, related_events=same_day,
                                      **common_context)
            (event_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  Built {len(events)} event detail pages")

    # Category landing pages
    try:
        cat_tmpl = env.get_template("category.html")
    except TemplateNotFound:
        cat_tmpl = None

    if cat_tmpl:
        cat_dir = SITE_DIR / "category"
        cat_dir.mkdir(exist_ok=True)
        for cat_name in categories:
            cat_slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
            cat_events = [e for e in events if e.category == cat_name]
            cat_events_by_date = _group_events_by_date(cat_events)
            page_dir = cat_dir / cat_slug
            page_dir.mkdir(exist_ok=True)
            html = cat_tmpl.render(
                category_name=cat_name,
                category_slug=cat_slug,
                events_by_date=cat_events_by_date,
                category_event_count=len(cat_events),
                **common_context,
            )
            (page_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  Built {len(categories)} category pages")

    # RSS
    rss_xml = _generate_rss(events, site_title, site_url, tagline)
    (SITE_DIR / "feed.xml").write_text(rss_xml, encoding="utf-8")

    # Sitemap (include category pages)
    category_slugs = [re.sub(r'[^a-z0-9]+', '-', c.lower()).strip('-') for c in categories]
    sitemap_xml = _generate_sitemap(events, site_url, category_slugs)
    (SITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    # robots.txt
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n",
        encoding="utf-8")

    # iCal subscription feeds
    cal_dir = SITE_DIR / "calendar"
    cal_dir.mkdir(exist_ok=True)

    # Main feed — all upcoming events
    main_ical = _generate_ical(events, "Madison Events", site_url)
    (cal_dir / "all.ics").write_text(main_ical, encoding="utf-8")

    # Per-category feeds
    ical_count = 1  # counting main feed
    for cat_name in categories:
        cat_slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
        cat_ical = _generate_ical(events, f"Madison Events — {cat_name}", site_url,
                                  category=cat_name)
        (cal_dir / f"{cat_slug}.ics").write_text(cat_ical, encoding="utf-8")
        ical_count += 1
    print(f"  Built {ical_count} iCal feeds")

    # Static assets
    if STATIC_DIR.exists():
        dest = SITE_DIR / "static"
        shutil.copytree(str(STATIC_DIR), str(dest))

    # .nojekyll
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Site build complete: {SITE_DIR} ({len(events)} events)")


if __name__ == "__main__":
    build()
