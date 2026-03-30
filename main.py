import sys
from pathlib import Path

# Add src to python path to ensure imports work correctly
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from scraper.cli import app

if __name__ == "__main__":
    app()
