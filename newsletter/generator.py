"""Newsletter content generator for Madison Events.

Generates curated weekly newsletters with Editor's Picks,
weekend highlights, and categorized event listings.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path

from config import OUTPUT_DIR, SITE_URL, SITE_TITLE, SPONSOR_TIERS
from models import Event
from curator import select_editors_picks, select_weekend_picks

logger = logging.getLogger(__name__)


def generate_newsletter_html(events: list[Event]) -> str:
    """Generate a weekly newsletter email in HTML format with curated picks."""
    today = date.today()
    week_start = today
    week_end = today + timedelta(days=6)

    # Filter to this week's events
    week_events = [
        e for e in events
        if week_start <= e.date <= week_end
    ]
    week_events.sort(key=lambda e: (e.date, e.time_start or ""))

    # Get curated picks
    editors_picks = select_editors_picks(events, count=5)
    weekend_picks = select_weekend_picks(events, count=3)

    # Group remaining by category
    by_category = {}
    pick_titles = {p["event"].title for p in editors_picks}
    for event in week_events:
        if event.title in pick_titles:
            continue  # Don't repeat picks in category listings
        cat = event.category or "Other Events"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(event)

    week_start_str = week_start.strftime("%B %-d")
    week_end_str = week_end.strftime("%-d, %Y")

    html = f"""
<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a2e;">
    <!-- Header -->
    <div style="background:#1a1a2e;color:white;padding:24px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:24px;">{SITE_TITLE}</h1>
        <p style="margin:8px 0 0;color:#aaa;font-size:14px;">Your Weekly Guide to Madison</p>
        <p style="margin:4px 0 0;color:#ccc;font-size:16px;">{week_start_str} - {week_end_str}</p>
    </div>

    <!-- Sponsor banner -->
    <div style="background:#f8f8f8;padding:12px;text-align:center;border:1px solid #e0e0e0;border-top:none;">
        <p style="margin:0;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1px;">Presented by Our Sponsors</p>
        <p style="margin:4px 0 0;font-size:13px;color:#666;">
            <a href="{SITE_URL}/sponsors.html" style="color:#c41e3a;">Become a sponsor</a> and reach Madison's event-goers
        </p>
    </div>

    <!-- Intro -->
    <div style="padding:20px 24px;border:1px solid #e0e0e0;border-top:none;">
        <p style="font-size:15px;line-height:1.6;color:#333;">
            Happy {today.strftime('%A')}! We dug through <strong>{len(week_events)} events</strong>
            happening in Madison this week and picked the ones actually worth your time.
            Here's what made the cut.
        </p>
    </div>
"""

    # Editor's Picks section
    if editors_picks:
        html += """
    <!-- Editor's Picks -->
    <div style="padding:20px 24px;border:1px solid #e0e0e0;border-top:none;">
        <h2 style="font-size:18px;color:#c41e3a;border-bottom:2px solid #c41e3a;padding-bottom:8px;margin-bottom:16px;">
            Editor's Picks
        </h2>
"""
        for i, pick in enumerate(editors_picks):
            event = pick["event"]
            commentary = pick["commentary"]
            html += f"""
        <div style="padding:14px 0;border-bottom:1px solid #f0f0f0;">
            <h3 style="margin:0;font-size:16px;">
                <a href="{event.url}" style="color:#1a1a2e;text-decoration:none;">{event.title}</a>
            </h3>
            <p style="margin:4px 0 0;font-size:13px;color:#666;">
                {event.date_display} {('at ' + event.time_start) if event.time_start else ''}
                {(' | ' + event.venue) if event.venue else ''}
                {(' | ' + event.price) if event.price else ''}
            </p>
            <p style="margin:6px 0 0;font-size:14px;color:#444;font-style:italic;">
                {commentary}
            </p>
            {('<p style="margin:6px 0 0;font-size:13px;color:#888;">' + event.description[:120] + '...</p>') if event.description and len(event.description) > 10 else ''}
        </div>
"""
        html += "    </div>\n"

    # Mid-newsletter sponsor slot
    html += f"""
    <!-- Mid-newsletter sponsor slot -->
    <div style="background:#fff8f8;padding:16px 24px;text-align:center;border:1px solid #e0e0e0;border-top:none;">
        <p style="margin:0;font-size:11px;color:#999;text-transform:uppercase;">Sponsored</p>
        <p style="margin:8px 0;font-size:15px;color:#333;">Your business could be here!</p>
        <a href="{SITE_URL}/sponsors.html" style="color:#c41e3a;font-size:13px;">Learn about newsletter sponsorship</a>
    </div>
"""

    # Weekend picks
    if weekend_picks:
        html += """
    <!-- Weekend Picks -->
    <div style="padding:20px 24px;border:1px solid #e0e0e0;border-top:none;">
        <h2 style="font-size:18px;color:#333;margin-bottom:12px;">Weekend Picks</h2>
