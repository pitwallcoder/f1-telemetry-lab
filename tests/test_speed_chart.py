import numpy as np

from pitwall import speed_chart
from pitwall.speed_chart import Comparison, Driver, Quality
from pitwall.telemetry import Zone

LEC = Driver("LEC", "e8002d", {}, None)
VER = Driver("VER", "3671c6", {}, None)


def comparison(zones, where, total):
    return Comparison({}, "", LEC, VER, np.array([0.0, total]), zones, where, [], None, None)


MIXED = comparison([Zone(0.30, 0, 1), Zone(-0.12, 2, 3), Zone(0.08, 4, 5)], ["T1–T3", "T7", "T12"], 0.31)


def test_table_says_who_gained_where_and_adds_up_to_the_lap_gap():
    assert speed_chart.table(MIXED) == [
        ("A", "LEC", 0.3, "T1–T3"), ("B", "VER", 0.12, "T7"), ("C", "LEC", 0.08, "T12"),
        ("·", "LEC", 0.05, "rest of lap"), ("=", "LEC", 0.31, "lap")]


def test_table_credits_the_rest_of_the_lap_to_whoever_gained_it():
    rest = speed_chart.table(comparison([Zone(0.40, 0, 1)], ["T1"], 0.25))[-2]
    assert rest == ("·", "VER", 0.15, "rest of lap")


def test_zones_take_the_colour_of_the_driver_who_gained_there():
    assert [speed_chart.zone_colour(MIXED, z) for z in MIXED.zones] == ["#e8002d", "#3671c6", "#e8002d"]


def test_lap_time_is_formatted_like_timing_screens():
    assert speed_chart.lap_time(78.128) == "1:18.128"
    assert speed_chart.lap_time(59.9) == "0:59.900"


def test_quality_flags_sessions_outside_the_validated_range():
    assert Quality((3.4, 2.9), (-0.9, -3.2, -0.3)).trustworthy()
    assert not Quality((3.8, 3.1), (4.0, -3.7, -16.0)).trustworthy()
    assert not Quality((10.8, 3.0), (-0.3, 4.1, 2.0)).trustworthy()
