import logging
import os
from datetime import datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

REGION_ORDER = [
    "Ancient Rome",
    "Ancient Greece",
    "Europe",
    "United States",
]

# ── Colour palette ────────────────────────────────────────────────────────────
COLOR_H1    = {"red": 0.10, "green": 0.21, "blue": 0.42}  # deep navy
COLOR_H2    = {"red": 0.38, "green": 0.12, "blue": 0.12}  # dark burgundy
COLOR_LINK  = {"red": 0.13, "green": 0.40, "blue": 0.67}  # steel blue

# ── Image display size (points) ───────────────────────────────────────────────
IMAGE_WIDTH_PT  = 430
IMAGE_HEIGHT_PT = 260


def _get_services():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(GoogleRequest())
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return docs, drive


def create_daily_doc(date: datetime, events: list[dict]) -> str:
    """
    Create a Google Doc containing the daily digest and return its shareable URL.

    The document is built in four phases:
      1. Assemble the full text and record where formatting + images should go.
      2. Insert all text into the doc in one batchUpdate.
      3. Apply paragraph and text styles in batched batchUpdates.
      4. Insert images one at a time, working backwards through the document
         so that each insertion does not shift the indices of remaining images.
    """
    docs_service, drive_service = _get_services()

    day = date.day
    month = date.strftime("%B")
    year = date.year
    date_str = f"{month} {day}, {year}"
    doc_title = f"On This Day — {date_str}"

    # --- Create the blank document via Drive API ---
    # Using Drive's files.create is more reliable than docs.documents.create
    # and lets us set the parent folder in one call.
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    file_metadata = {
        "name": doc_title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    drive_file = drive_service.files().create(
        body=file_metadata,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    doc_id = drive_file["id"]
    logger.info(f"Created Google Doc via Drive API: {doc_id}")

    # Make readable by anyone with the link
    drive_service.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()

    # --- Build and populate the document ---
    _build_document(docs_service, doc_id, date_str, events)

    return f"https://docs.google.com/document/d/{doc_id}/edit"


def _build_document(docs_service, doc_id: str, date_str: str, events: list[dict]):
    """Populate the Google Doc with structured, formatted content."""

    by_region: dict[str, list[dict]] = {r: [] for r in REGION_ORDER}
    for event in events:
        region = event.get("region", "")
        if region in by_region:
            by_region[region].append(event)

    # -----------------------------------------------------------------------
    # Phase 1: Build the full text string and record formatting + image slots
    #
    # idx is always the next character position in the final document (1-based).
    # Formatting requests reference these positions; images are inserted later.
    # -----------------------------------------------------------------------
    text_parts: list[str] = []
    format_requests: list[dict] = []
    image_positions: list[tuple[int, str]] = []  # (doc_index, url)

    idx = 1  # Google Docs body content starts at index 1

    def _para_request(start: int, end: int, style: dict, fields: str) -> dict:
        return {
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": style,
                "fields": fields,
            }
        }

    def _text_request(start: int, end: int, style: dict, fields: str) -> dict:
        return {
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "textStyle": style,
                "fields": fields,
            }
        }

    def append(
        text: str,
        *,
        para_style: str | None = None,
        space_above: float = 0,
        space_below: float = 0,
        alignment: str | None = None,
        text_color: dict | None = None,
        link_url: str | None = None,
        italic: bool = False,
    ) -> None:
        nonlocal idx
        start = idx
        text_parts.append(text)
        end = idx + len(text)

        # ── Paragraph style ──────────────────────────────────────────────────
        para_dict: dict = {}
        para_fields: list[str] = []

        if para_style:
            para_dict["namedStyleType"] = para_style
            para_fields.append("namedStyleType")
        if space_above:
            para_dict["spaceAbove"] = {"magnitude": space_above, "unit": "PT"}
            para_fields.append("spaceAbove")
        if space_below:
            para_dict["spaceBelow"] = {"magnitude": space_below, "unit": "PT"}
            para_fields.append("spaceBelow")
        if alignment:
            para_dict["alignment"] = alignment
            para_fields.append("alignment")

        if para_fields:
            format_requests.append(_para_request(start, end, para_dict, ",".join(para_fields)))

        # ── Text style (applies to all characters except the trailing \n) ────
        text_end = end - 1 if text.endswith("\n") else end
        if text_end > start:
            text_dict: dict = {}
            text_fields: list[str] = []

            if text_color:
                text_dict["foregroundColor"] = {"color": {"rgbColor": text_color}}
                text_fields.append("foregroundColor")
            if link_url:
                text_dict["link"] = {"url": link_url}
                text_dict["underline"] = True
                if not text_color:
                    text_dict["foregroundColor"] = {"color": {"rgbColor": COLOR_LINK}}
                text_fields += ["link", "underline", "foregroundColor"]
            if italic:
                text_dict["italic"] = True
                text_fields.append("italic")

            if text_fields:
                format_requests.append(
                    _text_request(start, text_end, text_dict, ",".join(sorted(set(text_fields))))
                )

        idx = end

    def reserve_image(url: str | None) -> None:
        """
        Add a dedicated paragraph that will hold the image.
        The paragraph is center-aligned with breathing room above and below,
        so the image never runs into adjacent text.
        """
        nonlocal idx
        if not url:
            return

        start = idx
        text_parts.append("\n")  # one blank paragraph — the image goes here
        end = idx + 1

        format_requests.append(_para_request(
            start, end,
            {
                "alignment": "CENTER",
                "spaceAbove": {"magnitude": 10, "unit": "PT"},
                "spaceBelow": {"magnitude": 14, "unit": "PT"},
            },
            "alignment,spaceAbove,spaceBelow",
        ))

        # The image is inserted at `start` (the first character of this paragraph),
        # so it fills the paragraph without touching any surrounding text.
        image_positions.append((start, url))
        idx = end

    # ── Document title ────────────────────────────────────────────────────────
    append(
        f"On This Day — {date_str}\n",
        para_style="TITLE",
        alignment="CENTER",
        space_below=10,
    )
    append("\n")  # visual gap under the title

    # ── One section per region ────────────────────────────────────────────────
    for region in REGION_ORDER:
        region_events = by_region.get(region, [])
        if not region_events:
            continue

        append(
            f"{region}\n",
            para_style="HEADING_1",
            text_color=COLOR_H1,
            space_above=20,
            space_below=6,
        )

        for event in region_events:
            heading_text = f"{event.get('title', '')}  ·  {event.get('year', '')}\n"
            append(
                heading_text,
                para_style="HEADING_2",
                text_color=COLOR_H2,
                space_above=16,
                space_below=4,
            )

            # Image gets its own isolated, centered paragraph
            reserve_image(event.get("image_url"))

            # Body paragraphs — justified for a clean editorial look
            body = event.get("body", "").strip()
            for para in body.split("\n\n"):
                para = para.strip()
                if para:
                    append(
                        f"{para}\n",
                        para_style="NORMAL_TEXT",
                        alignment="JUSTIFIED",
                        space_below=8,
                    )

            wiki_url = event.get("wikipedia_url", "")
            if wiki_url:
                append(
                    "Read more →\n",
                    para_style="NORMAL_TEXT",
                    link_url=wiki_url,
                    italic=True,
                    space_above=4,
                    space_below=18,
                )
            else:
                append("\n")  # gap if no link

        append("\n")  # gap between regions

    full_text = "".join(text_parts)

    # -----------------------------------------------------------------------
    # Phase 2: Insert all text in a single request
    # -----------------------------------------------------------------------
    logger.info(f"Inserting {len(full_text):,} characters into the document")
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": full_text}}]},
    ).execute()

    # -----------------------------------------------------------------------
    # Phase 3: Apply formatting in batches of 50 (API request-size limit)
    # -----------------------------------------------------------------------
    if format_requests:
        chunk_size = 50
        for i in range(0, len(format_requests), chunk_size):
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": format_requests[i : i + chunk_size]},
            ).execute()
        logger.info(f"Applied {len(format_requests)} formatting requests")

    # -----------------------------------------------------------------------
    # Phase 4: Insert images — highest index first so earlier indices stay valid
    # -----------------------------------------------------------------------
    for img_idx, img_url in sorted(image_positions, key=lambda x: x[0], reverse=True):
        try:
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [{
                        "insertInlineImage": {
                            "location": {"index": img_idx},
                            "uri": img_url,
                            "objectSize": {
                                "height": {"magnitude": IMAGE_HEIGHT_PT, "unit": "PT"},
                                "width": {"magnitude": IMAGE_WIDTH_PT, "unit": "PT"},
                            },
                        }
                    }]
                },
            ).execute()
            logger.info(f"Inserted image at index {img_idx}")
        except Exception as e:
            logger.error(f"Could not insert image at index {img_idx} ({img_url}): {e}")
