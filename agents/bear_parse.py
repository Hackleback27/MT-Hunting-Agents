"""
bear_parse.py - loads FWP's black bear quota page into the database.

FWP doesn't publish yearly black bear harvest estimates by district the way it
does for deer, elk and antelope. What it does publish is a live "quota status"
page: for each Bear Management Unit (BMU), the bears reported taken so far this
season, any female or total quota, and whether the unit is open or closed.
regs_fetch.py saves that page; this reads it.

    python -m agents.bear_parse
"""

import re
import sys
from datetime import date, datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from database import connect, log_run  # noqa: E402

AGENT = "bear_parse"
HTML = ROOT / "data" / "raw" / "regs" / "bear_quota.html"
REGS = ROOT / "data" / "raw" / "regs" / "bear_regs.html"

CARD = re.compile(r"BMU\s+(\d{3}[A-Z]?)([^:<]*):\s*([^<]+?)\s*--\s*(OPEN|CLOSED)", re.I)
ROW = re.compile(r"<tr>\s*(?:<!--.*?-->\s*)?<td>\s*(Total|Female|Male)\s*</td>\s*<td>\s*([^<]*?)\s*</td>"
                 r"\s*<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>", re.I | re.S)


def num(text):
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


def parse(html: str):
    updated = re.search(r"Status Updated:\s*([^<]+)", html)
    updated = unescape(updated.group(1)).strip() if updated else None
    year = date.today().year
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%B %d, %Y, %I:%M %p"):
        try:
            when = datetime.strptime(updated, fmt)
            year, updated = when.year, when.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
            break
        except (TypeError, ValueError):
            continue
    cards = list(CARD.finditer(html))
    for i, c in enumerate(cards):
        block = html[c.end(): cards[i + 1].start() if i + 1 < len(cards) else len(html)]
        rows = {r.group(1).title(): r for r in ROW.finditer(block)}
        total, female = rows.get("Total"), rows.get("Female")
        status_text = (total or female).group(4) if (total or female) else c.group(4)
        closed_on = re.search(r"\((\d\d/\d\d/\d{4})\)", status_text or "")
        unit = c.group(1) + (" (no hounds)" if "WITHOUT HOUNDS" in c.group(2).upper() else "")
        yield {
            "bmu": unit, "year": year, "season": c.group(3).strip().title(),
            "status": c.group(4).upper(), "closed_on": closed_on.group(1) if closed_on else None,
            "harvest": num(total.group(3)) if total else None,
            "total_quota": num(total.group(2)) if total else None,
            "female_harvest": num(female.group(3)) if female else None,
            "female_quota": num(female.group(2)) if female else None,
            "updated": updated,
        }


def parse_regs(html: str, year: int) -> dict:
    """Season dates and drawing-only units from FWP's black bear page."""
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())

    def grab(pattern):
        m = re.search(pattern, text, flags=re.I)
        return m.group(1).strip() if m else None

    def units(pattern):
        m = re.search(pattern, text, flags=re.I)
        return ",".join(re.findall(r"\d{3}", m.group(1))) if m else None

    return {
        "year": year,
        "spring": grab(r"Spring: ([A-Z][a-z]+\.? ?\d+ ?- ?[A-Z][a-z]+\.? ?\d+)"),
        "archery": grab(r"Archery: ([A-Z][a-z]+\.? ?\d+ ?- ?[A-Z][a-z]+\.? ?\d+)"),
        "fall": grab(r"Fall: ([A-Z][a-z]+\.? ?\d+ ?- ?[A-Z][a-z]+\.? ?\d+)"),
        "draw_bmus": units(r"permits ([\d, and]+?) are allotted by drawing"),
        "quota_bmus": units(r"In BMUs ([\d, and]+?) when the quota"),
    }


def run():
    if not HTML.exists():
        raise SystemExit("No bear page yet. Run: python -m agents.regs_fetch")
    rows = list(parse(HTML.read_text(encoding="utf-8")))
    conn = connect()
    if rows:
        conn.execute("DELETE FROM bear_harvest WHERE year = ?", (rows[0]["year"],))
    conn.executemany("""
        INSERT OR REPLACE INTO bear_harvest (bmu, year, season, status, closed_on, harvest,
            female_harvest, female_quota, total_quota, updated)
        VALUES (:bmu, :year, :season, :status, :closed_on, :harvest,
            :female_harvest, :female_quota, :total_quota, :updated)
    """, rows)
    if REGS.exists() and rows:
        regs = parse_regs(REGS.read_text(encoding="utf-8"), rows[0]["year"])
        conn.execute("""INSERT OR REPLACE INTO bear_regs (year, spring, archery, fall, draw_bmus, quota_bmus)
                        VALUES (:year, :spring, :archery, :fall, :draw_bmus, :quota_bmus)""", regs)
        print(f"  bear seasons {regs['year']}: spring {regs['spring']}, archery {regs['archery']}, "
              f"fall {regs['fall']}; drawing-only units: {regs['draw_bmus']}")
    conn.commit()
    log_run(conn, AGENT, len(rows), "ok" if rows else "error", rows[0]["updated"] if rows else "no units found")
    conn.close()
    total = sum(r["harvest"] or 0 for r in rows)
    print(f"  black bear: {len(rows)} units, {total} bears reported so far"
          + (f" (as of {rows[0]['updated']})" if rows else ""))
    return rows


if __name__ == "__main__":
    run()
