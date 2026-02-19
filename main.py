"""
On This Day — daily history digest
===================================
Orchestrates the full pipeline:
  1. Generate historical events for today via the Anthropic API
  2. Fetch a Wikimedia Commons image for each event
  3. Create a formatted Google Doc with all content
  4. Post a summary to Discord
"""

import logging
import sys
from datetime import datetime

from dotenv import load_dotenv

from discord_notifier import post_digest
from generator import generate_events
from google_drive import create_daily_doc
from wikimedia import find_image_url

# Load .env for local development — no-op in GitHub Actions (secrets are env vars)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    date = datetime.utcnow()
    logger.info(f"Starting digest for {date.strftime('%B %d, %Y')} UTC")

    # Step 1: Generate events
    events = generate_events(date)
    if not events:
        logger.warning("Claude returned no events for today. Nothing to publish.")
        return

    # Step 2: Attach a Wikimedia image URL to each event
    for event in events:
        query = event.get("wikimedia_search_query", "").strip()
        event["image_url"] = find_image_url(query) if query else None

    # Step 3: Create the Google Doc
    doc_url = create_daily_doc(date, events)
    logger.info(f"Document ready: {doc_url}")

    # Step 4: Post to Discord
    post_digest(date, events, doc_url)

    logger.info("Digest complete.")


if __name__ == "__main__":
    main()
