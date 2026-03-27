#!/usr/bin/env python3
"""Notify search engines about sitemap updates and submit URLs via IndexNow.

Run after each site deploy to tell Google, Bing, and Yandex about new/updated content.

Usage:
    python scripts/notify_search_engines.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
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


def main() -> int:
    print("Notifying search engines...")
    errors = 0
    errors += submit_indexnow()
    if errors:
        print(f"Done with {errors} error(s)")
    else:
        print("Done — all notifications sent successfully")
    return 0  # Don't fail the pipeline over notification errors


if __name__ == "__main__":
    sys.exit(main())
