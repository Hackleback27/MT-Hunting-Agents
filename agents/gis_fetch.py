"""
gis_fetch.py - downloads hunting district boundaries from FWP's map service.

  data/gis/deer_elk.geojson   deer & elk hunting districts
  data/gis/antelope.geojson   antelope hunting districts
  data/gis/bear.geojson       black bear management units

These feed the map on the website's Biology tab. Shapes are simplified
(about 1 km accuracy) so the page stays small. FWP's map service hands out a
short-lived public access key to anyone who opens its Hunt Planner map; this
asks for one the same way.
"""

import json
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "gis"
SESSION = ("https://fwp.mt.gov/gis/sessionInfo?forceProd=false&forceTest=false&forcePub=false"
           "&protocol=https%3A&hostName=fwp.mt.gov&agsVersion=10.5")
SERVICE = "https://fwp-gis.mt.gov/arcgis/rest/services/wild/huntPlannerNew/MapServer"
LAYERS = {"deer_elk": 54, "antelope": 44, "bear": 51}
HEADERS = {"User-Agent": "Mozilla/5.0 (Hunting Team data pull)", "Referer": "https://fwp.mt.gov/gis/maps/huntPlanner/"}


def fetch() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = requests.get(SESSION, timeout=60, headers=HEADERS).json()["gisSession"]["token"]
    for name, layer in LAYERS.items():
        resp = requests.get(f"{SERVICE}/{layer}/query", timeout=120, headers=HEADERS, params={
            "where": "1=1", "outFields": "DISTRICT", "returnGeometry": "true", "outSR": 4326,
            "maxAllowableOffset": 0.01, "geometryPrecision": 3, "f": "geojson", "token": token,
        })
        resp.raise_for_status()
        data = resp.json()
        if "features" not in data:
            raise SystemExit(f"FWP map service error for {name}: {data.get('error')}")
        for f in data["features"]:
            f["properties"] = {"district": str(f["properties"].get("DISTRICT", "")).strip()}
        (OUT_DIR / f"{name}.geojson").write_text(json.dumps(data, separators=(",", ":")))
        print(f"  {name}: {len(data['features'])} districts")


if __name__ == "__main__":
    fetch()
