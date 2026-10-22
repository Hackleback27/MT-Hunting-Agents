"""One-time helper: downloads the raw FWP files (harvest + regulations) so Claude can build the parsers.
In VS Code, click the Run button (triangle, top right). Safe to delete afterwards."""
from agents.fwp_fetch import fetch as fetch_harvest
from agents.regs_fetch import fetch as fetch_regs

print("Downloading FWP harvest estimates...")
fetch_harvest()
print("Downloading FWP regulations...")
fetch_regs()
print("\nAll done. Tell Claude it finished.")
