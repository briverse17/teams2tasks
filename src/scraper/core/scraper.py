import asyncio
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Set, Union

from loguru import logger
from playwright.async_api import BrowserContext, Page, async_playwright
from .models import Chat, Message, ScrapeOutput
from ..config import settings

# Common selectors and patterns
CHAT_LIST_CONTAINER_SELECTOR = 'div[role="tree"][data-tid="simple-collab-dnd-rail"]'
CHAT_LIST_ITEM_SELECTOR = '[role="treeitem"][data-item-type="chat"]'
MESSAGE_SELECTORS = [
    'div[data-tid="chat-message"]',
    'div[data-tid="chat-pane-message"]',
    '.fui-ChatMessage',
    '[role="row"]',
    '[role="listitem"]'
]
AVATAR_SELECTOR = '[data-tid="avatar"]'

class TeamsScraper:
    def __init__(self, auth_path: str = "teams_auth.json"):
        self.auth_path = Path(auth_path)
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

    async def _setup_context(self, playwright) -> BrowserContext:
        browser = await playwright.chromium.launch(headless=False)
        if self.auth_path.exists():
            logger.info(f"Using existing auth from {self.auth_path}")
            context = await browser.new_context(storage_state=str(self.auth_path))
        else:
            logger.warning("No auth file found. Manual login required.")
            context = await browser.new_context()
        return context

    def _is_chat_today(self, chat_text: str) -> bool:
        """Determines if a chat is active today based on sidebar indicators."""
        # Typical older indicators in Teams: "Yesterday", "Mon", "3/29", etc.
        patterns = [
            r'\b(Yesterday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b',
            r'\d{1,2}/\d{1,2}'
        ]
        
        for pattern in patterns:
            if re.search(pattern, chat_text, re.IGNORECASE):
                return False
        
        # If text is too short, probably not a valid chat item
        if len(chat_text.strip()) < 5:
            return False
            
        return True

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parses various date formats to date object."""
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            try:
                # Handle DD/MM or MM/DD - risky, assuming DD/MM
                today = date.today()
                parts = date_str.split('/')
                if len(parts) == 2:
                    return date(today.year, int(parts[1]), int(parts[0]))
            except:
                pass
        return None

    async def _get_chat_id(self, chat_item) -> str:
        """Extracts chat ID from elements like id='title-chat-list-item_ID'."""
        title_el = await chat_item.query_selector('[id^="title-chat-list-item"]')
        if title_el:
            id_val = await title_el.get_attribute("id")
            if id_val and "_" in id_val:
                return id_val.split("_", 1)[1]
        return "unknown_chat"

    async def _get_sender_info(self, msg_el) -> dict:
        """Attempts to find name and email of the sender using aria roles and labels."""
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
                            const timeTag = timeEl.tagName === 'TIME' ? timeEl : timeEl.querySelector('time');
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
                    const authEl = el.querySelector('[data-tid*="author"], [data-tid*="name"], [class*="author"]');
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
                    match = re.search(r'\(([^)]+@[^)]+)\)', label)
                    if match:
                        email = match.group(1)
            
            return {"name": author, "email": email, "timestamp": timestamp}
        except Exception as e:
            logger.debug(f"Info extraction error: {e}")
            return {"name": "Unknown", "email": None, "timestamp": None}

    async def scrape(self, mode: str = "default", targets: List[str] = None):
        async with async_playwright() as p:
            context = await self._setup_context(p)
            page = await context.new_page()
            try:
                # Use v2 endpoint
                await page.goto("https://teams.microsoft.com/v2/", wait_until="commit", timeout=settings.timeout)
            except Exception as e:
                logger.error(f"Navigation error: {e}")
            
            logger.info(f"Waiting {settings.stabilize_wait/1000}s to stabilize...")
            await asyncio.sleep(settings.stabilize_wait / 1000) 

            # Process side bar items
            try:
                # Target the specific chat list container to exclude other rails
                await page.wait_for_selector(CHAT_LIST_CONTAINER_SELECTOR, timeout=settings.timeout)
                chat_list_container = await page.query_selector(CHAT_LIST_CONTAINER_SELECTOR)
                chat_elements = await chat_list_container.query_selector_all(CHAT_LIST_ITEM_SELECTOR)
            except Exception as e:
                logger.warning(f"Error finding chat list container or items: {e}")
                # Fallback to general search if container-based fails
                chat_elements = await page.query_selector_all(CHAT_LIST_ITEM_SELECTOR)

            logger.info(f"Found {len(chat_elements)} candidate chat items in sidebar.")

            target_dates = []
            if mode == "by_dates" and targets:
                target_dates = [self._parse_date(d) for d in targets if self._parse_date(d)]
                logger.info(f"Filtering for dates: {target_dates}")

            chats_data = []
            for chat_el in chat_elements:
                chat_text = (await chat_el.inner_text()).strip()
                chat_name = chat_text.split('\n')[0]
                
                # Explicitly exclude system items
                if any(sys_item in chat_name.lower() for sys_item in ["copilot", "mentions", "unread", "activity"]):
                    logger.debug(f"Skipping system item: {chat_name}")
                    continue

                chat_id = await self._get_chat_id(chat_el)

                should_process = False
                if mode == "default":
                    if self._is_chat_today(chat_text):
                        should_process = True
                elif mode == "by_chats" and targets:
                    if any(t.lower() in chat_name.lower() for t in targets):
                        should_process = True
                elif mode == "by_dates":
                    should_process = True 

                if not should_process:
                    continue

                logger.info(f"Opening chat: {chat_name}")
                try:
                    await chat_el.scroll_into_view_if_needed()
                    await chat_el.click(force=True)
                    await asyncio.sleep(settings.click_wait / 1000)

                    # Discover messages within current chat viewport
                    msg_elements = []
                    # Try primary page
                    for sel in MESSAGE_SELECTORS:
                        msg_elements = await page.query_selector_all(sel)
                        if msg_elements:
                            break
                    
                    # Try internal frames if not found
                    if not msg_elements:
                        for frame in page.frames:
                            for sel in MESSAGE_SELECTORS:
                                msg_elements = await frame.query_selector_all(sel)
                                if msg_elements:
                                    break
                            if msg_elements:
                                break

                    chat_messages = []
                    for msg_el in msg_elements:
                        info = await self._get_sender_info(msg_el)
                        timestamp_str = info.get("timestamp")
                        
                        if not timestamp_str:
                            continue
                            
                        # Handle varied timestamp formats
                        try:
                            if "T" in timestamp_str:
                                # ISO format
                                # Ensure Z or offset
                                if not any(c in timestamp_str for c in ["+", "Z"]):
                                    timestamp_str += "Z"
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            else:
                                # Fallback to today if it's just a time string
                                dt = datetime.combine(date.today(), datetime.min.time())
                        except:
                            continue
                        
                        msg_date = dt.date()
                        
                        # Date filtering
                        if mode == "default":
                            if msg_date != date.today():
                                continue
                        elif mode == "by_dates" and target_dates:
                            if msg_date not in target_dates:
                                continue
                                
                        text = await msg_el.inner_text()
                        mid = await msg_el.get_attribute("data-mid")

                        chat_messages.append(Message(
                            id=mid or "unknown",
                            timestamp=dt,
                            sender_name=info["name"],
                            sender_email=info["email"],
                            text=text.strip()
                        ))

                    if chat_messages:
                        chats_data.append(Chat(
                            id=chat_id,
                            name=chat_name,
                            messages=chat_messages
                        ))
                except Exception as e:
                    logger.error(f"Error processing chat {chat_name}: {e}")

            output = ScrapeOutput(chats=chats_data)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"scrape_{mode}_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output.model_dump_json(indent=2))
            
            logger.info(f"Scrape completed. Saved to {output_file}")
            await context.close()
            return output
