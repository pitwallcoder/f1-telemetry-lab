"""Speed-trace comparison of two drivers' fastest valid laps: gather the facts, draw them, write them out.

The chart only states measured facts; interpretation belongs in the post that shares it.
"""
from dataclasses import dataclass

import numpy as np

from pitwall import circuits, distance, openf1, style, telemetry
from pitwall.circuits import UNITS_PER_M
from pitwall.telemetry import Trace

FALLBACK_COLOUR = "a1a1aa"
ZONE_TAGS = "ABCDEFGH"
PAD_S = 3  # data either side of the lap, so the fit and the finish line are not cut at the edges
GRID_S = 0.05
ZONE_INSET_M = 8  # zones touch end to end; a small gap keeps neighbours of the same colour apart


@dataclass(frozen=True)
class Driver:
    name: str
    colour: str
    lap: dict
    trace: Trace


@dataclass(frozen=True)
class TrackMap:
    x: np.ndarray
    y: np.ndarray
    t: np.ndarray
    finish: list
    rotation: float


@dataclass(frozen=True)
class Quality:
    """How well the two laps agree with official timing before being pinned to it."""
    fit_residual_m: tuple  # position scatter around each car's fitted distance
    line_disagreement_m: tuple  # where the two cars are at their official sector 1, sector 2 and finish crossings

    def trustworthy(self):
        # 90% of the 15 validation sessions (README) stay within these.
        return max(map(abs, self.line_disagreement_m)) <= 5 and max(self.fit_residual_m) <= 6


@dataclass(frozen=True)
class Comparison:
    session: dict
    meeting_name: str
    fast: Driver
    slow: Driver
    gap: np.ndarray
    zones: list  # telemetry.Zone in lap order; positive gain: the faster car gained there
    where: list
    corner_d: list
    track: TrackMap
    quality: Quality

    @property
    def context(self):
        return f"{self.session['year']} {self.meeting_name} · {self.session['session_name']}"

    @property
    def slug(self):
        return openf1.slug(self.session)

    def sector_gaps(self):
        return [self.slow.lap[f"duration_sector_{i}"] - self.fast.lap[f"duration_sector_{i}"] for i in (1, 2, 3)]

    def biggest_zone(self):
        return max(self.zones, key=lambda z: abs(z.gain), default=None)


@dataclass(frozen=True)
class _Run:
    lap: dict
    t: np.ndarray
    d: np.ndarray  # metres from this car's own position at its official lap start
    start_s: float  # where that was on the track line
    speed: np.ndarray
    residual_m: float
    pos_t: np.ndarray
    pos_x: np.ndarray
    pos_y: np.ndarray


def from_session(year, circuit, session_code, wanted_drivers=()):
    """Comparison for e.g. 2026, "Mexico City", "FP1", ["LEC", "ANT"]; names as documented in README."""
    session = openf1.find_session(year, circuit, session_code)
    meeting = openf1.get("meetings", meeting_key=session["meeting_key"])
    drivers, best_laps = openf1.session_laps(session)
    pair = openf1.pick_drivers(best_laps, drivers, list(wanted_drivers))
    meeting_name = meeting[0]["meeting_name"] if meeting else session["location"]
    return compare(session, meeting_name, drivers, best_laps, pair)


