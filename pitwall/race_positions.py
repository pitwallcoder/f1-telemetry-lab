"""Position chart: every driver's place at the end of every lap, with tyre stops and neutralisations.

  uv run python -m pitwall.race_positions 2026 "Mexico City" --code PW-009
"""
from dataclasses import dataclass

from pitwall import cli, openf1, race, style

NEUTRAL_SHADE = {"VSC": 0.16, "SC": 0.16, "RED": 0.28}


@dataclass(frozen=True)
class Chart:
    race: race.Race
    places: dict  # driver -> {lap: position}; lap 0 is the grid
    tyres: list  # (driver, lap the tyre was fitted at the end of, compound); lap 0 is the starting set
    periods: list
    classified: dict  # driver -> official position after penalties
    second_drivers: set  # drawn dashed: the teammate who started behind

    @property
    def last_lap(self):
        return max(max(laps) for laps in self.places.values())


def places_by_driver(order, starting_grid):
    places = {driver: {0: position} for driver, position in starting_grid.items()}
    for lap, drivers in order.items():
        for position, driver in enumerate(drivers, 1):
            places.setdefault(driver, {})[lap] = position
    return places


def second_drivers(drivers, starting_grid):
    """Per team, every driver who started behind a teammate. Drivers with no team name have no teammate."""
    teams = {}
    for number, info in drivers.items():
        if info.get("team_name") and number in starting_grid:
            teams.setdefault(info["team_name"], []).append((starting_grid[number], number))
    return {number for cars in teams.values() for _, number in sorted(cars)[1:]}


def tyre_changes(stints):
    return [(s["driver_number"], s["lap_start"] - 1, s["compound"]) for s in stints]


def chart(r):
    starting_grid = race.grid(r.positions)
    return Chart(r, places_by_driver(race.running_order(r.laps), starting_grid), tyre_changes(r.stints),
                 r.periods, race.classification(r.result),
                 second_drivers(r.drivers, starting_grid))


def road_finish(c, driver):
    """Where a classified driver crossed the line on his last lap, lapped or not; None for a retirement."""
    places = c.places[driver]
    return places[max(places)] if driver in c.classified else None


def finish_label(c, driver, road_position):
    """Official position, starred when a penalty dropped the driver below where he crossed the line."""
    official = c.classified.get(driver, road_position)
    return f"P{official}*" if official > road_position else f"P{official}"


def render(c):
    s = c.race.session
    fig = style.race_figure(f"{s['year']} {c.race.meeting_name} · Race · Position chart")
    ax = style.bare_axes(fig, [0.075, 0.075, 0.85, 0.815])
    n, last = len(c.places), c.last_lap
    ax.set_ylim(n + 0.6, -0.1)  # headroom above P1 for two rows of period labels
    ax.set_xlim(-0.6, last + 0.6)
    for y in range(1, n + 1):
        ax.axhline(y, color=style.GRID, linewidth=0.6, zorder=0)
    neutralisations(ax, c.periods, lambda row: -0.05 + 0.33 * row)
    for driver in sorted(c.places, key=lambda d: (d not in c.second_drivers, -c.places[d].get(0, n + 1))):
        _driver_line(ax, c, driver, last)
    _tyres(ax, c)
    ax.set_yticks([])
    ax.set_xticks([0, *range(5, last, 5)])
    ax.set_xticklabels(["Grid", *[f"L{k}" for k in range(5, last, 5)]], fontweight="semibold", fontsize=9)
    fig.text(0.925, 0.03, "position at the end of every lap (official timing) · circles = tyre fitted · shaded = VSC / SC / "
             "red flag · dashed = second driver of the team · × = retired", color=style.FAINT, fontsize=8.5, ha="right")
    if any(finish_label(c, d, road_finish(c, d)).endswith("*") for d in c.places if d in c.classified):
        fig.text(0.075, 0.03, "Right: official classification. *Crossed the line higher, dropped by a time penalty.",
                 color=style.FAINT, fontsize=8.5)
    return fig


LABEL_GAP_LAPS = 3  # label centres closer than this would overlap at 8 pt


