import pytest

from pitwall import circuits, net
from pitwall.openf1 import DataNotFound


def test_missing_track_line_is_reported(monkeypatch):
    monkeypatch.setattr(net, "fetch_json", lambda url, cache=False: None)
    with pytest.raises(DataNotFound, match="no track line for circuit 65 in 2026"):
        circuits.circuit(65, 2026)


def test_track_line_and_corners_are_converted_to_metres(monkeypatch):
    square = {"x": [0, 1000, 1000, 0], "y": [0, 0, 1000, 1000], "rotation": 36,
              "corners": [{"number": 1, "trackPosition": {"x": 1000, "y": 500}}]}
    monkeypatch.setattr(net, "fetch_json", lambda url, cache=False: square)
    track = circuits.circuit(65, 2026)
    assert track.line.length == pytest.approx(400.0)
    assert [(n, round(s)) for n, s in track.corners] == [(1, 150)]
    assert track.rotation == 36
