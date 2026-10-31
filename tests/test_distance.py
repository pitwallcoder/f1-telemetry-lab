import numpy as np
import pytest

from pitwall import distance

SQUARE = distance.track_line(np.array([0.0, 100.0, 100.0, 0.0]), np.array([0.0, 0.0, 100.0, 100.0]))


def test_track_line_is_closed_with_arc_length():
    assert SQUARE.length == pytest.approx(400.0)
    assert SQUARE.s[1] - SQUARE.s[0] == pytest.approx(distance.LINE_STEP_M)


def test_project_finds_the_arc_length_of_the_nearest_point():
    s = distance.project(SQUARE, [50.0, 103.0, 0.5], [2.0, 30.0, 60.0])
    assert list(np.round(s)) == [50.0, 130.0, 340.0]


def lap_with_known_truth(speed_bias=1.02, delay=0.1, noise_m=3.0, seed=7):
    """A car whose true distance is known: speed reads `speed_bias` high, its clock runs `delay` late,
    and positions scatter `noise_m` around the truth and wrap at the line."""
    length = 1000.0
    # Straights at 85 m/s and hard stops to 25 m/s every 6 s: sharp changes are what pin down the clock offset.
    fine = np.arange(-5, 25, 0.001)
    phase = fine % 6
    v_fine = np.where(phase < 3, 85.0, np.where(phase < 4, 85 - 60 * (phase - 3), 25 + 20 * (phase - 4)))
    d_fine = np.cumsum(v_fine) * 0.001
    true_speed = lambda t: np.interp(t, fine, v_fine)
    true_distance = lambda t: np.interp(t, fine, d_fine)
    t_car = np.arange(-3, 23, 0.27)
    speed_kmh = true_speed(t_car - delay) * speed_bias * 3.6
    t_pos = np.arange(-3, 23, 0.22)
    noise = np.random.default_rng(seed).normal(0, noise_m, len(t_pos))
    s_pos = (true_distance(t_pos) + 400 + noise) % length
    return t_car, speed_kmh, t_pos, s_pos, length, true_distance


def test_fuse_recovers_distance_and_clock_offset_despite_biased_speed_and_noisy_positions():
    t_car, speed, t_pos, s_pos, length, truth = lap_with_known_truth()
    fit = distance.fuse(t_car, speed, t_pos, s_pos, length)
    t = np.linspace(0, 20, 200)
    error = fit.distance(t) - fit.distance(np.array([0.0]))[0] - (truth(t) - truth(0))
    assert fit.delay == pytest.approx(0.1, abs=0.04)
    assert np.sqrt(np.mean(error ** 2)) < 1.5


def test_along_lap_measures_from_the_finish_line_wherever_the_track_line_starts():
    assert list(distance.along_lap([950.0, 100.0, 899.0], 900.0, 1000.0)) == [50.0, 200.0, 999.0]


def test_pin_passes_through_every_anchor_and_bends_linearly_between():
    t = np.linspace(0, 10, 101)
    d = t * 10.0
    pinned = distance.pin(t, d, [(0.0, 0.0), (5.0, 52.0), (10.0, 100.0)])
    assert np.interp(5.0, t, pinned) == pytest.approx(52.0)
    assert np.interp(2.5, t, pinned) == pytest.approx(26.0)
    assert pinned[-1] == pytest.approx(100.0)
