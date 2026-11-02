from pitwall import race, race_positions


def test_places_start_from_the_grid_then_follow_the_running_order():
    places = race_positions.places_by_driver({1: [63, 44], 2: [44, 63]}, {44: 1, 63: 2})
    assert places == {44: {0: 1, 1: 2, 2: 1}, 63: {0: 2, 1: 1, 2: 2}}


def test_second_driver_is_the_teammate_who_started_behind():
    drivers = {16: {"team_name": "Ferrari"}, 44: {"team_name": "Ferrari"}, 50: {"team_name": None}, 87: {"team_name": "Haas"}}
    assert race_positions.second_drivers(drivers, {44: 1, 16: 3, 50: 18, 87: 14}) == {16}


def test_tyre_changes_are_drawn_at_the_end_of_the_lap_before_the_stint():
    stints = [{"driver_number": 16, "lap_start": 1, "compound": "SOFT"}, {"driver_number": 16, "lap_start": 28, "compound": "MEDIUM"}]
    assert race_positions.tyre_changes(stints) == [(16, 0, "SOFT"), (16, 27, "MEDIUM")]


def chart(classified):
    r = race.Race({}, "", {}, [], [], [], [], [], [])
    return race_positions.Chart(r, {}, [], [], classified, set())


def test_finish_label_stars_a_driver_a_penalty_dropped_below_his_road_position():
    c = chart({81: 13, 43: 7})
    assert race_positions.finish_label(c, 81, 7) == "P13*"
    assert race_positions.finish_label(c, 43, 8) == "P7"
    assert race_positions.finish_label(c, 99, 5) == "P5"
