from datetime import datetime, timedelta

from pitwall import race

T0 = datetime.fromisoformat("2026-11-01T20:00:00+00:00")


def at(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat()


def lap(driver, number, start_s, duration=None):
    return {"driver_number": driver, "lap_number": number, "date_start": at(start_s), "lap_duration": duration}


def message(second, lap_number, text):
    return {"date": at(second), "lap_number": lap_number, "message": text}


def test_running_order_follows_the_line_crossings_not_the_lap_records():
    laps = [lap(1, 1, 0), lap(1, 2, 10), lap(1, 3, 21, 9.0),
            lap(2, 1, 0), lap(2, 2, 11), lap(2, 3, 20, 10.5)]
    # car 2 leads at the end of lap 2 (20 s vs 21 s); the last lap has no next start, so start + lap time decides
    assert race.running_order(laps) == {1: [1, 2], 2: [2, 1], 3: [1, 2]}


def test_grid_is_each_drivers_first_position_record():
    records = [{"date": at(5), "driver_number": 44, "position": 2},
               {"date": at(1), "driver_number": 44, "position": 1},
               {"date": at(1), "driver_number": 63, "position": 2}]
    assert race.grid(records) == {44: 1, 63: 2}


def test_neutralisations_from_race_control_including_a_safety_car_turned_red_flag():
    messages = [message(1, 7, "VSC DEPLOYED"), message(2, 8, "VSC ENDING"),
                message(3, 44, "SAFETY CAR DEPLOYED"), message(4, 45, "RED FLAG - RACE SUSPENDED"),
                message(5, 46, "SAFETY CAR LIGHTS ON"), message(6, 46, "SESSION STARTED"),
                message(7, 59, "SAFETY CAR DEPLOYED"), message(8, 62, "SAFETY CAR IN THIS LAP"),
                {"date": at(0), "lap_number": None, "message": "SESSION STARTED"}]
    assert race.neutralisations(messages) == [race.Neutralisation("VSC", 7, 8), race.Neutralisation("SC", 44, 44),
                                              race.Neutralisation("RED", 45, 46), race.Neutralisation("SC", 59, 62)]


def leader_and_lapped_car():
    """Car 1 laps every 10 s; car 2 every 12.5 s, so its lap numbers lag the leader's."""
    return [lap(1, n, 10 * (n - 1), 10.0) for n in range(1, 6)] + [lap(2, n, 12.5 * (n - 1), 12.5) for n in range(1, 5)]


def test_unrepresentative_laps_follow_the_clock_so_a_lapped_car_loses_its_own_safety_car_laps():
    periods = race.neutralisations([message(21, 3, "SAFETY CAR DEPLOYED"), message(29, 3, "SAFETY CAR IN THIS LAP")])
    assert race.unrepresentative_laps(leader_and_lapped_car(), periods) == {
        (1, 1), (1, 3), (1, 4), (2, 1), (2, 2), (2, 3), (2, 4)}


def test_unrepresentative_laps_add_no_restart_lap_after_a_vsc():
    periods = race.neutralisations([message(21, 3, "VSC DEPLOYED"), message(29, 3, "VSC ENDING")])
    assert race.unrepresentative_laps(leader_and_lapped_car(), periods) == {(1, 1), (1, 3), (2, 1), (2, 2), (2, 3)}


def test_classification_leaves_out_unclassified_drivers():
    result = [{"driver_number": 3, "position": 1}, {"driver_number": 81, "position": 15},
              {"driver_number": 14, "position": None}]
    assert race.classification(result) == {3: 1, 81: 15}


def test_compound_by_lap_covers_every_lap_of_each_stint():
    stints = [{"driver_number": 16, "lap_start": 1, "lap_end": 2, "compound": "SOFT"},
              {"driver_number": 16, "lap_start": 3, "lap_end": 3, "compound": "MEDIUM"}]
    assert race.compound_by_lap(stints) == {(16, 1): "SOFT", (16, 2): "SOFT", (16, 3): "MEDIUM"}


def test_a_period_still_open_when_the_race_ends_runs_to_the_last_lap():
    messages = [message(1, 60, "RED FLAG - RACE SUSPENDED"), message(2, 61, "CHEQUERED FLAG")]
    assert race.neutralisations(messages) == [race.Neutralisation("RED", 60, 61)]


def test_a_repeated_start_message_does_not_open_a_second_period():
    messages = [message(1, 10, "RED FLAG - RACE SUSPENDED"), message(2, 10, "RED FLAG - RACE SUSPENDED"),
                message(3, 12, "SESSION STARTED")]
    assert race.neutralisations(messages) == [race.Neutralisation("RED", 10, 12)]
