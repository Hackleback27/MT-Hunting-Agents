"""
regs_fetch.py - downloads this year's FWP regulations and the bear quota page.

  data/raw/regs/dea_regulations.pdf   Deer, Elk & Antelope regulations booklet
  data/raw/regs/bear_quota.html       Black bear harvest-so-far and quota status
  data/raw/regs/bear_regs.html        Black bear season dates and permit units

The booklet's web address changes every year, so the link is looked up on
FWP's elk regulations page each time.
"""

import re
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "regs"
REGS_PAGE = "https://fwp.mt.gov/hunt/regulations/elk"
FALLBACK_PDF = ("https://fwp.mt.gov/binaries/content/assets/fwp/hunt/regulations/2026/"
                "2026-dea-regulations-final-with-low-resolution-maps-for-web.pdf")
BEAR_QUOTA = "https://myfwp.mt.gov/fwpPub/speciesQuotaDiv"      # the table the quota page loads
BEAR_REGS = "https://fwp.mt.gov/hunt/regulations/black-bear"
HEADERS = {"User-Agent": "Mozilla/5.0 (Hunting Team data pull)"}


def booklet_url() -> str:
    try:
        html = requests.get(REGS_PAGE, timeout=60, headers=HEADERS).text
        links = re.findall(r'href="([^"]+dea[^"]*regulations[^"]*\.pdf)"', html, flags=re.I)
        if links:
            link = links[0]
            return link if link.startswith("http") else "https://fwp.mt.gov" + link
    except requests.RequestException:
        pass
    return FALLBACK_PDF


def fetch() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = booklet_url()
    print(f"  regulations booklet: {url.rsplit('/', 1)[-1]}")
    pdf = requests.get(url, timeout=180, headers=HEADERS)
    pdf.raise_for_status()
    (OUT_DIR / "dea_regulations.pdf").write_bytes(pdf.content)
    (OUT_DIR / "dea_regulations_url.txt").write_text(url)
    print(f"  saved dea_regulations.pdf ({len(pdf.content) / 1e6:.1f} MB)")

    bear = requests.post(BEAR_QUOTA, timeout=60, headers=HEADERS, data={
        "wmrSpeciesCd": "BB", "regsSpeciesCd": "", "district": "", "speciesName": "Black Bear", "licYear": ""})
    bear.raise_for_status()
    (OUT_DIR / "bear_quota.html").write_text(bear.text, encoding="utf-8")
    print("  saved bear_quota.html")

    regs = requests.get(BEAR_REGS, timeout=60, headers=HEADERS)
    regs.raise_for_status()
    (OUT_DIR / "bear_regs.html").write_text(regs.text, encoding="utf-8")
    print("  saved bear_regs.html")


if __name__ == "__main__":
    fetch()
