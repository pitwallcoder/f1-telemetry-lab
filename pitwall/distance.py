"""Where a car is along the track at each moment of its lap. Pure maths, no network.

Car speed (~4 Hz) integrates into a smooth distance that drifts; positions (~4 Hz) projected onto the official
track line do not drift but scatter by several metres. The fit keeps the shape of the first and the level of the
second. Validated against official sector times, which it does not use: median error ~0.02 s (see README).
"""
from dataclasses import dataclass

import numpy as np

KNOT_S = 6.0  # stable from 4 to 12 s; shorter knots start fitting position noise
DELAYS_S = np.arange(-0.3, 0.301, 0.02)  # car-data clock vs position clock, typically +0.1 s
LINE_STEP_M = 0.5


@dataclass(frozen=True)
class TrackLine:
    x: np.ndarray
    y: np.ndarray
    s: np.ndarray
    length: float


@dataclass(frozen=True)
class Fit:
    t_car: np.ndarray
    integrated: np.ndarray
    delay: float
    knots: np.ndarray
    correction: np.ndarray
    residual_m: float

    def distance(self, t):
        """Unwrapped arc length along the track line at lap time `t`."""
        return np.interp(t + self.delay, self.t_car, self.integrated) + np.interp(t, self.knots, self.correction)


def track_line(x, y):
    """Closed track line resampled every LINE_STEP_M, with arc length."""
    x, y = np.append(x, x[0]), np.append(y, y[0])
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    fine = np.arange(0, s[-1], LINE_STEP_M)
    return TrackLine(np.interp(fine, s, x), np.interp(fine, s, y), fine, float(s[-1]))


def project(line, px, py):
    """Arc length of the nearest track-line point to each position."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    nearest = [np.argmin((line.x - a) ** 2 + (line.y - b) ** 2) for a, b in zip(px, py)]
    return line.s[np.array(nearest, dtype=int)]


def along_lap(s, lap_start_s, length):
    """Metres from the lap start to track-line position `s`; the track line need not begin at the finish."""
    return (np.asarray(s, float) - lap_start_s) % length


def fuse(t_car, speed_kmh, t_pos, s_pos, length):
    """Fit integrated speed to projected positions: a smooth correction plus the clock offset between streams."""
    v = np.asarray(speed_kmh, float) / 3.6
    integrated = np.concatenate([[0], np.cumsum(np.diff(t_car) * (v[1:] + v[:-1]) / 2)])
    s = np.unwrap(np.asarray(s_pos) / length * 2 * np.pi) / (2 * np.pi) * length
    knots = np.arange(t_pos[0], t_pos[-1] + KNOT_S, KNOT_S)
    hats = np.column_stack([np.interp(t_pos, knots, np.eye(len(knots))[k]) for k in range(len(knots))])
    best = None
    for delay in DELAYS_S:
        target = s - np.interp(t_pos + delay, t_car, integrated)
        correction, *_ = np.linalg.lstsq(hats, target, rcond=None)
        residual = float(np.sqrt(np.mean((target - hats @ correction) ** 2)))
        if best is None or residual < best.residual_m:
            best = Fit(np.asarray(t_car), integrated, float(delay), knots, correction, residual)
    return best


def pin(t, d, anchors):
    """Shift a distance curve smoothly so it passes through each (time, distance) anchor exactly."""
    times = [a for a, _ in anchors]
    shifts = [target - np.interp(at, t, d) for at, target in anchors]
    return d + np.interp(t, times, shifts)
