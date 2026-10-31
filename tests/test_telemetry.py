import numpy as np
import pytest

from pitwall import telemetry
from pitwall.telemetry import Trace, Zone, braking_points, segments


def trace(t, distance):
    return Trace(np.asarray(t, float), np.asarray(distance, float), None)


def test_delta_is_the_time_difference_at_the_same_track_distance():
    fast = trace([0, 40, 80], [0, 2000, 4000])
    slow = trace([0, 40.3, 80.5], [0, 2000, 4000])
    assert list(np.round(telemetry.delta(fast, slow), 3)) == [0.0, 0.3, 0.5]


def test_smooth_keeps_flat_parts_and_ends_and_softens_a_step():
    d = np.arange(0, 1000, 5.0)
    step = np.where(d < 500, 0.0, 0.4)
    smoothed = telemetry.smooth(d, step, window_m=100)
    assert smoothed[0] == 0.0 and smoothed[-1] == pytest.approx(0.4)
    assert np.interp(400, d, smoothed) == 0.0 and np.interp(600, d, smoothed) == pytest.approx(0.4)
    assert 0.15 < np.interp(500, d, smoothed) < 0.25


def profile(points, step=5.0):
    """Trace through (distance, speed) corners of a piecewise-linear speed profile."""
    d = np.arange(0, points[-1][0] + step, step)
    v = np.interp(d, [p[0] for p in points], [p[1] for p in points])
    return Trace(np.cumsum(np.concatenate([[0], np.diff(d) / (v[1:] / 3.6)])), d, v)


# A hard stop from 330 at 800 m, another from 300 at 1500 m, then a chicane braked from only 180 km/h.
LAP = profile([(0, 280), (700, 330), (800, 330), (900, 100), (1300, 300), (1500, 300), (1600, 150),
               (1700, 180), (1750, 110), (1900, 260), (2500, 300)])


def at(trace, metres):
    return int(np.argmin(np.abs(trace.distance - metres)))


def test_braking_points_are_the_top_of_each_hard_stop():
    assert [round(LAP.distance[i]) for i in braking_points(LAP)] == [800, 1500, 1700]


def test_braking_points_ignore_drag_on_a_long_straight():
    straight = profile([(0, 300), (600, 345), (900, 330), (1000, 120), (1300, 300)])
    points = [round(straight.distance[i]) for i in braking_points(straight)]
    assert len(points) == 1 and 700 <= points[0] <= 900


def test_segments_cover_the_whole_lap_and_skip_slow_braking_points():
    bounds = segments(LAP)
    assert bounds[0][0] == 0 and bounds[-1][1] == len(LAP.distance) - 1
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:]))
    assert [round(LAP.distance[s]) for s, _ in bounds] == [0, 800, 1500]


def test_segment_zones_measure_net_change_so_a_spike_given_back_does_not_count():
    gap = np.zeros_like(LAP.distance)
    gap[at(LAP, 850):] += 0.30   # kept: stop at 800 m
    gap[at(LAP, 1550):] -= 0.02  # lost at 1500 m; same segment as the chicane, braked from too slow to split
    gap[at(LAP, 1760):] += 0.10  # kept: chicane
    gap[at(LAP, 1740):at(LAP, 1770)] += 0.4  # a braking-zone spike that is given back
    zones = telemetry.segment_zones(LAP, gap)
    assert [round(z.gain, 3) for z in zones] == [0.0, 0.3, 0.08]
    assert round(sum(z.gain for z in zones), 3) == round(gap[-1], 3)


def test_segment_zones_shade_braking_and_corner_not_the_next_straight():
    zone = telemetry.segment_zones(LAP, np.where(LAP.distance > 850, 0.3, 0.0))[1]
    assert round(LAP.distance[zone.start]) == 800
    assert 900 < LAP.distance[zone.end] < 1300


# In lap order, with the biggest gains of each driver not first.
ZONES = [Zone(0.09, 0, 1), Zone(-0.06, 2, 3), Zone(0.31, 4, 5), Zone(0.02, 6, 7), Zone(-0.12, 8, 9), Zone(0.18, 10, 11)]


def test_strongest_picks_the_biggest_gains_for_each_driver():
    assert [z.gain for z in telemetry.strongest(ZONES, 2)] == [0.31, 0.18]
    assert [z.gain for z in telemetry.strongest(ZONES, 2, sign=-1)] == [-0.12, -0.06]


def test_strongest_ignores_gains_below_the_threshold():
    assert telemetry.strongest(ZONES, 5, min_gain=0.1) == [Zone(0.31, 4, 5), Zone(0.18, 10, 11)]


CORNERS = [(1, 1200.0), (2, 1280.0), (3, 1340.0), (6, 2220.0)]


@pytest.mark.parametrize("start, end, expected", [
    (1190, 1500, "T1–T3"),
    (1250, 1300, "T2"),
    (2100, 2200, "into T6"),
    (1360, 1450, "out of T3"),
])
def test_zone_name_uses_official_corners(start, end, expected):
    assert telemetry.zone_name(start, end, CORNERS) == expected


def test_zone_name_calls_a_cornerless_first_zone_the_start_straight():
    assert telemetry.zone_name(0, 120, CORNERS) == "start straight"


def test_table_rows_add_up_to_the_printed_lap_gap():
    # Unrounded these sum to 0.7442, rounded to 0.743: only rounding first keeps the column honest.
    zones = [Zone(0.3794, 0, 1), Zone(0.1794, 2, 3), Zone(0.1854, 4, 5)]
    gains, rest, total = telemetry.table_rows(zones, 0.65949)
    assert gains == [0.379, 0.179, 0.185]
    assert (rest, total) == (-0.084, 0.659)
