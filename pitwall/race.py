"""A race lap by lap from official timing: running order, neutralised laps, grid and classification.

Pure functions over OpenF1 records, plus `load`, the one place that fetches them.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from pitwall import openf1


@dataclass(frozen=True)
class Neutralisation:
    kind: str  # "VSC", "SC" or "RED"
    first_lap: int
    last_lap: int


@dataclass(frozen=True)
class Race:
    session: dict
    meeting_name: str
    drivers: dict  # driver number -> OpenF1 driver record
    laps: list
    stints: list
    pits: list
    result: list
    messages: list
    positions: list


def line_crossings(laps):
    """(driver, lap) -> when the driver crossed the line to complete that lap.

    The next lap's start is the official crossing; the last lap falls back to start plus lap time.
    """
    crossed = {}
    for lap in laps:
        if lap.get("date_start") and lap["lap_number"] > 1:
            crossed[(lap["driver_number"], lap["lap_number"] - 1)] = datetime.fromisoformat(lap["date_start"])
    for lap in laps:
        key = (lap["driver_number"], lap["lap_number"])
        if key not in crossed and lap.get("date_start") and lap.get("lap_duration"):
            crossed[key] = datetime.fromisoformat(lap["date_start"]) + timedelta(seconds=lap["lap_duration"])
    return crossed


def running_order(laps):
    """lap -> driver numbers in the order they completed it."""
    by_lap = {}
    for (driver, lap), moment in line_crossings(laps).items():
        by_lap.setdefault(lap, []).append((moment, driver))
    return {lap: [driver for _, driver in sorted(cars)] for lap, cars in sorted(by_lap.items())}


def grid(position_records):
    """driver -> starting position: each driver's first position record of the session."""
    first = {}
    for record in sorted(position_records, key=lambda r: r["date"]):
        first.setdefault(record["driver_number"], record["position"])
    return first


STARTS = {"VSC DEPLOYED": "VSC", "SAFETY CAR DEPLOYED": "SC", "RED FLAG": "RED"}
ENDS = {"VSC": "VSC ENDING", "SC": "SAFETY CAR IN THIS LAP", "RED": "SESSION STARTED"}


def neutralisations(messages):
    """VSC, safety car and red flag periods from race control, by lap of the leader.

    A period cut short by another (a safety car turned into a red flag) ends the lap before; a red flag ends when
    the session restarts.
    """
    periods, current = [], None
    for message in sorted((m for m in messages if m.get("lap_number")), key=lambda m: m["date"]):
        text, lap = message["message"], message["lap_number"]
        kind = next((k for prefix, k in STARTS.items() if text.startswith(prefix)), None)
        if kind:
            if current:
                periods.append(Neutralisation(*current, max(current[1], lap - 1)))
            current = (kind, lap)
        elif current and text.startswith(ENDS[current[0]]):
            periods.append(Neutralisation(*current, lap))
            current = None
    return periods


def unrepresentative_laps(periods):
    """Laps that say nothing about pace: lap 1, every neutralised lap, and the restart lap after a SC or red flag."""
    laps = {1}
    for period in periods:
        laps.update(range(period.first_lap, period.last_lap + 1))
        if period.kind in ("SC", "RED"):
            laps.add(period.last_lap + 1)
    return laps


def classification(result):
    """driver -> official finishing position (after penalties); unclassified drivers are left out."""
    return {r["driver_number"]: r["position"] for r in result if r.get("position")}


def compound_by_lap(stints):
    """(driver, lap) -> tyre compound."""
    return {(s["driver_number"], lap): s["compound"]
            for s in stints for lap in range(s["lap_start"], s["lap_end"] + 1)}


def load(year, circuit):
    session = openf1.find_session(year, circuit, "R")
    key, cache = session["session_key"], openf1.settled(session)
    fetch = lambda endpoint: openf1.get(endpoint, cache=cache, session_key=key)
    laps = fetch("laps")
    if not laps:
        raise openf1.DataNotFound("OpenF1 has no lap data for this race yet")
    return Race(session, openf1.meeting_name(session), {d["driver_number"]: d for d in fetch("drivers")}, laps,
                fetch("stints"), fetch("pit"), fetch("session_result"), fetch("race_control"), fetch("position"))
