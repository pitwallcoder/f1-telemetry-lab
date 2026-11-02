import pytest

from pitwall.openf1 import DataNotFound
from pitwall import track_limits

SESSION = {"date_start": "2026-11-01T20:00:00+00:00", "circuit_short_name": "Mexico City"}


def message(date, text):
    return {"date": f"2026-11-01T{date}+00:00", "message": text}


def test_deletions_read_car_and_turn_and_skip_other_messages():
    messages = [message("20:10:00", "CAR 81 (PIA) TIME 1:22.907 DELETED - TRACK LIMITS AT TURN 12 LAP 5 14:10:09"),
                message("20:11:00", "CAR 10 (GAS) LAP DELETED - TRACK LIMITS AT TURN 1 LAP 7 14:11:00 (PIT)"),
                message("20:12:00", "BLACK AND WHITE FLAG FOR CAR 18 (STR) - TRACK LIMITS"),
                message("20:13:00", "CAR 44 (HAM) TIME 1:23.000 DELETED - DOUBLE YELLOW AT TURN 3")]
    assert track_limits.deletions(messages, SESSION) == [
        track_limits.Deletion(81, "PIA", 12, "Mexico City"), track_limits.Deletion(10, "GAS", 1, "Mexico City")]


def test_deletions_skip_messages_from_before_the_session():
    early = {"date": "2026-10-31T17:36:46+00:00",
             "message": "CAR 10 (GAS) LAP DELETED - TRACK LIMITS AT TURN 12 LAP 2 11:35:28"}
    assert track_limits.deletions([early], SESSION) == []


def test_a_reinstated_time_or_lap_cancels_that_deletion_only():
    messages = [message("20:10:00", "CAR 44 (HAM) TIME 1:12.028 DELETED - TRACK LIMITS AT TURN 9 LAP 5 14:10:00"),
                message("20:11:00", "CAR 44 (HAM) TIME 1:12.500 DELETED - TRACK LIMITS AT TURN 4 LAP 7 14:11:00"),
                message("20:12:00", "CAR 55 (SAI) LAP DELETED - TRACK LIMITS AT TURN 1 LAP 1 14:12:00"),
                message("20:20:00", "CAR 44 (HAM) TIME 1:12.028 WILL BE REINSTATED"),
                message("20:21:00", "CAR 55 (SAI) LAP 1 WILL BE REINSTATED")]
    assert track_limits.deletions(messages, SESSION) == [track_limits.Deletion(44, "HAM", 4, "Mexico City")]



def test_a_session_without_deletions_is_reported_not_drawn():
    empty = track_limits.Tally("context", [], {}, "x", 2026)
    with pytest.raises(DataNotFound, match="no laps"):
        track_limits.render(empty)


def test_season_headline_names_everyone_tied_at_the_top():
    ant, sai, new = (track_limits.Deletion(12, "ANT", 1, "A"), track_limits.Deletion(55, "SAI", 4, "B"),
                     track_limits.Deletion(99, "XXX", 4, "B"))
    drivers = {12: {"last_name": "Antonelli"}, 55: {"last_name": "Sainz"}}
    assert track_limits.headline(track_limits.Tally("c", [ant, sai, ant, sai, new], drivers, "x", 2026)) == \
        "Antonelli and Sainz lost the most laps to track limits in 2026: 2 each"
    assert track_limits.headline(track_limits.Tally("c", [ant, new, new], drivers, "x", 2026)) == \
        "XXX lost the most laps to track limits in 2026: 2"
