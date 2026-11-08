from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = ROOT / "data" / "db" / "matchlens.duckdb"
EXCEL_PATH = INPUT_DIR / "matchlens_research_tracker.xlsx"
