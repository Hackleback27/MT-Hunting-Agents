# Hunting Team: Montana hunting districts

A small team of Python scripts and AI agents that pull Montana FWP harvest
estimates (mule deer, whitetail, elk, antelope), this year's regulations
(general vs draw, legal animals, season dates) and black bear quota status
into one database (`hunting.db`), then publish them as a website and an
Excel workbook.

Live site: https://hackleback27.github.io/MT-Hunting-Agents/

## Once a year

After FWP posts the new season's harvest estimates (usually spring or summer),
double-click **`yearly_update.bat`**. It downloads the new data, loads it,
rebuilds the website and the workbook, and pushes to GitHub, which republishes
the site.

## What's in here

| File | Job |
|---|---|
| `agents/fwp_fetch.py` | Script: downloads deer, elk and antelope harvest estimates from FWP |
| `agents/regs_fetch.py` | Script: downloads the regulations booklet and bear quota page |
| `agents/regs_parse.py` | Script: reads the booklet into general/draw status and hunting opportunities |
| `agents/bear_parse.py` | Script: loads black bear harvest so far and season dates |
| `agents/harvest_agent.py` | Agent: uses Claude to map any harvest file's columns, then saves rows |
| `agents/llm.py` | Shared helper for asking Claude for JSON |
| `database.py` | The shared SQLite database every agent writes into |
| `build_site.py` | Builds `docs/index.html`, the public website (GitHub Pages) |
| `export_excel.py` | Builds `exports/Montana_Hunting_Districts.xlsx` with charts |
| `dashboard.py` | Local Flask dashboard at http://127.0.0.1:5000 |
| `yearly_update.py` | Runs all of the above in order |

## Setting up on another computer

1. Install [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win).
2. In VS Code: **Clone Git Repository** and pick this repo.
3. In the VS Code terminal:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Create a file called `.env` with your key: `ANTHROPIC_API_KEY=sk-ant-...`
   (it is never uploaded to GitHub).

Before working, click **Sync** (or run `git pull`) to get the latest. When you're done, commit and push.
