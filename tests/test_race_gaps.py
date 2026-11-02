import pytest

from pitwall import race_gaps


def lap(driver, number, start, seconds=None):
    return {"driver_number": driver, "lap_number": number, "date_start": f"2026-11-01T20:{start}+00:00",
            "lap_duration": seconds}


def test_gap_is_time_behind_whoever_completed_that_lap_first():
    laps = [lap(1, 1, "00:00"), lap(1, 2, "01:30"), lap(1, 3, "03:00", 90.0),
            lap(4, 1, "00:00"), lap(4, 2, "01:32"), lap(4, 3, "02:59", 95.0)]
    assert race_gaps.gaps(laps) == {1: {1: 0.0, 2: pytest.approx(1.0), 3: 0.0},
                                    4: {1: pytest.approx(2.0), 2: 0.0, 3: pytest.approx(4.0)}}


def test_labels_closer_than_the_minimum_are_pushed_apart_in_order():
    assert race_gaps.spread({"A": 0.0, "B": 0.5, "C": 10.0}, 2.0) == {"A": 0.0, "B": 2.0, "C": 10.0}
    assert race_gaps.spread({"A": 0.0, "B": 0.5, "C": 3.0}, 2.0) == {"A": 0.0, "B": 2.0, "C": 4.0}


def test_only_the_top_finishers_by_official_classification_are_drawn():
    result = [{"driver_number": d, "position": p} for d, p in zip(range(1, 13), range(12, 0, -1))]
    behind = {d: {1: float(d)} for d in range(1, 13)}
    assert list(race_gaps.top_finishers(result, behind)) == [12, 11, 10, 9, 8, 7, 6, 5, 4, 3]
