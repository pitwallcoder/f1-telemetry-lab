"""Pure lap-comparison maths: no network, no plotting."""
from dataclasses import dataclass

import numpy as np

MIN_ZONE_GAIN_S = 0.05
BRAKE_DROP_KMH = 40
BRAKE_LOOKAHEAD_M = 150
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


def braking_points(trace):
    """Top-speed index of each braking zone: a run of points from which speed drops hard within a short distance.

    The top of the run, not of the whole straight: drag can bleed off speed well before the driver brakes.
    """
    d, v = trace.distance, trace.speed
    braking = np.array([v[(d > d[i]) & (d <= d[i] + BRAKE_LOOKAHEAD_M)].min(initial=v[i]) <= v[i] - BRAKE_DROP_KMH
                        for i in range(len(d))])
    starts = np.flatnonzero(braking & ~np.concatenate([[False], braking[:-1]]))
    ends = np.flatnonzero(braking & ~np.concatenate([braking[1:], [False]]))
    runs = (part for s, e in zip(starts, ends) for part in _split_at_reacceleration(v, s, e))
    # Last of equal maxima: the point right before the driver brakes.
    return [int(e - np.argmax(v[s:e + 1][::-1])) for s, e in runs]


def _split_at_reacceleration(v, start, end):
    """Two stops close together form one braking run; cut it where the car clearly speeds up again."""
    cuts = [i for i in range(start + 1, end)
            if v[i] < v[i - 1] and v[i] <= v[i + 1] and v[i:end + 1].max() - v[i] >= BRAKE_DROP_KMH / 2]
    bounds = [start, *cuts, end]
    return list(zip(bounds, bounds[1:]))


def segments(trace):
    """Braking point to braking point, covering the whole lap.

    The gap is only read where both cars are flat out: in braking zones and corners it swings with
    where each driver brakes, so a peak there says nothing about the time actually kept.
    """
    fast_enough = MIN_READ_SPEED_RATIO * trace.speed.max()
    inner = (i for i in braking_points(trace) if 0 < i < len(trace.distance) - 1 and trace.speed[i] >= fast_enough)
    bounds = [0, *inner, len(trace.distance) - 1]
    return list(zip(bounds, bounds[1:]))


def corner_phase_end(speed, start, end):
    """Last point of a segment still below halfway between its slowest corner and the next straight's top speed."""
    threshold = (speed[start:end + 1].min() + speed[end]) / 2
    slow = np.flatnonzero(speed[start:end + 1] < threshold)
    return start + int(slow[-1]) + 1 if len(slow) else end


def segment_zones(trace, gap):
    """Every segment as a zone, in lap order: net gap change over the segment (positive: the faster car gained),
    spanning the braking-and-corner part for shading."""
    return [Zone(float(gap[end] - gap[start]), start, corner_phase_end(trace.speed, start, end))
            for start, end in segments(trace)]


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
