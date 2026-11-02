"""Track limits: laps and times race control deleted for track limits, by driver and by turn in one session, or by
driver and by circuit over a season.

  uv run python -m pitwall.track_limits 2026 --session "Mexico City" R --code PW-013
  uv run python -m pitwall.track_limits 2026 --code PW-014                             # the season so far
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from pitwall import cli, openf1, style

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
    title: str
    subtitle: str
    deletions: list
    drivers: dict  # driver number -> OpenF1 record, for colours
    places: Counter  # turn ("T12") or circuit -> deletions
    place_label: str
    name: str  # file name


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


def session_tally(year, circuit, code):
    s = openf1.find_session(year, circuit, code)
    cache = openf1.settled(s)
    found = deletions(openf1.get("race_control", cache=cache, session_key=s["session_key"]), s)
    drivers = {d["driver_number"]: d for d in openf1.get("drivers", cache=cache, session_key=s["session_key"])}
    return Tally(f"{year} {openf1.meeting_name(s)} · {s['session_name']} · Track limits",
                 "Laps and lap times deleted for track limits", found, drivers,
                 Counter(f"T{d.turn}" for d in found), "BY TURN", openf1.slug(s))


def season_tally(year):
    now = datetime.now(timezone.utc)
    done = [s for s in openf1.get("sessions", year=year) if s["session_name"] in openf1.SESSIONS.values()
            and not s.get("is_cancelled") and datetime.fromisoformat(s["date_end"]) < now]
    if not done:
        raise openf1.DataNotFound(f"OpenF1 has no finished sessions for {year} yet")
    found = [d for s in done for d in
             deletions(openf1.get("race_control", cache=openf1.settled(s, now), session_key=s["session_key"]), s)]
    drivers = {d["driver_number"]: d for d in openf1.get("drivers", session_key=done[-1]["session_key"])}
    rounds = len({s["meeting_key"] for s in done})
    return Tally(f"{year} track limits so far", f"Laps and lap times deleted, every session · {rounds} rounds, "
                 f"up to {done[-1]['circuit_short_name']}", found, drivers,
                 Counter(d.circuit for d in found), "BY CIRCUIT", f"{year}-season")


def render(t):
    if not t.deletions:
        raise openf1.DataNotFound("Race control deleted no laps for track limits")
    fig = style.race_figure(t.title)
    fig.text(0.5, 0.875, f"{t.subtitle} · {len(t.deletions)} in total", color=style.MUTED, fontsize=11, ha="center")
    by_driver = Counter(d.driver for d in t.deletions)
    names = {d.driver: d.acronym for d in t.deletions}
    rows = [(names[n], k, style.team_colour(t.drivers.get(n, {}))) for n, k in by_driver.most_common()]
    _bars(fig, [0.1, 0.1, 0.38, 0.72], "BY DRIVER", rows)
    _bars(fig, [0.6, 0.1, 0.3, 0.72], t.place_label, [(p, k, style.MUTED) for p, k in t.places.most_common(12)])
    fig.text(0.95, 0.04, "Source: race control messages (OpenF1). Reinstated laps are not counted.",
             color=style.FAINT, fontsize=8.5, ha="right")
    return fig


def _bars(fig, rect, heading, rows):
    ax = style.bare_axes(fig, rect)
    longest = max(k for _, k, _ in rows)
    ax.set_xlim(0, longest * 1.15)
    ax.set_ylim(max(len(rows), 12) - 0.4, -0.6)
    for y, (label, k, colour) in enumerate(rows):
        ax.barh(y, k, height=0.62, color=colour, linewidth=0)
        ax.text(-longest * 0.02, y, label, ha="right", va="center", color=colour, fontsize=10.5, fontweight="bold")
        ax.text(k + longest * 0.02, y, str(k), va="center", color=style.TEXT, fontsize=10.5, family=style.DIGITS)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(rect[0], rect[1] + rect[3] + 0.015, heading, color=style.FAINT, fontsize=8.5, fontweight="bold")


def facts(t, code):
    names = {d.driver: d.acronym for d in t.deletions}
    return {"code": code, "title": t.title, "total": len(t.deletions),
            "by_driver": {names[n]: k for n, k in Counter(d.driver for d in t.deletions).most_common()},
            t.place_label.lower().replace(" ", "_"): dict(t.places.most_common()),
            "sources": ["OpenF1 race control"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.track_limits", __doc__, "PW-013", circuit=False)
    parser.add_argument("--session", nargs=2, metavar=("CIRCUIT", "SESSION"), help="one session instead of the season")
    args = parser.parse_args(argv)
    t = cli.fetch(lambda: session_tally(args.year, *args.session) if args.session else season_tally(args.year))
    fig = cli.fetch(lambda: render(t))
    print(style.save(fig, facts(t, args.code), args.code, f"{t.name}_track-limits", args.out))
    for n, k in Counter(d.acronym for d in t.deletions).most_common(5):
        print(f"  {n:<4}{k}")


if __name__ == "__main__":
    main()
