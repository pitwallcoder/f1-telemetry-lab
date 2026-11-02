"""Gap to the leader: every driver's time behind the car in front of the race at the end of each lap, with tyre
stops and neutralisations.

  uv run python -m pitwall.race_gaps 2026 "Mexico City" --code PW-018
"""
from pitwall import cli, openf1, race, race_positions, style

TOP = 10  # every car on one chart is unreadable; the top ten finishers carry the story


def gaps(laps):
    """driver -> {lap: seconds behind the first car to complete that lap}."""
    crossed = race.line_crossings(laps)
    first = {}
    for (_, lap), moment in crossed.items():
        first[lap] = min(first.get(lap, moment), moment)
    out = {}
    for (driver, lap), moment in sorted(crossed.items()):
        out.setdefault(driver, {})[lap] = (moment - first[lap]).total_seconds()
    return out


def spread(ys, min_gap):
    """Label positions in the same order as `ys`, pushed down until no two are closer than `min_gap`."""
    out, last = {}, None
    for key, y in sorted(ys.items(), key=lambda kv: kv[1]):
        out[key] = y if last is None else max(y, last + min_gap)
        last = out[key]
    return out


def top_finishers(result, behind):
    classified = race.classification(result)
    return {d: behind[d] for d in sorted(classified, key=classified.get)[:TOP] if d in behind}


def render(r, behind):
    s, behind = r.session, top_finishers(r.result, behind)
    last = max(max(g) for g in behind.values())
    lead_lap = [g[last] for d, g in behind.items() if last in g]
    bottom = max(lead_lap) * 1.08 + 2
    fig = style.race_figure(f"{s['year']} {r.meeting_name} · Race · Gap to the leader")
    fig.text(0.5, 0.875, f"Top {TOP} finishers, official classification", color=style.MUTED, fontsize=11, ha="center")
    ax = style.bare_axes(fig, [0.06, 0.08, 0.86, 0.77])
    ax.set_xlim(0.4, last + 0.6)
    ax.set_ylim(bottom, -bottom * 0.1)
    race_positions.neutralisations(ax, r.periods, lambda row: -bottom * (0.075 - 0.035 * row))
    second = race_positions.second_drivers(r.drivers, race.grid(r.positions))
    for d, g in behind.items():
        laps = sorted(g)
        ax.plot(laps, [g[k] for k in laps], color=style.team_colour(r.drivers[d]), linewidth=1.4, zorder=3,
                linestyle=(0, (4, 2.2)) if d in second else "-", solid_joinstyle="round")
    for d, lap, compound in race_positions.tyre_changes(r.stints):
        if compound in style.TYRES and lap in behind.get(d, {}) and behind[d][lap] < bottom:
            race_positions.tyre_marker(ax, lap, behind[d][lap], compound, nudge=bottom * 0.002)
    finishers = {d: g[last] for d, g in behind.items() if last in g}
    for d, y in spread(finishers, bottom * 0.026).items():
        info = r.drivers[d]
        ax.text(last + 0.9, y, f"{info['name_acronym']} +{finishers[d]:.1f}" if finishers[d] else info["name_acronym"],
                color=style.team_colour(info), fontsize=9, fontweight="bold", va="center", family=style.DIGITS)
    ticks = range(0, int(bottom), 10 if bottom < 80 else 20)
    ax.set_yticks(list(ticks))
    ax.set_yticklabels([f"{t} s" for t in ticks], family=style.DIGITS, fontsize=9)
    ax.set_xticks(range(5, last + 1, 5))
    ax.set_xticklabels([f"L{k}" for k in range(5, last + 1, 5)], fontweight="semibold", fontsize=9)
    for t in ticks:
        ax.axhline(t, color=style.GRID, linewidth=0.6, zorder=0)
    fig.text(0.92, 0.03, "seconds behind the first car to complete each lap (official timing) · circles = tyre fitted · "
             f"shaded = VSC / SC / red flag · dashed = second driver of the team · top {TOP} finishers", color=style.FAINT, fontsize=8.5, ha="right")
    return fig


def facts(r, behind, code):
    s = r.session
    return {"code": code, "event": r.meeting_name, "year": s["year"],
            "drivers": {r.drivers[d]["name_acronym"]: [round(g[k], 3) for k in sorted(g)] for d, g in behind.items()},
            "neutralisations": [{"kind": p.kind, "first_lap": p.first_lap, "last_lap": p.last_lap} for p in r.periods],
            "sources": ["OpenF1"]}


def main(argv=None):
    args = cli.parser("python -m pitwall.race_gaps", __doc__, "PW-018").parse_args(argv)
    r = cli.fetch(lambda: race.load(args.year, args.circuit))
    behind = gaps(r.laps)
    print(style.save(render(r, behind), facts(r, behind, args.code), args.code,
                     f"{openf1.slug(r.session)}_gaps", args.out))


if __name__ == "__main__":
    main()
