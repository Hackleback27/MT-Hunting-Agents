"""
harvest_agent.py - Agent #1: loads FWP harvest estimates into the database.

How to use:
  1. Export harvest estimates from FWP (CSV or Excel) and drop the files in
     data/raw/harvest/
  2. Run:  python -m agents.harvest_agent

The agent shows Claude the top of each file/sheet, Claude works out which
row is the header and which column is district / species / year / hunters /
hunter days / harvest, and the agent then cleans and saves every row.
Re-running is safe: rows are updated, not duplicated.
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import connect, log_run          # noqa: E402
from agents.llm import ask_json                # noqa: E402

AGENT = "harvest_agent"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "harvest"
FIELDS = ["district", "species", "year", "hunters", "hunter_days", "harvest"]

SYSTEM = """You map messy wildlife harvest spreadsheets onto a fixed schema.
You will see the first rows of one sheet, with 0-based row and column numbers.
Return:
{
  "skip": false,                 // true if this sheet has no per-district harvest table
  "reason": "",                  // short explanation if skip is true
  "header_row": 0,               // row number holding the column headers
  "columns": {                   // column number for each field, or null if absent
    "district": 0, "species": null, "year": null,
    "hunters": 1, "hunter_days": 2, "harvest": 3
  },
  "constants": {                 // values that apply to every row when there is no column for them
    "species": "elk",            // infer from file name, sheet name or title rows; null if unknown
    "year": 2024
  }
}
"harvest" means TOTAL animals harvested (not just bulls, cows, bucks or does), if a total exists.
Species should be one of: elk, mule deer, whitetail, antelope, moose, bighorn sheep,
mountain goat, black bear, mountain lion, wolf, turkey, or another plain lower-case name."""

SPECIES_ALIASES = {
    "white-tailed deer": "whitetail", "whitetail deer": "whitetail", "white tail": "whitetail",
    "white-tail": "whitetail", "mule": "mule deer", "muley": "mule deer",
    "pronghorn": "antelope", "pronghorn antelope": "antelope", "bear": "black bear",
    "lion": "mountain lion", "bighorn": "bighorn sheep", "sheep": "bighorn sheep",
    "goat": "mountain goat",
}


def blank(value):
    return value is None or str(value).strip() == ""


def to_int(value):
    """'1,234' -> 1234; blanks and junk -> None."""
    if blank(value):
        return None
    text = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def clean_district(value):
    """Keep real district numbers like '313' or '260A'; drop 'Total', 'Region 3', blanks."""
    if blank(value):
        return None
    text = str(value).strip()
    text = re.sub(r"\.0$", "", text)               # 313.0 -> 313
    text = re.sub(r"^(HD|District)\s*", "", text, flags=re.I)
    return text if re.fullmatch(r"\d{2,3}[A-Za-z]?", text) else None


def clean_species(value):
    if blank(value):
        return None
    text = str(value).strip().lower()
    return SPECIES_ALIASES.get(text, text) or None


def read_sheets(path: Path):
    """Yield (sheet_name, list of rows) for a CSV or Excel file. Every cell is a string."""
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            yield "csv", [row for row in csv.reader(f)]
    else:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            yield ws.title, [["" if c is None else str(c) for c in row]
                             for row in ws.iter_rows(values_only=True)]


def map_sheet(path: Path, sheet: str, rows: list) -> dict:
    """Work out the sheet's layout. Our own clean files skip Claude; anything else asks Claude."""
    if rows and [c.strip().lower() for c in rows[0][:6]] == FIELDS:
        return {"skip": False, "header_row": 0, "columns": {f: i for i, f in enumerate(FIELDS)},
                "constants": {}}
    preview = "\n".join(f"row {i}: " + " | ".join(f"[{j}] {c}" for j, c in enumerate(r))
                        for i, r in enumerate(rows[:15]))
    prompt = (f"File name: {path.name}\nSheet name: {sheet}\n"
              f"Total rows: {len(rows)}\n\nFirst rows ([n] is the column number):\n{preview}")
    return ask_json(SYSTEM, prompt)


def extract_rows(sheet_rows: list, plan: dict, source: str):
    cols, consts = plan.get("columns", {}), plan.get("constants", {}) or {}
    rows = []
    for r in sheet_rows[int(plan.get("header_row", 0)) + 1:]:
        get = lambda f: r[cols[f]] if cols.get(f) is not None and cols[f] < len(r) else None
        district = clean_district(get("district"))
        species = clean_species(get("species")) or clean_species(consts.get("species"))
        year = to_int(get("year")) or to_int(consts.get("year"))
        if not (district and species and year):
            continue
        hunters, days, harvest = to_int(get("hunters")), to_int(get("hunter_days")), to_int(get("harvest"))
        rows.append({
            "district": district, "species": species, "year": year,
            "hunters": hunters, "hunter_days": days, "harvest": harvest,
            "success_rate": round(harvest / hunters, 3) if hunters and harvest is not None else None,
            "days_per_kill": round(days / harvest, 1) if days and harvest else None,
            "source_file": source,
        })
    return rows


def save(conn, rows):
    conn.executemany("""
        INSERT INTO harvest_stats (district, species, year, hunters, hunter_days, harvest,
                                   success_rate, days_per_kill, source_file)
        VALUES (:district, :species, :year, :hunters, :hunter_days, :harvest,
                :success_rate, :days_per_kill, :source_file)
        ON CONFLICT(district, species, year) DO UPDATE SET
            hunters=excluded.hunters, hunter_days=excluded.hunter_days,
            harvest=excluded.harvest, success_rate=excluded.success_rate,
            days_per_kill=excluded.days_per_kill, source_file=excluded.source_file,
            collected_at=datetime('now')
    """, rows)
    conn.commit()


def run():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in sorted(RAW_DIR.iterdir())
             if p.suffix.lower() in (".csv", ".xlsx", ".xls") and not p.name.startswith("~$")]
    if not files:
        print(f"No files found. Put FWP harvest exports (CSV/Excel) in:\n  {RAW_DIR}")
        return

    conn = connect()
    total = 0
    for path in files:
        for sheet, data in read_sheets(path):
            label = f"{path.name} [{sheet}]"
            try:
                plan = map_sheet(path, sheet, data)
                if plan.get("skip"):
                    print(f"  skipped {label}: {plan.get('reason', '')}")
                    continue
                rows = extract_rows(data, plan, path.name)
                save(conn, rows)
                total += len(rows)
                print(f"  {label}: saved {len(rows)} rows "
                      f"(species={plan.get('constants', {}).get('species')}, header row {plan.get('header_row')})")
            except Exception as e:
                print(f"  ERROR on {label}: {e}")
                log_run(conn, AGENT, 0, "error", f"{label}: {e}")
    log_run(conn, AGENT, total, "ok", f"{len(files)} file(s)")
    print(f"\nDone. {total} harvest rows in the database.")


if __name__ == "__main__":
    run()
