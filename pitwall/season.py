"""A season's results, one session per round: the classified order and who drove for which team."""
from dataclasses import dataclass
from datetime import datetime, timezone

from pitwall import openf1


@dataclass(frozen=True)
class Round:
    session: dict
    result: list
    drivers: dict  # driver number -> OpenF1 driver record


def weekend_drivers(records):
    """driver -> record across a weekend's sessions, keeping one that names the team: a stand-in's team can be
    missing from a single session."""
    drivers = {}
    for record in records:
        if record["driver_number"] not in drivers or record.get("team_name"):
            drivers[record["driver_number"]] = record
    return drivers


def finished_sessions(sessions, session_name, now):
    return sorted((s for s in sessions if s["session_name"] == session_name and not s.get("is_cancelled")
                   and datetime.fromisoformat(s["date_end"]) < now), key=lambda s: s["date_start"])


def load(year, session_name):
    """Every finished, non-cancelled `session_name` of the season that has a published result."""
    rounds = []
    for s in finished_sessions(openf1.get("sessions", year=year), session_name, datetime.now(timezone.utc)):
        cache = openf1.settled(s)
        result = openf1.get("session_result", cache=cache, session_key=s["session_key"])
        if result:
            drivers = openf1.get("drivers", cache=cache, meeting_key=s["meeting_key"])
            rounds.append(Round(s, result, weekend_drivers(drivers)))
    if not rounds:
        raise openf1.DataNotFound(f"OpenF1 has no {session_name} results for {year} yet")
    return rounds
