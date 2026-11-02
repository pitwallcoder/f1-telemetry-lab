from pitwall import style


def test_lap_time_is_formatted_like_timing_screens():
    assert style.lap_time(78.128) == "1:18.128"
    assert style.lap_time(59.9) == "0:59.900"