def label_rows(periods):
    """(period, row) with each label over its own shading; a label too close to the previous one drops a row."""
    rows, previous = [], None
    for p in periods:
        centre = (p.first_lap + p.last_lap) / 2
        row = 1 - previous[1] if previous and centre - previous[0] < LABEL_GAP_LAPS else 0
        rows.append((p, row))
        previous = (centre, row)
    return rows


def neutralisations(ax, periods, label_y):
    """Shade each VSC, safety car and red flag; `label_y(row)` is where a label in that row goes, in data units."""
    for p in periods:
        ax.axvspan(p.first_lap - 0.5, p.last_lap + 0.5, color="#c98a1a", alpha=NEUTRAL_SHADE[p.kind], linewidth=0, zorder=0)
    for p, row in label_rows(periods):
        ax.text((p.first_lap + p.last_lap) / 2, label_y(row), p.kind, color="#e0a33a", fontsize=8, ha="center",
                va="top", fontweight="bold")


def _driver_line(ax, c, driver, last):
    info, laps = c.race.drivers[driver], sorted(c.places[driver])
    y, colour = [c.places[driver][k] for k in laps], style.team_colour(c.race.drivers[driver])
    ax.plot(laps, y, color=colour, linewidth=1.6, linestyle=(0, (4, 2.2)) if driver in c.second_drivers else "-",
            zorder=3, solid_joinstyle="round", dash_joinstyle="round")
    label = {"color": colour, "fontsize": 9.5, "fontweight": "bold", "va": "center"}
    if 0 in c.places[driver]:
        ax.text(-1.2, y[0], f"P{y[0]} {info['name_acronym']}", ha="right", **label)
    if driver in c.classified:
        ax.text(last + 1.2, y[-1], f"{info['name_acronym']} {finish_label(c, driver, y[-1])}", **label)
    else:
        ax.scatter([laps[-1]], [y[-1]], marker="x", s=36, color=style.TEXT, linewidths=1.3, zorder=5)


def _tyres(ax, c):
    for driver, lap, compound in c.tyres:
        if compound not in style.TYRES or lap not in c.places.get(driver, {}):
            continue
        tyre_marker(ax, lap, c.places[driver][lap], compound)


def tyre_marker(ax, x, y, compound, nudge=0.02):
    """A circle in the compound's colour with its initial, where a tyre set was fitted."""
    ax.scatter([x], [y], s=118, color=style.TYRES[compound], edgecolors=style.BG, linewidths=1.2, zorder=6)
    ax.text(x, y + nudge, compound[0], color=style.TEXT if compound in ("SOFT", "INTERMEDIATE", "WET") else "#111111",
            fontsize=6.8, fontweight="bold", ha="center", va="center", zorder=7)


def facts(c, code):
    s, last = c.race.session, c.last_lap
    names = {n: d["name_acronym"] for n, d in c.race.drivers.items()}
    return {
        "code": code, "event": c.race.meeting_name, "session": s["session_name"], "year": s["year"],
        "laps": last,
        "drivers": [{"name": names[d], "grid": p.get(0), "last_lap": max(p), "road_finish": road_finish(c, d),
                     "classified": c.classified.get(d), "places": [p[k] for k in sorted(p)]} for d, p in c.places.items()],
        "neutralisations": [{"kind": p.kind, "first_lap": p.first_lap, "last_lap": p.last_lap} for p in c.periods],
        "tyres": [{"driver": names.get(d, str(d)), "fitted_after_lap": lap, "compound": comp} for d, lap, comp in c.tyres],
        "sources": ["OpenF1"],
    }


def save(fig, c, code, out_dir="out"):
    return style.save(fig, facts(c, code), code, f"{openf1.slug(c.race.session)}_positions", out_dir)


def main(argv=None):
    args = cli.parser("python -m pitwall.race_positions", __doc__, "PW-009").parse_args(argv)
    c = cli.fetch(lambda: chart(race.load(args.year, args.circuit)))
    print(save(render(c), c, args.code, args.out))


if __name__ == "__main__":
    main()
