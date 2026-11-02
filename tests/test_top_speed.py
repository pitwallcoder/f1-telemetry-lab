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
