# Changelog

## [0.2.0] - 2026-03-30
### Professionalization & Enhancements
- Refactored project structure to follow the deterministic coding school pattern.
- Migrated core logic to `src/scraper` with Pydantic models for structured output.
- Implemented `Typer` CLI with multiple modes: `default`, `by-chats`, and `by-dates`.
- Expanded message extraction to include:
  - `id`: Unique message ID (data-mid).
  - `chat_id`: Unique thread/chat ID.
  - `sender_email`: Attempted extraction from avatar aria-labels.
- Added automated `by_dates` filtering and scrolling support.
- Centralized configuration via `pydantic-settings`.
- Integrated `uv` for dependency management.

## [0.1.0] - 2026-03-29
### Initial Prototype
- Basic MS Teams scraping functionality using Playwright and BeautifulSoup.
- Regex-based filtering for "today's" chats.
- Authentication persistence via `teams_auth.json`.