def compare(session, meeting_name, drivers, best_laps, pair):
    fast_n, slow_n = sorted(pair, key=lambda n: best_laps[n]["lap_duration"])
    track = circuits.circuit(session["circuit_key"], session["year"])
    fast_run, slow_run = (_run(session, best_laps[n], track.line) for n in (fast_n, slow_n))
    fast_d, slow_d, official_gaps, disagreement = _pin_to_official_lines(fast_run, slow_run)
    fast, slow = (_driver(drivers[n], run, d) for n, run, d in ((fast_n, fast_run, fast_d), (slow_n, slow_run, slow_d)))
    raw_gap = telemetry.delta(fast.trace, slow.trace)
    gap = distance.pin(fast_d, telemetry.smooth(fast_d, raw_gap), official_gaps)
    every = telemetry.turning_zones(gap, telemetry.measurable(fast.trace), telemetry.straight_ends(fast.trace))
    zones = telemetry.notable(every, len(ZONE_TAGS))
    corner_d = [(n, float(np.interp(distance.along_lap(s, fast_run.start_s, track.line.length), fast_run.d, fast_d)))
                for n, s in track.corners]
    where = [telemetry.zone_name(fast.trace.distance[z.start], fast.trace.distance[z.end], corner_d) for z in zones]
    quality = Quality((fast_run.residual_m, slow_run.residual_m), disagreement)
    return Comparison(session, meeting_name, fast, slow, gap, zones, where, corner_d,
                      _track_map(fast_run, track.rotation), quality)


def _run(session, lap, line):
    t_car, car = openf1.lap_samples("car_data", session, lap, pad_s=PAD_S)
    t_pos, positions = openf1.lap_samples("location", session, lap, pad_s=PAD_S)
    speed = np.array([c["speed"] for c in car], dtype=float)
    x = np.array([p["x"] for p in positions], dtype=float) / UNITS_PER_M
    y = np.array([p["y"] for p in positions], dtype=float) / UNITS_PER_M
    fit = distance.fuse(t_car, speed, t_pos, distance.project(line, x, y), line.length)
    t = np.append(np.arange(0, lap["lap_duration"], GRID_S), lap["lap_duration"])
    d = fit.distance(t)
    return _Run(lap, t, d - d[0], float(d[0] % line.length), np.interp(t + fit.delay, t_car, speed),
                fit.residual_m, t_pos, x, y)


def _crossings(lap):
    """Official times at which the car crossed the sector 1 and 2 lines and the finish line."""
    s1, s2 = lap["duration_sector_1"], lap["duration_sector_2"]
    return [s1, s1 + s2, lap["lap_duration"]]


def _pin_to_official_lines(a, b):
    """Both cars cross the same timing lines: hold each at the lines' shared position at its official times.

    Also returns the official gap at each line, as (distance, seconds), for the gap curve to pass through.
    """
    anchors_a, anchors_b, gaps, disagreement = [(0.0, 0.0)], [(0.0, 0.0)], [(0.0, 0.0)], []
    for ta, tb in zip(_crossings(a.lap), _crossings(b.lap)):
        da, db = float(np.interp(ta, a.t, a.d)), float(np.interp(tb, b.t, b.d))
        disagreement.append(round(db - da, 1))
        anchors_a.append((ta, (da + db) / 2))
        anchors_b.append((tb, (da + db) / 2))
        gaps.append(((da + db) / 2, tb - ta))
    return distance.pin(a.t, a.d, anchors_a), distance.pin(b.t, b.d, anchors_b), gaps, tuple(disagreement)


def _driver(info, run, d):
    return Driver(info["name_acronym"], info.get("team_colour") or FALLBACK_COLOUR, run.lap, Trace(run.t, d, run.speed))


def _track_map(run, rotation):
    finish = [(float(np.interp(at, run.pos_t, run.pos_x)), float(np.interp(at, run.pos_t, run.pos_y))) for at in (0, 0.2)]
    in_lap = (run.pos_t >= 0) & (run.pos_t <= run.lap["lap_duration"])
    return TrackMap(run.pos_x[in_lap], run.pos_y[in_lap], run.pos_t[in_lap], finish, rotation)


def zone_colour(comparison, zone):
    """A zone takes the colour of the driver who gained time there."""
    return f"#{(comparison.fast if zone.gain > 0 else comparison.slow).colour}"


def _inset(comparison, zone):
    d = comparison.fast.trace.distance
    return d[zone.start] + ZONE_INSET_M, d[zone.end] - ZONE_INSET_M


