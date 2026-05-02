"""MCP server exposing MRT/LRT station exit lookups backed by the
data.gov.sg LTA station-exits GeoJSON dataset (loaded once at import).

Tools:
- list_stations() -> list[str]
- station_exits(station_name) -> list[{exit_code, lat, lon}]
- nearest_exits(lat, lon, max_results=3) -> list[{station, exit_code, lat, lon, distance_meters}]
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "mrt_exits.geojson"
EARTH_RADIUS_M = 6_371_000.0
_MRT_SUFFIX_RE = re.compile(r"\s+(MRT|LRT)\s+STATION\s*$", re.IGNORECASE)

mcp = FastMCP("mrt-exits")


def _normalize_station(name: str) -> str:
    """Uppercase and strip trailing 'MRT STATION' / 'LRT STATION' for matching."""
    return _MRT_SUFFIX_RE.sub("", name.strip().upper()).strip()


def _load_features() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"MRT exits dataset not found at {DATA_FILE}. "
            "Run: poetry run python scripts/download_mrt_exits.py"
        )
    data = json.loads(DATA_FILE.read_text())
    out: list[dict[str, Any]] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        if lat is None or lon is None:
            continue
        # Field names from data.gov.sg LTA dataset: STATION_NA, EXIT_CODE
        station = props.get("STATION_NA") or props.get("station_na") or ""
        exit_code = props.get("EXIT_CODE") or props.get("exit_code") or ""
        out.append(
            {
                "station": str(station),
                "station_norm": _normalize_station(str(station)),
                "exit_code": str(exit_code),
                "lat": float(lat),
                "lon": float(lon),
            }
        )
    return out


_FEATURES = _load_features()


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@mcp.tool()
async def list_stations() -> list[str]:
    """Return all unique MRT/LRT station names in Singapore."""
    return sorted({f["station"] for f in _FEATURES if f["station"]})


@mcp.tool()
async def station_exits(station_name: str) -> list[dict[str, Any]]:
    """Return all exits for a given MRT/LRT station.

    Matching is case-insensitive and tolerates a trailing 'MRT STATION' /
    'LRT STATION' suffix. Returns an empty list if the station is unknown.
    """
    target = _normalize_station(station_name)
    return [
        {"exit_code": f["exit_code"], "lat": f["lat"], "lon": f["lon"]}
        for f in _FEATURES
        if f["station_norm"] == target
    ]


@mcp.tool()
async def nearest_exits(
    lat: float, lon: float, max_results: int = 3
) -> list[dict[str, Any]]:
    """Return the N MRT/LRT exits closest to the given coordinate, sorted by distance."""
    if not -90 <= lat <= 90:
        raise ValueError(f"lat must be in [-90, 90], got {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"lon must be in [-180, 180], got {lon}")
    if max_results < 1:
        raise ValueError(f"max_results must be >= 1, got {max_results}")
    scored = [
        {
            "station": f["station"],
            "exit_code": f["exit_code"],
            "lat": f["lat"],
            "lon": f["lon"],
            "distance_meters": _haversine_meters(lat, lon, f["lat"], f["lon"]),
        }
        for f in _FEATURES
    ]
    scored.sort(key=lambda r: r["distance_meters"])
    return scored[:max_results]


if __name__ == "__main__":
    mcp.run(transport="stdio")
