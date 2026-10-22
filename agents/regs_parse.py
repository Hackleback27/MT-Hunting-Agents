"""
regs_parse.py - reads FWP's Deer, Elk & Antelope regulations booklet (PDF) and
pulls out, for every hunting district:

  - what you can shoot (legal animal), on which license, and the season dates
  - whether the district is GENERAL (a general license lets you hunt the
    buck/bull) or LIMITED (the buck/bull needs a permit you draw for)

Run after regs_fetch.py:
    python -m agents.regs_parse

How "general" vs "limited" is decided, per district and species:
  general  - a General License row allows an antlered or either-sex animal
             (ignoring youth-only / PTHFV-only rows)
  limited  - no such row, but a Permit (drawing) allows one
  antlerless only - only antlerless opportunities
  Antelope licenses are all by drawing, so antelope is always limited.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from database import connect, log_run  # noqa: E402

AGENT = "regs_parse"
PDF = ROOT / "data" / "raw" / "regs" / "dea_regulations.pdf"
CACHE = ROOT / "data" / "raw" / "regs" / "dea_regulations.txt"

MON = r"(?:Jan|Feb|Mar|Apr|April|May|Jun|June|Jul|July|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
DATE = rf"{MON} ?\d{{1,2}} ?- ?{MON} ?\d{{1,2}}"
D_OR_DASH = rf"({DATE}|-)"
APPLY = rf"((?:OTC: ?)?{MON} \d{{1,2}}|-)"
QUOTA = r"(UNL|[\d,]+|-)"
RANGE = r"([\d,]+ ?- ?[\d,]+|-)"

DE_LICENSE = r"(General (?:Deer|Elk) License|(?:Deer|Elk) B License: \d{3}-\d{2}|(?:Deer|Elk) Permit: \d{3}-\d{2})"
DE_ANIMAL = (r"((?:Either-sex|Antlered Buck|Antlerless only|Antlerless|Brow-tined Bull or Antlerless|"
             r"Brow-tined Bull|Spike Bull or Antlerless|Spike Bull|Antlered Bull|Antlered)"
             r" (?:White-tailed Deer|Mule Deer|deer Deer|Deer|Elk))")
DE_ROW = re.compile(rf"(?:{DE_LICENSE} )?{DE_ANIMAL} {APPLY} {QUOTA} {RANGE} "
                    rf"{D_OR_DASH} {D_OR_DASH} {D_OR_DASH} {D_OR_DASH} {D_OR_DASH}")

PA_LICENSE = r"(Antelope (?:B )?License: \d{3}-\d{2})"
PA_ROW = re.compile(rf"{PA_LICENSE} (Either-sex|Doe/Fawn|Buck|Antlered Buck) {APPLY} {QUOTA} {RANGE} "
                    rf"{D_OR_DASH} {D_OR_DASH}")

HEADER = re.compile(r"HD (\d{3}[A-Z]{0,2}(?: [NSEW])?) ?- ?")
HEADER_END = re.compile(r" (?:NOTE:|Note:|NOTE |DEER |ELK |Antelope (?:B )?License:)")


def pdf_text() -> str:
    """Whole booklet as one line of text. Cached, because reading the PDF takes a minute."""
    if CACHE.exists() and CACHE.stat().st_mtime >= PDF.stat().st_mtime:
        return CACHE.read_text(encoding="utf-8")
    from pypdf import PdfReader
    print("  reading the regulations PDF (about a minute)...")
    pages = [p.extract_text() or "" for p in PdfReader(PDF).pages]
    text = " ".join(" ".join(pages).split())
    CACHE.write_text(text, encoding="utf-8")
    return text


BOILERPLATE = [
    r"HD \d{3}[A-Z]?(?: [NSEW])? ?- ?[^|]{0,80}?- Continued on the Next Page",
    r"\d{1,3} Hunters using archery equipment, see page \d+ for licensing requirements\.",
    r"Hunters using archery equipment, see page \d+ for licensing requirements\.",
    r"(?:Deer & Elk|Antelope HD) Regulations",
    r"Turn In Poachers\. Enough is Enough! ?TIPMONT\.MT\.GOV",
    r"LICENSE/PERMIT OPPORTUNITY APPL ?Y BY DATE QUOTA QUOTA RANGE EARL ?Y SEASON DATES ARCHERY ONL ?Y SEASON "
    r"DATES GENERAL SEASON DATES HERITAGE MUZZLELOADER SEASON DATES LATE SEASON DATES OPPORTUNITY SPECIFIC "
    r"DETAILS AND/OR RESTRICTIONS",
    r"License Opportunity Apply by Date Quota Quota Range Archery Season Dates Season Dates "
    r"Opportunity Specif?i?c Information/ Restrictions",
    r"20\\d\\d Deer • Elk • Antelope Visit fwp\.mt\.gov \d{1,3}",
]


def strip_boilerplate(text: str) -> str:
    """Remove page headers/footers that land in the middle of district tables."""
    text = text.replace("Antelope HD Regulations", " ANTELOPE_SECTION ", 1)
    for pat in BOILERPLATE:
        text = re.sub(pat, " ", text)
    return " ".join(text.split())


def booklet_year(text: str) -> int:
    m = re.search(r"\b(20\d\d) Deer\W+Elk\W+Antelope", text)
    return int(m.group(1)) if m else 0


def sections(text: str, start: int, end: int):
    """Yield (district, name, body) for each 'HD 313-Gardiner' block between start and end.
    '- Continued' blocks are merged into the district they continue."""
    hits = [m for m in HEADER.finditer(text, start, end)]
    out = {}
    order = []
    for i, m in enumerate(hits):
        stop = hits[i + 1].start() if i + 1 < len(hits) else end
        rest = text[m.end():stop]
        cut = HEADER_END.search(" " + rest)
        name = (rest[:cut.start()] if cut else rest[:60]).strip()
        body = rest[len(name):]
        cont = name.endswith("Continued")
        name = re.sub(r"\s*-\s*Continued.*$", "", name).strip()
        d = m.group(1).replace(" ", "")
        if d not in out:
            out[d] = [name, ""]
            order.append(d)
        out[d][1] += " " + body
        if not cont and len(name) > len(out[d][0]):
            out[d][0] = name
    for d in order:
        yield d, out[d][0], out[d][1]


FOOTER = re.compile(r" (?:Turn In Poachers|\d{1,3} (?:Antelope HD|Deer & Elk) Regulations|\d{1,3} Contact List|\d{1,3} Hunters using|HD \d{3}[A-Z]? ?- ?[^.]*?Continued|Region \d(?= HD | Portions)|Portions of HDs)")
STRAY_COLUMNS = re.compile(rf"(?:(?:{DATE}|-) ){{3,}}(?:{DATE}|-)?")


def tidy_details(text: str) -> str | None:
    """Notes column only: drop page footers and leftover date columns from wrapped rows."""
    text = FOOTER.split(" " + text)[0]
    text = STRAY_COLUMNS.sub(" ", text + " ")
    text = re.sub(r"\s+", " ", text).strip(" -")
    text = re.sub(r"\s*\b\d{1,3}$", "", text)          # stray page number
    return text[:300] or None


def clean(s):
    return None if s in (None, "-") else re.sub(r"\s+", " ", s).replace(" -", "-").replace("- ", "-")


def license_kind(lic: str, apply: str) -> tuple[str, str]:
    """('general' | 'b_license' | 'permit' | 'license', 'general' | 'otc' | 'draw')"""
    if lic.startswith("General"):
        return "general", "general"
    kind = "permit" if "Permit" in lic else "b_license" if "B License" in lic else "license"
    return kind, "otc" if apply and apply.startswith("OTC") else "draw"


def species_of(animal: str) -> list[str]:
    if "White-tailed" in animal:
        return ["whitetail"]
    if "Mule Deer" in animal:
        return ["mule deer"]
    if animal.endswith("Deer"):
        return ["mule deer", "whitetail"]
    return ["elk"]


def parse_deer_elk(text: str):
    start = text.find("HD 100-")
    end = text.find("ANTELOPE_SECTION")
    if start < 0:
        raise SystemExit("Couldn't find the deer & elk district tables in the booklet.")
    end = end if end > start else len(text)
    for district, name, body in sections(text, start, end):
        matches = list(DE_ROW.finditer(body))
        lic = None
        for i, m in enumerate(matches):
            nxt = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            details = body[m.end():nxt]
            details = re.split(r" (?:DEER|ELK) (?=General|Deer|Elk)", details)[0]
            # a block's header word (DEER/ELK) can sit right before the next license name
            details = re.sub(r"\s*\b(?:DEER|ELK)\s*$", "", details)
            lic = m.group(1) or lic
            if lic is None:
                continue
            animal = m.group(2).replace("deer Deer", "Deer")
            kind, how = license_kind(lic, m.group(3))
            for sp in species_of(animal):
                yield {
                    "district": district, "district_name": name, "species": sp,
                    "license": lic, "kind": kind, "how": how, "legal_animal": animal,
                    "apply_by": clean(m.group(3)), "quota": clean(m.group(4)),
                    "early": clean(m.group(6)), "archery": clean(m.group(7)),
                    "general": clean(m.group(8)), "muzzleloader": clean(m.group(9)),
                    "late": clean(m.group(10)), "details": tidy_details(details),
                }


def antelope_rows(district, name, body):
    matches = list(PA_ROW.finditer(body))
    for i, m in enumerate(matches):
        nxt = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        lic = m.group(1)
        kind, how = license_kind(lic, m.group(3))
        animal = {"Doe/Fawn": "Doe/Fawn Antelope"}.get(m.group(2), m.group(2) + " Antelope")
        yield {
            "district": district, "district_name": name, "species": "antelope",
            "license": lic, "kind": kind, "how": how, "legal_animal": animal,
            "apply_by": clean(m.group(3)), "quota": clean(m.group(4)),
            "early": None, "archery": clean(m.group(6)), "general": clean(m.group(7)),
            "muzzleloader": None, "late": None, "details": tidy_details(body[m.end():nxt]),
        }


PORTIONS = re.compile(r"Portions of HDs ([\d, and]+?) (North|South) of the Yellowstone River")


def parse_antelope(text: str):
    start = text.find("ANTELOPE_SECTION")
    if start < 0:
        return
    end = text.find("Contact List", start)
    end = end if end > 0 else len(text)
    for district, name, body in sections(text, start, end):
        body = PORTIONS.split(body)[0]          # region-wide blocks are handled below
        yield from antelope_rows(district, name, body)
    # Region 7 lists licenses for groups of districts north/south of the Yellowstone.
    blocks = list(PORTIONS.finditer(text, start, end))
    for i, b in enumerate(blocks):
        stop = blocks[i + 1].start() if i + 1 < len(blocks) else end
        side = b.group(2).lower()
        for d in re.findall(r"\d{3}", b.group(1)):
            yield from antelope_rows(d, f"Region 7 ({side} of the Yellowstone)", text[b.end():stop])


def is_antlered(animal: str) -> bool:
    return not animal.startswith("Antlerless") and not animal.startswith("Doe/Fawn")


def restricted_to_few(details: str | None) -> bool:
    d = (details or "").lower()
    return "only youth" in d or "pthfv" in d or d.startswith("only hunters with")


def classify(opps: list[dict]) -> str:
    if opps and opps[0]["species"] == "antelope":
        return "limited"
    if any(o["kind"] == "general" and is_antlered(o["legal_animal"]) and not restricted_to_few(o["details"])
           and (o["archery"] or o["general"]) for o in opps):
        return "general"
    if any(o["kind"] == "permit" and is_antlered(o["legal_animal"]) for o in opps):
        return "limited"
    if opps:
        return "antlerless only"
    return "closed"


def run():
    if not PDF.exists():
        raise SystemExit("No regulations PDF yet. Run: python -m agents.regs_fetch")
    raw = pdf_text()
    year = booklet_year(raw)
    text = strip_boilerplate(raw)
    opps, seen = [], set()
    for o in list(parse_deer_elk(text)) + list(parse_antelope(text)):
        key = (o["district"], o["species"], o["license"], o["legal_animal"], o["archery"], o["general"])
        if key not in seen:                          # same license listed twice for one district
            seen.add(key)
            opps.append(o)

    groups = {}
    for o in opps:
        groups.setdefault((o["district"], o["species"]), []).append(o)

    conn = connect()
    conn.execute("DELETE FROM reg_opportunities WHERE year = ?", (year,))
    conn.execute("DELETE FROM district_access WHERE year = ?", (year,))
    conn.executemany("""
        INSERT INTO reg_opportunities (district, species, year, license, kind, how, legal_animal,
            apply_by, quota, early, archery, general, muzzleloader, late, details)
        VALUES (:district, :species, :year, :license, :kind, :how, :legal_animal,
            :apply_by, :quota, :early, :archery, :general, :muzzleloader, :late, :details)
    """, [{**o, "year": year} for o in opps])
    conn.executemany("""
        INSERT INTO district_access (district, species, year, district_name, access, has_permits)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [(d, sp, year, g[0]["district_name"], classify(g),
           int(any(o["kind"] == "permit" for o in g))) for (d, sp), g in groups.items()])
    conn.commit()
    counts = {}
    for (d, sp), g in groups.items():
        counts.setdefault(sp, {}).setdefault(classify(g), 0)
        counts[sp][classify(g)] += 1
    log_run(conn, AGENT, len(opps), "ok", f"{year} booklet")
    conn.close()
    print(f"  {year} regulations: {len(opps)} hunting opportunities in {len(groups)} district/species pairs")
    for sp, c in sorted(counts.items()):
        print(f"    {sp:<10} " + ", ".join(f"{k}: {v}" for k, v in sorted(c.items())))
    return opps


if __name__ == "__main__":
    run()
