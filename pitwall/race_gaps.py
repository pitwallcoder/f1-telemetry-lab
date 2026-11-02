"""The fight between two drivers: how far apart they were at the end of every lap, with their pit stops and the
neutralisations.

  uv run python -m pitwall.race_gaps 2026 "Mexico City" --code PW-018            # the top two finishers
  uv run python -m pitwall.race_gaps 2026 "Mexico City" LEC HAM
"""
from pitwall import cli, openf1, race, race_positions, style

NAMES = {"VSC": "VSC", "SC": "SAFETY CAR", "RED": "RED FLAG"}


def between(laps, first, second):
    """lap -> seconds `second` crossed the line after `first`; negative when `second` was ahead."""
    crossed = race.line_crossings(laps)
    return {lap: (crossed[(second, lap)] - moment).total_seconds()
            for (driver, lap), moment in sorted(crossed.items()) if driver == first and (second, lap) in crossed}


def pair(result, drivers, wanted):
    """Two drivers by acronym or number, the top two finishers when none are given; the one classified ahead first."""
    classified = race.classification(result)
    if not wanted:
        picked = sorted(classified, key=classified.get)[:2]
    else:
        by_name = {d["name_acronym"].upper(): n for n, d in drivers.items()}
        picked = [int(w) if str(w).isdigit() else by_name.get(str(w).upper()) for w in wanted]
        missing = [w for w, n in zip(wanted, picked) if n not in drivers]
        if missing:
            raise openf1.DataNotFound(f"Not in this race: {', '.join(missing)}")
    return tuple(sorted(picked, key=lambda n: classified.get(n, 99)))


def headline(drivers, first, second, gap, classified):
    a, b = style.surname(drivers[first]), style.surname(drivers[second])
    if second not in classified:
        return f"{a} vs {b}, who did not finish"
    if gap[max(gap)] < 0:
        return f"{a} finished ahead of {b} after penalties"
    return f"{a} beat {b} by {gap[max(gap)]:.1f} s"


def colours(drivers, first, second):
    """Team colours, with the second driver in white when both share a team."""
    a, b = style.team_colour(drivers[first]), style.team_colour(drivers[second])
    return a, style.TEXT if a.lower() == b.lower() else b


def render(r, first, second, gap):
    s, (ca, cb) = r.session, colours(r.drivers, first, second)
    na, nb = style.surname(r.drivers[first]), style.surname(r.drivers[second])
    fig = style.story_figure(headline(r.drivers, first, second, gap, race.classification(r.result)), f"{s['year']} {r.meeting_name} · Race",
                             f"How far apart {na} and {nb} were at the end of every lap. Above the line: {na} ahead. "
                             f"Below: {nb} ahead.")
    ax = style.bare_axes(fig, [0.08, 0.1, 0.84, 0.66])
    laps = sorted(gap)
    y = [gap[k] for k in laps]
    top = max(max(y), -min(y), 2) * 1.15
    ax.set_xlim(laps[0] - 0.5, laps[-1] + 0.5)
    ax.set_ylim(-top, top * 1.12)
    race_positions.neutralisations(ax, r.periods, lambda row: top * (1.08 - 0.08 * row), NAMES)
    ax.axhline(0, color=style.MUTED, linewidth=1)
    ax.fill_between(laps, y, 0, where=[v >= 0 for v in y], color=ca, alpha=0.3, linewidth=0, interpolate=True)
    ax.fill_between(laps, y, 0, where=[v <= 0 for v in y], color=cb, alpha=0.3, linewidth=0, interpolate=True)
    ax.plot(laps, y, color=style.TEXT, linewidth=1.8, zorder=3)
    ax.text(laps[0], top * 0.9, f"{na} ahead", color=ca, fontsize=13, fontweight="bold")
    ax.text(laps[0], -top * 0.9, f"{nb} ahead", color=cb, fontsize=13, fontweight="bold", va="bottom")
    _stops(ax, r, first, second, gap, (na, nb), top)
    ticks = [t for t in range(-int(top), int(top) + 1) if t % _step(top) == 0]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{abs(t)} s" for t in ticks], family=style.DIGITS, fontsize=10)
    ax.set_xticks(range(5, laps[-1] + 1, 5))
    ax.set_xticklabels([f"Lap {k}" for k in range(5, laps[-1] + 1, 5)], fontsize=10)
    for t in ticks:
        ax.axhline(t, color=style.GRID, linewidth=0.6, zorder=0)
    fig.text(0.95, 0.03, "Official timing: time between the two cars crossing the line · data: OpenF1",
             color=style.FAINT, fontsize=9, ha="right")
    return fig


def _step(top):
    return next(s for s in (1, 2, 5, 10, 20) if top / s <= 6)


def _stops(ax, r, first, second, gap, names, top):
    """A tyre circle where each of the two fitted new tyres, with who pitted: the first driver's label above, the
    second's below, so stops on the same lap don't overlap. A second set on the next lap (a stop under a safety car,
    then a change in the red-flag pit lane) keeps the first label only."""
    labelled = set()
    for driver, lap, compound in sorted(race_positions.tyre_changes(r.stints), key=lambda c: c[1]):
        if driver not in (first, second) or lap not in gap or compound not in style.TYRES:
            continue
        race_positions.tyre_marker(ax, lap, gap[lap], compound, nudge=top * 0.004)
        if (driver, lap - 1) not in labelled:
            ax.annotate(f"{names[driver != first]} pits", (lap, gap[lap]), xytext=(0, 15 if driver == first else -15),
                        textcoords="offset points", ha="center", va="center", color=style.TEXT, fontsize=10)
        labelled.add((driver, lap))


def facts(r, first, second, gap, code):
    s = r.session
    return {"code": code, "event": r.meeting_name, "year": s["year"],
            "drivers": [r.drivers[first]["name_acronym"], r.drivers[second]["name_acronym"]],
            "gap_s_by_lap": {lap: round(g, 3) for lap, g in sorted(gap.items())},
            "positive_means": f"{r.drivers[first]['name_acronym']} ahead",
            "neutralisations": [{"kind": p.kind, "first_lap": p.first_lap, "last_lap": p.last_lap} for p in r.periods],
            "sources": ["OpenF1"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.race_gaps", __doc__, "PW-018")
    parser.add_argument("drivers", nargs="*", help="two acronyms or numbers; default: the top two finishers")
    args = parser.parse_args(argv)
    if len(args.drivers) not in (0, 2):
        parser.error("give exactly two drivers, or none for the top two finishers")
    r = cli.fetch(lambda: race.load(args.year, args.circuit))
    first, second = cli.fetch(lambda: pair(r.result, r.drivers, args.drivers))
    gap = between(r.laps, first, second)
    names = f"{r.drivers[first]['name_acronym']}-vs-{r.drivers[second]['name_acronym']}"
    print(style.save(render(r, first, second, gap), facts(r, first, second, gap, args.code), args.code,
                     f"{openf1.slug(r.session)}_gap_{names}", args.out))


if __name__ == "__main__":
    main()
