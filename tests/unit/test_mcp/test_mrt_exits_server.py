"""Unit tests for the MRT exits MCP server."""

import pytest

from src.mcp import mrt_exits_server as srv


async def test_list_stations_returns_known_stations():
    stations = await srv.list_stations()
    assert isinstance(stations, list)
    assert len(stations) > 100  # Singapore has ~150+ MRT/LRT stations
    upper = {s.upper() for s in stations}
    assert any("RAFFLES PLACE" in s for s in upper)
    assert any("CHANGI AIRPORT" in s for s in upper)


async def test_station_exits_returns_multiple_exits_for_raffles_place():
    exits = await srv.station_exits("Raffles Place")
    assert len(exits) >= 2
    for e in exits:
        assert "exit_code" in e
        assert "lat" in e and "lon" in e
        assert -90 < e["lat"] < 90
        assert -180 < e["lon"] < 180


async def test_station_exits_is_case_insensitive_and_handles_mrt_suffix():
    a = await srv.station_exits("raffles place")
    b = await srv.station_exits("RAFFLES PLACE MRT STATION")
    assert len(a) > 0
    assert len(a) == len(b)


async def test_station_exits_unknown_station_returns_empty_list():
    assert await srv.station_exits("Hogwarts") == []


async def test_nearest_exits_returns_closest_first():
    # Coordinates near Raffles Place MRT (1 Raffles Place)
    results = await srv.nearest_exits(lat=1.2839, lon=103.8516, max_results=3)
    assert len(results) == 3
    distances = [r["distance_meters"] for r in results]
    assert distances == sorted(distances)
    assert "RAFFLES PLACE" in results[0]["station"].upper()


async def test_nearest_exits_validates_coordinate_ranges():
    with pytest.raises(ValueError):
        await srv.nearest_exits(lat=999.0, lon=0.0)
    with pytest.raises(ValueError):
        await srv.nearest_exits(lat=0.0, lon=999.0)


async def test_nearest_exits_validates_max_results():
    with pytest.raises(ValueError):
        await srv.nearest_exits(lat=1.28, lon=103.85, max_results=21)


def test_haversine_known_distance():
    # Marina Bay Sands area — roughly 300m test
    d = srv._haversine_meters(1.2834, 103.8607, 1.2816, 103.8636)
    assert 250 < d < 400
