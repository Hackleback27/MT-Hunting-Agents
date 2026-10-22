"""
export_excel.py - writes the database out as an Excel workbook with charts.

    python export_excel.py

Creates exports/Montana_Hunting_Districts.xlsx with these sheets:
  Summary         statewide totals per species and year (formulas) + line chart
  Top Districts   best-odds districts per species for its latest surveyed year,
                  with General / Draw status, + bar charts
  Trends          every district's harvest by year, colour-shaded, with % change
  Regulations     every hunting opportunity from this year's booklet
  Black Bear      this season's bear harvest and quota status by unit
  Data            every harvest row, as a filterable Excel table

Uses openpyxl only (pure Python), so it runs even with Smart App Control on.
"""

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from database import connect

ROOT = Path(__file__).parent
OUT = ROOT / "exports" / "Montana_Hunting_Districts.xlsx"
SPECIES = ["mule deer", "whitetail", "elk", "antelope"]
COLORS = {"mule deer": "A0522D", "whitetail": "2F5D3A", "elk": "6B4E9B", "antelope": "C08A1E"}
MALE = {"mule deer": "Bucks", "whitetail": "Bucks", "elk": "Bulls", "antelope": "Bucks"}
TOP_N = 25

FONT = "Arial"
H1 = Font(name=FONT, size=16, bold=True, color="1F2A22")
H2 = Font(name=FONT, size=12, bold=True, color="2F5D3A")
BOLD = Font(name=FONT, bold=True)
BODY = Font(name=FONT)
NOTE = Font(name=FONT, italic=True, size=9, color="5D6A60")
HEAD_FILL = PatternFill("solid", fgColor="2F5D3A")
HEAD_FONT = Font(name=FONT, bold=True, color="FFFFFF")
GEN_FILL = PatternFill("solid", fgColor="E2EFE2")
DRAW_FILL = PatternFill("solid", fgColor="F8E6D6")


def load():
    conn = connect()
    q = lambda sql, *a: [dict(r) for r in conn.execute(sql, a)]
    rows = q("""SELECT district, species, year, hunters, hunter_days, harvest, antlered, antlerless
                FROM harvest_stats WHERE harvest IS NOT NULL ORDER BY species, district, year""")
    reg_year = q("SELECT MAX(year) AS y FROM district_access")[0]["y"]
    access = {(r["district"], r["species"]): r for r in q("SELECT * FROM district_access WHERE year = ?", reg_year)}
    opps = q("SELECT * FROM reg_opportunities WHERE year = ? ORDER BY species, district", reg_year)
    bear_year = q("SELECT MAX(year) AS y FROM bear_harvest")[0]["y"]
    bear = q("SELECT * FROM bear_harvest WHERE year = ? ORDER BY bmu", bear_year) if bear_year else []
    conn.close()
    return rows, reg_year, access, opps, bear


def access_label(access, district, species):
    a = access.get((district, species)) or access.get((district.rstrip("NSEW"), species))
    if not a:
        return ""
    return {"general": "General", "limited": "Draw"}.get(a["access"], a["access"].title())


def header(ws, row, labels, start_col=1):
    for i, text in enumerate(labels):
        c = ws.cell(row=row, column=start_col + i, value=text)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
        c.alignment = Alignment(horizontal="center", wrap_text=True)


def widths(ws, sizes):
    for col, w in sizes.items():
        ws.column_dimensions[col].width = w


def shade(cell, label):
    if label == "General":
        cell.fill = GEN_FILL
    elif label == "Draw":
        cell.fill = DRAW_FILL


