"""Session, driver and lap lookups on top of the OpenF1 API."""
import re
from datetime import datetime, timedelta, timezone

import numpy as np

from pitwall import net

API = "https://api.openf1.org/v1/"
# Our codes for F1's official session names, exactly as OpenF1 publishes them. Pre-season testing is not covered.
SESSIONS = {
    "FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3",
    "SQ": "Sprint Qualifying", "S": "Sprint", "Q": "Qualifying", "R": "Race",
}
CAR = re.compile(r"^CAR (\d+)\b")
TIME = re.compile(r"\bTIME ([\d:.]+)")
LAP = re.compile(r"\bLAP (\d+)\b")
SETTLE_TIME = timedelta(hours=12)


class DataNotFound(Exception):
    """A session, driver or lap the user asked for does not exist or has no data yet."""


def get(endpoint, cache=False, **params):
    return net.fetch_json(net.build_url(API + endpoint, **params), cache=cache) or []


def settled(session, now=None):
    """Whether a session's data can be cached for good: stewards can still delete laps hours after the flag."""
    now = now or datetime.now(timezone.utc)
    return now - datetime.fromisoformat(session["date_end"]) > SETTLE_TIME


def match_session(sessions, circuit, code, now):
    """The finished session `code` at `circuit`, OpenF1's official circuit_short_name (e.g. "Mexico City")."""
    if code not in SESSIONS:
        raise DataNotFound(f"Unknown session '{code}'. Use one of: {', '.join(SESSIONS)}")
    circuits = sorted({s["circuit_short_name"] for s in sessions})
    if not circuits:
        raise DataNotFound("OpenF1 has no sessions for that season")
    if circuit not in circuits:
        raise DataNotFound(f"Unknown circuit '{circuit}'. This season: {', '.join(circuits)}")
    found = [s for s in sessions if s["circuit_short_name"] == circuit and s["session_name"] == SESSIONS[code]]
    if not found:
        raise DataNotFound(f"No {SESSIONS[code]} at {circuit} this season")
    if len(found) > 1:
        raise DataNotFound(f"{circuit} hosts several {SESSIONS[code]} sessions this season; not supported")
    session = found[0]
    if datetime.fromisoformat(session["date_end"]) > now:
        raise DataNotFound(f"{circuit} {SESSIONS[code]} has not finished yet")
    return session


def slug(session):
    return re.sub(r"[^a-z0-9]+", "-", f"{session['year']} {session['circuit_short_name']} {session['session_name']}".lower()).strip("-")


def meeting_name(session):
    meeting = get("meetings", meeting_key=session["meeting_key"])
    return meeting[0]["meeting_name"] if meeting else session["location"]


def find_session(year, circuit, code):
    return match_session(get("sessions", year=year), circuit, code, datetime.now(timezone.utc))


def _lap_verdict(message):
    """(car, deleted time or None, lap number in the message or None, verb) for a lap deletion or reinstatement.

    Seen formats: "CAR 87 (BEA) TIME 1:23.165 DELETED - TRACK LIMITS AT TURN 12 LAP 3 12:34:13",
    "CAR 18 (STR) TIME 1:58.718 DELETED - DOUBLE YELLOW AT TURN 3" and "CAR 27 (HUL) LAP DELETED - ... LAP 2".
    """
    car = CAR.match(message)
    verb = next((v for v in ("REINSTATED", "DELETED") if v in message), None)
    if not car or not verb:
        return None
    time, lap = TIME.search(message), LAP.search(message)
    return int(car[1]), time and _seconds(time[1]), lap and int(lap[1]), verb


def _seconds(lap_time):
    minutes, _, seconds = lap_time.rpartition(":")
    return int(minutes or 0) * 60 + float(seconds)


def _lap_number(car_laps, deleted_time, message_lap):
    """OpenF1 lap number a race-control message refers to.

    Race control's "LAP n" is OpenF1's lap n - 1 (every timed deletion in 15 sessions matched that way), so the
    deleted time decides when given, and n - 1 otherwise.
    """
    expected = message_lap - 1 if message_lap else None
    if deleted_time is None:
        return expected
    same_time = [lap["lap_number"] for lap in car_laps if abs(lap["lap_duration"] - deleted_time) < 0.0005]
    return expected if expected in same_time else next(iter(same_time), None)


def deleted_laps(messages, laps):
    """(driver, lap number) pairs that race control deleted and did not reinstate, in message order."""
    timed = [lap for lap in laps if lap.get("lap_duration")]
    deleted = set()
    for message in sorted(messages, key=lambda m: m["date"]):
        verdict = _lap_verdict(message["message"])
        if verdict is None:
            continue
        car, deleted_time, message_lap, verb = verdict
        number = _lap_number([lap for lap in timed if lap["driver_number"] == car], deleted_time, message_lap)
        if number is None:
            continue
        if verb == "DELETED":
            deleted.add((car, number))
        else:
            deleted.discard((car, number))
    return deleted


def fastest_valid_laps(laps, deleted):
    """Each driver's quickest complete lap (all three sectors timed) that race control did not delete."""
    best = {}
    for lap in laps:
        key = (lap["driver_number"], lap["lap_number"])
        complete = lap.get("lap_duration") and all(lap.get(f"duration_sector_{i}") for i in (1, 2, 3))
        if not complete or key in deleted:
            continue
        if lap["driver_number"] not in best or lap["lap_duration"] < best[lap["driver_number"]]["lap_duration"]:
            best[lap["driver_number"]] = lap
    return best


def pick_drivers(best_laps, drivers, wanted):
    """Driver numbers for `wanted` acronyms or numbers; the session's top two when none are given."""
    if not wanted:
        ranked = sorted((n for n in best_laps if n in drivers), key=lambda n: best_laps[n]["lap_duration"])
        if len(ranked) < 2:
            raise DataNotFound("This session has fewer than two drivers with a valid lap")
        return ranked[:2]
    by_name = {d["name_acronym"].upper(): d["driver_number"] for d in drivers.values()}
    picked = []
    for item in wanted:
        number = int(item) if str(item).isdigit() else by_name.get(str(item).upper())
        if number not in drivers:
            raise DataNotFound(f"Driver '{item}' is not in this session")
        if number not in best_laps:
            raise DataNotFound(f"{drivers[number]['name_acronym']} has no valid timed lap in this session")
        picked.append(number)
    if picked[0] == picked[1]:
        raise DataNotFound("Pick two different drivers")
    return picked


def session_laps(session):
    key, cache = session["session_key"], settled(session)
    drivers = {d["driver_number"]: d for d in get("drivers", cache=cache, session_key=key)}
    messages = get("race_control", cache=cache, session_key=key)
    laps = get("laps", cache=cache, session_key=key)
    if not laps:
        raise DataNotFound("OpenF1 has no lap data for this session yet")
    return drivers, fastest_valid_laps(laps, deleted_laps(messages, laps))


def lap_samples(endpoint, session, lap, pad_s=0):
    """Samples of one lap from a time-series endpoint, with time measured from the lap start."""
    start = datetime.fromisoformat(lap["date_start"])
    pad = timedelta(seconds=pad_s)
    samples = get(endpoint, cache=settled(session), session_key=session["session_key"],
                  driver_number=lap["driver_number"],
                  **{"date>": (start - pad).isoformat(),
                     "date<": (start + timedelta(seconds=lap["lap_duration"]) + pad).isoformat()})
    if not samples:
        raise DataNotFound(f"OpenF1 has no {endpoint} for car {lap['driver_number']} lap {lap['lap_number']}")
    t = np.array([(datetime.fromisoformat(s["date"]) - start).total_seconds() for s in samples])
    return t, samples
