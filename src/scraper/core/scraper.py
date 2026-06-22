"""Core Teams Scraper module using Playwright."""

import asyncio
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import yaml
from loguru import logger
from playwright.async_api import BrowserContext, ElementHandle, Playwright, async_playwright

from ..config import settings
from .models import Chat, Message, ScrapeOutput

# Common selectors and patterns
CHAT_LIST_CONTAINER_SELECTOR = 'div[role="tree"][data-tid="simple-collab-dnd-rail"]'
CHAT_LIST_ITEM_SELECTOR = '[role="treeitem"][data-item-type="chat"]'
MESSAGE_SELECTORS = [
    'div[data-tid="chat-message"]',
    'div[data-tid="chat-pane-message"]',
    ".fui-ChatMessage",
    '[role="row"]',
    '[role="listitem"]',
]
AVATAR_SELECTOR = '[data-tid="avatar"]'


class TeamsScraper:
    """A scraper to extract chat messages and metadata from MS Teams Web app."""

    def __init__(
        self, auth_path: str = "teams_auth.json", profile_dir: str = "teams_profile"
    ) -> None:
        """Initialize the TeamsScraper."""
        self.auth_path = Path(auth_path)
        self.profile_dir = Path(profile_dir)
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)
        self.chats_config_map = self._load_chats_config()


    def _load_chats_config(self) -> dict[str, Any]:
        config_path = settings.chats_config_path
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                    return {
                        chat.get("id"): chat
                        for chat in config_data.get("chats", [])
                        if chat.get("id")
                    }
            except Exception as e:
                logger.error(f"Error loading chats_config.yaml: {e}")
        return {}

    async def _setup_context(self, playwright: Playwright) -> BrowserContext:
        is_new_profile = not self.profile_dir.exists()
        self.profile_dir.mkdir(exist_ok=True)

        logger.info(f"Using persistent profile directory: {self.profile_dir}")
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=settings.headless,
        )

        # Seed with existing teams_auth.json cookies if the profile is new/empty
        if is_new_profile and self.auth_path.exists():
            try:
                with open(self.auth_path, encoding="utf-8") as f:
                    state = json.load(f)
                    cookies = state.get("cookies", [])
                    if cookies:
                        await context.add_cookies(cookies)
                        logger.info(f"Seeded persistent profile with cookies from {self.auth_path}")
            except Exception as e:
                logger.warning(f"Could not seed cookies from {self.auth_path}: {e}")

        return context



    def _is_chat_today(self, chat_text: str) -> bool:
        """Determine if a chat is active today based on sidebar indicators."""
        # Typical older indicators in Teams: "Yesterday", "Mon", "3/29", etc.
        patterns = [r"\b(Yesterday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", r"\d{1,2}/\d{1,2}"]

        for pattern in patterns:
            if re.search(pattern, chat_text, re.IGNORECASE):
                return False

        # If text is too short, probably not a valid chat item
        if len(chat_text.strip()) < 5:
            return False

        return True

    def _parse_date(self, date_str: str) -> date | None:
        """Parse various date formats to date object."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            try:
                # Handle DD/MM or MM/DD or DD-MM
                today = date.today()
                # Try common separators
                for sep in ["/", "-", "."]:
                    if sep in date_str:
                        parts = date_str.split(sep)
                        if len(parts) == 2:
                            # Assume DD/MM and current year
                            return date(today.year, int(parts[1]), int(parts[0]))
                        if len(parts) == 3:
                            # DD/MM/YYYY or YYYY/MM/DD
                            if len(parts[0]) == 4:
                                return date(int(parts[0]), int(parts[1]), int(parts[2]))
                            else:
                                return date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception as e:
                logger.debug(f"Could not parse custom date format: {e}")
        return None

    def _parse_sidebar_date(self, text: str) -> date | None:
        """Parse various sidebar date formats into date objects."""
        if not text:
            return None

        # Clean up common noise and non-standard characters
        text = text.strip().replace("\xa0", " ").replace("\n", " ")

        today = date.today()

        # 1. Long formats (e.g. "Monday, March 30, 2026" or "Apr 1, 2026")
        # Attempt to parse using common patterns
        month_names = [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
        month_full = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        lower_text = text.lower()
        found_month = -1
        for i, m in enumerate(month_names):
            if m in lower_text:
                found_month = i + 1
                break
        if found_month == -1:
            for i, m in enumerate(month_full):
                if m in lower_text:
                    found_month = i + 1
                    break

        if found_month != -1:
            # Extract day and year if possible
            match_day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", text)
            match_year = re.search(r"\b(20\d{2})\b", text)

            if match_day:
                day = int(match_day.group(1))
                year = int(match_year.group(1)) if match_year else today.year
                try:
                    dt = date(year, found_month, day)
                    # If this yields a future date, check if year rollover is needed
                    if dt > today and not match_year:
                        dt = date(year - 1, found_month, day)
                    return dt
                except Exception as e:
                    logger.debug(f"Could not parse match parts into date: {e}")


        # 2. Time only (e.g. "12:34 PM") -> Today
        if re.search(r"\d{1,2}:\d{2}\s*(?:AM|PM)?", text, re.IGNORECASE):
            return today

        # 3. "Yesterday"
        if "yesterday" in lower_text:
            return today - timedelta(days=1)

        # 4. Weekdays ("Mon", "Tue", etc.)
        weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for i, wd_str in enumerate(weekdays):
            if wd_str in lower_text:
                target_day = i
                current_day = today.weekday()
                diff = (current_day - target_day) % 7
                if diff == 0:
                    diff = 7
                return today - timedelta(days=diff)

        # 5. Numeric patterns: DD/MM or MM/DD logic moved to a multi-interpret helper
        return None

    def _get_ambiguous_sidebar_dates(self, text: str) -> set[date]:
        """Return possible dates for ambiguous numeric string (e.g., '4/2')."""
        dates: set[date] = set()
        if not text:
            return dates

        match = re.search(r"(\d{1,2})[/-](\d{1,2})", text)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            today = date.today()

            # Possible interpretation 1: DD/MM
            try:
                if 1 <= b <= 12 and 1 <= a <= 31:
                    d1 = date(today.year, b, a)
                    if d1 > today:
                        d1 = date(today.year - 1, b, a)
                    dates.add(d1)
            except Exception as e:
                logger.debug(f"Failed parsing ambiguous interpretation 1: {e}")

            # Possible interpretation 2: MM/DD
            try:
                if 1 <= a <= 12 and 1 <= b <= 31:
                    d2 = date(today.year, a, b)
                    if d2 > today:
                        d2 = date(today.year - 1, a, b)
                    dates.add(d2)
            except Exception as e:
                logger.debug(f"Failed parsing ambiguous interpretation 2: {e}")

        return dates

    async def _get_chat_id(self, chat_item: ElementHandle) -> str:
        """Extract chat ID from elements like id='title-chat-list-item_ID'."""
        title_el = await chat_item.query_selector('[id^="title-chat-list-item"]')
        if title_el:
            id_val = await title_el.get_attribute("id")
            if id_val and "_" in id_val:
                return str(id_val.split("_", 1)[1])
        return "unknown_chat"

    async def _get_sender_info(self, msg_el: ElementHandle) -> dict[str, Any]:
        """Attempt to find name and email of the sender using aria roles."""
        try:

            # Robust mapping using aria-labelledby relationships
            info = await msg_el.evaluate("""el => {
                const aria = el.getAttribute('aria-labelledby') || '';
                const ids = aria.split(' ');
                let author = 'Unknown';
                let timestamp = null;

                ids.forEach(id => {
                    if (id.includes('author')) {
                        const authorEl = document.getElementById(id);
                        if (authorEl) author = authorEl.innerText.trim();
                    }
                    if (id.includes('timestamp') || id.includes('time')) {
                        const timeEl = document.getElementById(id);
                        if (timeEl) {
                            const timeTag = timeEl.tagName === 'TIME'
                                ? timeEl
                                : timeEl.querySelector('time');
                            if (timeTag && timeTag.getAttribute('datetime')) {
                                timestamp = timeTag.getAttribute('datetime');
                            } else {
                                timestamp = timeEl.innerText.trim();
                            }
                        }
                    }

                });

                if (!timestamp) {
                   timestamp = el.getAttribute('data-timestamp') || el.getAttribute('title');
                }
                
                if (author === 'Unknown') {
                    const authEl = el.querySelector(
                        '[data-tid*="author"], [data-tid*="name"], [class*="author"]'
                    );
                    if (authEl) author = authEl.innerText.trim();
                }

                return { author, timestamp };
            }""")

            author = info.get("author", "Unknown")
            timestamp = info.get("timestamp")
            email = None

            # Email extraction from avatar
            avatar = await msg_el.query_selector(AVATAR_SELECTOR)
            if avatar:
                label = await avatar.get_attribute("aria-label")
                if label and "(" in label and ")" in label:
                    match = re.search(r"\(([^)]+@[^)]+)\)", label)
                    if match:
                        email = match.group(1)

            return {"name": author, "email": email, "timestamp": timestamp}
        except Exception as e:
            logger.debug(f"Info extraction error: {e}")
            return {"name": "Unknown", "email": None, "timestamp": None}

    async def scrape(
        self,
        mode: str = "default",
        targets: list[str] | None = None,
        stop_early: bool = False,
    ) -> ScrapeOutput:
        """Scrape MS Teams chat history based on the configured mode and targets."""
        async with async_playwright() as p:
            context = await self._setup_context(p)
            page = await context.new_page()

            try:
                # Use v2 endpoint
                await page.goto(
                    "https://teams.microsoft.com/v2/", wait_until="commit", timeout=settings.timeout
                )
            except Exception as e:
                logger.error(f"Navigation error: {e}")

            logger.info(f"Waiting {settings.stabilize_wait / 1000}s to stabilize...")
            await asyncio.sleep(settings.stabilize_wait / 1000)

            try:
                await context.storage_state(path=str(self.auth_path))
                logger.info(f"Auth state saved/updated to {self.auth_path}")
            except Exception as e:
                logger.error(f"Failed to save auth state: {e}")

            # Process side bar items
            try:
                # Target the specific chat list container to exclude other rails
                await page.wait_for_selector(CHAT_LIST_CONTAINER_SELECTOR, timeout=settings.timeout)
                chat_list_container = await page.query_selector(CHAT_LIST_CONTAINER_SELECTOR)
                if chat_list_container is None:
                    raise ValueError("Chat list container not found")
                chat_elements = await chat_list_container.query_selector_all(
                    CHAT_LIST_ITEM_SELECTOR
                )
            except Exception as e:
                logger.warning(f"Error finding chat list container or items: {e}")
                # Fallback to general search if container-based fails
                chat_elements = await page.query_selector_all(CHAT_LIST_ITEM_SELECTOR)

            logger.info(f"Found {len(chat_elements)} candidate chat items in sidebar.")

            target_dates = []
            from_date = None
            to_date = None

            if mode == "by_dates" and targets:
                target_dates = [self._parse_date(d) for d in targets if self._parse_date(d)]
                logger.info(f"Filtering for specific dates: {target_dates}")
            elif mode == "by_range" and targets:
                from_date = self._parse_date(targets[0])
                to_date = self._parse_date(targets[1]) if len(targets) > 1 else date.today()
                logger.info(
                    f"Filtering for range: {from_date} to {to_date} (stop_early={stop_early})"
                )

            # Pre-scan and metadata aggregation
            chat_items: list[dict[str, Any]] = []
            for chat_el in chat_elements:
                try:
                    chat_text = (await chat_el.inner_text()).strip()
                    chat_name = chat_text.split("\n")[0]

                    # Explicitly exclude system items
                    if any(
                        sys_item in chat_name.lower()
                        for sys_item in ["copilot", "mentions", "unread", "activity"]
                    ):
                        logger.debug(f"Skipping system item: {chat_name}")
                        continue

                    chat_id = await self._get_chat_id(chat_el)
                    chat_config = self.chats_config_map.get(chat_id)

                    # Skip if disabled in config
                    if chat_config and not chat_config.get("scrape", {}).get("enabled", True):
                        logger.info(f"Skipping chat '{chat_name}' (disabled in chats_config.yaml)")
                        continue

                    # Determine priority
                    priority_str = (
                        chat_config.get("scrape", {}).get("priority", "medium")
                        if chat_config
                        else "medium"
                    )
                    priority_val = (
                        3 if priority_str == "high" else (1 if priority_str == "low" else 2)
                    )

                    # Determine custom/effective from_date for this specific chat
                    chat_from_date = from_date
                    if chat_config:
                        sync_depth_days = chat_config.get("scrape", {}).get("sync_depth_days")
                        if sync_depth_days is not None:
                            custom_from_date = date.today() - timedelta(days=sync_depth_days)
                            if chat_from_date:
                                chat_from_date = max(chat_from_date, custom_from_date)
                            else:
                                chat_from_date = custom_from_date

                    should_process = False
                    if mode == "default":
                        if self._is_chat_today(chat_text):
                            should_process = True
                    elif mode == "by_chats" and targets:
                        if any(t.lower() in chat_name.lower() for t in targets):
                            should_process = True
                    elif mode == "by_dates":
                        should_process = True
                    elif mode == "by_range":
                        # Targeted sidebar date extraction - using multiple signals
                        signals: list[str] = []
                        ts_el = await chat_el.query_selector(
                            'time, [class*="timestamp"], [data-tid*="timestamp"]'
                        )
                        if ts_el:
                            aria_lbl = await ts_el.get_attribute("aria-label")
                            if aria_lbl:
                                signals.append(aria_lbl)
                            title_val = await ts_el.get_attribute("title")
                            if title_val:
                                signals.append(title_val)
                            signals.append(await ts_el.inner_text())


                        # Try to parse any signal unambiguously
                        sidebar_date = None
                        for s in signals:
                            sidebar_date = self._parse_sidebar_date(s)
                            if sidebar_date:
                                logger.debug(
                                    f"Chat '{chat_name}' sidebar signal '{s}' -> {sidebar_date}"
                                )
                                break

                        if sidebar_date:
                            if chat_from_date is not None and to_date is not None:
                                fd: date = chat_from_date
                                td: date = to_date
                                if fd <= sidebar_date <= td:
                                    logger.info(
                                        f"Chat '{chat_name}' active on {sidebar_date}. "
                                        "Processing..."
                                    )
                                    should_process = True
                                elif sidebar_date < fd:
                                    if stop_early:
                                        logger.info(
                                            f"Chat '{chat_name}' active on {sidebar_date} "
                                            f"(older than {fd}). "
                                            "Stopping early due to --stop-early."
                                        )

                                        break
                                    else:
                                        logger.debug(
                                            f"Chat '{chat_name}' active on {sidebar_date} "
                                            f"(older than {fd}). Skipping."
                                        )
                                        should_process = False
                                else:
                                    logger.debug(
                                        f"Chat '{chat_name}' active on {sidebar_date} "
                                        f"(newer than {td}). Skipping."
                                    )
                                    should_process = False
                            else:
                                should_process = True
                        else:
                            # Ambiguity Check: handle numeric e.g. "4/2"
                            potential_dates = set()
                            for s in signals:
                                potential_dates.update(self._get_ambiguous_sidebar_dates(s))

                            if potential_dates:
                                # If ANY interpretation falls in range, we must process it
                                if chat_from_date is not None and to_date is not None:
                                    fd_ambig: date = chat_from_date
                                    td_ambig: date = to_date
                                    in_range = [
                                        d for d in potential_dates
                                        if fd_ambig <= d <= td_ambig
                                    ]
                                else:
                                    in_range = []

                                if in_range:
                                    logger.info(
                                        f"Chat '{chat_name}' has ambiguous date(s) "
                                        f"{potential_dates}. Interpretations {in_range} "
                                        "are in range. Opening..."
                                    )
                                    should_process = True
                                else:
                                    logger.debug(
                                        f"Chat '{chat_name}' has ambiguous date(s) "
                                        f"{potential_dates}. None are in range. Skipping."
                                    )
                                    should_process = False
                            else:
                                # Final fallback: open to verify
                                logger.debug(
                                    f"Could not parse sidebar date for '{chat_name}'. "
                                    "Opening to verify."
                                )
                                should_process = True

                    if should_process:
                        chat_items.append({
                            "el": chat_el,
                            "id": chat_id,
                            "name": chat_name,
                            "text": chat_text,
                            "priority": priority_val,
                            "chat_from_date": chat_from_date,
                            "config": chat_config
                        })
                except Exception as e:
                    logger.warning(f"Error pre-scanning chat element: {e}")

            # Sort remaining processed chats by priority descending (high priority first)
            chat_items.sort(key=lambda x: int(x["priority"]), reverse=True)
            logger.info(
                f"Prepared {len(chat_items)} chats to process "
                "after filtering and sorting by priority."
            )

            chats_data = []
            for item in chat_items:
                target_el = cast(ElementHandle, item["el"])
                target_id = str(item["id"])
                target_name = str(item["name"])
                item["config"]
                target_from_date = item["chat_from_date"]

                logger.info(f"Opening chat: {target_name}")
                try:
                    await target_el.scroll_into_view_if_needed()
                    await target_el.click(force=True)
                    await asyncio.sleep(settings.click_wait / 1000)

                    # Discover the context where message elements exist (page or internal frame)
                    target_context = page
                    msg_elements = []
                    for sel in MESSAGE_SELECTORS:
                        msg_elements = await page.query_selector_all(sel)
                        if msg_elements:
                            target_context = page
                            break

                    if not msg_elements:
                        for frame in page.frames:
                            for sel in MESSAGE_SELECTORS:
                                msg_elements = await frame.query_selector_all(sel)
                                if msg_elements:
                                    target_context = frame
                                    break
                            if msg_elements:
                                break

                    # Determine the oldest date we need to scroll back to
                    scroll_limit_date = target_from_date
                    if mode == "default" and scroll_limit_date is None:
                        scroll_limit_date = date.today()
                    elif mode == "by_dates" and target_dates:
                        scroll_limit_date = min(target_dates)

                    # Dynamic resolution of the scrollable container inside target_context
                    scroll_container_js = """() => {
                        const selectors = [
                            'div[data-tid="chat-message"]',
                            'div[data-tid="chat-pane-message"]',
                            '.fui-ChatMessage',
                            '[role="row"]',
                            '[role="listitem"]'
                        ];
                        let msg = null;
                        for (const selector of selectors) {
                            msg = document.querySelector(selector);
                            if (msg) break;
                        }
                        if (msg) {
                            let parent = msg.parentElement;
                            while (parent) {
                                const style = window.getComputedStyle(parent);
                                if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                                    return parent;
                                }
                                parent = parent.parentElement;
                            }
                        }
                        const logs = document.querySelector('div[role="log"], [data-tid="chat-pane-layout"]');
                        if (logs) return logs;
                        return document.querySelector('.fui-ChatPane') || document.body;
                    }"""
                    scroll_container = await target_context.evaluate_handle(scroll_container_js)

                    chat_messages = {}
                    prev_scroll_top = -1
                    reached_top_count = 0
                    max_scroll_attempts = 100  # Avoid infinite loops

                    for attempt in range(max_scroll_attempts):
                        # Get current scroll position details
                        scroll_info = await target_context.evaluate("""(container) => {
                            if (!container) return { scrollTop: 0, scrollHeight: 0, clientHeight: 0 };
                            return {
                                scrollTop: container.scrollTop,
                                scrollHeight: container.scrollHeight,
                                clientHeight: container.clientHeight
                            };
                        }""", scroll_container)

                        scroll_top = scroll_info["scrollTop"]

                        # Extract all visible messages in the current view
                        current_msg_elements = []
                        for sel in MESSAGE_SELECTORS:
                            current_msg_elements = await target_context.query_selector_all(sel)
                            if current_msg_elements:
                                break

                        current_attempt_oldest_date = None
                        for msg_el in current_msg_elements:
                            info = await self._get_sender_info(msg_el)
                            timestamp_str = info.get("timestamp")

                            if not timestamp_str:
                                continue

                            try:
                                if "T" in timestamp_str:
                                    if not any(c in timestamp_str for c in ["+", "Z"]):
                                        timestamp_str += "Z"
                                    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                else:
                                    dt = datetime.combine(date.today(), datetime.min.time())
                            except Exception as e:
                                logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
                                continue

                            msg_date = dt.date()
                            if current_attempt_oldest_date is None or msg_date < current_attempt_oldest_date:
                                current_attempt_oldest_date = msg_date

                            text = await msg_el.inner_text()
                            mid = await msg_el.get_attribute("data-mid")
                            msg_key = mid if mid else f"{dt.isoformat()}_{info['name']}_{text[:20]}"

                            chat_messages[msg_key] = Message(
                                id=mid or "unknown",
                                timestamp=dt,
                                sender_name=info["name"],
                                sender_email=info["email"],
                                text=text.strip(),
                            )

                        logger.info(
                            f"[{target_name}] Scroll attempt {attempt + 1}: "
                            f"Found {len(current_msg_elements)} messages in DOM. "
                            f"Total unique messages: {len(chat_messages)}."
                        )

                        # Check exit condition 1: reached/passed oldest target date
                        if scroll_limit_date is not None and current_attempt_oldest_date is not None:
                            if current_attempt_oldest_date < scroll_limit_date:
                                logger.info(
                                    f"[{target_name}] Reached oldest message date ({current_attempt_oldest_date}) "
                                    f"beyond target date ({scroll_limit_date}). Stopping scroll."
                                )
                                break

                        # Check exit condition 2: reached the top of the scroll container
                        if scroll_top == prev_scroll_top:
                            reached_top_count += 1
                            if reached_top_count >= 3:
                                logger.info(
                                    f"[{target_name}] Reached top of chat history (scroll position stable at {scroll_top}). "
                                    "Stopping scroll."
                                )
                                break
                        else:
                            reached_top_count = 0

                        prev_scroll_top = scroll_top

                        # Scroll up
                        await target_context.evaluate("""(container) => {
                            if (container) {
                                container.scrollTop = Math.max(0, container.scrollTop - 600);
                            }
                        }""", scroll_container)

                        # Wait for Teams to render the next batch
                        await asyncio.sleep(settings.click_wait / 1000)

                    # Post-process and filter the collected messages
                    chat_messages_list = []
                    for msg in chat_messages.values():
                        msg_date = msg.timestamp.date()

                        if mode == "default":
                            start_dt = target_from_date if target_from_date is not None else date.today()
                            if not (start_dt <= msg_date <= date.today()):
                                continue
                        elif mode == "by_range":
                            start_dt = target_from_date if target_from_date is not None else date.today()
                            end_dt = to_date if to_date is not None else date.today()
                            if not (start_dt <= msg_date <= end_dt):
                                continue
                        elif mode == "by_dates" and target_dates:
                            if msg_date not in target_dates:
                                continue

                        chat_messages_list.append(msg)

                    # Sort messages chronologically
                    chat_messages_list.sort(key=lambda x: x.timestamp)

                    if chat_messages_list:
                        if target_id.startswith("48:"):
                            chat_type = "personal"
                        elif "@unq.gbl.spaces" in target_id:
                            chat_type = "one-on-one"
                        else:
                            chat_type = "group"

                        # Extract participant IDs by stripping prefix/suffix and splitting on '_'
                        cleaned_id = target_id
                        if ":" in cleaned_id:
                            cleaned_id = cleaned_id.split(":", 1)[1]
                        if "@" in cleaned_id:
                            cleaned_id = cleaned_id.split("@", 1)[0]
                        participants = [p for p in cleaned_id.split("_") if p]

                        chats_data.append(
                            Chat(
                                id=target_id,
                                name=target_name,
                                type=chat_type,
                                participants=participants,
                                messages=chat_messages_list,
                            )
                        )
                except Exception as e:
                    logger.error(f"Error processing chat {target_name}: {e}")

            output = ScrapeOutput(chats=chats_data)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"scrape_{mode}_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output.model_dump_json(indent=2))

            logger.info(f"Scrape completed. Saved to {output_file}")
            try:
                await context.storage_state(path=str(self.auth_path))
                logger.info(f"Auth state updated and saved to {self.auth_path}")
            except Exception as e:
                logger.error(f"Failed to save final auth state: {e}")
            await context.close()
            return output

