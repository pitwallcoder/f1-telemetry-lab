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
