"""
yearly_update.py - the once-a-year button.

Run it after FWP publishes new harvest numbers (usually spring/summer):
    python yearly_update.py
or double-click yearly_update.bat.

What it does, in order:
  1. Downloads every year of deer data FWP has (new years get picked up automatically)
  2. Runs the harvest agent to load it into hunting.db
  3. Rebuilds the website (docs/index.html)
  4. Rebuilds the Excel workbook (exports/Montana_Deer_Harvest.xlsx)
  5. Uploads everything to GitHub, which republishes the website
"""

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def step(n, text):
    print(f"\n=== Step {n}/5  {text} ===")


step(1, "Downloading deer harvest data from FWP")
from agents.fwp_fetch import fetch          # noqa: E402
fetch()

step(2, "Loading it into the database (harvest agent)")
from agents.harvest_agent import run        # noqa: E402
run()

step(3, "Building the website")
from build_site import build as build_site  # noqa: E402
build_site()

step(4, "Building the Excel workbook")
from export_excel import build as build_xl  # noqa: E402
build_xl()

step(5, "Uploading to GitHub")
if not shutil.which("git"):
    print("Git isn't installed, so nothing was uploaded. The site and workbook are updated locally.")
    sys.exit()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


git("add", "-A")
if git("diff", "--cached", "--quiet").returncode == 0:
    print("No changes since last time. FWP may not have published new numbers yet.")
else:
    git("commit", "-m", f"Yearly data update {date.today().isoformat()}")
    push = git("push")
    print(push.stdout or push.stderr or "Pushed.")
    print("Done. GitHub will republish the site in a minute or two.")
