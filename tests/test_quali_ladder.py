import pytest

from pitwall import quali_ladder, style
from pitwall.openf1 import DataNotFound

DRIVERS = {12: {"name_acronym": "ANT", "team_colour": "27F4D2"}, 30: {"name_acronym": "LAW", "team_colour": "6692FF"},
           77: {"name_acronym": "BOT", "team_colour": None}, 5: {"name_acronym": "BOR", "team_colour": "F50537"}}


def lap(driver, number, s1, s2, s3):
    return {"driver_number": driver, "lap_number": number, "lap_duration": round(s1 + s2 + s3, 3),
            "duration_sector_1": s1, "duration_sector_2": s2, "duration_sector_3": s3}


def result(position, driver, duration):
    return {"position": position, "driver_number": driver, "duration": duration}


LAPS = [lap(12, 5, 25.4, 37.4, 31.6), lap(12, 9, 25.31, 37.297, 31.428),
        lap(30, 4, 25.6, 37.7, 31.9), lap(30, 7, 25.551, 37.643, 31.864), lap(77, 3, 26.147, 38.465, 32.911)]


def test_each_row_uses_the_lap_of_the_last_segment_with_a_time():
    rows = quali_ladder.ladder([result(22, 77, [97.523, None, None]), result(1, 12, [95.0, 94.4, 94.035]),
                                result(10, 30, [95.2, 95.058, None]), result(20, 5, [None, None, None])],
                               LAPS, DRIVERS)
    assert [(r.position, r.name, r.segment, r.lap["lap_number"], r.colour) for r in rows] == [
        (1, "ANT", "Q3", 9, "27F4D2"), (10, "LAW", "Q2", 7, "6692FF"), (22, "BOT", "Q1", 3, "a1a1aa")]
    assert quali_ladder.sector_gaps(rows[1], rows[0]) == pytest.approx([0.241, 0.346, 0.436])


def test_a_disqualified_driver_is_left_out_like_the_official_order():
    rows = quali_ladder.ladder([result(None, 30, [None, 95.2, 95.058]), result(1, 12, [95.0, 94.4, 94.035])],
                               LAPS, DRIVERS)
    assert [r.name for r in rows] == ["ANT"]


def test_a_classifying_time_without_its_lap_is_reported():
    with pytest.raises(DataNotFound, match="no lap with sectors for LAW's Q2 time 95.1"):
        quali_ladder.ladder([result(10, 30, [95.2, 95.1, None])], LAPS, DRIVERS)


def test_a_time_set_twice_uses_the_later_lap():
    laps = LAPS + [lap(12, 11, 25.3, 37.5, 31.6)]
    rows = quali_ladder.ladder([result(1, 12, [95.0, 94.4, None])], laps, DRIVERS)
    assert rows[0].lap["lap_number"] == 11


def test_sprint_qualifying_names_its_segments():
    rows = quali_ladder.ladder([result(1, 12, [95.0, 94.4, 94.035])], LAPS, DRIVERS, quali_ladder.SPRINT_SEGMENTS)
    assert rows[0].segment == "SQ3"


def test_no_classified_driver_is_reported():
    with pytest.raises(DataNotFound, match="no qualifying result"):
        quali_ladder.ladder([result(None, 30, [95.2, 95.058, None])], LAPS, DRIVERS)


def test_a_lap_faster_than_pole_is_labelled_as_a_negative_gap():
    rows = quali_ladder.ladder([result(1, 30, [None, None, 95.058]), result(14, 12, [94.035, None, None])],
                               LAPS, DRIVERS)
    fig = quali_ladder.render({"year": 2026, "session_name": "Qualifying"}, "Test GP", rows, "PW-TEST")
    labels = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "-1.023" in labels


def test_the_fastest_time_in_each_sector_is_purple():
    laps = [lap(12, 9, 25.31, 37.297, 31.428), lap(30, 7, 25.2, 37.643, 31.4)]
    rows = quali_ladder.ladder([result(1, 12, [None, None, 94.035]), result(2, 30, [None, None, 94.243])],
                               laps, DRIVERS)
    fig = quali_ladder.render({"year": 2026, "session_name": "Qualifying"}, "Test GP", rows, "PW-TEST")
    purple = sorted(t.get_text() for ax in fig.axes for t in ax.texts if t.get_color() == style.PURPLE)
    assert purple == ["-0.028", "-0.110", "37.297"]