def data_sheet(wb, rows, access):
    ws = wb.create_sheet("Data")
    labels = ["District", "Region", "Species", "Year", "License", "Hunters", "Hunter days", "Harvest",
              "Bucks/Bulls", "Does/Cows", "Per hunter", "Days per animal"]
    header(ws, 1, labels)
    for i, r in enumerate(rows, start=2):
        lab = access_label(access, r["district"], r["species"])
        ws.append([r["district"], int(r["district"][0]), r["species"], r["year"], lab,
                   r["hunters"], r["hunter_days"], r["harvest"], r["antlered"], r["antlerless"],
                   f'=IF(F{i}>0,H{i}/F{i},"")', f'=IF(AND(G{i}>0,H{i}>0),G{i}/H{i},"")'])
        for c in ws[i]:
            c.font = BODY
        shade(ws[f"E{i}"], lab)
        for col in "FGHIJ":
            ws[f"{col}{i}"].number_format = "#,##0"
        ws[f"K{i}"].number_format = "0%"
        ws[f"L{i}"].number_format = "0.0"
    last = len(rows) + 1
    tab = Table(displayName="Harvest", ref=f"A1:L{last}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium7", showRowStripes=True)
    ws.add_table(tab)
    ws.freeze_panes = "A2"
    widths(ws, {"A": 10, "B": 8, "C": 12, "D": 8, "E": 10, "F": 10, "G": 12, "H": 10, "I": 12, "J": 11, "K": 11, "L": 10})
    return last


def summary_sheet(wb, years, last):
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Montana big game harvest, statewide"
    ws["A1"].font = H1
    ws["A2"] = "Totals are formulas over the Data sheet, so they update if you edit it."
    ws["A2"].font = NOTE
    header(ws, 4, ["Year"] + [s.title() for s in SPECIES])
    for i, y in enumerate(years, start=5):
        ws[f"A{i}"] = y
        ws[f"A{i}"].font = BODY
        for k, sp in enumerate(SPECIES):
            col = get_column_letter(2 + k)
            ws[f"{col}{i}"] = (f'=SUMIFS(Data!$H$2:$H${last},Data!$C$2:$C${last},"{sp}",'
                               f'Data!$D$2:$D${last},$A{i})')
            ws[f"{col}{i}"].number_format = "#,##0"
            ws[f"{col}{i}"].font = BODY
    end = 4 + len(years)

    chart = LineChart()
    chart.title = "Animals harvested statewide"
    chart.y_axis.title = "Animals"
    chart.y_axis.numFmt = "#,##0"
    chart.height, chart.width = 8, 17
    chart.add_data(Reference(ws, min_col=2, max_col=1 + len(SPECIES), min_row=4, max_row=end), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=5, max_row=end))
    for s, sp in zip(chart.series, SPECIES):
        s.graphicalProperties.line.solidFill = COLORS[sp]
        s.graphicalProperties.line.width = 28000
        s.smooth = False
    ws.add_chart(chart, "H4")

    notes = [
        "Source: Montana FWP harvest estimates (myfwp.mt.gov).",
        "Hunter numbers are surveyed every other year: deer in odd years, elk and antelope in even years.",
        "General = buck/bull on a general license. Draw = buck/bull needs a permit or license from a drawing (lottery).",
        "Antelope districts use their own numbering. Antelope licenses are all by drawing.",
    ]
    for k, n in enumerate(notes):
        ws[f"A{end + 2 + k}"] = n
        ws[f"A{end + 2 + k}"].font = NOTE
    widths(ws, {"A": 10, "B": 13, "C": 13, "D": 13, "E": 13})


