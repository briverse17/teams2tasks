"""CLI commands for managing chats_config.yaml."""

# ruff: noqa: B008

from typing import Any

import typer
import yaml
from rich.console import Console

from ..config import settings

config_app = typer.Typer(help="Configure chat scraping and inference settings")
console = Console()


def load_config() -> dict[str, Any]:
    """Load configuration from chats_config.yaml.

    Returns:
        dict[str, Any]: The loaded configuration dictionary.

    Raises:
        Exit: If the configuration file does not exist or has invalid content.

    """
    yaml_path = settings.chats_config_path
    if not yaml_path.exists():
        console.print(f"[red]Error: {yaml_path} not found.[/red]")
        raise typer.Exit(1)
    with open(yaml_path, encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {"chats": []}
        except Exception as e:
            console.print(f"[red]Error reading chats_config.yaml: {e}[/red]")
            raise typer.Exit(1) from e


def save_config(data: dict[str, Any]) -> None:
    """Save configuration to chats_config.yaml.

    Args:
        data: The configuration data to save.

    Raises:
        Exit: If saving the configuration to the file fails.

    """
    yaml_path = settings.chats_config_path
    try:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        console.print(f"[red]Error saving config to chats_config.yaml: {e}[/red]")
        raise typer.Exit(1) from e


def cast_value(new_value_str: str, original_value: object) -> object:
    """Cast string value to the type of the original value.

    Args:
        new_value_str: The string representation of the new value.
        original_value: The original value to determine the type from.

    Returns:
        object: The casted value of the same type as the original value.

    """
    if isinstance(original_value, bool):
        return new_value_str.lower() in ["true", "t", "yes", "y", "1"]
    elif isinstance(original_value, int):
        return int(new_value_str)
    elif isinstance(original_value, list):
        return [item.strip() for item in new_value_str.split(",") if item.strip()]
    return new_value_str


def prompt_field(prompt_text: str, current_value: object) -> object:
    """Prompt user for a value, showing the current value as default.

    Args:
        prompt_text: The prompt message to display.
        current_value: The current/default value of the field.

    Returns:
        object: The new value entered by the user, or the current value if empty.

    """
    if isinstance(current_value, list):
        display_val = ", ".join(str(item) for item in current_value)
    else:
        display_val = str(current_value)

    user_input = input(f"  {prompt_text} [{display_val}]: ").strip()
    if not user_input:
        return current_value

    if isinstance(current_value, bool):
        return user_input.lower() in ["true", "t", "yes", "y", "1"]
    elif isinstance(current_value, int):
        try:
            return int(user_input)
        except ValueError:
            console.print(
                f"  [yellow]Invalid integer. Keeping existing value: {current_value}[/yellow]"
            )
            return current_value
    elif isinstance(current_value, list):
        return [item.strip() for item in user_input.split(",") if item.strip()]
    return user_input


def run_interactive_menu(chats: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Run interactive keyboard/menu navigation for chats.

    Args:
        chats: List of configured chat dictionaries.

    Returns:
        dict[str, Any] | None: The selected chat dictionary, or None if exit.

    """
    num_chats = len(chats)
    if num_chats == 0:
        console.print("[yellow]No chats found in configuration.[/yellow]")
        return None

    try:
        import msvcrt
        selected_idx = 0
        while True:
            console.clear()
            console.print(
                "[bold cyan]Navigate with Up/Down arrows. "
                "Press Enter to edit, or Esc/q to exit.[/bold cyan]\n"
            )

            for idx, chat in enumerate(chats):
                indicator = "-> " if idx == selected_idx else "   "
                color = "green bold" if idx == selected_idx else "white"
                console.print(
                    f"[{color}]{indicator}{chat.get('name', 'Unknown')} "
                    f"({chat.get('type', 'unknown')})[/] - "
                    f"[dim]{chat.get('id', '')}[/dim]"
                )

            key = None
            while key is None:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\x00', b'\xe0'):
                        ch2 = msvcrt.getch()
                        if ch2 == b'H':
                            key = "up"
                        elif ch2 == b'P':
                            key = "down"
                    elif ch in (b'\r', b'\n'):
                        key = "enter"
                    elif ch in (b'\x1b', b'q', b'Q'):
                        key = "quit"

            if key == "up":
                selected_idx = (selected_idx - 1) % num_chats
            elif key == "down":
                selected_idx = (selected_idx + 1) % num_chats
            elif key == "enter":
                return chats[selected_idx]
            elif key == "quit":
                return None
    except ImportError:
        console.print("[bold cyan]Select a chat by entering its number:[/bold cyan]\n")
        for idx, chat in enumerate(chats):
            console.print(
                f"  [{idx + 1}] {chat.get('name', 'Unknown')} "
                f"({chat.get('type', '')}) - [dim]{chat.get('id', '')}[/dim]"
            )

        while True:
            try:
                choice = input("\nEnter choice (or 'q' to quit): ").strip()
                if choice.lower() in ['q', 'quit']:
                    return None
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < num_chats:
                    return chats[choice_idx]
                console.print("[red]Invalid choice. Try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")


def edit_chat_fields_iteratively(chat: dict[str, Any]) -> None:
    """Edit chat config fields one by one.

    Args:
        chat: The chat dictionary to modify in-place.

    """
    console.print(
        f"\n[bold green]Editing chat: {chat.get('name', 'Unknown')} "
        f"({chat.get('id', '')})[/bold green]"
    )
    console.print("[dim]Press Enter to keep the current value shown in brackets.[/dim]\n")

    # 1. Top level name & type
    chat["name"] = prompt_field("Chat Name", chat.get("name", ""))
    chat["type"] = prompt_field("Chat Type (group/one-on-one/personal)", chat.get("type", ""))

    # 2. Scrape group
    scrape = chat.setdefault("scrape", {})
    scrape["enabled"] = prompt_field(
        "Scrape Enabled (true/false)", scrape.get("enabled", True)
    )
    scrape["priority"] = prompt_field(
        "Scrape Priority (high/medium/low)", scrape.get("priority", "medium")
    )
    scrape["sync_depth_days"] = prompt_field(
        "Scrape Sync Depth (days)", scrape.get("sync_depth_days", 7)
    )

    # 3. Infer group
    infer = chat.setdefault("infer", {})
    infer["enabled"] = prompt_field(
        "Task Inference Enabled (true/false)", infer.get("enabled", True)
    )
    infer["target_assignees"] = prompt_field(
        "Task Target Assignees (comma-separated)",
        infer.get("target_assignees", ["Nguyen Minh Vu"]),
    )
    infer["ignore_keywords"] = prompt_field(
        "Task Ignore Keywords (comma-separated)", infer.get("ignore_keywords", [])
    )
    infer["custom_instructions"] = prompt_field(
        "Task Custom Instructions", infer.get("custom_instructions", "")
    )

    # 4. Metadata group
    metadata = chat.setdefault("metadata", {})
    metadata["category"] = prompt_field(
        "Metadata Category", metadata.get("category", "general")
    )
    metadata["status"] = prompt_field(
        "Metadata Status (active/archived)", metadata.get("status", "active")
    )

    console.print("\n[green]Chat configuration updated successfully![/green]")


@config_app.command(name="list")
def list_chats() -> None:
    """List all configured chats and their basic settings."""
    config_data = load_config()
    chats = config_data.get("chats", [])
    if not chats:
        console.print("[yellow]No chats configured.[/yellow]")
        return

    console.print("[bold cyan]Configured Chats:[/bold cyan]\n")
    for chat in chats:
        c_id = chat.get("id", "N/A")
        name = chat.get("name", "Unknown")
        c_type = chat.get("type", "group")
        scrape_enabled = chat.get("scrape", {}).get("enabled", True)
        infer_enabled = chat.get("infer", {}).get("enabled", True)

        scrape_status = "[green]Yes[/green]" if scrape_enabled else "[red]No[/red]"
        infer_status = "[green]Yes[/green]" if infer_enabled else "[red]No[/red]"

        console.print(
            f"  - [bold]{name}[/bold] ({c_type}) - Scrape: {scrape_status} | "
            f"Infer: {infer_status}\n"
            f"    [dim]ID: {c_id}[/dim]\n"
        )


@config_app.command(name="edit")
def edit_chat(
    chat_id: str | None = typer.Argument(
        None, help="The target Chat ID to configure. If omitted, launches menu."
    ),
) -> None:
    """Launch the interactive menu, or edit a specific chat iteratively.

    Args:
        chat_id: The specific Chat ID to edit. If not provided, launches interactive menu.

    """
    config_data = load_config()
    chats = config_data.get("chats", [])

    if chat_id is None:
        target_chat = run_interactive_menu(chats)
        if target_chat is None:
            console.print("[yellow]No chat selected. Exiting.[/yellow]")
            return
        edit_chat_fields_iteratively(target_chat)
        save_config(config_data)
        return

    # Find matching chat by ID
    target_chat = None
    for chat in chats:
        if chat.get("id") == chat_id:
            target_chat = chat
            break

    if not target_chat:
        console.print(f"[red]Error: Chat with ID '{chat_id}' not found in chats_config.yaml[/red]")
        raise typer.Exit(1)

    edit_chat_fields_iteratively(target_chat)
    save_config(config_data)


@config_app.command(name="get")
def get_config(
    chat_id: str = typer.Argument(..., help="The target Chat ID"),
    field_path: str | None = typer.Argument(
        None, help="Specific field path (e.g. 'scrape.priority')"
    ),
) -> None:
    """Get the current configuration details for a specific chat or field.

    Args:
        chat_id: The target Chat ID to query.
        field_path: The dot-separated path to a nested field. If None, prints all details.

    Raises:
        Exit: If the chat ID or the field path is invalid.

    """
    config_data = load_config()
    chats = config_data.get("chats", [])

    target_chat = None
    for chat in chats:
        if chat.get("id") == chat_id:
            target_chat = chat
            break

    if not target_chat:
        console.print(f"[red]Error: Chat with ID '{chat_id}' not found in chats_config.yaml[/red]")
        raise typer.Exit(1)

    if field_path is None:
        # Print all details as YAML snippet
        console.print(f"[bold green]Configuration for '{target_chat.get('name')}':[/bold green]")
        yaml_str = yaml.safe_dump(
            target_chat, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        console.print(yaml_str)
        return

    # Print specific field
    try:
        if "." in field_path:
            group, subfield = field_path.split(".", 1)
            if group not in target_chat or not isinstance(target_chat[group], dict):
                console.print(f"[red]Error: Invalid field path '{field_path}'[/red]")
                raise typer.Exit(1)
            if subfield not in target_chat[group]:
                console.print(f"[red]Error: Invalid field path '{field_path}'[/red]")
                raise typer.Exit(1)
            console.print(f"{field_path}: {target_chat[group][subfield]}")
        else:
            if field_path not in target_chat:
                console.print(f"[red]Error: Invalid field path '{field_path}'[/red]")
                raise typer.Exit(1)
            console.print(f"{field_path}: {target_chat[field_path]}")
    except Exception as e:
        console.print(f"[red]Error retrieving field value: {e}[/red]")
        raise typer.Exit(1) from e


@config_app.command(name="set")
def set_config(
    chat_id: str = typer.Argument(..., help="The target Chat ID"),
    field_path: str = typer.Argument(
        ..., help="Specific field path to update (e.g. 'scrape.priority')"
    ),
    new_value: str = typer.Argument(..., help="New value for the field"),
) -> None:
    """Update a configuration field value directly.

    Args:
        chat_id: The target Chat ID to update.
        field_path: The dot-separated path to a nested field.
        new_value: The new value string to cast and assign to the field.

    Raises:
        Exit: If the chat ID or field path is invalid or casting fails.

    """
    config_data = load_config()
    chats = config_data.get("chats", [])

    target_chat = None
    for chat in chats:
        if chat.get("id") == chat_id:
            target_chat = chat
            break

    if not target_chat:
        console.print(f"[red]Error: Chat with ID '{chat_id}' not found in chats_config.yaml[/red]")
        raise typer.Exit(1)

    try:
        if "." in field_path:
            group, subfield = field_path.split(".", 1)
            if group not in target_chat:
                console.print(f"[red]Error: Invalid field group '{group}'[/red]")
                raise typer.Exit(1)
            if not isinstance(target_chat[group], dict):
                console.print(
                    f"[red]Error: Field '{group}' is not a nested configuration group[/red]"
                )
                raise typer.Exit(1)
            if subfield not in target_chat[group]:
                console.print(f"[red]Error: Invalid subfield '{subfield}' in '{group}'[/red]")
                raise typer.Exit(1)

            orig_val = target_chat[group][subfield]
            target_chat[group][subfield] = cast_value(new_value, orig_val)
        else:
            if field_path not in target_chat:
                console.print(f"[red]Error: Invalid field '{field_path}'[/red]")
                raise typer.Exit(1)
            orig_val = target_chat[field_path]
            target_chat[field_path] = cast_value(new_value, orig_val)

        save_config(config_data)
        console.print(
            f"[green]Successfully updated '{field_path}' of chat "
            f"'{target_chat.get('name')}' to: {new_value}[/green]"
        )
    except Exception as e:
        console.print(f"[red]Error performing update: {e}[/red]")
        raise typer.Exit(1) from e
