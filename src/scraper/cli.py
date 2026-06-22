"""CLI entrypoint for Teams scraper and task inference."""

import typer

from .commands.config import config_app
from .commands.infer import infer_app
from .commands.scrape import scrape_app

app = typer.Typer(help="Professional MS Teams Scraper CLI")

# Register sub-typer applications
app.add_typer(scrape_app, name="scrape")
app.add_typer(infer_app, name="infer")
app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()
