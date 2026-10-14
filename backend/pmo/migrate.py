"""Apply the initial schema revision; safe to rerun against an initialized DB."""
from pathlib import Path
from dotenv import load_dotenv
from .storage import database

if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    engine, _ = database()
    engine.dispose()
    print("Schema revision 1 is ready.")
