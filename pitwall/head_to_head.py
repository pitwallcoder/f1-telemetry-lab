"""Teammate head-to-head over a season: who was classified ahead, in qualifying or in the race, round by round.

  uv run python -m pitwall.head_to_head 2026 Q --code PW-011
  uv run python -m pitwall.head_to_head 2026 R --code PW-012
"""
import statistics
from dataclasses import dataclass

from pitwall import cli, openf1, race, season, style

SESSIONS = {"Q": "Qualifying", "R": "Race"}
RULE = "A classified driver beats an unclassified teammate (DNF, DSQ, no time); rounds where neither is classified don't count."


@dataclass(frozen=True)
class Duel:
    team: str
    first: int  # the teammate with more rounds ahead
    second: int
    wins: dict  # driver -> rounds ahead
    gaps: list  # qualifying: first minus second, seconds, in the last part both set a time in
    drivers: dict  # driver -> OpenF1 record from the last round they were teammates (colour, acronym)

    def name(self, driver):
        return self.drivers[driver]["name_acronym"]

    @property
    def median_gap(self):
        return statistics.median(self.gaps) if self.gaps else None


def ahead(a, b, position):
    """The teammate classified ahead, or None when neither is classified."""
    pa, pb = position.get(a), position.get(b)
    if pa is None and pb is None:
        return None
    return a if pb is None or (pa is not None and pa < pb) else b


def same_part_gap(times_a, times_b):
    """a minus b in the last part of qualifying both set a time in (Q3, else Q2, else Q1), or None."""
    common = [(x, y) for x, y in zip(times_a or [], times_b or []) if x and y]
    return common[-1][0] - common[-1][1] if common else None


def teammates(r):
    """(team, a, b) for every team with exactly two drivers in this round's result; teams are per round because
    drivers change seats mid-season."""
    cars = {}
    for row in r.result:
        cars.setdefault(r.drivers.get(row["driver_number"], {}).get("team_name"), []).append(row["driver_number"])
    return [(t, *sorted(pair)) for t, pair in cars.items() if t and len(pair) == 2]


def duels(rounds, with_gaps):
    tally = {}
    for r in rounds:
        position = race.classification(r.result)
        times = {row["driver_number"]: row.get("duration") for row in r.result}
        for t, a, b in teammates(r):
            winner = ahead(a, b, position)
            if winner is None:
                continue
            entry = tally.setdefault((t, a, b), {a: 0, b: 0, "gaps": []})
            entry[winner] += 1
            entry["drivers"] = {a: r.drivers[a], b: r.drivers[b]}
            gap = same_part_gap(times[a], times[b]) if with_gaps else None
            if gap is not None:
                entry["gaps"].append(gap)
    if not tally:
        raise openf1.DataNotFound("OpenF1 has no team names for these rounds yet, so no teammates can be paired")
    return sorted((_duel(t, a, b, e) for (t, a, b), e in tally.items()),
                  key=lambda d: (d.team, -sum(d.wins.values())))


def _duel(t, a, b, entry):
    first, second = (a, b) if entry[a] >= entry[b] else (b, a)
    sign = 1 if first == a else -1
    return Duel(t, first, second, {a: entry[a], b: entry[b]}, [sign * g for g in entry["gaps"]], entry["drivers"])


def render(rounds, found, kind):
    year, last = rounds[-1].session["year"], rounds[-1].session["circuit_short_name"]
    fig = style.race_figure(f"{year} teammate head-to-head · {SESSIONS[kind]}")
    fig.text(0.5, 0.875, f"Who was classified ahead, round by round · {len(rounds)} rounds, up to {last}",
             color=style.MUTED, fontsize=11, ha="center")
    ax = style.bare_axes(fig, [0.2, 0.1, 0.56 if kind == "Q" else 0.6, 0.74])
    widest = max(max(d.wins.values()) for d in found)
    ax.set_xlim(-widest * 1.45, widest * 1.45)
    ax.set_ylim(len(found) - 0.4, -0.6)
    ax.axvline(0, color=style.FAINT, linewidth=0.8)
    ax.set_xticks([])
    ax.set_yticks([])
    for y, d in enumerate(found):
        _row(fig, ax, y, d, kind)
    fig.text(0.05, 0.045, RULE, color=style.FAINT, fontsize=8.5)
    if kind == "Q":
        fig.text(0.86, 0.855, "MEDIAN GAP", color=style.FAINT, fontsize=8.5, fontweight="bold", ha="center")
        fig.text(0.95, 0.045, "Gap: last part of qualifying both drivers set a time in", color=style.FAINT, fontsize=8.5,
                 ha="right")
    return fig


def _row(fig, ax, y, d, kind):
    colour = style.team_colour(d.drivers[d.first])
    wf, ws = d.wins[d.first], d.wins[d.second]
    ax.barh(y, -wf, height=0.58, color=colour, linewidth=0)
    ax.barh(y, ws, height=0.58, color=colour, alpha=0.4, linewidth=0)
    name = {"fontsize": 11.5, "fontweight": "bold", "va": "center"}
    ax.text(-wf - 0.4, y, f"{d.name(d.first)}  {wf}", ha="right", color=style.TEXT, **name)
    ax.text(ws + 0.4, y, f"{ws}  {d.name(d.second)}", ha="left", color=style.MUTED, **name)
    fy = _fig_y(fig, ax, y)
    fig.text(0.05, fy, d.team, color=colour, fontsize=10.5, fontweight="bold", va="center")
    if kind == "Q" and d.median_gap is not None:
        fig.text(0.86, fy, gap_label(d), color=style.TEXT,
                 fontsize=10, va="center", ha="center", family=style.DIGITS)


def gap_label(d):
    if round(d.median_gap, 3) == 0:
        return "level"
    return f"{d.name(d.first if d.median_gap < 0 else d.second)} by {abs(d.median_gap):.3f} s"


def _fig_y(fig, ax, y):
    return fig.transFigure.inverted().transform(ax.transData.transform((0, y)))[1]


def facts(rounds, found, kind, code):
    return {
        "code": code, "year": rounds[-1].session["year"], "session": SESSIONS[kind],
        "rounds": [r.session["circuit_short_name"] for r in rounds],
        "duels": [{"team": d.team, "drivers": [d.name(d.first), d.name(d.second)],
                   "ahead": [d.wins[d.first], d.wins[d.second]],
                   "median_gap_s": None if d.median_gap is None else round(d.median_gap, 3)} for d in found],
        "rule": RULE, "sources": ["OpenF1"],
    }


def save(fig, rounds, found, kind, code, out_dir="out"):
    name = f"{rounds[-1].session['year']}-teammates-{SESSIONS[kind].lower()}"
    return style.save(fig, facts(rounds, found, kind, code), code, name, out_dir)


def main(argv=None):
    parser = cli.parser("python -m pitwall.head_to_head", __doc__, "PW-011", circuit=False)
    parser.add_argument("session", choices=SESSIONS, help="Q for qualifying, R for the race")
    args = parser.parse_args(argv)
    rounds = cli.fetch(lambda: season.load(args.year, SESSIONS[args.session]))
    found = cli.fetch(lambda: duels(rounds, with_gaps=args.session == "Q"))
    print(save(render(rounds, found, args.session), rounds, found, args.session, args.code, args.out))
    for d in found:
        gap = "" if d.median_gap is None else f"  median {d.median_gap:+.3f} s"
        print(f"  {d.team:<16}{d.name(d.first)} {d.wins[d.first]}-{d.wins[d.second]} {d.name(d.second)}{gap}")


if __name__ == "__main__":
    main()
