# MS Teams Chat Scraper

Deterministic and professional CLI tool for extracting MS Teams messages with advanced filtering.

## Features
- **3 Execution Modes**: 
  - `default`: Scrapes active chats from today.
  - `by-chats`: Scrapes specific chat names.
  - `by-dates`: Scrapes messages for specific dates.
- **Deep Extraction**: Captures `chat_id`, `message_id`, `sender_name`, `sender_email`, and `timestamp`.
- **Session Persistence**: Uses `teams_auth.json` to maintain authentication state.
- **Structured Output**: Generates Pydantic-validated JSON files in `outputs/`.

## Prerequisites
- [uv](https://github.com/astral-sh/uv)
- Playwright Chromium dependencies

## Setup
```bash
uv sync
uv run playwright install chromium
```

## Usage
### Default Mode (Today's active chats)
```bash
uv run python main.py default
```

### By Chat Names
```bash
uv run python main.py by-chats "General" "Operations"
```

### By Specific Dates
```bash
uv run python main.py by-dates "2026-03-30" "2026-03-29"
```

## Configuration
Controlled via `src/scraper/config.py` or environment variables prefixed with `TEAMS_`:
- `TEAMS_AUTH_PATH`: Path to auth JSON.
- `TEAMS_OUTPUT_DIR`: Directory for scraped data.
- `TEAMS_TIMEOUT`: Browser timeout in ms.
- `TEAMS_HEADLESS`: Run in headless mode (default: False).
