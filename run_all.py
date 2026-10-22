"""
run_all.py - one click does everything:
  1. installs any missing library
  2. creates the database
  3. downloads deer harvest data from FWP
  4. runs the harvest agent (Claude maps the columns, data is saved)
  5. prints the most popular districts

In VS Code: open this file and click the Run button (triangle, top right).
"""

import subprocess
import sys
from pathlib import Path

print("Step 1/5  Checking libraries...")
try:
    import openpyxl  # noqa: F401  (reads Excel files; pure Python)
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "openpyxl"])

print("Step 2/5  Creating database...")
from database import connect          # noqa: E402
connect()

print("Step 3/5  Downloading deer harvest data from Montana FWP...")
from agents.fwp_fetch import fetch    # noqa: E402
fetch()

print("Step 4/5  Running harvest agent...")
from agents.harvest_agent import run  # noqa: E402
run()

print("\nStep 5/5  Most popular districts:")
for sp in ("mule deer", "whitetail"):
    subprocess.call([sys.executable, str(Path(__file__).parent / "report.py"), sp])
