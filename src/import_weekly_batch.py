from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "input"
TRACKER = INPUT / "matchlens_research_tracker.xlsx"
BATCH = INPUT / "weekly_matches_2026_W44.csv"
META = INPUT / "weekly_metadata_2026_W44.csv"
DATES = INPUT / "match_dates.csv"
WEEKLY_META = INPUT / "weekly_metadata.csv"


def append_unique(existing, new, key):
    existing_keys = set(existing[key].astype(int)) if not existing.empty else set()
    return pd.concat([existing, new[~new[key].astype(int).isin(existing_keys)]], ignore_index=True)


def main():
    if not TRACKER.exists():
        raise FileNotFoundError(f"Tracker not found: {TRACKER}")

    batch = pd.read_csv(BATCH)
    metadata = pd.read_csv(META)

    wb = load_workbook(TRACKER)
    ws = wb["Core Match Data"]
    existing_ids = {int(ws.cell(r, 1).value) for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value is not None}
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

    added = 0
    for _, row in batch.iterrows():
        match_id = int(row["Match ID"])
        if match_id in existing_ids:
            continue
        ws.append([None if pd.isna(row.get(h)) else row.get(h) for h in headers])
        existing_ids.add(match_id)
        added += 1

    wb.save(TRACKER)

    date_rows = metadata[["match_id", "match_date"]].copy()
    if DATES.exists():
        dates = pd.read_csv(DATES)
        dates = append_unique(dates, date_rows, "match_id")
    else:
        dates = date_rows
    dates.sort_values("match_id").to_csv(DATES, index=False)

    if WEEKLY_META.exists():
        weekly = pd.read_csv(WEEKLY_META)
        weekly = append_unique(weekly, metadata, "match_id")
    else:
        weekly = metadata
    weekly.sort_values("match_id").to_csv(WEEKLY_META, index=False)

    print(f"Weekly batch imported. Added {added} matches. Tracker now contains {len(existing_ids)} matches.")


if __name__ == "__main__":
    main()
