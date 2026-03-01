# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

A daily "On This Day in History" digest. The script uses the Anthropic API to write
historical articles in the style of Dan Jones — clear, grounded, vivid without drama.
It creates a formatted Google Doc (with Wikimedia Commons images) and posts the day's
headlines and teasers to Discord via webhook. Runs daily via GitHub Actions at 06:00 UTC.

Regions covered: Ancient Rome, Ancient Greece, Europe from Classical Era until Fall of Soviet Union, United States.

Amount of articles: 2 most notable events (Claude picks the best across all regions).

## Tech Stack

- Language: Python 3.11+
- AI: Anthropic API (`claude-sonnet-4-6`)
- Storage: Google Docs + Google Drive API (OAuth 2.0 with stored refresh token)
- Images: Wikimedia Commons API (JPEG/PNG only, < 25 MB)
- Notifications: Discord webhook (plain message with titles + doc link)
- CI/CD: GitHub Actions (daily cron)

## File Structure

```
.
├── main.py                      # Entry point — orchestrates the full pipeline
├── generator.py                 # Anthropic API calls, prompt logic, JSON parsing
├── wikimedia.py                 # Wikimedia Commons image search
├── google_drive.py              # Google Docs creation and Drive upload
├── discord_notifier.py          # Discord webhook posting
├── auth_setup.py                # One-time OAuth token setup (run locally)
├── requirements.txt
├── .env.example                 # Template for local secrets
├── .gitignore
└── .github/
    └── workflows/
        └── daily.yml            # GitHub Actions cron (06:00 UTC)
```

## Pipeline (main.py)

1. `generate_events(date)` → list of event dicts from Claude
2. `find_image_url(query)` → Wikimedia image URL per event (or None)
3. `create_daily_doc(date, events)` → formatted Google Doc, returns shareable URL
4. `post_digest(date, events, doc_url)` → Discord message with titles + teasers

## Event Dict Shape

```python
{
    "region": "Ancient Rome",
    "title": "Short title without year",
    "year": "44 BC",
    "teaser": "One-sentence hook.",
    "body": "3-5 paragraphs, separated by \\n\\n.",
    "wikipedia_url": "https://en.wikipedia.org/wiki/...",
    "wikimedia_search_query": "keywords for image search",
    "image_url": "https://upload.wikimedia.org/..."  # added by main.py
}
```

## Google Docs Build Strategy

`google_drive.py` populates a doc in four phases:
1. Build the full text string, recording paragraph-style requests and image slot positions
2. Insert all text in one `batchUpdate` (index 1)
3. Apply all formatting in chunked `batchUpdate` calls (50 requests per batch)
4. Insert images one at a time, going **backwards** (highest index first) so earlier
   indices stay valid after each insertion

## Google Docs Design

The document is built to read like a curated journal, not a Wikipedia dump.

**Typography hierarchy**
- Title (`TITLE` style): centred, 10 pt gap below
- Region header (`HEADING_1`): deep navy `#1A3569`, 20 pt above / 6 pt below
- Event title (`HEADING_2`): dark burgundy `#611E1E`, 16 pt above / 4 pt below
- Body (`NORMAL_TEXT`): justified, 8 pt between paragraphs
- "Read more →" link: italic, steel blue, 18 pt below

**Images**
- Every event gets one Wikimedia Commons image (JPEG/PNG, ≤ 25 MB)
- Each image lives in its **own isolated paragraph** — `\n` before and after —
  so it never runs into surrounding text
- The image paragraph is centre-aligned with 10 pt above and 14 pt below
- Images are inserted last, working backwards through the document so earlier
  indices stay valid after each insertion (430 × 260 pt display size)

**Auth**
- Uses OAuth 2.0 with a long-lived refresh token (not a service account)
- Run `python auth_setup.py` once locally to obtain `GOOGLE_REFRESH_TOKEN`,
  `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET`

## Secrets (GitHub Actions secrets + local `.env`)

- `ANTHROPIC_API_KEY`
- `GOOGLE_CLIENT_ID` — from the OAuth 2.0 client credential
- `GOOGLE_CLIENT_SECRET` — from the OAuth 2.0 client credential
- `GOOGLE_REFRESH_TOKEN` — obtained by running `auth_setup.py` once
- `GOOGLE_DRIVE_FOLDER_ID` — ID from the target folder's URL (optional)
- `DISCORD_WEBHOOK_URL`

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (reads from .env)
python main.py
```

## Writing Style Guide

Dan Jones style means:
- Concrete names, dates, and numbers — not "many soldiers" but "around 4,000 men"
- Human scale — what did it feel like to be there?
- Short declarative sentences alongside longer ones
- No breathless superlatives ("the greatest", "forever changed")
- Context given without turning into a lecture

## Do's and Don'ts

- Always use model `claude-sonnet-4-6`
- Always build one fresh doc per day — never append to an existing one
- Never hallucinate Wikipedia URLs — only link to known, substantial articles
- Never commit `.env` or any `*.json` file (covered by `.gitignore`)
- Never catch bare `except:` — always name the exception type
