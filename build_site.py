"""
build_site.py - turns hunting.db into a website you can open anywhere.

    python build_site.py

It writes docs/index.html. GitHub Pages serves the docs/ folder as a public
website, so after you push to GitHub the site updates by itself.

What goes into the page:
  - harvest estimates for mule deer, whitetail, elk and antelope (all years)
  - this year's regulations per district: general vs drawing, and every
    hunting opportunity (license, legal animal, season dates)
  - black bear harvest so far this season by bear management unit
No server needed: the result is one static HTML file.
"""

import json
from datetime import date
from pathlib import Path

from database import connect

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "site.html"
OUT = ROOT / "docs" / "index.html"


def build():
    conn = connect()
    q = lambda sql, *a: [dict(r) for r in conn.execute(sql, a)]

    harvest = [[r["district"], r["species"], r["year"], r["hunters"], r["hunter_days"], r["harvest"],
                r["antlered"], r["antlerless"]]
               for r in q("""SELECT district, species, year, hunters, hunter_days, harvest, antlered, antlerless
                             FROM harvest_stats WHERE harvest IS NOT NULL ORDER BY species, district, year""")]
    if not harvest:
        raise SystemExit("No harvest data in hunting.db yet. Run yearly_update.py first.")

    reg_year = (q("SELECT MAX(year) AS y FROM district_access")[0]["y"]) or None
    access, opps = {}, {}
    for r in q("SELECT * FROM district_access WHERE year = ?", reg_year):
        access.setdefault(r["species"], {})[r["district"]] = [r["access"], r["district_name"], r["has_permits"]]
    for r in q("""SELECT * FROM reg_opportunities WHERE year = ?
                  ORDER BY district, species, CASE kind WHEN 'general' THEN 0 WHEN 'permit' THEN 1 ELSE 2 END""",
               reg_year):
        opps.setdefault(r["species"], {}).setdefault(r["district"], []).append(
            [r["kind"], r["how"], r["license"], r["legal_animal"], r["early"], r["archery"], r["general"],
             r["muzzleloader"], r["late"], r["apply_by"], r["quota"], r["details"]])

    bear_year = q("SELECT MAX(year) AS y FROM bear_harvest")[0]["y"]
    bear = q("""SELECT bmu, status, closed_on, harvest, female_harvest, female_quota, total_quota, updated
                FROM bear_harvest WHERE year = ? ORDER BY bmu""", bear_year) if bear_year else []
    bear_regs = (q("SELECT * FROM bear_regs WHERE year = ?", bear_year) or [None])[0] if bear_year else None
    conn.close()

    data = {
        "built": date.today().isoformat(),
        "harvest": harvest,
        "years": sorted({r[2] for r in harvest}),
        "regYear": reg_year, "access": access, "opps": opps,
        "bear": {"year": bear_year, "units": bear, "regs": bear_regs},
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    # "</" is escaped so the data can never close the <script> tag early.
    html = html.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    (OUT.parent / ".nojekyll").touch()   # tells GitHub Pages to serve the file as-is
    print(f"Built {OUT.relative_to(ROOT)}  ({len(harvest):,} harvest rows, "
          f"{sum(len(v) for d in opps.values() for v in d.values()):,} regulation rows, "
          f"{len(bear)} bear units, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
