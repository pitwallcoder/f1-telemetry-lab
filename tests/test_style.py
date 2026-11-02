import pytest

from pitwall import style


def test_lap_time_is_formatted_like_timing_screens():
    assert style.lap_time(78.128) == "1:18.128"
    assert style.lap_time(59.9) == "0:59.900"


def test_a_race_chart_looks_the_same_whatever_was_drawn_before_it():
    import matplotlib
    keys = ["font.family", "font.sans-serif", "axes.labelsize", "xtick.labelsize", "ytick.labelsize", "text.color"]
    style.race_figure("first")
    fresh = {k: matplotlib.rcParams[k] for k in keys}
    style.figure()
    style.race_figure("after another chart")
    assert {k: matplotlib.rcParams[k] for k in keys} == fresh


def test_surname_falls_back_to_the_full_name_then_the_acronym():
    assert style.surname({"last_name": "Norris", "full_name": "Lando NORRIS"}) == "Norris"
    assert style.surname({"last_name": None, "full_name": "Ryo HIRAKAWA", "name_acronym": "HIR"}) == "Hirakawa"
    assert style.surname({"name_acronym": "HIR"}) == "HIR"


def test_outward_points_away_from_the_middle_of_the_circuit():
    import numpy as np
    angle = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    x, y = 100 * np.cos(angle), 100 * np.sin(angle)
    assert style.outward(x, y, 100.0, 0.0) == pytest.approx([1.0, 0.0], abs=0.02)
    assert style.outward(x, y, 0.0, -100.0) == pytest.approx([0.0, -1.0], abs=0.02)
