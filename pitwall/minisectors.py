"""Minisector dominance: the track split into equal parts, each coloured by the driver who was fastest through it on
his fastest lap.

  uv run python -m pitwall.minisectors 2026 "Mexico City" Q --code PW-019          # fastest of the top 3 teams
  uv run python -m pitwall.minisectors 2026 "Mexico City" Q VER LEC RUS
"""
from dataclasses import dataclass

import numpy as np

from pitwall import circuits, cli, openf1, speed_chart, style

MINISECTORS = 25
# Distances are good to a few metres at the timing lines (README), worth ~0.02 s at speed: a closer minisector has no
# measurable winner.
TIE_S = 0.02
TEAMS = 3


@dataclass(frozen=True)
class Dominance:
    session: dict
    meeting_name: str
    drivers: dict
    laps: dict  # driver -> fastest valid lap
    times: dict  # driver -> seconds in each minisector
    winners: list  # driver or None (too close to call) per minisector
    track: tuple  # x, y of the fastest lap's positions and the minisector each one is in
    rotation: float


def sector_times(t, d, length, n=MINISECTORS):
    """Time spent in each of `n` equal parts of the lap, from a run's time and pinned distance."""
    return np.diff(np.interp(np.linspace(0, length, n + 1), d, t))


def winners(times, tie_s=TIE_S):
    """Per minisector, the driver with the lowest time, or None when the next one is within `tie_s`."""
    drivers = list(times)
    table = np.array([times[d] for d in drivers])
    out = []
    for column in table.T:
        first, second = np.sort(column)[:2]
        out.append(drivers[int(np.argmin(column))] if second - first >= tie_s else None)
    return out


def default_drivers(best_laps, drivers):
    """The fastest driver of each of the TEAMS fastest teams."""
    picked, teams = [], set()
    for n in sorted(best_laps, key=lambda n: best_laps[n]["lap_duration"]):
        team = drivers.get(n, {}).get("team_name")
        if team not in teams:
            teams.add(team)
            picked.append(n)
    return picked[:TEAMS]


def dominance(year, circuit, code, wanted):
    session = openf1.find_session(year, circuit, code)
    drivers, best_laps = openf1.session_laps(session)
    picked = named(drivers, best_laps, wanted) if wanted else default_drivers(best_laps, drivers)
    circuit_line = circuits.circuit(session["circuit_key"], session["year"])
    runs = [speed_chart.lap_run(session, best_laps[n], circuit_line.line) for n in picked]
    pinned, _, shared = speed_chart.pin_to_shared_lines(runs)
    length = float(shared[-1])
    times = {n: sector_times(r.t, d, length) for n, r, d in zip(picked, runs, pinned)}
    return Dominance(session, openf1.meeting_name(session), drivers, {n: best_laps[n] for n in picked}, times,
                     winners(times), _track(runs[0], pinned[0], length), circuit_line.rotation)


def named(drivers, best_laps, wanted):
    """Drivers by acronym or number, each with a valid timed lap, fastest first."""
    by_name = {d["name_acronym"].upper(): n for n, d in drivers.items()}
    picked = [int(w) if str(w).isdigit() else by_name.get(str(w).upper()) for w in wanted]
    missing = [w for w, n in zip(wanted, picked) if n not in best_laps]
    if missing:
        raise openf1.DataNotFound(f"No valid timed lap in this session for: {', '.join(missing)}")
    return sorted(set(picked), key=lambda n: best_laps[n]["lap_duration"])


def _track(run, d, length):
    """Positions of a lap and the minisector each falls in."""
    inside = (run.pos_t >= 0) & (run.pos_t <= run.lap["lap_duration"])
    at = np.interp(run.pos_t[inside], run.t, d)
    part = np.clip((at / length * MINISECTORS).astype(int), 0, MINISECTORS - 1)
    return run.pos_x[inside], run.pos_y[inside], part


def colour(dom, driver):
    return style.team_colour(dom.drivers[driver]) if driver is not None else style.FAINT


