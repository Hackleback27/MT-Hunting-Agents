"""
yearly_update.py - the once-a-year button.

Run it after FWP publishes new harvest numbers and regulations (usually
spring/summer):
    python yearly_update.py
or double-click yearly_update.bat.

The Hunting Team, in order:
  1. fwp_fetch      downloads deer, elk and antelope harvest estimates
  2. regs_fetch     downloads the regulations booklet and the bear quota page
  3. harvest_agent  loads harvest files into hunting.db (asks Claude to map
                    any file it doesn't recognise)
  4. regs_parse     reads the booklet: general vs draw, legal animals, dates
  5. bear_parse     loads black bear harvest so far and season dates
  6. build_site     rebuilds the website (docs/index.html)
  7. export_excel   rebuilds the Excel workbook
  8. uploads everything to GitHub, which republishes the website
"""

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# pypdf reads the regulations PDF. It's pure Python, so Smart App Control allows it.
try:
    import pypdf  # noqa: F401
except ImportError:
    print("Installing pypdf (reads the regulations PDF)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pypdf"])

STEPS = 8


def step(n, text):
    print(f"\n=== Step {n}/{STEPS}  {text} ===")


step(1, "Downloading harvest estimates from FWP")
from agents.fwp_fetch import fetch as fetch_harvest   # noqa: E402
fetch_harvest()

step(2, "Downloading regulations and bear quota status")
from agents.regs_fetch import fetch as fetch_regs     # noqa: E402
fetch_regs()

step(3, "Loading harvest into the database (harvest agent)")
from agents.harvest_agent import run as run_harvest   # noqa: E402
run_harvest()

step(4, "Reading the regulations booklet")
from agents.regs_parse import run as run_regs         # noqa: E402
run_regs()

step(5, "Loading black bear data")
from agents.bear_parse import run as run_bear         # noqa: E402
run_bear()

step(6, "Building the website")
from build_site import build as build_site            # noqa: E402
build_site()

step(7, "Building the Excel workbook")
from export_excel import build as build_xl            # noqa: E402
build_xl()

step(8, "Uploading to GitHub")
# A terminal opened before Git was installed doesn't know where Git is, so check the usual places too.
GIT = shutil.which("git") or next((p for p in [
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"),
] if os.path.exists(p)), None)
if not GIT:
    print("Git isn't installed, so nothing was uploaded. The site and workbook are updated locally.")
    sys.exit()


def git(*args):
    return subprocess.run([GIT, *args], cwd=ROOT, text=True, capture_output=True)


git("add", "-A")
if git("diff", "--cached", "--quiet").returncode == 0:
    print("No changes since last time. FWP may not have published new numbers yet.")
else:
    git("commit", "-m", f"Data update {date.today().isoformat()}")
    push = git("push")
    print(push.stdout or push.stderr or "Pushed.")
    print("Done. GitHub will republish the site in a minute or two.")
