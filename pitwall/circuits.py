"""Official track line and corners from the MultiViewer API, in metres, in OpenF1's location coordinates."""
from dataclasses import dataclass

import numpy as np

from pitwall import distance, net
from pitwall.openf1 import DataNotFound

API = "https://api.multiviewer.app/api/v1/circuits/{key}/{year}"
UNITS_PER_M = 10  # MultiViewer and OpenF1 positions are in decimetres


@dataclass(frozen=True)
class Circuit:
    line: distance.TrackLine
    corners: list  # (number, arc length along `line`)
    rotation: float  # degrees, as on TV graphics


def circuit(circuit_key, year):
    info = net.fetch_json(API.format(key=circuit_key, year=year), cache=True)
    if not info or not info.get("x") or not info.get("corners"):
        raise DataNotFound(f"MultiViewer has no track line for circuit {circuit_key} in {year}")
    line = distance.track_line(np.asarray(info["x"], float) / UNITS_PER_M, np.asarray(info["y"], float) / UNITS_PER_M)
    numbers = [c["number"] for c in info["corners"]]
    xs = [c["trackPosition"]["x"] / UNITS_PER_M for c in info["corners"]]
    ys = [c["trackPosition"]["y"] / UNITS_PER_M for c in info["corners"]]
    return Circuit(line, list(zip(numbers, distance.project(line, xs, ys))), info.get("rotation", 0))
