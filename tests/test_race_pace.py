import pytest

from pitwall import race, race_pace
from pitwall.openf1 import DataNotFound


def lap(driver, number, seconds, out_lap=False):
    return {"driver_number": driver, "lap_number": number, "lap_duration": seconds, "is_pit_out_lap": out_lap}


def test_representative_laps_drop_excluded_pit_and_out_laps():
    laps = [lap(1, 1, 90.0), lap(1, 2, 80.0), lap(1, 3, 95.0), lap(1, 4, 99.0), lap(1, 5, 81.0, out_lap=True),
            lap(1, 6, 80.5), lap(1, 7, None)]
    pits = [{"driver_number": 1, "lap_number": 3}]
    compounds = {(1, 2): "SOFT", (1, 6): "MEDIUM"}
    assert race_pace.representative_laps(laps, pits, {1}, compounds) == {1: [(2, 80.0, "SOFT"), (6, 80.5, "MEDIUM")]}


def test_fuel_correction_takes_off_the_fuel_still_on_board():
    assert race_pace.fuel_corrected(81.0, 1, 71) == pytest.approx(81.0 - 0.035 * 70)
    assert race_pace.fuel_corrected(80.0, 71, 71) == 80.0


def test_driver_pace_ignores_laps_three_percent_slower_than_his_median():
    laps = [(lap_n, 80.0, "SOFT") for lap_n in range(1, 6)] + [(6, 90.0, "SOFT")]
    pace = race_pace.driver_pace(7, laps, total_laps=6)
    assert [lap_n for lap_n, _, _ in pace.laps] == [1, 2, 3, 4, 5]
    assert pace.median == pytest.approx(80.0 - 0.035 * 3)


def fake_race(laps, result):
    return race.Race(session={}, meeting_name="", drivers={}, laps=laps, stints=[], pits=[], result=result,
                     messages=[], positions=[])


def test_ranking_orders_classified_drivers_by_median_and_skips_the_rest():
    laps = [lap(d, n, t) for d, t in ((1, 81.0), (2, 80.0), (3, 79.0)) for n in (2, 3, 4)]
    result = [{"driver_number": 1, "position": 1}, {"driver_number": 2, "position": 2}, {"driver_number": 3, "position": None}]
    assert [p.driver for p in race_pace.ranking(fake_race(laps, result))] == [2, 1]


def test_ranking_without_representative_laps_is_reported():
    with pytest.raises(DataNotFound, match="representative laps"):
        race_pace.ranking(fake_race([lap(1, 1, 90.0)], [{"driver_number": 1, "position": 1}]))
