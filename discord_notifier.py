import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

REGION_ORDER = [
    "Ancient Rome",
    "Ancient Greece",
    "Europe",
    "United States",
]

# Discord message character limit
DISCORD_MAX_CHARS = 2000


def post_digest(date: datetime, events: list[dict], doc_url: str) -> None:
    """Post a summary of today's events to Discord via webhook."""
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]

    day = date.day
    month = date.strftime("%B")
    year = date.year
    date_str = f"{month} {day}, {year}"

    # Group events by region
    by_region: dict[str, list[dict]] = {}
    for event in events:
        region = event.get("region", "")
        by_region.setdefault(region, []).append(event)

    lines: list[str] = [f"**On This Day — {date_str}**\n"]

    for region in REGION_ORDER:
        region_events = by_region.get(region, [])
        if not region_events:
            continue

        lines.append(f"**{region}**")
        for event in region_events:
            title = event.get("title", "")
            year_str = event.get("year", "")
            teaser = event.get("teaser", "")
            lines.append(f"• **{title}** ({year_str}) — {teaser}")
        lines.append("")  # blank line between regions

    lines.append(f"[Read the full digest →]({doc_url})")

    content = "\n".join(lines)

    # Truncate if somehow we blow the Discord limit (shouldn't happen for ~10 events)
    if len(content) > DISCORD_MAX_CHARS:
        cutoff = content.rfind("\n", 0, DISCORD_MAX_CHARS - 60)
        content = content[:cutoff] + f"\n\n[Read the full digest →]({doc_url})"

    resp = requests.post(webhook_url, json={"content": content}, timeout=10)
    resp.raise_for_status()
    logger.info("Posted digest to Discord")
