import logging
import requests

logger = logging.getLogger(__name__)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}

# Wikimedia requires a descriptive User-Agent — edit the contact address if you fork this
HEADERS = {
    "User-Agent": "OnThisDayDigest/1.0 (https://github.com/; history-digest-bot)"
}


def find_image_url(query: str) -> str | None:
    """
    Search Wikimedia Commons for an image matching the query.
    Returns a direct HTTPS URL to the image file, or None if nothing suitable is found.
    """
    try:
        search_resp = requests.get(
            COMMONS_API,
            headers=HEADERS,
            params={
                "action": "query",
                "list": "search",
                "srnamespace": 6,  # File namespace only
                "srsearch": query,
                "format": "json",
                "srlimit": 8,
            },
            timeout=10,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("query", {}).get("search", [])

        if not results:
            logger.warning(f"No Wikimedia results for query: {query!r}")
            return None

        for result in results:
            page_title = result["title"]  # e.g. "File:Julius Caesar.jpg"
            url = _get_image_url(page_title)
            if url:
                logger.info(f"Found image for {query!r}: {url}")
                return url

        logger.warning(f"No suitable images found for query: {query!r}")
        return None

    except requests.RequestException as e:
        logger.error(f"Wikimedia API error for {query!r}: {e}")
        return None


def _get_image_url(page_title: str) -> str | None:
    """Fetch the direct file URL for a Wikimedia Commons file page."""
    try:
        resp = requests.get(
            COMMONS_API,
            headers=HEADERS,
            params={
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "titles": page_title,
                "format": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})

        for page in pages.values():
            for info in page.get("imageinfo", []):
                mime = info.get("mime", "")
                url = info.get("url", "")
                size = info.get("size", 0)

                if mime not in ALLOWED_MIME_TYPES:
                    continue
                # Skip absurdly large files (> 25 MB) — Google Docs will reject them
                if size > 25_000_000:
                    continue
                if url.startswith("https://"):
                    return url

        return None

    except requests.RequestException as e:
        logger.error(f"Wikimedia imageinfo error for {page_title!r}: {e}")
        return None
