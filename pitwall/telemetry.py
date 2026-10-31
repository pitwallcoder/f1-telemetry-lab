"""Pure lap-comparison maths: no network, no plotting."""
from dataclasses import dataclass

import numpy as np

MIN_ZONE_GAIN_S = 0.05
# A rise or fall of the gap smaller than this is treated as noise when finding where it turns.
TURN_S = 0.025
# Straight-line time is won slowly and corner time quickly, so zones are also cut where a long straight ends:
# where the car brakes from above this share of its top speed.
STRAIGHT_RATIO = 0.8
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


def straight_ends(trace):
    """Indices where the car starts braking at the end of a long straight."""
    fast = trace.speed >= STRAIGHT_RATIO * trace.speed.max()
    return np.flatnonzero(fast[:-1] & ~fast[1:])


def turning_zones(gap, readable, cuts=(), threshold=TURN_S):
    """Split the lap where the gap turns, reading it only at `readable` points, the lap start and the lap end,
    and at each of `cuts`.

    A turn counts once the gap has moved back by `threshold` from its last extreme, so noise doesn't split a zone.
    Zones are in lap order and their gains add up to the lap gap.
    """
    points = np.unique(np.concatenate([[0], np.flatnonzero(readable), [len(gap) - 1]]))
    turns, extreme, trend = [points[0]], points[0], 0
    for i in points[1:]:
        if trend == 0:
            trend, extreme = np.sign(gap[i] - gap[extreme]), i
        elif trend * (gap[i] - gap[extreme]) > 0:
            extreme = i
        elif trend * (gap[extreme] - gap[i]) >= threshold:
            turns.append(extreme)
            trend, extreme = -trend, i
    bounds = np.unique(np.concatenate([turns, [extreme, points[-1]], np.asarray(cuts, dtype=int)]))
    return [Zone(float(gap[b] - gap[a]), int(a), int(b)) for a, b in zip(bounds, bounds[1:])]


def notable(zones, limit, min_gain=MIN_ZONE_GAIN_S):
    """Zones where either car gained at least `min_gain`, the `limit` biggest of them, in lap order."""
    big = sorted((z for z in zones if abs(z.gain) >= min_gain), key=lambda z: abs(z.gain), reverse=True)
    return sorted(big[:limit], key=lambda z: z.start)


def zone_name(d_start, d_end, corner_d):
    """Corners inside the zone, or the corners on either side of it: "T3→T4", "line→T1", "T17→line"."""
    inside = [n for n, d in corner_d if d_start <= d <= d_end]
    if inside:
        return f"T{inside[0]}" if len(inside) == 1 else f"T{inside[0]}–T{inside[-1]}"
    before = [n for n, d in corner_d if d < d_start]
    after = [n for n, d in corner_d if d > d_end]
    return f"{f'T{before[-1]}' if before else 'line'}→{f'T{after[0]}' if after else 'line'}"


def table_rows(zones, total_gap):
    """Rounded zone gains plus a 'rest of lap' that makes the printed column add up to the lap gap."""
    gains = [round(z.gain, 3) for z in zones]
    total = round(float(total_gap), 3)
    return gains, round(total - sum(gains), 3), total
