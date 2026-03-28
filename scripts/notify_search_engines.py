#!/usr/bin/env python3
"""Notify search engines about sitemap updates and submit URLs via IndexNow.

Run after each site deploy to tell Google, Bing, and Yandex about new/updated content.

Usage:
    python scripts/notify_search_engines.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

SITE_DIR = Path(__file__).parent.parent / "_site"
SITE_URL = "https://orithena-org.github.io/madison-events"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"

# Note: Google and Bing deprecated their sitemap ping endpoints (404/410).
# Google discovers sitemaps via robots.txt and Search Console.
# Bing uses IndexNow for instant URL submission.
INDEXNOW_API = "https://api.indexnow.org/indexnow"


def submit_indexnow() -> int:
    """Submit URLs to IndexNow for instant indexing on Bing/Yandex."""
    indexnow_file = SITE_DIR / "indexnow-urls.json"
    if not indexnow_file.exists():
        print("  [indexnow] No indexnow-urls.json found, skipping")
        return 0

    data = json.loads(indexnow_file.read_text())
    url_count = len(data.get("urlList", []))
    if url_count == 0:
        print("  [indexnow] No URLs to submit")
        return 0

    # IndexNow API accepts up to 10,000 URLs per request
    payload = json.dumps(data).encode("utf-8")
    try:
        req = urllib.request.Request(
            INDEXNOW_API,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  [indexnow] Submitted {url_count} URLs: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        # 202 = accepted, 200 = OK — both are success
        if e.code in (200, 202):
            print(f"  [indexnow] Submitted {url_count} URLs: HTTP {e.code}")
        else:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"  [indexnow] Submission failed: HTTP {e.code} — {body}")
            return 1
    except Exception as e:
        print(f"  [indexnow] Submission failed: {e}")
        return 1
    return 0


def submit_pingomatic() -> int:
    """Ping Ping-o-Matic to notify 20+ aggregators about feed updates."""
    rss_url = f"{SITE_URL}/feed.xml"
    body = ET.tostring(
        ET.fromstring(
            '<?xml version="1.0"?>'
            "<methodCall>"
            "<methodName>weblogUpdates.ping</methodName>"
            "<params>"
            f"<param><value>Madison Events - Local Event Guide</value></param>"
            f"<param><value>{SITE_URL}</value></param>"
            f"<param><value>{SITE_URL}</value></param>"
            f"<param><value>{rss_url}</value></param>"
            "</params>"
            "</methodCall>"
        ),
        encoding="unicode",
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            "http://rpc.pingomatic.com/RPC2",
            data=body,
            headers={"Content-Type": "text/xml"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode("utf-8", errors="replace")
            if "flerror" in result and "<boolean>0</boolean>" in result:
                print("  [pingomatic] Ping successful — notified 20+ aggregators")
            elif "too awesome" in result.lower():
                print("  [pingomatic] Rate-limited (already pinged recently)")
            else:
                print(f"  [pingomatic] Ping sent, response: {result[:200]}")
    except Exception as e:
        print(f"  [pingomatic] Ping failed: {e}")
        return 1
    return 0


def submit_websub() -> int:
    """Notify WebSub hub that the RSS feed has been updated."""
    feed_url = f"{SITE_URL}/feed.xml"
    data = urllib.parse.urlencode({
        "hub.mode": "publish",
        "hub.url": feed_url,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  [websub] Published feed update: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        if e.code == 204:
            print("  [websub] Published feed update: HTTP 204")
        else:
            print(f"  [websub] Publish failed: HTTP {e.code}")
            return 1
    except Exception as e:
        print(f"  [websub] Publish failed: {e}")
        return 1
    return 0


def main() -> int:
    print("Notifying search engines...")
    errors = 0
    errors += submit_indexnow()
    errors += submit_pingomatic()
    errors += submit_websub()
    if errors:
        print(f"Done with {errors} error(s)")
    else:
        print("Done — all notifications sent successfully")
    return 0  # Don't fail the pipeline over notification errors


if __name__ == "__main__":
    sys.exit(main())