"""
        for pick in weekend_picks:
            event = pick["event"]
            commentary = pick["commentary"]
            html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #f5f5f5;">
            <strong style="font-size:14px;">{event.title}</strong>
            <span style="font-size:12px;color:#888;"> - {event.date.strftime('%A')}</span>
            {('<span style="font-size:12px;color:#888;"> @ ' + event.venue + '</span>') if event.venue else ''}
            <p style="margin:4px 0 0;font-size:13px;color:#666;font-style:italic;">{commentary}</p>
        </div>
"""
        html += "    </div>\n"

    # Events by category
    for category, cat_events in by_category.items():
        html += f"""
    <div style="padding:16px 24px;border:1px solid #e0e0e0;border-top:none;">
        <h2 style="font-size:16px;color:#333;margin-bottom:12px;">{category}</h2>
"""
        for event in cat_events[:6]:
            source_colors = {
                "isthmus": "#e74c3c",
                "eventbrite": "#3498db",
                "uw_madison": "#c5050c",
            }
            dot_color = source_colors.get(event.source, "#999")
            html += f"""
        <div style="padding:8px 0;border-bottom:1px solid #f5f5f5;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:6px;"></span>
            <strong style="font-size:14px;">{event.title}</strong>
            <span style="font-size:12px;color:#888;"> - {event.date.strftime('%a %b %-d')}</span>
            {('<span style="font-size:12px;color:#888;"> @ ' + event.venue + '</span>') if event.venue else ''}
        </div>
"""
        if len(cat_events) > 6:
            html += f"""
        <p style="font-size:13px;color:#c41e3a;margin-top:8px;">
            +{len(cat_events) - 6} more {category.lower()} events on the website
        </p>
"""
        html += "    </div>\n"

    # Footer
    html += f"""
    <!-- CTA -->
    <div style="padding:24px;text-align:center;border:1px solid #e0e0e0;border-top:none;">
        <a href="{SITE_URL}" style="display:inline-block;padding:12px 32px;background:#c41e3a;color:white;text-decoration:none;border-radius:6px;font-weight:600;font-size:15px;">
            See All {len(week_events)} Events
        </a>
    </div>

    <!-- Footer -->
    <div style="background:#1a1a2e;color:#aaa;padding:20px 24px;text-align:center;border-radius:0 0 8px 8px;font-size:12px;">
        <p style="margin:0;">&copy; {today.year} {SITE_TITLE} | Built by Orithena</p>
        <p style="margin:8px 0 0;">
            <a href="#" style="color:#aaa;">Unsubscribe</a> |
            <a href="{SITE_URL}" style="color:#aaa;">View Online</a> |
            <a href="{SITE_URL}/sponsors.html" style="color:#aaa;">Advertise</a>
        </p>
        <p style="margin:8px 0 0;color:#666;">
            Events sourced from Isthmus, Eventbrite, and UW-Madison
        </p>
    </div>
</div>
"""
    return html


def generate_newsletter_plain(events: list[Event]) -> str:
    """Generate a plain-text version of the newsletter."""
    today = date.today()
    week_end = today + timedelta(days=6)

    week_events = [
        e for e in events
        if today <= e.date <= week_end
    ]
    week_events.sort(key=lambda e: (e.date, e.time_start or ""))

    editors_picks = select_editors_picks(events, count=5)

    lines = [
        f"{SITE_TITLE} - Your Weekly Guide to Madison",
        f"{today.strftime('%B %-d')} - {week_end.strftime('%B %-d, %Y')}",
        "=" * 50,
        "",
        f"We dug through {len(week_events)} events this week. Here's what made the cut.",
        "",
    ]

    if editors_picks:
        lines.append("EDITOR'S PICKS")
        lines.append("-" * 30)
        for pick in editors_picks:
            event = pick["event"]
            commentary = pick["commentary"]
            lines.append(f"\n* {event.title}")
            lines.append(f"  {event.date_display} {event.time_display}")
            if event.venue:
                lines.append(f"  @ {event.venue}")
            if event.price:
                lines.append(f"  {event.price}")
            lines.append(f"  >> {commentary}")
            if event.url:
                lines.append(f"  {event.url}")

    lines.append("")
    lines.append("MORE THIS WEEK")
    lines.append("-" * 30)

    pick_titles = {p["event"].title for p in editors_picks}
    remaining = [e for e in week_events if e.title not in pick_titles]

    for event in remaining[:10]:
        lines.append(f"\n* {event.title}")
        lines.append(f"  {event.date_display} {event.time_display}")
        if event.venue:
            lines.append(f"  @ {event.venue}")
        if event.url:
            lines.append(f"  {event.url}")

    if len(remaining) > 10:
        lines.append(f"\n...and {len(remaining) - 10} more events!")

    lines.extend([
        "",
        f"See all events: {SITE_URL}",
        "",
        "-" * 50,
        f"(c) {today.year} {SITE_TITLE} | Built by Orithena",
        "Unsubscribe: reply with UNSUBSCRIBE",
    ])

    return "\n".join(lines)


def save_newsletter(events: list[Event]) -> Path:
    """Generate and save newsletter content."""
    html = generate_newsletter_html(events)
    plain = generate_newsletter_plain(events)

    output_dir = OUTPUT_DIR / "newsletter"
    html_file = output_dir / "newsletter.html"
    plain_file = output_dir / "newsletter.txt"

    html_file.write_text(html)
    plain_file.write_text(plain)

    logger.info(f"Saved newsletter to {output_dir}")
    return output_dir
