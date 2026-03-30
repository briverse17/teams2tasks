# Project Architecture

> MS Teams Scraper (Playwright)

## Overview

The scraper is an automation tool designed to bypass the complexity of MS Teams' dynamic UI to extract conversation data for compliance or monitoring.

## System Flow

1. **Authentication**:
   - Checks for `teams_auth.json`.
   - If missing, it uses a **manual login mode** to capture session storage.
   - Saves `storage_state` to `teams_auth.json`.
2. **Navigation**:
   - Uses `chromium.launch(headless=True)`.
   - Navigates to `https://teams.cloud.microsoft`.
   - Generous stabilization wait (20-45s) for legacy and current SPA performance.
3. **Scouting**:
   - Identifies the chat navigation container (`[role="tree"]`).
   - Discovers chat items (`[role="treeitem"]`).
4. **Scraping**:
   - Sequentially clicks each chat.
   - Searches message containers inside the main context and all **iframes**.
   - Filters findings using `datetime` comparison to today's start.

## Trade-offs and Decisions

- **Playwright over Selenium**: Better handling of shadow DOMs and direct Chromium DevTools (CDP) access.
- **Sync over Async**: Synchronous execution was chosen for simpler script usage in a local manual flow.
- **Heuristic Timestamps**: Since Teams values attributes inconsistently, we use a multi-selector falloff (data-timestamp → title → inner_text).

## Future Consideration

- **CDP Attachment Mode**: Already pioneered as a debug tool; could be formalized to "take over" a manual Chrome session.
- **Teams Alerting**: Potential integration with incoming/outgoing webhooks for reporting.
