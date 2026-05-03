"""One-shot downloader for the LTA MRT/LRT station exits GeoJSON dataset
from data.gov.sg. Run once; commit the data file or .gitignore it."""

import json
import urllib.request
from pathlib import Path

DATASET_ID = "d_b39d3a0871985372d7e1637193335da5"
OUT = Path(__file__).resolve().parent.parent / "data" / "mrt_exits.geojson"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    poll_url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{DATASET_ID}/poll-download"
    req = urllib.request.Request(poll_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    download_url = body["data"]["url"]
    with urllib.request.urlopen(download_url) as resp:
        OUT.write_bytes(resp.read())
    print(f"Downloaded {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