def render(comparison, code):
    c = comparison
    fig = style.figure()
    style.context_line(fig, code, c.context)
    _timing_header(fig, c)
    speed_ax = _speed_panel(fig, c)
    _gap_panel(fig, c, speed_ax)
    zone_masks = []
    for tag, z in zip(ZONE_TAGS, c.zones):
        start, end = np.interp(_inset(c, z), c.fast.trace.distance, c.fast.trace.t)
        zone_masks.append((tag, (c.track.t >= start) & (c.track.t <= end), zone_colour(c, z)))
    style.track_map(fig, [0.78, 0.46, 0.19, 0.30], c.track.x, c.track.y, zone_masks, c.track.finish, c.track.rotation)
    _gain_table(fig, c)
    style.footer(fig, "data: OpenF1 · track & corners: MultiViewer")
    return fig


def lap_time(seconds):
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}:{rest:06.3f}"


def _timing_header(fig, c):
    big = {"fontsize": 26, "fontweight": "bold"}
    style.text_row(fig, 0.04, 0.85, [
        (c.fast.name, f"#{c.fast.colour}", big), (lap_time(c.fast.lap["lap_duration"]), style.TEXT, big),
        ("   ", style.TEXT, big),
        (c.slow.name, f"#{c.slow.colour}", big), (f"+{c.gap[-1]:.3f}", style.TEXT, big)])
    sectors = "   ".join(f"S{i} {g:+.3f}" for i, g in enumerate(c.sector_gaps(), 1))
    fig.text(0.04, 0.808, f"Fastest laps · {c.slow.name} vs {c.fast.name} by sector   {sectors}", fontsize=10,
             color=style.MUTED)


def _speed_panel(fig, c):
    ax = fig.add_axes([0.06, 0.39, 0.68, 0.37])
    style.style_axes(ax)
    for z in c.zones:
        style.highlight(ax, *_inset(c, z), zone_colour(c, z))
    # Team-mates share a colour, so the slower one gets a dashed line.
    slow_dash = "--" if c.slow.colour.lower() == c.fast.colour.lower() else "-"
    for driver, dash in ((c.fast, "-"), (c.slow, slow_dash)):
        ax.plot(driver.trace.distance, driver.trace.speed, color=f"#{driver.colour}", linewidth=1.2,
                linestyle=dash, label=driver.name)
    ax.set_ylabel("Speed [km/h]")
    ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=style.TEXT, ncols=2)
    ax.tick_params(labelbottom=False)
    style.corner_ticks(ax, c.corner_d)
    return ax


