import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from src.inference.engine import infer_tasks_from_chat

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
def scrape_by_chats(chats: List[str] = typer.Argument(..., help="List of chat names to scrape")):
    """Scrape messages for specific chat names."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    console.print(f"[bold cyan]Fetching specific chats: {chats}...[/bold cyan]")
    asyncio.run(scraper.scrape(mode="by_chats", targets=chats))


@app.command(name="by-dates")
def scrape_by_dates(
    dates: List[str] = typer.Argument(
        ..., help="List of dates (ISO format YYYY-MM-DD or DD/MM) to scrape"
    ),
):
    """Scrape messages for specific dates."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    console.print(f"[bold cyan]Fetching messages for dates: {dates}...[/bold cyan]")
    asyncio.run(scraper.scrape(mode="by_dates", targets=dates))


@app.command(name="by-range")
def scrape_by_range(
    from_date: str = typer.Argument(..., help="Start date (YYYY-MM-DD or DD/MM)"),
    to_date: Optional[str] = typer.Argument(
        None, help="End date (YYYY-MM-DD or DD/MM), defaults to today"
    ),
    stop_early: bool = typer.Option(
        False, "--stop-early", help="Stop scanning sidebar when a chat is before from-date"
    ),
):
    """Scrape messages within a date range."""
    scraper = TeamsScraper(auth_path=str(settings.auth_path))
    to_date_str = to_date if to_date else "today"
    console.print(
        f"[bold cyan]Fetching messages from {from_date} to {to_date_str} (stop_early={stop_early})...[/bold cyan]"
    )
    asyncio.run(
        scraper.scrape(
            mode="by_range",
            targets=[from_date, to_date] if to_date else [from_date],
            stop_early=stop_early,
        )
    )


@app.command(name="infer")
def infer_tasks(
    json_path: str = typer.Argument(..., help="Path to scraped JSON file"),
    chats: Optional[List[str]] = typer.Option(
        None, "--chats", help="Filter to specific chat names (can repeat)"
    ),
):
    """Run task inference on scraped JSON."""
    input_file = Path(json_path)
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {json_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Loading data from {json_path}...[/bold cyan]")
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    chats_data = data.get("chats", []) if isinstance(data, dict) else data
    if not isinstance(chats_data, list):
        console.print("[red]Error: Invalid scraping output format.[/red]")
        raise typer.Exit(1)

    if chats:
        chats_data = [c for c in chats_data if c.get("name", "") in chats]
        found = [c.get("name", "") for c in chats_data]
        missing = [c for c in chats if c not in found]
        console.print(f"[cyan]Processing {len(chats_data)} of {len(chats)} requested chats[/cyan]")
        if missing:
            console.print(f"[yellow]Chats not found: {missing}[/yellow]")

    console.print(f"[cyan]Running inference for user: {settings.user_name}[/cyan]\n")

    all_tasks = []
    for chat in chats_data:
        chat_name = chat.get("name", "Unknown Chat")
        messages = chat.get("messages", [])
        if not messages:
            console.print(f"  [dim]Skipping '{chat_name}': No messages[/dim]")
            continue

        console.print(f"  Processing '{chat_name}' ({len(messages)} messages)...", end=" ")
        try:
            tasks = infer_tasks_from_chat(
                chat_name=chat_name,
                messages=messages,
                user_name=settings.user_name,
                window_size=30,
            )
            console.print(f"[green]✓[/green] {len(tasks)} tasks")
            all_tasks.extend(tasks)
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"tasks_inferred_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✓[/bold green] {len(all_tasks)} tasks inferred")
    console.print(f"[dim]Saved to: {output_path}[/dim]")


if __name__ == "__main__":
    app()
