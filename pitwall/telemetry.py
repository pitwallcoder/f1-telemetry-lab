"""Pure lap-comparison maths: no network, no plotting."""
from dataclasses import dataclass

import numpy as np

MIN_ZONE_GAIN_S = 0.05
# A rise or fall of the gap smaller than this is treated as noise when finding where it turns.
TURN_S = 0.025
# Gaps are only read where 5 m of position error is under ~0.1 s: from ~60% of top speed up.
MIN_READ_SPEED_RATIO = 0.6
# At ~4 Hz the gap line jitters in slow corners; 100 m of smoothing halves the spikes without moving it at the
# official timing lines (checked against sector times, see README).
GAP_SMOOTHING_M = 100


@dataclass(frozen=True)
class Trace:
    t: np.ndarray
    distance: np.ndarray
    speed: np.ndarray


@dataclass(frozen=True)
class Zone:
    gain: float
    start: int
    end: int


def delta(fast, slow):
    """Time `slow` is behind `fast` at each point of `fast`'s lap; both measured along the same track line."""
    return np.interp(fast.distance, slow.distance, slow.t) - fast.t


def smooth(distance, values, window_m=GAP_SMOOTHING_M):
    """Moving average over `window_m` metres of track, holding the end values."""
    grid = np.arange(0, distance[-1], 1.0)
    on_grid = np.interp(grid, distance, values)
    width = int(window_m)
    padded = np.concatenate([np.full(width, on_grid[0]), on_grid, np.full(width, on_grid[-1])])
    averaged = np.convolve(padded, np.ones(width) / width, mode="same")[width:-width]
    return np.interp(distance, grid, averaged)


def measurable(trace):
    """Points fast enough for the gap to be read reliably."""
    return trace.speed >= MIN_READ_SPEED_RATIO * trace.speed.max()


def turning_zones(gap, readable, threshold=TURN_S):
    """Split the lap where the gap turns, reading it only at `readable` points, the lap start and the lap end.

    A turn counts once the gap has moved back by `threshold` from its last extreme, so noise doesn't split a zone.
    Zones are in lap order; what trimming leaves out of them belongs to the rest of the lap.
    """
    points = np.flatnonzero(readable)
    points = np.unique(np.concatenate([[0], points, [len(gap) - 1]]))
    turns, extreme, trend = [points[0]], points[0], 0
    for i in points[1:]:
        if trend == 0:
            trend, extreme = np.sign(gap[i] - gap[extreme]), i
        elif trend * (gap[i] - gap[extreme]) > 0:
            extreme = i
        elif trend * (gap[extreme] - gap[i]) >= threshold:
            turns.append(extreme)
            trend, extreme = -trend, i
    turns += [extreme, points[-1]]
    # Trimming can leave a turn's flat tail, or the lap end repeated, with no length; those drop out.
    zones = (_trim(gap, points, a, b) for a, b in zip(turns, turns[1:]))
    return [z for z in zones if z.end > z.start]


def _trim(gap, points, start, end, threshold=TURN_S):
    """Zone from `start` to `end` without its flat ends: the stretches where the gap stays within `threshold` of
    its value at the turn. Cut only at readable `points`."""
    inside = points[(points >= start) & (points <= end)]
    a = max((p for p in inside if abs(gap[p] - gap[start]) < threshold), default=start)
    b = min((p for p in inside if p >= a and abs(gap[end] - gap[p]) < threshold), default=end)
    return Zone(float(gap[b] - gap[a]), int(a), int(b))


def strongest(zones, limit, sign=1, min_gain=MIN_ZONE_GAIN_S):
    """Up to `limit` zones where the faster (sign=1) or slower (sign=-1) car gained at least `min_gain`."""
    gains = sorted((z for z in zones if sign * z.gain >= min_gain), key=lambda z: sign * z.gain, reverse=True)
    return gains[:limit]


def zone_name(d_start, d_end, corner_d):
    """Corners inside the zone, else the nearest one it leads into or out of."""
    inside = [n for n, d in corner_d if d_start <= d <= d_end]
    if inside:
        return f"T{inside[0]}" if len(inside) == 1 else f"T{inside[0]}–T{inside[-1]}"
    if d_start == 0:
        return "start straight"
    before = [(d_start - d, n) for n, d in corner_d if d < d_start]
    after = [(d - d_end, n) for n, d in corner_d if d > d_end]
    if after and (not before or min(after) < min(before)):
        return f"into T{min(after)[1]}"
    return f"out of T{min(before)[1]}"


def table_rows(zones, total_gap):
    """Rounded zone gains plus a 'rest of lap' that makes the printed column add up to the lap gap."""
    gains = [round(z.gain, 3) for z in zones]
    total = round(float(total_gap), 3)
    return gains, round(total - sum(gains), 3), total
