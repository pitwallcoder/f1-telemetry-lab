import numpy as np
import pytest

from pitwall import minisectors


def test_sector_times_split_the_lap_into_equal_lengths():
    t = np.array([0.0, 10.0, 30.0])
    d = np.array([0.0, 500.0, 1000.0])
    assert minisectors.sector_times(t, d, 1000.0, 4) == pytest.approx([5.0, 5.0, 10.0, 10.0])


def test_a_minisector_goes_to_the_fastest_unless_the_margin_is_too_small_to_measure():
    times = {1: np.array([5.00, 5.00, 5.10]), 16: np.array([5.10, 4.99, 5.00])}
    assert minisectors.winners(times) == [1, None, 16]


def test_default_drivers_are_the_fastest_of_the_three_fastest_teams():
    best = {n: {"lap_duration": t} for n, t in ((1, 76.0), (6, 76.1), (16, 76.2), (44, 76.3), (63, 76.4))}
    drivers = {1: {"team_name": "Red Bull"}, 6: {"team_name": "Red Bull"}, 16: {"team_name": "Ferrari"},
               44: {"team_name": "Ferrari"}, 63: {"team_name": "Mercedes"}}
    assert minisectors.default_drivers(best, drivers) == [1, 16, 63]
