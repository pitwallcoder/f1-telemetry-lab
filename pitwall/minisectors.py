"""Minisector dominance: the track split into equal parts, each coloured by the driver who was fastest through it on
his fastest lap.

  uv run python -m pitwall.minisectors 2026 "Mexico City" Q --code PW-019          # fastest of the top 2 teams
  uv run python -m pitwall.minisectors 2026 "Mexico City" Q VER LEC RUS
"""
from dataclasses import dataclass

import numpy as np

from pitwall import circuits, cli, openf1, speed_chart, style

MINISECTORS = 25
# Distances are good to a few metres at the timing lines (README), worth ~0.02 s at speed: a closer minisector has no
# measurable winner.
TIE_S = 0.02
TEAMS = 2  # two colours read at a glance; a third turns the map into a puzzle


@dataclass(frozen=True)
class Dominance:
    session: dict
    meeting_name: str
    drivers: dict
    laps: dict  # driver -> fastest valid lap
    times: dict  # driver -> seconds in each minisector
    winners: list  # driver or None (too close to call) per minisector
    track: tuple  # x, y of the fastest lap's positions and the minisector each one is in
    corners: list  # (number, x, y)
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
                     winners(times), _track(runs[0], pinned[0], length), _corners(circuit_line),
                     circuit_line.rotation)


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


def _corners(c):
    return [(n, float(np.interp(s, c.line.s, c.line.x)), float(np.interp(s, c.line.s, c.line.y))) for n, s in c.corners]


def headline(drivers, laps):
    (a, la), (b, lb) = sorted(laps.items(), key=lambda kv: kv[1]["lap_duration"])[:2]
    gap = lb["lap_duration"] - la["lap_duration"]
    return f"{style.surname(drivers[a])} beat {style.surname(drivers[b])} by {gap:.3f} s: where each was quicker"


def colour(dom, driver):
    return style.team_colour(dom.drivers[driver]) if driver is not None else style.FAINT


def render(dom):
    s = dom.session
    fig = style.story_figure(headline(dom.drivers, dom.laps), f"{s['year']} {dom.meeting_name} · {s['session_name']} · "
                             "fastest laps", f"The track cut into {MINISECTORS} equal parts, each in the colour of the "
                             f"driver who was quicker there. Grey: less than {TIE_S} s apart, too close to call.")
    ax = fig.add_axes([0.03, 0.06, 0.62, 0.72])
    x, y, part = dom.track
    x, y = style.rotate(np.asarray(x, float), np.asarray(y, float), dom.rotation)
    for k, who in enumerate(dom.winners):
        idx = np.flatnonzero(part == k)
        if idx.size:
            idx = np.append(idx, min(idx[-1] + 1, len(x) - 1))
            ax.plot(x[idx], y[idx], color=colour(dom, who), linewidth=9 if who else 5, solid_capstyle="butt", zorder=2)
    _corner_numbers(ax, dom, x, y)
    ax.scatter([x[0]], [y[0]], s=70, color=style.TEXT, zorder=3)
    ax.annotate("start / finish", (x[0], y[0]), xytext=(10, -14), textcoords="offset points", color=style.TEXT,
                fontsize=10)
    ax.set_aspect("equal")
    ax.axis("off")
    _legend(fig, dom)
    return fig


def _corner_numbers(ax, dom, x, y):
    """Each corner's number just off the track, on the side away from the middle of the circuit."""
    span = max(np.ptp(x), np.ptp(y))
    for n, px, py in dom.corners:
        px, py = style.rotate(np.array(px), np.array(py), dom.rotation)
        normal = style.outward(x, y, px, py)
        ax.text(px + normal[0] * span * 0.035, py + normal[1] * span * 0.035, str(n), color=style.MUTED,
                fontsize=10, ha="center", va="center", family=style.DIGITS)


def _legend(fig, dom):
    best = min(lap["lap_duration"] for lap in dom.laps.values())
    for k, n in enumerate(dom.laps):
        y, info, lap = 0.68 - k * 0.15, dom.drivers[n], dom.laps[n]["lap_duration"]
        fig.text(0.68, y, style.surname(info), color=colour(dom, n), fontsize=24, fontweight="bold", va="center")
        fig.text(0.68, y - 0.05, f"quicker in {dom.winners.count(n)} of {MINISECTORS} parts", color=style.TEXT,
                 fontsize=13, va="center")
        fig.text(0.95, y, style.lap_time(lap) if lap == best else f"+{lap - best:.3f} s", color=style.MUTED,
                 fontsize=15, va="center", ha="right", family=style.DIGITS)
    ties = dom.winners.count(None)
    if ties:
        fig.text(0.68, 0.68 - len(dom.laps) * 0.15, f"{ties} parts too close to call", color=style.MUTED, fontsize=13,
                 va="center")
    fig.text(0.95, 0.04, "Distance from car speed and position, pinned to official sector times · data: OpenF1 · "
             "track: MultiViewer", color=style.FAINT, fontsize=9, ha="right")


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
    parser.add_argument("drivers", nargs="*", help="acronyms or numbers; default: fastest of the top 2 teams")
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
