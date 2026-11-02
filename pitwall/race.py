"""A race lap by lap from official timing: running order, neutralised laps, grid and classification.

Pure functions over OpenF1 records, plus `load`, the one place that fetches them.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pitwall import openf1


@dataclass(frozen=True)
class Neutralisation:
    kind: str  # "VSC", "SC" or "RED"
    first_lap: int  # leader's laps, for drawing
    last_lap: int
    start: datetime = field(default=None, compare=False)  # race-control clock, for judging every car's laps
    end: datetime = field(default=None, compare=False)


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
    the session restarts; a period still open at the end runs to the last lap race control reported.
    """
    periods, current, lap, now = [], None, None, None

    def close(last_lap):
        kind, first_lap, start = current
        periods.append(Neutralisation(kind, first_lap, last_lap, start, now))

    for message in sorted((m for m in messages if m.get("lap_number")), key=lambda m: m["date"]):
        text, lap, now = message["message"], message["lap_number"], datetime.fromisoformat(message["date"])
        kind = next((k for prefix, k in STARTS.items() if text.startswith(prefix)), None)
        if kind and current and kind == current[0]:
            continue   # race control re-announcing the same period
        if kind:
            if current:
                close(max(current[1], lap - 1))
            current = (kind, lap, now)
        elif current and text.startswith(ENDS[current[0]]):
            close(lap)
            current = None
    if current:
        close(lap)
    return periods


def unrepresentative_laps(laps, periods):
    """(driver, lap) pairs that say nothing about pace: lap 1, any lap run partly under a VSC, SC or red flag, and
    each driver's first lap after a SC or red flag. Judged on the clock, so lapped cars lose their own laps."""
    excluded = {(x["driver_number"], 1) for x in laps if x["lap_number"] == 1}
    restart = set()
    for lap in sorted((x for x in laps if x.get("date_start") and x.get("lap_duration")),
                      key=lambda x: (x["driver_number"], x["lap_number"])):
        key, start = (lap["driver_number"], lap["lap_number"]), datetime.fromisoformat(lap["date_start"])
        end = start + timedelta(seconds=lap["lap_duration"])
        hit = [p for p in periods if start < p.end and p.start < end]
        if hit or key[0] in restart:
            excluded.add(key)
        restart.discard(key[0])
        if any(p.kind in ("SC", "RED") for p in hit):
            restart.add(key[0])
    return excluded


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