def render(dom):
    s = dom.session
    fig = style.race_figure(f"{s['year']} {dom.meeting_name} · {s['session_name']} · Minisector dominance")
    fig.text(0.5, 0.875, f"Fastest laps, track split into {MINISECTORS} equal minisectors, each in the colour of "
             "whoever was quickest through it", color=style.MUTED, fontsize=11, ha="center")
    ax = fig.add_axes([0.04, 0.08, 0.6, 0.76])
    x, y, part = dom.track
    x, y = style.rotate(np.asarray(x, float), np.asarray(y, float), dom.rotation)
    ax.plot(x, y, color=style.GRID, linewidth=9, solid_capstyle="round", zorder=1)
    for k, who in enumerate(dom.winners):
        idx = np.flatnonzero(part == k)
        if idx.size:
            idx = np.append(idx, min(idx[-1] + 1, len(x) - 1))
            ax.plot(x[idx], y[idx], color=colour(dom, who), linewidth=6, solid_capstyle="butt", zorder=2)
    ax.scatter([x[0]], [y[0]], s=60, color=style.TEXT, zorder=3)
    ax.annotate("start / finish", (x[0], y[0]), xytext=(8, 8), textcoords="offset points", color=style.MUTED,
                fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")
    _legend(fig, dom)
    return fig


def _legend(fig, dom):
    best = min(lap["lap_duration"] for lap in dom.laps.values())
    fig.text(0.7, 0.78, "MINISECTORS", color=style.FAINT, fontsize=8.5, fontweight="bold")
    for k, n in enumerate(dom.laps):
        y, info, lap = 0.72 - k * 0.075, dom.drivers[n], dom.laps[n]["lap_duration"]
        fig.text(0.7, y, info["name_acronym"], color=colour(dom, n), fontsize=16, fontweight="bold", va="center")
        fig.text(0.76, y, str(dom.winners.count(n)), color=style.TEXT, fontsize=16, fontweight="bold", va="center",
                 family=style.DIGITS)
        fig.text(0.8, y, style.lap_time(lap) if lap == best else f"{style.lap_time(lap)}  +{lap - best:.3f}",
                 color=style.MUTED, fontsize=11, va="center", family=style.DIGITS)
    ties = dom.winners.count(None)
    if ties:
        y = 0.72 - len(dom.laps) * 0.075
        fig.text(0.7, y, "—", color=style.FAINT, fontsize=16, fontweight="bold", va="center")
        fig.text(0.76, y, str(ties), color=style.MUTED, fontsize=16, fontweight="bold", va="center",
                 family=style.DIGITS)
        fig.text(0.8, y, f"within {TIE_S} s, too close to call", color=style.FAINT, fontsize=11, va="center")
    fig.text(0.95, 0.03, "Distance from speed and position fused, pinned to official sector times (see README). "
             "data: OpenF1 · track: MultiViewer", color=style.FAINT, fontsize=8.5, ha="right")


def facts(dom, code):
    name = lambda n: dom.drivers[n]["name_acronym"] if n is not None else None
    s = dom.session
    return {"code": code, "year": s["year"], "event": dom.meeting_name, "session": s["session_name"],
            "minisectors": MINISECTORS, "tie_s": TIE_S,
            "drivers": [{"name": name(n), "lap_time": style.lap_time(dom.laps[n]["lap_duration"]),
                         "won": dom.winners.count(n), "minisector_s": [round(float(t), 3) for t in dom.times[n]]}
                        for n in dom.laps],
            "winners": [name(n) for n in dom.winners],
            "precision": {"minisector_s": TIE_S}, "sources": ["OpenF1", "MultiViewer"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.minisectors", __doc__, "PW-019")
    parser.add_argument("session", choices=openf1.SESSIONS, help="session code")
    parser.add_argument("drivers", nargs="*", help="acronyms or numbers; default: fastest of the top 3 teams")
    args = parser.parse_args(argv)
    dom = cli.fetch(lambda: dominance(args.year, args.circuit, args.session, args.drivers))
    names = "-vs-".join(dom.drivers[n]["name_acronym"] for n in dom.laps)
    print(style.save(render(dom), facts(dom, args.code), args.code,
                     f"{openf1.slug(dom.session)}_minisectors_{names}", args.out))
    for n in dom.laps:
        print(f"  {dom.drivers[n]['name_acronym']:<4}{dom.winners.count(n)}")
    print(f"  tie {dom.winners.count(None)}")


if __name__ == "__main__":
    main()
