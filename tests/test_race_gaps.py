import pytest

from pitwall import race_gaps
from pitwall.openf1 import DataNotFound


def lap(driver, number, start, seconds=None):
    return {"driver_number": driver, "lap_number": number, "date_start": f"2026-11-01T20:{start}+00:00",
            "lap_duration": seconds}


def test_gap_is_how_far_the_second_driver_crossed_the_line_behind_the_first_each_lap():
    laps = [lap(1, 1, "00:00"), lap(1, 2, "01:30"), lap(1, 3, "03:00", 90.0),
            lap(4, 1, "00:00"), lap(4, 2, "01:32"), lap(4, 3, "02:59", 95.0)]
    assert race_gaps.between(laps, 1, 4) == {1: pytest.approx(2.0), 2: pytest.approx(-1.0), 3: pytest.approx(4.0)}


def test_pair_defaults_to_the_top_two_and_puts_the_one_classified_ahead_first():
    result = [{"driver_number": 44, "position": 2}, {"driver_number": 1, "position": 1},
              {"driver_number": 16, "position": 3}]
    drivers = {1: {"name_acronym": "VER"}, 44: {"name_acronym": "HAM"}, 16: {"name_acronym": "LEC"}}
    assert race_gaps.pair(result, drivers, []) == (1, 44)
    assert race_gaps.pair(result, drivers, ["lec", "1"]) == (1, 16)


def test_pair_rejects_an_unknown_driver():
    with pytest.raises(DataNotFound, match="XYZ"):
        race_gaps.pair([{"driver_number": 1, "position": 1}], {1: {"name_acronym": "VER"}}, ["VER", "XYZ"])


def test_headline_gives_the_margin_on_the_last_lap():
    drivers = {1: {"last_name": "Verstappen"}, 44: {"last_name": "Hamilton"}}
    assert race_gaps.headline(drivers, 1, 44, {70: -3.0, 71: 0.84}, classified={1: 1, 44: 2}) == \
        "Verstappen beat Hamilton by 0.8 s"


def test_headline_when_the_second_driver_did_not_finish_or_a_penalty_reversed_the_road_order():
    drivers = {1: {"last_name": "Verstappen"}, 44: {"last_name": "Hamilton"}}
    assert race_gaps.headline(drivers, 1, 44, {70: 3.0, 71: 2.0}, classified={1: 1}) == \
        "Verstappen vs Hamilton, who did not finish"
    assert race_gaps.headline(drivers, 1, 44, {70: -3.0, 71: -2.0}, classified={1: 1, 44: 2}) == \
        "Verstappen finished ahead of Hamilton after penalties"
