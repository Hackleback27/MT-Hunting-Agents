"""
fwp_fetch.py - downloads deer harvest estimates straight from Montana FWP.

FWP's harvest search (myfwp.mt.gov/fwpPub/harvestReports) has a "Generate CSV"
button. This does the same request directly, keeps the clean, labeled deer rows
(mule deer / whitetail), and saves them in data/raw/harvest/ in our own format.

Note: FWP's CSV also contains unlabeled rows for elk, moose, sheep and goat
("na" in the species column). Those can't be told apart reliably, so they are
skipped on purpose. Elk will come from a different FWP source.
"""

import csv
import io
import re
from datetime import date
from pathlib import Path

import requests

URL = "https://myfwp.mt.gov/fwpPub/downloadHarvReports.action"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "harvest"
SPECIES = {"md": "mule deer", "wt": "whitetail"}


def download_deer(year: int) -> list[dict]:
    resp = requests.post(URL, timeout=60, data={
        "fileType": "CSV", "fileName": "fwpHarvestEstimatesReport",
        "survey": "DE", "startYr": str(year), "endYr": str(year), "district": "",
    })
    resp.raise_for_status()
    rows = []
    reader = csv.reader(io.StringIO(resp.text))
    next(reader, None)                                  # skip header
    for r in reader:
        if len(r) < 8:
            continue
        yr, district, sp, residency = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
        if residency != "SUM" or sp not in SPECIES:
            continue                                    # keep resident+nonresident totals only
        if not re.fullmatch(r"\d{3}[A-Z]?", district):
            continue                                    # drop Reg_3, 3XX, State, etc.
        # FWP leaves hunters/days at 0 in years it didn't survey effort (e.g. 2022, 2024).
        # Store those as blank (missing), not zero, so success rates aren't faked.
        hunters, days = int(r[4]) or None, int(r[5]) or None
        rows.append({"district": district, "species": SPECIES[sp], "year": int(yr),
                     "hunters": hunters, "hunter_days": days, "harvest": int(r[7])})
    return rows


def fetch(first_year: int = 2021, last_year: int | None = None) -> Path:
    """Download every year from first_year up to this year.

    FWP posts a season's estimates the following year, so the newest year
    is often not out yet. Years with no rows are skipped, which means you
    never have to edit this file: just re-run it once FWP publishes.
    """
    last_year = last_year or date.today().year
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows, found = [], []
    for y in range(first_year, last_year + 1):
        try:
            rows = download_deer(y)
        except requests.RequestException as e:
            print(f"  FWP deer {y}: download failed ({e}), skipping")
            continue
        if not rows:
            print(f"  FWP deer {y}: not published yet")
            continue
        print(f"  FWP deer {y}: {len(rows)} district rows")
        all_rows += rows
        found.append(y)
    if not all_rows:
        raise SystemExit("FWP returned no deer data. Check your internet connection or the FWP site.")
    out = OUT_DIR / f"fwp_deer_{min(found)}-{max(found)}.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["district", "species", "year", "hunters", "hunter_days", "harvest"])
        w.writeheader()
        w.writerows(all_rows)
    print(f"  saved {out.name}")
    return out


if __name__ == "__main__":
    fetch()
