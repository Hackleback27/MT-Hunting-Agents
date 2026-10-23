"""
fwp_fetch.py - downloads deer, elk and antelope harvest estimates from Montana FWP.

FWP's harvest page (myfwp.mt.gov/fwpPub/harvestReports) has a "Generate CSV"
button, but that CSV is broken: it returns deer numbers whatever species you
pick, and drops the column saying which license each row is for. So this uses
the page's "View Report" table instead, which is correct for every species.

Output: data/raw/harvest/fwp_harvest.csv with one row per district, species
and year (resident + nonresident totals). The raw HTML is kept next to it in
data/raw/harvest/html/ so you can see exactly what FWP returned.

Notes:
  - Deer hunter numbers are surveyed in odd years, elk and antelope in even
    years. In the other years FWP reports harvest only, hunters come back 0,
    and we store them as blank so success rates aren't faked.
  - Antelope districts have their own numbering (antelope 300 is not the same
    ground as deer/elk 300).
"""

import csv
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import requests

URL = "https://myfwp.mt.gov/fwpPub/reportResultsDiv_input.action"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "harvest"
SURVEYS = {"DE": "deer", "EL": "elk", "PA": "antelope"}
DEER_SPECIES = {"md": "mule deer", "wt": "whitetail"}
FIELDS = ["district", "species", "year", "hunters", "hunter_days", "harvest", "antlered", "antlerless"]


class TableParser(HTMLParser):
    """Collects every <tr> as a list of cell strings."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def num(text):
    try:
        return int(float(text.replace(",", "")))
    except (ValueError, AttributeError):
        return None


def parse_report(html: str, survey: str) -> list[dict]:
    """Turn one FWP report page into clean rows."""
    p = TableParser()
    p.feed(html)
    if not p.rows:
        return []
    head = [h.lower() for h in p.rows[0]]
    col = {name: i for i, name in enumerate(head)}

    def get(row, name):
        i = col.get(name)
        return row[i] if i is not None and i < len(row) else ""

    male = "bucks" if "bucks" in col else "bulls"
    female = "does" if "does" in col else "cows"
    out = []
    for r in p.rows[1:]:
        if get(r, "residency") != "SUM":
            continue                                         # keep resident + nonresident totals
        district = get(r, "hunting")
        if not re.fullmatch(r"\d{3}[A-Z]{0,2}", district):
            continue                                         # drop Reg_3, 3XX, State, etc.
        if survey == "DE":
            species = DEER_SPECIES.get(get(r, "deer species"))
            if not species:
                continue                                     # skip the all_deer total row
        else:
            species = SURVEYS[survey]
        hunters, days = num(get(r, "hunters")) or None, num(get(r, "days")) or None
        out.append({"district": district, "species": species, "year": num(get(r, "license year")),
                    "hunters": hunters, "hunter_days": days, "harvest": num(get(r, "total harvest")),
                    "antlered": num(get(r, male)), "antlerless": num(get(r, female))})
    return out


def download(survey: str, first: int, last: int) -> str:
    resp = requests.post(URL, timeout=120, data={
        "reportNm": "HarvestEstimates", "speciesCd": survey,
        "licYearStart": str(first), "licYearEnd": str(last), "districtId": "ALL",
    })
    resp.raise_for_status()
    return resp.text


def fetch(first_year: int = 2004, last_year: int | None = None) -> Path:
    """Download every species for first_year..this year (FWP's online estimates start in 2004).
    New years appear by themselves."""
    last_year = last_year or date.today().year
    (OUT_DIR / "html").mkdir(parents=True, exist_ok=True)
    rows = []
    for survey, name in SURVEYS.items():
        html = None
        for end in range(last_year, first_year - 1, -1):    # newest year may not be published yet
            try:
                html = download(survey, first_year, end)
            except requests.RequestException as e:
                print(f"  FWP {name} {first_year}-{end}: download failed ({e})")
                continue
            got = parse_report(html, survey)
            if got:
                break
        if not html or not got:
            print(f"  FWP {name}: no data returned")
            continue
        (OUT_DIR / "html" / f"{name}.html").write_text(html, encoding="utf-8")
        years = sorted({r["year"] for r in got})
        print(f"  FWP {name}: {len(got)} rows, {years[0]}-{years[-1]}")
        rows += got
    if not rows:
        raise SystemExit("FWP returned no harvest data. Check your internet connection or the FWP site.")
    out = OUT_DIR / "fwp_harvest.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"  saved {out.name}")
    return out


if __name__ == "__main__":
    fetch()
