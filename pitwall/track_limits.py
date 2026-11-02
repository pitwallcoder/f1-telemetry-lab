"""Track limits: laps and times race control deleted for track limits, by driver and by turn in one session, or by
driver and by circuit over a season.

  uv run python -m pitwall.track_limits 2026 --session "Mexico City" R --code PW-013
  uv run python -m pitwall.track_limits 2026 --code PW-014                             # the season so far
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from pitwall import circuits, cli, openf1, season, style

DELETED = re.compile(r"^CAR (\d+) \((\w+)\) (TIME [\d:.]+|LAP) DELETED - TRACK LIMITS AT TURN (\d+)(?: LAP (\d+))?")
REINSTATED = re.compile(r"^CAR (\d+) \(\w+\) (TIME [\d:.]+|LAP \d+) WILL BE REINSTATED")


@dataclass(frozen=True)
class Deletion:
    driver: int
    acronym: str
    turn: int
    circuit: str


@dataclass(frozen=True)
class Tally:
    context: str
    deletions: list
    drivers: dict  # driver number -> OpenF1 record, for names and colours
    name: str  # file name
    year: int
    circuit: circuits.Circuit = None  # one session: where the turns are


def deletions(messages, session):
    """Track-limits deletions in message order, minus those race control reinstated."""
    start, found = datetime.fromisoformat(session["date_start"]), {}
    for m in sorted(messages, key=lambda m: m["date"]):
        # OpenF1 files a few messages of an earlier session of the weekend under this one; deletions published
        # after the flag are real, so only the start bounds the session.
        if datetime.fromisoformat(m["date"]) < start:
            continue
        if hit := DELETED.match(m["message"]):
            car, acronym, what, turn, lap = hit.groups()
            ref = what if what != "LAP" else f"LAP {lap}"
            found[(int(car), ref)] = Deletion(int(car), acronym, int(turn), session["circuit_short_name"])
        elif hit := REINSTATED.match(m["message"]):
            found.pop((int(hit[1]), hit[2]), None)
    return list(found.values())


TOP_DRIVERS = 15


def session_tally(year, circuit, code):
    s = openf1.find_session(year, circuit, code)
    cache = openf1.settled(s)
    found = deletions(openf1.get("race_control", cache=cache, session_key=s["session_key"]), s)
    drivers = season.weekend_drivers(openf1.get("drivers", cache=cache, meeting_key=s["meeting_key"]))
    return Tally(f"{year} {openf1.meeting_name(s)} · {s['session_name']} · Track limits", found, drivers,
                 openf1.slug(s), year, circuits.circuit(s["circuit_key"], year))


def season_tally(year):
    now = datetime.now(timezone.utc)
    done = [s for s in openf1.get("sessions", year=year) if s["session_name"] in openf1.SESSIONS.values()
            and not s.get("is_cancelled") and datetime.fromisoformat(s["date_end"]) < now]
    if not done:
        raise openf1.DataNotFound(f"OpenF1 has no finished sessions for {year} yet")
    found = [d for s in done for d in
             deletions(openf1.get("race_control", cache=openf1.settled(s, now), session_key=s["session_key"]), s)]
    drivers = season.weekend_drivers(openf1.get("drivers", meeting_key=done[-1]["meeting_key"]))
    rounds = len({s["meeting_key"] for s in done})
    return Tally(f"{year} season · {rounds} rounds, up to {done[-1]['circuit_short_name']} · every session",
                 found, drivers, f"{year}-season", year)


def _name(t, driver, acronym):
    return style.surname(t.drivers[driver]) if driver in t.drivers else acronym


def headline(t):
    if t.circuit:
        turn, k = Counter(d.turn for d in t.deletions).most_common(1)[0]
        if len(t.deletions) == 1:
            return f"1 lap deleted for track limits, at Turn {turn}"
        return f"{len(t.deletions)} laps deleted for track limits, {k} of them at Turn {turn}"
    by_driver = Counter((d.driver, d.acronym) for d in t.deletions).most_common()
    top = [_name(t, n, a) for (n, a), k in by_driver if k == by_driver[0][1]]
    who = top[0] if len(top) == 1 else f"{', '.join(top[:-1])} and {top[-1]}"
    return f"{who} lost the most laps to track limits in {t.year}: {by_driver[0][1]}{' each' if len(top) > 1 else ''}"


def render(t):
    if not t.deletions:
        raise openf1.DataNotFound("Race control deleted no laps for track limits")
    fig = style.story_figure(headline(t), t.context, "Laps and lap times race control deleted because the car went "
                             "beyond the white lines" + (", including practice" if not t.circuit else ""))
    by_driver = Counter((d.driver, d.acronym) for d in t.deletions).most_common(TOP_DRIVERS)
    _bars(fig, [0.66, 0.08, 0.24, 0.66] if t.circuit else [0.16, 0.08, 0.3, 0.66], "DRIVERS",
          [(_name(t, n, a), k, t.drivers.get(n, {})) for (n, a), k in by_driver])
    if t.circuit:
        _turn_map(fig, t)
    else:
        _bars(fig, [0.64, 0.08, 0.26, 0.66], "CIRCUITS",
              [(c, k, None) for c, k in Counter(d.circuit for d in t.deletions).most_common(TOP_DRIVERS)])
    fig.text(0.95, 0.03, "Reinstated laps are not counted · data: OpenF1 race control" +
             (" · track: MultiViewer" if t.circuit else ""),
             color=style.FAINT, fontsize=9, ha="right")
    return fig


def _bars(fig, rect, heading, rows):
    ax = style.bare_axes(fig, rect)
    longest = max(k for _, k, _ in rows)
    ax.set_xlim(0, longest * 1.15)
    ax.set_ylim(max(len(rows), 10) - 0.4, -0.6)
    for y, (label, k, driver) in enumerate(rows):
        colour = style.team_colour(driver) if driver is not None else style.MUTED
        ax.barh(y, k, height=0.62, color=colour, linewidth=0)
        ax.text(-longest * 0.03, y, label, ha="right", va="center", color=style.TEXT, fontsize=12, fontweight="bold")
        ax.text(k + longest * 0.02, y, str(k), va="center", color=style.TEXT, fontsize=12, family=style.DIGITS)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(rect[0], rect[1] + rect[3] + 0.02, heading, color=style.FAINT, fontsize=9, fontweight="bold")


def _turn_map(fig, t):
    """The circuit with a circle at every turn where laps were deleted, sized by how many."""
    c = t.circuit
    ax = fig.add_axes([0.03, 0.06, 0.55, 0.7])
    x, y = style.rotate(c.line.x, c.line.y, c.rotation)
    ax.plot(x, y, color=style.FAINT, linewidth=5, solid_capstyle="round")
    at = dict(c.corners)
    most = max(Counter(d.turn for d in t.deletions).values())
    for turn, k in Counter(d.turn for d in t.deletions).items():
        if turn not in at:
            continue
        px, py = style.rotate(np.interp(at[turn], c.line.s, c.line.x), np.interp(at[turn], c.line.s, c.line.y),
                              c.rotation)
        ax.scatter([px], [py], s=300 + 2200 * k / most, color="#e0a33a", alpha=0.85, edgecolors=style.BG,
                   linewidths=2, zorder=3)
        ax.text(px, py, str(k), color="#111111", fontsize=12 + 6 * k / most, fontweight="bold", ha="center",
                va="center", zorder=4, family=style.DIGITS)
        out = style.outward(x, y, px, py) * (26 + 18 * k / most)
        ax.annotate(f"Turn {turn}", (px, py), xytext=tuple(out), textcoords="offset points", color=style.TEXT,
                    fontsize=11, fontweight="bold", ha="center", va="center", zorder=4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.margins(0.08)


def facts(t, code):
    return {"code": code, "context": t.context, "total": len(t.deletions),
            "by_driver": {_name(t, n, a): k for (n, a), k in Counter((d.driver, d.acronym) for d in t.deletions).most_common()},
            "by_turn" if t.circuit else "by_circuit":
                dict(Counter(f"T{d.turn}" if t.circuit else d.circuit for d in t.deletions).most_common()),
            "sources": ["OpenF1 race control", "MultiViewer"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.track_limits", __doc__, "PW-013", circuit=False)
    parser.add_argument("--session", nargs=2, metavar=("CIRCUIT", "SESSION"), help="one session instead of the season")
    args = parser.parse_args(argv)
    t = cli.fetch(lambda: session_tally(args.year, *args.session) if args.session else season_tally(args.year))
    fig = cli.fetch(lambda: render(t))
    print(style.save(fig, facts(t, args.code), args.code, f"{t.name}_track-limits", args.out))
    print(f"  {headline(t)}")


if __name__ == "__main__":
    main()