def top_sheet(wb, rows, access):
    ws = wb.create_sheet("Top Districts")
    ws["A1"] = "Best-odds districts by species"
    ws["A1"].font = H1
    ws["A2"] = ("Ranked by harvest per hunter, districts with 100+ hunters, using each species' latest surveyed year. "
                "Draw districts usually rank high because hunter numbers are capped.")
    ws["A2"].font = NOTE

    col = 1
    for sp in SPECIES:
        surveyed = sorted({r["year"] for r in rows if r["species"] == sp and r["hunters"]})
        if not surveyed:
            continue
        year = surveyed[-1]
        pick = [r for r in rows if r["species"] == sp and r["year"] == year and (r["hunters"] or 0) >= 100]
        pick.sort(key=lambda r: r["harvest"] / r["hunters"], reverse=True)
        pick = pick[:TOP_N]
        c0 = get_column_letter(col)
        ws[f"{c0}4"] = f"{sp.title()}, {year}"
        ws[f"{c0}4"].font = H2
        header(ws, 5, ["#", "District", "License", "Hunters", "Harvest", MALE[sp], "Per hunter"], start_col=col)
        for i, r in enumerate(pick, start=6):
            L = [get_column_letter(col + k) for k in range(7)]
            lab = access_label(access, r["district"], sp)
            vals = [i - 5, r["district"], lab, r["hunters"], r["harvest"], r["antlered"], f"={L[4]}{i}/{L[3]}{i}"]
            for k, (v, fmt) in enumerate(zip(vals, ["0", "@", "@", "#,##0", "#,##0", "#,##0", "0%"])):
                c = ws[f"{L[k]}{i}"]
                c.value, c.number_format, c.font = v, fmt, BODY
            shade(ws[f"{L[2]}{i}"], lab)
        for k, w in enumerate([5, 9, 9, 9, 9, 9, 10]):
            ws.column_dimensions[get_column_letter(col + k)].width = w

        bar = BarChart()
        bar.type = "bar"
        bar.title = f"{sp.title()}: top 10 by harvest per hunter"
        bar.y_axis.numFmt = "0%"
        bar.y_axis.majorGridlines = None
        bar.legend = None
        bar.height, bar.width = 8, 12
        n = min(10, len(pick))
        bar.add_data(Reference(ws, min_col=col + 6, min_row=5, max_row=5 + n), titles_from_data=True)
        bar.set_categories(Reference(ws, min_col=col + 1, min_row=6, max_row=5 + n))
        bar.x_axis.scaling.orientation = "maxMin"      # #1 at the top
        bar.series[0].graphicalProperties.solidFill = COLORS[sp]
        ws.add_chart(bar, f"{c0}{8 + TOP_N}")
        col += 8
    ws.freeze_panes = "A6"


def trends_sheet(wb, rows, years, access):
    ws = wb.create_sheet("Trends")
    ws["A1"] = "Harvest by district and year"
    ws["A1"].font = H1
    ws["A2"] = "Darker green = more animals taken (shaded per species). Change compares the first and latest year."
    ws["A2"].font = NOTE

    table = defaultdict(dict)
    for r in rows:
        table[(r["species"], r["district"])][r["year"]] = r["harvest"]

    row = 4
    for sp in SPECIES:
        ws.cell(row=row, column=1, value=sp.title()).font = H2
        row += 1
        header(ws, row, ["District", "License"] + [str(y) for y in years] + ["Change"])
        first = row + 1
        for district in sorted(d for s, d in table if s == sp):
            row += 1
            vals = table[(sp, district)]
            ws.cell(row=row, column=1, value=district).font = BOLD
            lab = access_label(access, district, sp)
            c = ws.cell(row=row, column=2, value=lab)
            c.font = BODY
            shade(c, lab)
            for k, y in enumerate(years):
                c = ws.cell(row=row, column=3 + k, value=vals.get(y))
                c.number_format, c.font = "#,##0", BODY
            a, b = get_column_letter(3), get_column_letter(2 + len(years))
            c = ws.cell(row=row, column=3 + len(years),
                        value=f'=IF(AND(ISNUMBER({a}{row}),{a}{row}>0,ISNUMBER({b}{row})),{b}{row}/{a}{row}-1,"")')
            c.number_format, c.font = "+0%;-0%;0%", BODY
        rng = f"C{first}:{get_column_letter(2 + len(years))}{row}"
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color="FFFDF8",
                                                          end_type="percentile", end_value=95, end_color="5E9C6A"))
        chg = f"{get_column_letter(3 + len(years))}{first}:{get_column_letter(3 + len(years))}{row}"
        ws.conditional_formatting.add(chg, ColorScaleRule(start_type="num", start_value=-0.6, start_color="E8A397",
                                                          mid_type="num", mid_value=0, mid_color="FFFFFF",
                                                          end_type="num", end_value=0.6, end_color="9CCB9F"))
        row += 3
    widths(ws, {"A": 10, "B": 10})
    for k in range(len(years) + 1):
        ws.column_dimensions[get_column_letter(3 + k)].width = 10
    ws.freeze_panes = "C4"


