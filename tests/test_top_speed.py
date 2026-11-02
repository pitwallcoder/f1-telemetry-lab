import pytest

from pitwall import top_speed
from pitwall.openf1 import DataNotFound


def lap(driver, st, i1=None):
    return {"driver_number": driver, "st_speed": st, "i1_speed": i1}


def test_each_drivers_best_trap_speed_fastest_first_skipping_untimed_laps():
    laps = [lap(1, 340, 300), lap(1, None, 310), lap(16, 345), lap(16, 344), lap(44, None)]
    assert top_speed.ranking(laps, "st_speed") == [(16, 345), (1, 340)]
    assert top_speed.ranking(laps, "i1_speed") == [(1, 310)]


def test_a_session_without_trap_speeds_is_reported():
    with pytest.raises(DataNotFound, match="speed trap"):
        top_speed.ranking([lap(1, None)], "st_speed")


def test_headline_names_everyone_tied_on_the_top_speed():
    drivers = {10: {"last_name": "Gasly"}, 43: {"last_name": "Colapinto"}, 6: {"last_name": "Hadjar"}}
    assert top_speed.headline(drivers, [(10, 351), (43, 351), (6, 350)]) == \
        "Gasly and Colapinto were fastest through the speed trap: 351 km/h"
    assert top_speed.headline(drivers, [(6, 352), (10, 351)]) == "Hadjar was fastest through the speed trap: 352 km/h"


def test_headline_counts_rather_than_lists_a_crowd_tied_on_top():
    drivers = {n: {"last_name": f"D{n}"} for n in range(1, 6)}
    assert top_speed.headline(drivers, [(n, 351) for n in range(1, 6)]) == \
        "5 drivers were fastest through the speed trap: 351 km/h"
