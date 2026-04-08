#!/usr/bin/env python3
"""Standalone site builder for msndo.

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
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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


MADISON_TZ = ZoneInfo("America/Chicago")


def _tz_offset(event_date: date) -> str:
    """Return the UTC offset string for Madison, WI on a given date (e.g. '-05:00' or '-06:00')."""
    dt = datetime(event_date.year, event_date.month, event_date.day, 12, tzinfo=MADISON_TZ)
    offset = dt.utcoffset()
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _group_events_by_date(events: list[AttrDict]) -> OrderedDict:
    grouped: dict[str, list[AttrDict]] = {}
    for event in sorted(events, key=lambda e: e["date"]):
        key = e["date"].isoformat() if isinstance((e := event)["date"], date) else str(e["date"])
        grouped.setdefault(key, []).append(event)
    return OrderedDict(sorted(grouped.items()))


def _generate_rss(events: list[AttrDict], site_title: str, site_url: str,
                  tagline: str, feed_path: str = "feed.xml",
                  category: str | None = None) -> str:
    if category:
        events = [e for e in events if e.get("category") == category]
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
    atom_link.set("href", f"{site_url}/{feed_path}")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # WebSub hub for real-time push notifications to subscribers
    hub_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    hub_link.set("href", "https://pubsubhubbub.appspot.com/")
    hub_link.set("rel", "hub")

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
                      category_slugs: list[str] | None = None,
                      temporal_slugs: list[str] | None = None) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    today = datetime.utcnow().date()
    urls = [
        (f"{site_url}/", "daily", "1.0"),
        (f"{site_url}/index.html", "daily", "0.9"),
        (f"{site_url}/search/", "daily", "0.7"),
        (f"{site_url}/embed.html", "monthly", "0.5"),
    ]
    # Temporal pages get high priority — they target high-intent search queries
    for slug in (temporal_slugs or []):
        urls.append((f"{site_url}/{slug}/", "daily", "0.9"))
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
    today = datetime.now(MADISON_TZ).date()
    events = [e for e in events if isinstance(e["date"], date) and e["date"] >= today]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//msndo//orithena//EN",
        f"X-WR-CALNAME:{_ical_escape(cal_name)}",
        "X-WR-TIMEZONE:America/Chicago",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for event in sorted(events, key=lambda e: e["date"]):
        d = event["date"]
        start_time = _time_to_iso(event.time_display.split(" - ")[0] if event.time_display else "")
        uid = f"{event.url_slug}@msndo.com"

        lines.append("BEGIN:VEVENT")
        if start_time:
            dtstart = f"{d.strftime('%Y%m%d')}T{start_time.replace(':', '')}00"
            lines.append(f"DTSTART;TZID=America/Chicago:{dtstart}")
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
            lines.append(f"DTEND;TZID=America/Chicago:{dtend}")
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
    """Build the msndo static site from JSON data."""
    data = _load_data()
    all_events = [_wrap(e) for e in data["events"]]
    editors_picks = [AttrDict({"event": _wrap(p["event"]), "commentary": p["commentary"]})
                     for p in data.get("editors_picks", [])]

    # Split into upcoming (today or future) and all events.
    # Listings/feeds show only upcoming; detail pages exist for all (preserving URLs).
    today = date.today()
    events = [e for e in all_events
              if isinstance(e["date"], date) and e["date"] >= today]
    past_count = len(all_events) - len(events)
    print(f"Building site from {len(events)} upcoming events ({past_count} past events excluded from listings)...")

    # Prepare output directory
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True)

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["time_to_iso"] = _time_to_iso
    env.filters["tz_offset"] = _tz_offset

    site_title = "msndo"
    site_url = "https://msndo.com"
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
        ("embed.html", "embed.html", {}),
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

    # Search page (in /search/ directory for SearchAction schema)
    try:
        search_tmpl = env.get_template("search.html")
        search_dir = SITE_DIR / "search"
        search_dir.mkdir(exist_ok=True)
        html = search_tmpl.render(**common_context)
        (search_dir / "index.html").write_text(html, encoding="utf-8")
        print("  Wrote search/index.html")
    except TemplateNotFound:
        pass

    # Copy events data for client-side search and embed widget
    data_dir = SITE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    shutil.copy2(str(DATA_FILE), str(data_dir / "events.json"))
    print("  Copied events.json to data/")

    # Event detail pages
    try:
        detail_tmpl = env.get_template("event_detail.html")
    except TemplateNotFound:
        detail_tmpl = None

    if detail_tmpl:
        events_dir = SITE_DIR / "events"
        events_dir.mkdir(exist_ok=True)
        for event in all_events:
            same_day = [e for e in events
                        if e["date"] == event["date"] and e.title != event.title][:4]
            event_dir = events_dir / event.url_slug
            event_dir.mkdir(parents=True, exist_ok=True)
            html = detail_tmpl.render(event=event, related_events=same_day,
                                      **common_context)
            (event_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  Built {len(all_events)} event detail pages ({past_count} past)")

    # Category landing pages
    try:
        cat_tmpl = env.get_template("category.html")
    except TemplateNotFound:
        cat_tmpl = None

    if cat_tmpl:
        # SEO-optimized descriptions per category
        category_seo = {
            "Music": "Live music in Madison, WI — concerts, jazz, open mics, and performances at The Sylvee, Majestic Theatre, High Noon Saloon, and more.",
            "Arts & Entertainment": "Arts and entertainment in Madison, WI — gallery openings, theater, film screenings, and cultural events happening this week.",
            "Food & Drink": "Food and drink events in Madison, WI — tastings, cooking classes, food festivals, and restaurant specials from local venues.",
            "Comedy": "Comedy shows in Madison, WI — stand-up, improv, and open mic nights at Comedy on State and local venues.",
            "Community": "Community events in Madison, WI — meetups, volunteer opportunities, markets, and neighborhood gatherings.",
            "Education": "Educational events in Madison, WI — workshops, lectures, classes, and learning opportunities at UW-Madison and beyond.",
            "Sports": "Sports events in Madison, WI — Badgers games, recreational leagues, and spectator sports happening this week.",
            "Outdoors": "Outdoor events in Madison, WI — hiking, biking, nature walks, and outdoor activities around the lakes and trails.",
            "Wellness": "Wellness events in Madison, WI — yoga, meditation, fitness classes, and health workshops.",
            "Parks & Recreation": "Parks and recreation events in Madison, WI — activities at city parks, community centers, and recreation facilities.",
            "Festival": "Festivals in Madison, WI — music festivals, street fairs, cultural celebrations, and seasonal events.",
        }

        cat_dir = SITE_DIR / "category"
        cat_dir.mkdir(exist_ok=True)
        for cat_name in categories:
            cat_slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
            cat_events = [e for e in events if e.category == cat_name]
            cat_events_by_date = _group_events_by_date(cat_events)
            page_dir = cat_dir / cat_slug
            page_dir.mkdir(exist_ok=True)

            seo_desc = category_seo.get(cat_name, "")

            html = cat_tmpl.render(
                category_name=cat_name,
                category_slug=cat_slug,
                events_by_date=cat_events_by_date,
                category_event_count=len(cat_events),
                category_seo_description=seo_desc,
                **common_context,
            )
            (page_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  Built {len(categories)} category pages")

    # Temporal landing pages (this-week, this-weekend, today, free-events)
    try:
        temporal_tmpl = env.get_template("temporal.html")
    except TemplateNotFound:
        temporal_tmpl = None

    temporal_slugs: list[str] = []
    if temporal_tmpl:
        today = datetime.now(MADISON_TZ).date()
        # Calculate date ranges
        weekday = today.weekday()  # Monday=0 ... Sunday=6
        week_end = today + timedelta(days=(6 - weekday))  # end of this week (Sunday)
        # Weekend: Saturday-Sunday of this week (or today if already weekend)
        if weekday < 5:  # Mon-Fri
            saturday = today + timedelta(days=(5 - weekday))
        else:
            saturday = today  # Already Sat or Sun
        sunday = saturday + timedelta(days=(6 - saturday.weekday()))

        def _events_in_range(start: date, end: date) -> list[AttrDict]:
            return [e for e in events
                    if isinstance(e["date"], date) and start <= e["date"] <= end]

        def _free_events() -> list[AttrDict]:
            future = [e for e in events
                      if isinstance(e["date"], date) and e["date"] >= today]
            return [e for e in future
                    if e.price and any(kw in str(e.price).lower()
                                       for kw in ("free", "$0", "no cost", "no charge"))]

        temporal_pages = [
            {
                "slug": "today",
                "page_title": f"Things to Do in Madison Today — {today.strftime('%A, %B %-d')}",
                "page_heading": f"Things to Do in Madison Today",
                "meta_description": f"What's happening in Madison, WI today ({today.strftime('%A, %B %-d, %Y')}). Live music, food events, arts, comedy, and more — updated daily.",
                "date_range_display": today.strftime("%A, %B %-d, %Y"),
                "events_fn": lambda: _events_in_range(today, today),
            },
            {
                "slug": "this-week",
                "page_title": f"msndo — This Week — {today.strftime('%b %-d')} to {week_end.strftime('%b %-d')}",
                "page_heading": "Things to Do in Madison This Week",
                "meta_description": f"Discover {today.strftime('%b %-d')}–{week_end.strftime('%b %-d')} events in Madison, WI. Concerts, festivals, food events, free activities, and more from {len(sources)} local sources.",
                "date_range_display": f"{today.strftime('%A, %B %-d')} — {week_end.strftime('%A, %B %-d, %Y')}",
                "events_fn": lambda: _events_in_range(today, week_end),
            },
            {
                "slug": "this-weekend",
                "page_title": f"msndo — This Weekend — {saturday.strftime('%b %-d')}–{sunday.strftime('%-d')}",
                "page_heading": "Things to Do in Madison This Weekend",
                "meta_description": f"Weekend events in Madison, WI ({saturday.strftime('%b %-d')}–{sunday.strftime('%-d')}). Find live music, food, art, comedy, and free activities happening this Saturday and Sunday.",
                "date_range_display": f"{saturday.strftime('%A, %B %-d')} — {sunday.strftime('%A, %B %-d, %Y')}",
                "events_fn": lambda: _events_in_range(saturday, sunday),
            },
            {
                "slug": "free-events",
                "page_title": "Free Events in Madison, WI — No Cost Activities & Things to Do",
                "page_heading": "Free Events in Madison",
                "meta_description": "Free things to do in Madison, Wisconsin. Concerts, festivals, art shows, outdoor activities, and community events that cost nothing. Updated daily.",
                "date_range_display": f"Upcoming free events from {today.strftime('%B %-d, %Y')}",
                "events_fn": _free_events,
            },
        ]

        all_temporal_links = [
            {"slug": "today", "label": "Today's Events"},
            {"slug": "this-week", "label": "This Week"},
            {"slug": "this-weekend", "label": "This Weekend"},
            {"slug": "free-events", "label": "Free Events"},
        ]

        for page in temporal_pages:
            page_events = page["events_fn"]()
            page_events_by_date = _group_events_by_date(page_events)
            page_dir = SITE_DIR / page["slug"]
            page_dir.mkdir(exist_ok=True)

            # Category counts for this time slice
            cat_counts = {}
            for e in page_events:
                if e.category:
                    cat_counts[e.category] = cat_counts.get(e.category, 0) + 1

            related = [lnk for lnk in all_temporal_links if lnk["slug"] != page["slug"]]

            html = temporal_tmpl.render(
                page_slug=page["slug"],
                page_title=page["page_title"],
                page_heading=page["page_heading"],
                meta_description=page["meta_description"],
                date_range_display=page["date_range_display"],
                event_count=len(page_events),
                events_by_date=page_events_by_date,
                categories_with_counts=cat_counts,
                related_pages=related,
                **common_context,
            )
            (page_dir / "index.html").write_text(html, encoding="utf-8")
            temporal_slugs.append(page["slug"])

        print(f"  Built {len(temporal_pages)} temporal landing pages")

    # Weekly highlights page
    try:
        highlights_tmpl = env.get_template("highlights.html")
    except TemplateNotFound:
        highlights_tmpl = None

    if highlights_tmpl:
        today = today if 'today' in dir() else datetime.now(MADISON_TZ).date()
        weekday = today.weekday()
        week_end = today + timedelta(days=(6 - weekday))
        week_events = [e for e in events
                       if isinstance(e["date"], date) and today <= e["date"] <= week_end]

        # "More worth checking out": this week's events not in editor's picks
        pick_slugs = {p.event.url_slug for p in editors_picks}
        more_events = [e for e in week_events if e.url_slug not in pick_slugs]
        # Diversify by category — pick up to 10, spread across categories
        seen_cats: dict[str, int] = {}
        diverse_more: list[AttrDict] = []
        for e in sorted(more_events, key=lambda x: str(x["date"])):
            cat = e.category or "Other"
            if seen_cats.get(cat, 0) < 2:
                diverse_more.append(e)
                seen_cats[cat] = seen_cats.get(cat, 0) + 1
                if len(diverse_more) >= 10:
                    break

        highlights_dir = SITE_DIR / "highlights"
        highlights_dir.mkdir(exist_ok=True)
        html = highlights_tmpl.render(
            page_title=f"Madison Event Highlights — {today.strftime('%b %-d')} to {week_end.strftime('%b %-d')}",
            page_heading="This Week's Highlights",
            meta_description=f"The best events in Madison, WI this week ({today.strftime('%b %-d')}–{week_end.strftime('%b %-d')}). Editor's picks, live music, food, arts, and more.",
            date_range_display=f"{today.strftime('%A, %B %-d')} — {week_end.strftime('%A, %B %-d, %Y')}",
            editors_picks=editors_picks,
            more_events=diverse_more,
            total_this_week=len(week_events),
            **common_context,
        )
        (highlights_dir / "index.html").write_text(html, encoding="utf-8")
        temporal_slugs.append("highlights")
        print("  Built highlights page")

    # RSS — main feed
    rss_xml = _generate_rss(events, site_title, site_url, tagline)
    (SITE_DIR / "feed.xml").write_text(rss_xml, encoding="utf-8")

    # RSS — per-category feeds
    feed_dir = SITE_DIR / "feed"
    feed_dir.mkdir(exist_ok=True)
    rss_count = 1  # counting main feed
    for cat_name in categories:
        cat_slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
        feed_path = f"feed/{cat_slug}.xml"
        cat_rss = _generate_rss(events, f"{site_title} — {cat_name}",
                                site_url, tagline, feed_path=feed_path,
                                category=cat_name)
        (SITE_DIR / feed_path).write_text(cat_rss, encoding="utf-8")
        rss_count += 1
    print(f"  Built {rss_count} RSS feeds")

    # Sitemap (include category + temporal pages; all events for detail page URLs)
    category_slugs = [re.sub(r'[^a-z0-9]+', '-', c.lower()).strip('-') for c in categories]
    sitemap_xml = _generate_sitemap(all_events, site_url, category_slugs, temporal_slugs)
    (SITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    # robots.txt
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n",
        encoding="utf-8")

    # iCal subscription feeds
    cal_dir = SITE_DIR / "calendar"
    cal_dir.mkdir(exist_ok=True)

    # Main feed — all upcoming events
    main_ical = _generate_ical(events, "msndo", site_url)
    (cal_dir / "all.ics").write_text(main_ical, encoding="utf-8")

    # Per-category feeds
    ical_count = 1  # counting main feed
    for cat_name in categories:
        cat_slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
        cat_ical = _generate_ical(events, f"msndo — {cat_name}", site_url,
                                  category=cat_name)
        (cal_dir / f"{cat_slug}.ics").write_text(cat_ical, encoding="utf-8")
        ical_count += 1
    print(f"  Built {ical_count} iCal feeds")

    # Static assets
    if STATIC_DIR.exists():
        dest = SITE_DIR / "static"
        shutil.copytree(str(STATIC_DIR), str(dest))

    # IndexNow key file for Bing/Yandex instant indexing
    indexnow_key = "6846b3e2fc5b4a778c9b994e0ec146e9"
    (SITE_DIR / f"{indexnow_key}.txt").write_text(indexnow_key, encoding="utf-8")

    # Generate IndexNow URL list for submission
    indexnow_urls = [f"{site_url}/"]
    indexnow_urls.append(f"{site_url}/index.html")
    for slug in temporal_slugs:
        indexnow_urls.append(f"{site_url}/{slug}/")
    for slug in category_slugs:
        indexnow_urls.append(f"{site_url}/category/{slug}/")
    # Include upcoming event detail pages
    today_date = datetime.now(MADISON_TZ).date()
    for event in events:
        if isinstance(event["date"], date) and event["date"] >= today_date:
            indexnow_urls.append(f"{site_url}/{event.detail_url}")
    from urllib.parse import urlparse
    indexnow_data = {
        "host": urlparse(site_url).hostname,
        "key": indexnow_key,
        "keyLocation": f"{site_url}/{indexnow_key}.txt",
        "urlList": indexnow_urls,
    }
    (SITE_DIR / "indexnow-urls.json").write_text(
        json.dumps(indexnow_data, indent=2), encoding="utf-8")
    print(f"  Prepared {len(indexnow_urls)} URLs for IndexNow submission")

    # Copy curated content from output/site/ into _site/
    # These are generated by agent-01 tools (picks page, iCal feed) and committed
    # separately from the build.py-generated content.
    curated_dir = ROOT / "output" / "site"
    curated_subdirs = ["feeds", "picks"]
    curated_count = 0
    for subdir in curated_subdirs:
        src_dir = curated_dir / subdir
        if src_dir.exists():
            dest_dir = SITE_DIR / subdir
            dest_dir.mkdir(parents=True, exist_ok=True)
            for src in src_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(src_dir)
                    dest = dest_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dest))
                    curated_count += 1
    if curated_count:
        print(f"  Copied {curated_count} curated files from output/site/")

    # .nojekyll
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Site build complete: {SITE_DIR} ({len(events)} events)")


if __name__ == "__main__":
    build()
