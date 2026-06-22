"""CLI command for running task inference on scraped chat data."""

# ruff: noqa: B008

import json
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console

from ..config import settings

infer_app = typer.Typer(help="Run task inference on scraped JSON")
console = Console()


@infer_app.callback(invoke_without_command=True)
def infer_tasks(
    json_path: str = typer.Argument(..., help="Path to scraped JSON file"),
    chats: list[str] | None = typer.Option(
        None, "--chats", help="Filter to specific chat names (can repeat)"
    ),
) -> None:
    """Run task inference on scraped JSON.

    Args:
        json_path: Path to the scraped JSON file containing chat history.
        chats: List of specific chat names to filter the inference on.

    Raises:
        Exit: If the input file is not found or has an invalid format.

    """
    # Lazy import to avoid loading heavy modules (dspy, openai, etc.) on CLI startup
    from src.inference.engine import infer_tasks_from_chat

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

    # Load chats config map
    chats_config_map = {}
    config_path = settings.chats_config_path
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
                chats_config_map = {
                    chat.get("id"): chat
                    for chat in config_data.get("chats", [])
                    if chat.get("id")
                }
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load chats_config.yaml: {e}[/yellow]")

    all_tasks = []
    for chat in chats_data:
        chat_id = chat.get("id")
        chat_name = chat.get("name", "Unknown Chat")
        messages = chat.get("messages", [])

        chat_config = chats_config_map.get(chat_id) if chat_id else None

        # Skip if inference is disabled in config
        if chat_config and not chat_config.get("infer", {}).get("enabled", True):
            console.print(f"  [dim]Skipping '{chat_name}': Inference disabled in config[/dim]")
            continue

        if not messages:
            console.print(f"  [dim]Skipping '{chat_name}': No messages[/dim]")
            continue

        # Filter messages based on ignore_keywords
        ignore_keywords = (
            chat_config.get("infer", {}).get("ignore_keywords", []) if chat_config else []
        )
        if ignore_keywords:
            ignore_kws = [kw.lower() for kw in ignore_keywords]
            filtered_messages = []
            for msg in messages:
                msg_text = msg.get("text", "").lower()
                if any(kw in msg_text for kw in ignore_kws):
                    continue
                filtered_messages.append(msg)
            messages = filtered_messages

        if not messages:
            console.print(f"  [dim]Skipping '{chat_name}': All messages ignored[/dim]")
            continue

        assignees = (
            chat_config.get("infer", {}).get("target_assignees", [settings.user_name])
            if chat_config
            else [settings.user_name]
        )
        custom_instructions = (
            chat_config.get("infer", {}).get("custom_instructions") if chat_config else None
        )

        for assignee in assignees:
            console.print(
                f"  Processing '{chat_name}' for assignee '{assignee}' "
                f"({len(messages)} messages)...",
                end=" ",
            )

            try:
                tasks = infer_tasks_from_chat(
                    chat_name=chat_name,
                    messages=messages,
                    user_name=assignee,
                    window_size=30,
                    custom_instructions=custom_instructions,
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
