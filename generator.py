import os
import json
import logging
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a historian and writer in the style of Dan Jones. Your writing is clear,
grounded, and vivid without being dramatic. You focus on concrete human details, specific numbers,
dates, and the texture of daily life. You avoid purple prose, sweeping generalizations, and
breathless superlatives.

Good: "On 15 March 44 BC, Julius Caesar walked to the Theatre of Pompey for a Senate meeting.
He had been warned."

Bad: "In a moment that would echo through the ages, the fate of the Roman world hung in the
balance."

You always return valid JSON and nothing else."""


def generate_events(date: datetime) -> list[dict]:
    """Call Claude to generate historical events for the given date. Returns a list of event dicts."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    day = date.day
    month = date.strftime("%B")
    date_label = f"{month} {day}"

    user_prompt = f"""Today is {date_label}. Generate a historical digest for this date.

Search for notable historical events that occurred on {date_label} (any year) across these regions:
- Ancient Rome
- Ancient Greece
- Europe (Classical Era through the Fall of the Soviet Union)
- United States

Pick the 2 most interesting and significant events across all regions combined. Quality over quantity — only include events that are genuinely compelling.

Return a JSON object with this exact structure:
{{
  "events": [
    {{
      "region": "Ancient Rome",
      "title": "Short, punchy title — do not include the year in the title",
      "year": "44 BC",
      "teaser": "One sentence. Concrete, specific. Slightly surprising or human in scale.",
      "body": "3 to 5 paragraphs of narrative. Dan Jones style. No bullet points, no headers — actual paragraphs separated by double newlines. Focus on human-scale details, real names, real numbers, real places. Give enough context that someone unfamiliar with the period can follow it without it becoming a lecture.",
      "wikipedia_url": "https://en.wikipedia.org/wiki/REAL_ARTICLE_TITLE",
      "wikimedia_search_query": "3-4 keywords describing the visual you would want — e.g. 'Roman Senate ancient fresco' or 'medieval castle siege painting'"
    }}
  ]
}}

Strict date rules — read carefully:
- The event must have occurred ON {date_label} exactly. Do not include events that happened the day before, the day after, or "around" this date.
- For multi-day events (battles, sieges, trials, conferences): only include the event if {date_label} is the day it BEGAN. Do not cover it on subsequent days.
- If you cannot find 2 events that strictly match {date_label}, return fewer rather than stretching the date. Do NOT fabricate.
- Wikipedia URLs must be real, well-known articles — not stubs or obscure pages.
- wikimedia_search_query should describe a photograph, painting, or illustration — not a map or diagram.

Return only the JSON object. No markdown fences, no commentary."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude adds them anyway
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.error(f"Raw response:\n{raw}")
        raise

    events = data.get("events", [])
    logger.info(f"Generated {len(events)} events for {date_label}")
    for event in events:
        logger.info(f"  [{event.get('region', '?')}] {event.get('title', '?')} ({event.get('year', '?')})")

    return events
