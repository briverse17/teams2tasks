import asyncio
from typing import List, Optional
import typer
from rich.console import Console
from .core.scraper import TeamsScraper
from .config import settings

app = typer.Typer(help="Professional MS Teams Scraper CLI")
console = Console()

@app.command(name="default")
def scrape_default():
    """Scrape all active chats from today."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    console.print("[bold cyan]Fetching active chats for today...[/bold cyan]")
    asyncio.run(scraper.scrape(mode="default"))

@app.command(name="by-chats")
def scrape_by_chats(
    chats: List[str] = typer.Argument(..., help="List of chat names to scrape")
):
    """Scrape messages for specific chat names."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    console.print(f"[bold cyan]Fetching specific chats: {chats}...[/bold cyan]")
    asyncio.run(scraper.scrape(mode="by_chats", targets=chats))

@app.command(name="by-dates")
def scrape_by_dates(
    dates: List[str] = typer.Argument(..., help="List of dates (ISO format YYYY-MM-DD or DD/MM) to scrape")
):
    """Scrape messages for specific dates."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    console.print(f"[bold cyan]Fetching messages for dates: {dates}...[/bold cyan]")
    asyncio.run(scraper.scrape(mode="by_dates", targets=dates))

if __name__ == "__main__":
    app()
