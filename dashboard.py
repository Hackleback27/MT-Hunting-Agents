"""
dashboard.py - a small web app for exploring hunting.db in your browser.

Run it:
    python dashboard.py
then open http://127.0.0.1:5000 in your browser. Press Ctrl+C in the terminal to stop it.

How it fits together:
  - Flask is the web server. Each @app.route below is one URL.
  - "/" sends the page (templates/dashboard.html).
  - "/api/..." routes send data as JSON. The page's JavaScript calls them
    and draws charts with Chart.js.
"""

from flask import Flask, jsonify, render_template, request

from database import connect

app = Flask(__name__)

# Columns the page is allowed to sort by (whitelist, so nobody can inject SQL).
SORTABLE = {
    "hunter_days": "hunter_days DESC",
    "harvest": "harvest DESC",
    "success_rate": "success_rate DESC",
    "days_per_kill": "days_per_kill ASC",     # fewer days per animal = better
}


def query(sql, params=()):
    conn = connect()
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()
    return rows


@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/api/options")
def options():
    """Species and years available, for the dropdowns."""
    species = [r["species"] for r in query("SELECT DISTINCT species FROM harvest_stats ORDER BY species")]
    years = [r["year"] for r in query("SELECT DISTINCT year FROM harvest_stats ORDER BY year DESC")]
    return jsonify(species=species, years=years)


@app.route("/api/summary")
def summary():
    """Statewide totals for one species and year (the cards at the top)."""
    sp, yr = request.args["species"], int(request.args["year"])
    row = query("""
        SELECT COUNT(*) AS districts, SUM(harvest) AS harvest,
               SUM(hunter_days) AS hunter_days
        FROM harvest_stats WHERE species = ? AND year = ?
    """, (sp, yr))[0]
    best = query("""
        SELECT district, harvest FROM harvest_stats
        WHERE species = ? AND year = ? ORDER BY harvest DESC LIMIT 1
    """, (sp, yr))
    row["top_district"] = best[0] if best else None
    return jsonify(row)


@app.route("/api/top")
def top():
    """Top districts for one species and year, sorted by the chosen metric."""
    sp, yr = request.args["species"], int(request.args["year"])
    sort = request.args.get("sort") if request.args.get("sort") in SORTABLE else "hunter_days"
    min_hunters = int(request.args.get("min_hunters", 100))

    # Some years (FWP skipped the hunter survey) have harvest but no hunter counts.
    # Rankings that need hunter counts can't work for those years, so fall back to harvest.
    has_effort = query("SELECT COALESCE(SUM(hunters > 0), 0) AS n FROM harvest_stats WHERE species = ? AND year = ?",
                       (sp, yr))[0]["n"] > 0
    note = None
    if not has_effort and sort != "harvest":
        sort, note = "harvest", f"FWP didn't survey hunter numbers in {yr}, so districts are ranked by harvest."

    where = "species = ? AND year = ? AND harvest IS NOT NULL"
    params = [sp, yr]
    if has_effort:                       # the min-hunters filter only makes sense when counts exist
        where += " AND COALESCE(hunters, 0) >= ?"
        params.append(min_hunters)
    rows = query(f"""
        SELECT district, hunters, hunter_days, harvest, success_rate, days_per_kill
        FROM harvest_stats WHERE {where}
        ORDER BY {SORTABLE[sort]} LIMIT 25
    """, params)
    return jsonify(rows=rows, sort=sort, note=note, has_effort=has_effort)


@app.route("/api/trend/<district>")
def trend(district):
    """Every year of data for one district (the line chart)."""
    sp = request.args["species"]
    rows = query("""
        SELECT year, hunters, hunter_days, harvest, success_rate
        FROM harvest_stats WHERE district = ? AND species = ? ORDER BY year
    """, (district, sp))
    return jsonify(rows)


if __name__ == "__main__":
    print("Dashboard running at http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(debug=True)
