"""Full chart runs on recorded OpenF1 + MultiViewer responses for 2026 Mexico City FP1 (PW-001).

The recording is not in the repo (third-party data); create it with:
  uv run python -m tests.record_fixture mexico_2026_fp1 2026 "Mexico City" FP1
"""
import json
from pathlib import Path

import numpy as np
import pytest
from matplotlib import image

from pitwall import __main__ as cli
from pitwall import net, speed_chart

FIXTURE = Path(__file__).parent / "fixtures" / "mexico_2026_fp1.json"
pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="no recorded fixture; see module docstring")


@pytest.fixture
def recorded(monkeypatch):
    responses = json.loads(FIXTURE.read_text())

    def fetch(url, cache=False):
        assert url in responses, f"not recorded: {url}"
        return responses[url]

    monkeypatch.setattr(net, "fetch_json", fetch)


@pytest.fixture
def fp1(recorded):
    return speed_chart.from_session(2026, "Mexico City", "FP1")


def test_cli_prints_and_writes_the_chart_and_its_facts(recorded, tmp_path, capsys):
    cli.main(["2026", "Mexico City", "FP1", "--code", "PW-001", "--out", str(tmp_path)])
    lines = capsys.readouterr().out.splitlines()
    stem = tmp_path / "pw-001" / "pw-001_2026-mexico-city-practice-1_LEC-vs-ANT"
    assert image.imread(stem.with_name(stem.name + ".png")).shape == (900, 1600, 4)
    assert [line.split() for line in lines[1:-1]] == [
        ["A", "T1–T3", "LEC", "+0.396s"], ["B", "into", "T4", "ANT", "+0.066s"], ["C", "T4–T6", "ANT", "+0.144s"],
        ["D", "T7–T9", "LEC", "+0.060s"], ["E", "T10–T11", "LEC", "+0.181s"], ["F", "T12–T17", "LEC", "+0.274s"],
        ["·", "rest", "of", "lap", "ANT", "+0.042s"], ["=", "lap", "LEC", "+0.659s"]]
    assert lines[-1] == "check: position fit ±3.4/2.9 m, cars apart at official lines -0.9, -3.2, -0.3 m (pinned to 0)"
    facts = json.loads(stem.with_name(stem.name + ".json").read_text())
    assert facts["official_gap_s"] == {"lap": 0.659, "sectors": [0.345, 0.06, 0.254]}
    assert [(z["tag"], z["corners"], z["gained_by"], z["seconds"]) for z in facts["zones"]] == [
        ("A", "T1–T3", "LEC", 0.396), ("B", "into T4", "ANT", 0.066), ("C", "T4–T6", "ANT", 0.144),
        ("D", "T7–T9", "LEC", 0.06), ("E", "T10–T11", "LEC", 0.181), ("F", "T12–T17", "LEC", 0.274)]
    assert facts["rest_of_lap"] == {"gained_by": "ANT", "seconds": 0.042}


def test_cli_turns_missing_data_into_a_readable_error(recorded):
    with pytest.raises(SystemExit, match="error: Unknown circuit 'Mexico'"):
        cli.main(["2026", "Mexico", "FP1"])


def test_the_faster_driver_leads_whatever_order_they_are_given_in(recorded):
    comparison = speed_chart.from_session(2026, "Mexico City", "FP1", ["ANT", "LEC"])
    assert (comparison.fast.name, comparison.slow.name) == ("LEC", "ANT")
    assert comparison.gap[-1] == pytest.approx(0.659, abs=1e-6)


def test_context_uses_the_official_event_and_session_names(fp1):
    assert fp1.context == "2026 Mexico City Grand Prix · Practice 1"


def test_track_map_covers_only_the_fastest_lap(fp1):
    track, lap_s = fp1.track, fp1.fast.lap["lap_duration"]
    assert 0 <= track.t.min() < 1 and lap_s - 1 < track.t.max() <= lap_s
    assert track.rotation == 36


def test_gap_matches_official_sector_times_exactly(fp1):
    fast, slow = fp1.fast.lap, fp1.slow.lap
    for k in (1, 2):
        t_fast = sum(fast[f"duration_sector_{i}"] for i in range(1, k + 1))
        t_slow = sum(slow[f"duration_sector_{i}"] for i in range(1, k + 1))
        line = np.interp(t_fast, fp1.fast.trace.t, fp1.fast.trace.distance)
        assert np.interp(line, fp1.fast.trace.distance, fp1.gap) == pytest.approx(t_slow - t_fast, abs=1e-6)
    assert fp1.gap[-1] == pytest.approx(slow["lap_duration"] - fast["lap_duration"], abs=1e-6)


def test_both_cars_meet_the_official_timing_lines_within_a_few_metres(fp1):
    assert len(fp1.quality.line_disagreement_m) == 3
    assert max(abs(m) for m in fp1.quality.line_disagreement_m) < 5
    assert max(fp1.quality.fit_residual_m) < 5


def test_corners_are_measured_from_the_finish_line(fp1):
    distances = [d for _, d in fp1.corner_d]
    assert [n for n, _ in fp1.corner_d] == list(range(1, 18))
    assert distances == sorted(distances)
    # The track line starts 24.6 m before the finish here; T1 sat at ~1184 m in an earlier, independent method.
    assert 1170 < distances[0] < 1195