def regs_sheet(wb, opps, reg_year):
    ws = wb.create_sheet("Regulations")
    ws["A1"] = f"{reg_year} hunting opportunities by district"
    ws["A1"].font = H1
    ws["A2"] = ("Read automatically from FWP's Deer, Elk & Antelope regulations booklet. "
                "Always check the official booklet before you hunt.")
    ws["A2"].font = NOTE
    labels = ["District", "Species", "License", "How you get it", "Legal animal", "Archery", "General (rifle)",
              "Muzzleloader", "Late", "Apply by", "Quota", "Details"]
    header(ws, 4, labels)
    how = {"general": "General license", "otc": "Over the counter", "draw": "Drawing"}
    for i, o in enumerate(opps, start=5):
        vals = [o["district"], o["species"], o["license"], how.get(o["how"], o["how"]), o["legal_animal"],
                o["archery"], o["general"], o["muzzleloader"], o["late"], o["apply_by"], o["quota"], o["details"]]
        for k, v in enumerate(vals):
            c = ws.cell(row=i, column=1 + k, value=v)
            c.font = BODY
        if o["how"] == "general":
            ws.cell(row=i, column=4).fill = GEN_FILL
        elif o["how"] == "draw":
            ws.cell(row=i, column=4).fill = DRAW_FILL
    last = 4 + len(opps)
    if opps:
        tab = Table(displayName="Regulations", ref=f"A4:L{last}")
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(tab)
    ws.freeze_panes = "A5"
    widths(ws, {"A": 9, "B": 11, "C": 22, "D": 16, "E": 30, "F": 15, "G": 15, "H": 14, "I": 14,
                "J": 10, "K": 8, "L": 70})


def bear_sheet(wb, bear):
    ws = wb.create_sheet("Black Bear")
    year = bear[0]["year"] if bear else ""
    ws["A1"] = f"Black bear harvest {year}, season so far"
    ws["A1"].font = H1
    ws["A2"] = (f"From FWP's quota status page{', updated ' + bear[0]['updated'] if bear else ''}. "
                "FWP doesn't publish multi-year bear harvest by district.")
    ws["A2"].font = NOTE
    header(ws, 4, ["BMU", "Status", "Closed on", "Bears reported", "Female harvest", "Female quota", "Total quota"])
    for i, b in enumerate(bear, start=5):
        for k, v in enumerate([b["bmu"], b["status"], b["closed_on"], b["harvest"], b["female_harvest"],
                               b["female_quota"], b["total_quota"]]):
            c = ws.cell(row=i, column=1 + k, value=v)
            c.font = BODY
        ws.cell(row=i, column=2).fill = DRAW_FILL if b["status"] == "CLOSED" else GEN_FILL
    widths(ws, {"A": 16, "B": 10, "C": 12, "D": 15, "E": 15, "F": 13, "G": 12})


def build():
    rows, reg_year, access, opps, bear = load()
    if not rows:
        raise SystemExit("No harvest data in hunting.db yet. Run yearly_update.py first.")
    years = sorted({r["year"] for r in rows})
    wb = Workbook()
    last = data_sheet(wb, rows, access)
    summary_sheet(wb, years, last)
    top_sheet(wb, rows, access)
    trends_sheet(wb, rows, years, access)
    regs_sheet(wb, opps, reg_year)
    bear_sheet(wb, bear)
    wb.move_sheet("Data", offset=len(wb.sheetnames))
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
