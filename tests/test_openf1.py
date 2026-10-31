from datetime import datetime, timezone

import pytest

from pitwall import net, openf1
from pitwall.openf1 import DataNotFound

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def session(key, name, location, country, circuit, end="2026-10-30T19:30:00+00:00"):
    return {"session_key": key, "session_name": name, "location": location, "country_name": country,
            "circuit_short_name": circuit, "date_end": end}


SESSIONS = [
    session(1, "Practice 1", "Mexico City", "Mexico", "Mexico City"),
    session(2, "Qualifying", "Mexico City", "Mexico", "Mexico City", end="2026-10-31T22:00:00+00:00"),
    session(3, "Qualifying", "Austin", "United States", "Austin", end="2026-10-24T22:00:00+00:00"),
    session(4, "Sprint Qualifying", "Miami Gardens", "United States", "Miami", end="2026-05-01T22:00:00+00:00"),
    session(5, "Sprint", "Miami Gardens", "United States", "Miami", end="2026-05-02T17:00:00+00:00"),
]


@pytest.mark.parametrize("circuit, code, key", [
    ("Mexico City", "FP1", 1), ("Austin", "Q", 3), ("Miami", "SQ", 4), ("Miami", "S", 5)])
def test_match_session_by_official_circuit_and_session_code(circuit, code, key):
    assert openf1.match_session(SESSIONS, circuit, code, NOW)["session_key"] == key


def test_match_session_lists_the_season_circuits_for_an_unknown_one():
    with pytest.raises(DataNotFound, match="Unknown circuit 'Mexico'. This season: Austin, Mexico City, Miami"):
        openf1.match_session(SESSIONS, "Mexico", "FP1", NOW)


def test_match_session_rejects_unknown_codes():
    with pytest.raises(DataNotFound, match="Unknown session 'fp1'"):
        openf1.match_session(SESSIONS, "Mexico City", "fp1", NOW)


def test_match_session_explains_a_missing_session():
    with pytest.raises(DataNotFound, match="No Sprint at Mexico City"):
        openf1.match_session(SESSIONS, "Mexico City", "S", NOW)


def test_match_session_rejects_a_session_that_has_not_finished():
    with pytest.raises(DataNotFound, match="Mexico City Qualifying has not finished yet"):
        openf1.match_session(SESSIONS, "Mexico City", "Q", NOW)


def test_match_session_refuses_to_guess_between_two_events_at_one_circuit():
    twice = SESSIONS + [session(9, "Practice 1", "Mexico City", "Mexico", "Mexico City")]
    with pytest.raises(DataNotFound, match="several Practice 1"):
        openf1.match_session(twice, "Mexico City", "FP1", NOW)


def lap(driver, number, duration, sectors=(25.0, 30.0, 23.0)):
    return {"driver_number": driver, "lap_number": number, "lap_duration": duration,
            **{f"duration_sector_{k}": v for k, v in enumerate(sectors, 1)}}


def rc(message, at="2026-09-24T12:41:08+00:00"):
    return {"message": message, "date": at}


# Real Baku FP2 2026 timing: race control's "LAP 14" deleted RUS's 2:13.440, which OpenF1 numbers lap 13.
BAKU_RUS = [lap(63, 13, 133.44), lap(63, 14, 103.347)]


def test_deleted_time_identifies_the_lap_not_the_lap_number_in_the_message():
    message = rc("CAR 63 (RUS) TIME 2:13.440 DELETED - TRACK LIMITS AT TURN 1 LAP 14 16:38:55")
    assert openf1.deleted_laps([message], BAKU_RUS) == {(63, 13)}


def test_untimed_deletion_is_the_lap_before_the_message_lap_number():
    message = rc("CAR 27 (HUL) LAP DELETED - TRACK LIMITS AT TURN 14 LAP 2 12:34:27")
    assert openf1.deleted_laps([message], [lap(27, 1, 95.0), lap(27, 2, 80.1)]) == {(27, 1)}


def test_double_yellow_deletion_without_a_lap_number_is_found_by_its_time():
    message = rc("CAR 18 (STR) TIME 1:15.100 DELETED - DOUBLE YELLOW AT TURN 3")
    assert openf1.deleted_laps([message], [lap(18, 5, 75.1), lap(18, 6, 75.6)]) == {(18, 5)}


