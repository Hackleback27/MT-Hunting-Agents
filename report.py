"""
report.py - quick look at what's in the database.

    python report.py                 # top districts for every species
    python report.py elk             # just elk
"""

import sys
from database import connect

conn = connect()
species_filter = " ".join(sys.argv[1:]).lower() or None

latest = conn.execute("SELECT MAX(year) FROM harvest_stats").fetchone()[0]
if latest is None:
    print("No harvest data yet. Run:  python -m agents.harvest_agent")
    sys.exit()

species_list = [species_filter] if species_filter else [
    r[0] for r in conn.execute("SELECT DISTINCT species FROM harvest_stats ORDER BY species")]

for sp in species_list:
    rows = conn.execute("""
        SELECT district, year, hunters, hunter_days, harvest, success_rate, days_per_kill
        FROM harvest_stats
        WHERE species = ? AND year = (SELECT MAX(year) FROM harvest_stats WHERE species = ?)
        ORDER BY hunter_days DESC LIMIT 10
    """, (sp, sp)).fetchall()
    if not rows:
        print(f"\nNo data for '{sp}'.")
        continue
    print(f"\n=== {sp.upper()} - most popular districts ({rows[0]['year']}, by hunter days) ===")
    print(f"{'District':<10}{'Hunters':>9}{'Days':>9}{'Harvest':>9}{'Success':>9}{'Days/kill':>11}")
    for r in rows:
        succ = f"{r['success_rate']:.0%}" if r["success_rate"] is not None else "-"
        dpk = f"{r['days_per_kill']:.1f}" if r["days_per_kill"] else "-"
        print(f"{r['district']:<10}{r['hunters'] or 0:>9,}{r['hunter_days'] or 0:>9,}"
              f"{r['harvest'] or 0:>9,}{succ:>9}{dpk:>11}")
