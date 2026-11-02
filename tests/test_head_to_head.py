import pytest

from pitwall import head_to_head, season


def test_ahead_prefers_the_classified_driver_and_skips_rounds_neither_finished():
    assert head_to_head.ahead(1, 2, {1: 5, 2: 3}) == 2
    assert head_to_head.ahead(1, 2, {1: 12}) == 1
    assert head_to_head.ahead(1, 2, {}) is None


def test_same_part_gap_uses_the_last_part_both_set_a_time_in():
    assert head_to_head.same_part_gap([80.0, 79.5, 79.0], [80.2, 79.6, None]) == pytest.approx(-0.1)
    assert head_to_head.same_part_gap([80.0, None, None], [None, None, None]) is None


def round_(results, teams, times=None):
    times = times or {}
    return season.Round({}, [{"driver_number": n, "position": p, "duration": times.get(n)} for n, p in results],
                        {n: {"team_name": t, "name_acronym": str(n)} for n, t in teams.items()})


def test_teammates_follow_each_rounds_seats():
    early = round_([(1, 1), (30, 5), (6, 7)], {1: "Red Bull", 30: "Red Bull", 6: "Racing Bulls"})
    late = round_([(1, 1), (6, 4), (30, 6)], {1: "Red Bull", 6: "Red Bull", 30: "Racing Bulls"})
    assert head_to_head.teammates(early) == [("Red Bull", 1, 30)]
    assert head_to_head.teammates(late) == [("Red Bull", 1, 6)]


def test_duels_put_the_driver_with_more_rounds_first_and_orient_the_gap_to_him():
    teams = {16: "Ferrari", 44: "Ferrari"}
    rounds = [round_([(44, 1), (16, 3)], teams, {44: [80.0, 79.5, 79.0], 16: [80.1, 79.6, 79.3]}),
              round_([(44, 2), (16, 6)], teams, {44: [80.0, 79.5, 79.1], 16: [80.1, 79.6, 79.2]}),
              round_([(16, 1), (44, 2)], teams, {44: [80.0, 79.5, 79.2], 16: [80.0, 79.4, 79.0]}),
              round_([(16, None), (44, None)], teams)]
    [d] = head_to_head.duels(rounds, with_gaps=True)
    assert (d.first, d.second, d.wins) == (44, 16, {16: 1, 44: 2})
    assert d.gaps == pytest.approx([-0.3, -0.1, 0.2])
    assert d.median_gap == pytest.approx(-0.1)


def test_race_duels_carry_no_gaps():
    rounds = [round_([(1, 1), (81, 2)], {1: "McLaren", 81: "McLaren"}, {1: 5000.0, 81: 5003.0})]
    [d] = head_to_head.duels(rounds, with_gaps=False)
    assert d.gaps == [] and d.median_gap is None