def test_messages_apply_in_order_so_a_lap_deleted_again_stays_deleted():
    deleted = rc("CAR 63 (RUS) TIME 2:13.440 DELETED - TRACK LIMITS AT TURN 1 LAP 14", "2026-09-24T12:41:08+00:00")
    reinstated = rc("CAR 63 (RUS) TIME 2:13.440 REINSTATED", "2026-09-24T12:45:00+00:00")
    again = rc("CAR 63 (RUS) TIME 2:13.440 DELETED - TRACK LIMITS AT TURN 4 LAP 14", "2026-09-24T12:50:00+00:00")
    assert openf1.deleted_laps([again, deleted, reinstated], BAKU_RUS) == {(63, 13)}
    assert openf1.deleted_laps([deleted, reinstated], BAKU_RUS) == set()


def test_other_race_control_messages_and_untimed_laps_are_ignored():
    messages = [rc("GREEN LIGHT - PIT EXIT OPEN"), rc("CAR 62 (MIN) TIME 8:43.417 DELETED - DOUBLE YELLOW LAP 4")]
    assert openf1.deleted_laps(messages, [lap(62, 3, None), lap(62, 4, 80.0)]) == set()


def test_fastest_valid_laps_skips_deleted_untimed_and_incomplete_laps():
    laps = [lap(16, 8, 78.5), lap(16, 9, 77.9), lap(16, 10, None), lap(16, 11, 77.0, (25.0, None, None)),
            lap(12, 4, 78.7)]
    best = openf1.fastest_valid_laps(laps, {(16, 9)})
    assert {n: l["lap_number"] for n, l in best.items()} == {16: 8, 12: 4}


def test_settled_waits_hours_after_the_session_for_late_steward_decisions():
    session = {"date_end": "2026-10-30T19:30:00+00:00"}
    assert not openf1.settled(session, datetime(2026, 10, 30, 21, 0, tzinfo=timezone.utc))
    assert openf1.settled(session, datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc))


def test_match_session_explains_an_empty_season():
    with pytest.raises(DataNotFound, match="no sessions for that season"):
        openf1.match_session([], "Monza", "Q", NOW)


DRIVERS = {16: {"driver_number": 16, "name_acronym": "LEC"},
           12: {"driver_number": 12, "name_acronym": "ANT"},
           44: {"driver_number": 44, "name_acronym": "HAM"}}
BEST = {16: lap(16, 12, 78.128), 12: lap(12, 14, 78.787), 44: lap(44, 14, 78.866)}


def test_pick_drivers_defaults_to_the_top_two():
    assert openf1.pick_drivers(BEST, DRIVERS, []) == [16, 12]


def test_pick_drivers_default_skips_drivers_missing_from_the_entry_list():
    rookie = {**BEST, 99: lap(99, 3, 77.0)}
    assert openf1.pick_drivers(rookie, DRIVERS, []) == [16, 12]


def test_pick_drivers_accepts_acronyms_and_numbers():
    assert openf1.pick_drivers(BEST, DRIVERS, ["ham", "16"]) == [44, 16]


def test_pick_drivers_explains_what_is_wrong():
    with pytest.raises(DataNotFound, match="'XXX' is not in this session"):
        openf1.pick_drivers(BEST, DRIVERS, ["LEC", "XXX"])
    with pytest.raises(DataNotFound, match="HAM has no valid timed lap"):
        openf1.pick_drivers({16: BEST[16], 12: BEST[12]}, DRIVERS, ["LEC", "HAM"])
    with pytest.raises(DataNotFound, match="fewer than two"):
        openf1.pick_drivers({16: BEST[16]}, DRIVERS, [])
    with pytest.raises(DataNotFound, match="two different drivers"):
        openf1.pick_drivers(BEST, DRIVERS, ["LEC", "16"])


def test_sessions_without_laps_or_samples_are_reported(monkeypatch):
    monkeypatch.setattr(net, "fetch_json", lambda url, cache=False: [])
    session = {"session_key": 1, "date_end": "2026-10-30T19:30:00+00:00"}
    with pytest.raises(DataNotFound, match="no lap data"):
        openf1.session_laps(session)
    timed = {"driver_number": 16, "lap_number": 12, "date_start": "2026-10-30T19:00:37+00:00", "lap_duration": 78.1}
    with pytest.raises(DataNotFound, match="no car_data for car 16 lap 12"):
        openf1.lap_samples("car_data", session, timed)
