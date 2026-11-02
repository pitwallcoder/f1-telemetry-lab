import pytest

from pitwall import long_runs
from pitwall.openf1 import DataNotFound


def lap(driver, number, seconds, out_lap=False):
    return {"driver_number": driver, "lap_number": number, "lap_duration": seconds, "is_pit_out_lap": out_lap}


def stint(driver, first, last, compound="MEDIUM"):
    return {"driver_number": driver, "lap_start": first, "lap_end": last, "compound": compound}


def test_a_long_run_is_the_drivers_stint_with_most_race_pace_laps():
    quali_sim = [lap(4, 1, 100.0, out_lap=True), lap(4, 2, 78.0), lap(4, 3, 95.0)]
    run = [lap(4, 4, 110.0, out_lap=True)] + [lap(4, n, 81.0) for n in range(5, 11)] + [lap(4, 11, 92.0)]
    found = long_runs.runs(quali_sim + run, [stint(4, 1, 3, "SOFT"), stint(4, 4, 11)], excluded=set())
    [r] = found
    assert (r.pace.driver, r.compound) == (4, "MEDIUM")
    assert [n for n, _, _ in r.pace.laps] == [5, 6, 7, 8, 9, 10]


def test_runs_shorter_than_five_laps_are_not_long_runs():
    laps = [lap(4, n, 81.0) for n in range(2, 6)]
    assert long_runs.runs(laps, [stint(4, 1, 5)], excluded=set()) == []


def test_degradation_is_the_fuel_corrected_loss_per_lap():
    laps = [lap(4, n, 80.0 + 0.1 * n) for n in range(2, 8)]
    [r] = long_runs.runs(laps, [stint(4, 1, 7)], excluded=set())
    assert r.degradation == pytest.approx(0.1 + 0.035)


def test_excluded_laps_are_left_out():
    laps = [lap(4, n, 81.0) for n in range(2, 8)]
    [r] = long_runs.runs(laps, [stint(4, 1, 7)], excluded={(4, 7)})
    assert [n for n, _, _ in r.pace.laps] == [2, 3, 4, 5, 6]


def test_a_session_without_long_runs_is_reported():
    with pytest.raises(DataNotFound, match="long run"):
        long_runs.ranking([lap(4, 2, 81.0)], [stint(4, 1, 2)], [])


def test_push_and_cool_down_laps_are_not_a_long_run_even_when_cool_laps_are_the_majority():
    times = [93.1, 80.1, 103.9, 79.6, 118.4, 106.2, 80.0, 96.2]
    laps = [lap(18, n, t) for n, t in enumerate(times, 14)]
    assert long_runs.runs(laps, [stint(18, 14, 21, "SOFT")], excluded=set()) == []
