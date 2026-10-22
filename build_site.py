"""
build_site.py - turns hunting.db into a website you can open anywhere.

    python build_site.py

It writes docs/index.html. GitHub Pages serves the docs/ folder as a public
website, so after you push to GitHub the site updates by itself.

How it works:
  - Reads every harvest row from the database.
  - Bakes the data into templates/site.html (the page's JavaScript draws the
    charts and tables in the browser).
  - No server needed: the result is one static HTML file.
"""

import json
from datetime import date
from pathlib import Path

from database import connect

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "site.html"
OUT = ROOT / "docs" / "index.html"


def load_rows():
    conn = connect()
    rows = conn.execute("""
        SELECT district, species, year, hunters, hunter_days, harvest
        FROM harvest_stats
        WHERE harvest IS NOT NULL
        ORDER BY species, district, year
    """).fetchall()
    conn.close()
    # Compact lists instead of dicts keep the page small.
    return [[r["district"], r["species"], r["year"], r["hunters"], r["hunter_days"], r["harvest"]]
            for r in rows]


def build():
    rows = load_rows()
    if not rows:
        raise SystemExit("No harvest data in hunting.db yet. Run run_all.py first.")

    years = sorted({r[2] for r in rows})
    data = {
        "columns": ["district", "species", "year", "hunters", "hunter_days", "harvest"],
        "rows": rows,
        "built": date.today().isoformat(),
        "years": years,
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    # "</" is escaped so the data can never close the <script> tag early.
    html = html.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    (OUT.parent / ".nojekyll").touch()   # tells GitHub Pages to serve the file as-is
    print(f"Built {OUT.relative_to(ROOT)}  ({len(rows):,} rows, {years[0]}-{years[-1]}, "
          f"{OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
