#!/usr/bin/env python3
"""Standalone site builder for Madison Events.

Reads output/data/events.json (written by the orithena-org content pipeline)
and renders the site using Jinja2 templates. No dependency on orithena-org.

Usage:
    python build.py
"""
from __future__ import annotations

import json
import shutil
from collections import OrderedDict
from datetime import date, datetime
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


def _generate_sitemap(events: list[AttrDict], site_url: str) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    today = datetime.utcnow().date()
    urls = [
        (f"{site_url}/", "daily", "1.0"),
        (f"{site_url}/index.html", "daily", "0.9"),
    ]
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

    site_title = "Madison Events"
    site_url = ""
    tagline = "Your guide to everything happening in Madison, WI"
    goatcounter_site = "georgeauto"

    events_by_date = _group_events_by_date(events)
    categories = sorted(set(e.category for e in events if e.category))
    sources = {e.source: e.source_display for e in events if e.source}

    common_context = {
        "site_title": site_title,
        "site_tagline": tagline,
        "site_url": site_url,
        "categories": categories,
        "sources": sources,
        "total_events": len(events),
        "current_year": datetime.now().year,
        "last_updated": datetime.now().strftime("%B %-d, %Y at %-I:%M %p"),
        "goatcounter_site": goatcounter_site,
    }

    # Render main templates
    template_renders = [
        ("landing.html", "landing.html", {"editors_picks": editors_picks}),
        ("index.html", "index.html", {"events_by_date": events_by_date}),
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

    # RSS
    rss_xml = _generate_rss(events, site_title, site_url, tagline)
    (SITE_DIR / "feed.xml").write_text(rss_xml, encoding="utf-8")

    # Sitemap
    sitemap_xml = _generate_sitemap(events, site_url)
    (SITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    # robots.txt
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n",
        encoding="utf-8")

    # Static assets
    if STATIC_DIR.exists():
        dest = SITE_DIR / "static"
        shutil.copytree(str(STATIC_DIR), str(dest))

    # .nojekyll
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Site build complete: {SITE_DIR} ({len(events)} events)")


if __name__ == "__main__":
    build()
