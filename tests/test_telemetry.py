import numpy as np
import pytest

from pitwall import telemetry
from pitwall.telemetry import Trace, Zone


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


def test_measurable_is_the_fast_part_of_the_lap():
    trace = Trace(None, np.arange(5.0), np.array([300.0, 250.0, 179.0, 180.0, 100.0]))
    assert list(telemetry.measurable(trace)) == [True, True, False, True, False]


def readable_everywhere(gap):
    return np.ones(len(gap), dtype=bool)


def test_turning_zones_follow_rises_and_falls_and_add_up_to_the_lap():
    gap = np.array([0.0, 0.1, 0.3, 0.4, 0.3, 0.2, 0.25, 0.5])
    zones = telemetry.turning_zones(gap, readable_everywhere(gap))
    assert [(z.start, z.end, round(z.gain, 3)) for z in zones] == [(0, 3, 0.4), (3, 5, -0.2), (5, 7, 0.3)]
    assert round(sum(z.gain for z in zones), 3) == gap[-1]


def test_turning_zones_ignore_wiggles_smaller_than_the_threshold():
    gap = np.array([0.0, 0.2, 0.19, 0.21, 0.4])
    assert [(z.start, z.end) for z in telemetry.turning_zones(gap, readable_everywhere(gap))] == [(0, 4)]


def test_turning_zones_never_cut_at_an_unreadable_point():
    gap = np.array([0.0, 0.05, 0.4, -0.1, 0.39, 0.5, 0.5])  # the -0.1 dip sits in a slow corner
    readable = np.array([True, True, True, False, True, True, True])
    zones = telemetry.turning_zones(gap, readable)
    assert [(z.start, z.end, round(z.gain, 3)) for z in zones] == [(0, 5, 0.5)]


def test_turning_zones_drop_flat_ends():
    gap = np.array([0.0, 0.01, 0.02, 0.2, 0.39, 0.4, 0.4])
    zone, = telemetry.turning_zones(gap, readable_everywhere(gap))
    assert (zone.start, zone.end, round(zone.gain, 3)) == (2, 4, 0.37)


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
