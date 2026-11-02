from datetime import datetime, timezone

from pitwall import season


def test_weekend_drivers_keep_the_record_that_names_the_team():
    records = [{"driver_number": 50, "team_name": None}, {"driver_number": 50, "team_name": "Haas F1 Team"},
               {"driver_number": 50, "team_name": None},
               {"driver_number": 87, "team_name": None}]
    assert season.weekend_drivers(records) == {50: {"driver_number": 50, "team_name": "Haas F1 Team"},
                                               87: {"driver_number": 87, "team_name": None}}


def test_finished_sessions_skip_cancelled_unfinished_and_other_session_types():
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    sessions = [{"session_name": "Race", "date_start": "2026-03-08T04:00:00+00:00", "date_end": "2026-03-08T06:00:00+00:00"},
                {"session_name": "Race", "date_start": "2026-04-19T17:00:00+00:00", "date_end": "2026-04-19T19:00:00+00:00",
                 "is_cancelled": True},
                {"session_name": "Race", "date_start": "2026-11-08T17:00:00+00:00", "date_end": "2026-11-08T19:00:00+00:00"},
                {"session_name": "Qualifying", "date_start": "2026-03-07T05:00:00+00:00", "date_end": "2026-03-07T06:00:00+00:00"}]
    assert [s["date_start"][:10] for s in season.finished_sessions(sessions, "Race", now)] == ["2026-03-08"]


def test_a_weekends_driver_list_is_cached_only_once_its_last_session_has_settled():
    sessions = [{"meeting_key": 7, "date_end": "2026-11-01T00:00:00+00:00"},
                {"meeting_key": 7, "date_end": "2026-11-02T20:00:00+00:00"},
                {"meeting_key": 8, "date_end": "2026-11-09T20:00:00+00:00"}]
    sunday_morning = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    monday = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    assert season.weekend_settled(sessions, 7, sunday_morning) is False
    assert season.weekend_settled(sessions, 7, monday) is True
