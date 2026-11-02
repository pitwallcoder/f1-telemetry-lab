from pitwall import positions_gained
from pitwall.positions_gained import Gain


def test_gains_rank_most_places_gained_first_then_by_finish():
    grid = {1: 1, 16: 2, 44: 3, 10: 4}
    order = {1: [16, 1, 10, 44], 2: [16, 1, 10, 44]}
    classified = {16: 1, 44: 2, 1: 3}
    assert positions_gained.gains(grid, order, classified) == [
        Gain(16, grid=2, lap_one=1, finish=1), Gain(44, grid=3, lap_one=4, finish=2), Gain(1, grid=1, lap_one=2, finish=3)]
    assert Gain(44, 3, 4, 2).net == 1 and Gain(44, 3, 4, 2).first_lap == -1


def test_a_driver_with_no_grid_record_is_left_out():
    assert positions_gained.gains({1: 1}, {1: [1, 2]}, {1: 1, 2: 2}) == [Gain(1, 1, 1, 1)]
