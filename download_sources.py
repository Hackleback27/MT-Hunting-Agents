"""One-time helper: downloads raw FWP files so Claude can build and test. Safe to delete afterwards."""
from agents.fwp_fetch import fetch as fetch_harvest
from agents.gis_fetch import fetch as fetch_gis

print("Downloading FWP harvest estimates (2004 to now)...")
fetch_harvest()
print("Downloading district boundaries...")
fetch_gis()
print("\nAll done. Tell Claude it finished.")
