"""CLI command for scraping MS Teams chat history."""

# ruff: noqa: B008

import asyncio

import typer
from rich.console import Console

from ..config import settings

scrape_app = typer.Typer(help="Scrape MS Teams chat history")
console = Console()


@scrape_app.callback(invoke_without_command=True)
def scrape_chats(
    chats: list[str] | None = typer.Option(
        None, "--chats", help="List of chat names to scrape"
    ),
    dates: list[str] | None = typer.Option(
        None, "--dates", help="List of dates (YYYY-MM-DD or DD/MM) to scrape"
    ),
    from_date: str | None = typer.Option(
        None, "--from-date", help="Start date (YYYY-MM-DD or DD/MM)"
    ),
    to_date: str | None = typer.Option(
        None, "--to-date", help="End date (YYYY-MM-DD or DD/MM), defaults to today"
    ),
    stop_early: bool = typer.Option(
        False, "--stop-early", help="Stop scanning sidebar when a chat is before from-date"
    ),
    headless: bool = typer.Option(
        True, "--headless/--headful", help="Run browser in headless mode"
    ),
) -> None:
    """Scrape Teams chat history. Defaults to today's active chats.

    Args:
        chats: List of chat names to scrape.
        dates: List of specific dates (YYYY-MM-DD or DD/MM) to scrape.
        from_date: Start date (YYYY-MM-DD or DD/MM) for date-range scraping.
        to_date: End date (YYYY-MM-DD or DD/MM) for date-range scraping, defaults to today.
        stop_early: If True, stops scanning sidebar when a chat is before from-date.
        headless: Run browser in headless mode.

    """
    settings.headless = headless

    # Lazy import to avoid loading heavy modules (playwright, bs4, etc.) on CLI startup
    from ..core.scraper import TeamsScraper

    scraper = TeamsScraper(
        auth_path=str(settings.auth_path), profile_dir=str(settings.profile_dir)
    )

    if chats:
        console.print(f"[bold cyan]Fetching specific chats: {chats}...[/bold cyan]")
        asyncio.run(scraper.scrape(mode="by_chats", targets=chats))
    elif dates:
        console.print(f"[bold cyan]Fetching messages for dates: {dates}...[/bold cyan]")
        asyncio.run(scraper.scrape(mode="by_dates", targets=dates))
    elif from_date:
        to_date_str = to_date if to_date else "today"
        console.print(
            f"[bold cyan]Fetching messages from {from_date} to {to_date_str} "
            f"(stop_early={stop_early})...[/bold cyan]"
        )
        asyncio.run(
            scraper.scrape(
                mode="by_range",
                targets=[from_date, to_date] if to_date else [from_date],
                stop_early=stop_early,
            )
        )
    else:
        console.print("[bold cyan]Fetching active chats for today...[/bold cyan]")
        asyncio.run(scraper.scrape(mode="default"))