def _gap_panel(fig, c, speed_ax):
    ax = fig.add_axes([0.06, 0.13, 0.68, 0.2], sharex=speed_ax)
    style.style_axes(ax)
    distance_m = c.fast.trace.distance
    for tag, z in zip(ZONE_TAGS, c.zones):
        colour = zone_colour(c, z)
        style.highlight(ax, *_inset(c, z), colour)
        ax.annotate(tag, xy=((distance_m[z.start] + distance_m[z.end]) / 2, 1),
                    xycoords=("data", "axes fraction"), xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", color=colour, fontsize=9, fontweight="bold")
    # Below this speed a few metres of position error is worth tenths: draw that part of the line faded.
    reliable = telemetry.measurable(c.fast.trace)
    ax.plot(distance_m, c.gap, color=style.TEXT, linewidth=1.4, alpha=0.3)
    ax.plot(distance_m, np.where(reliable, c.gap, np.nan), color=style.TEXT, linewidth=1.4)
    ax.axhline(0, color=style.FAINT, linewidth=0.8)
    ax.text(0.01, 0.96, "faded: slow corners, ±0.2 s at 4 Hz", transform=ax.transAxes, fontsize=7,
            color=style.FAINT, va="top")
    ax.set_ylabel(f"{c.slow.name} gap [s]")
    ax.set_xlabel("Distance [m]")
    return ax


def table(comparison):
    """Rows of (tag, who gained, seconds gained, where); the rest-of-lap and lap rows make the column add up."""
    c = comparison
    gains, rest, total = telemetry.table_rows(c.zones, c.gap[-1])
    rows = [(tag, c.fast.name if gain > 0 else c.slow.name, abs(gain), place)
            for tag, gain, place in zip(ZONE_TAGS, gains, c.where)]
    rest_by = c.fast.name if rest >= 0 else c.slow.name
    return rows + [("·", rest_by, abs(rest), "rest of lap"), ("=", c.fast.name, total, "lap")]


def _gain_table(fig, c):
    fig.text(0.79, 0.40, "NET GAIN BY ZONE", fontsize=9, color=style.MUTED)
    colours = {c.fast.name: f"#{c.fast.colour}", c.slow.name: f"#{c.slow.colour}"}
    for k, (tag, who, seconds, place) in enumerate(table(c)):
        row_y = 0.36 - k * 0.036
        tag_colour = zone_colour(c, c.zones[k]) if k < len(c.zones) else style.MUTED
        fig.text(0.79, row_y, tag, fontsize=10, color=tag_colour, fontweight="bold")
        fig.text(0.805, row_y, who, fontsize=10, color=colours[who], fontweight="bold")
        fig.text(0.845, row_y, f"+{seconds:.3f}", fontsize=12, color=style.TEXT, fontweight="bold")
        fig.text(0.97, row_y, place, fontsize=9, color=style.MUTED, ha="right")


def facts(comparison, code):
    """Everything the chart states, for writing the post around it."""
    c = comparison
    fast_d, slow_d = c.fast.trace.distance, c.slow.trace.distance
    rest = table(c)[-2]

    def zone_facts(tag, zone, place):
        span = slice(zone.start, zone.end + 1)
        slow_speed = np.interp(fast_d[span], slow_d, c.slow.trace.speed)
        return {"tag": tag, "corners": place, "gained_by": c.fast.name if zone.gain > 0 else c.slow.name,
                "seconds": round(abs(zone.gain), 3), "biggest_on_lap": zone == c.biggest_zone(),
                "from_m": round(float(fast_d[zone.start])), "to_m": round(float(fast_d[zone.end])),
                "speed_at_braking_kmh": {c.fast.name: round(float(c.fast.trace.speed[zone.start])),
                                         c.slow.name: round(float(slow_speed[0]))},
                "minimum_speed_kmh": {c.fast.name: round(float(c.fast.trace.speed[span].min())),
                                      c.slow.name: round(float(slow_speed.min()))}}

    def driver_facts(d):
        return {"name": d.name, "lap_number": d.lap["lap_number"], "lap_time": lap_time(d.lap["lap_duration"]),
                "sectors": [d.lap[f"duration_sector_{i}"] for i in (1, 2, 3)],
                "top_speed_kmh": round(float(d.trace.speed.max()))}

    return {
        "code": code, "event": c.meeting_name, "session": c.session["session_name"], "year": c.session["year"],
        "circuit": c.session["circuit_short_name"],
        "faster": driver_facts(c.fast), "slower": driver_facts(c.slow),
        "official_gap_s": {"lap": round(float(c.gap[-1]), 3), "sectors": [round(g, 3) for g in c.sector_gaps()]},
        "zones": [zone_facts(tag, z, place) for tag, z, place in zip(ZONE_TAGS, c.zones, c.where)],
        "rest_of_lap": {"gained_by": rest[1], "seconds": rest[2]},
        "precision": {"lap_and_sectors": "official, exact", "zones_s": 0.05, "trustworthy": c.quality.trustworthy(),
                      "fit_residual_m": c.quality.fit_residual_m, "line_disagreement_m": c.quality.line_disagreement_m},
        "sources": ["OpenF1", "MultiViewer"],
    }


def save(fig, comparison, code, out_dir="out"):
    name = f"{comparison.slug}_{comparison.fast.name}-vs-{comparison.slow.name}"
    return style.save(fig, facts(comparison, code), code, name, out_dir)
