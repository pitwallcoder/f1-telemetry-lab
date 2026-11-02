"""Positions gained: every classified driver's grid slot against where he was after lap 1 and at the flag.

  uv run python -m pitwall.positions_gained 2026 "Mexico City" --code PW-017
"""
from dataclasses import dataclass

from pitwall import cli, openf1, race, style


@dataclass(frozen=True)
class Gain:
    driver: int
    grid: int
    lap_one: int
    finish: int  # official, after penalties

    @property
    def net(self):
        return self.grid - self.finish

    @property
    def first_lap(self):
        return self.grid - self.lap_one


def gains(starting_grid, order, classified):
    """Classified drivers with a grid slot and a lap 1, most places gained first, then by finish."""
    lap_one = {driver: place for place, driver in enumerate(order.get(1, []), 1)}
    found = [Gain(d, starting_grid[d], lap_one[d], p) for d, p in classified.items()
             if d in starting_grid and d in lap_one]
    return sorted(found, key=lambda g: (-g.net, g.finish))


def render(r, found):
    s = r.session
    fig = style.race_figure(f"{s['year']} {r.meeting_name} · Race · Positions gained")
    fig.text(0.5, 0.875, "Grid to the flag (bars) and grid to the end of lap 1 (rings) · classified drivers",
             color=style.MUTED, fontsize=11, ha="center")
    ax = style.bare_axes(fig, [0.2, 0.1, 0.6, 0.74])
    widest = max(max(abs(g.net), abs(g.first_lap)) for g in found) + 1
    ax.set_xlim(-widest, widest)
    ax.set_ylim(len(found) - 0.4, -0.6)
    ax.axvline(0, color=style.FAINT, linewidth=0.8)
    for y, g in enumerate(found):
        info = r.drivers[g.driver]
        colour = style.team_colour(info)
        ax.barh(y, g.net, height=0.58, color=colour, linewidth=0)
        ax.scatter([g.first_lap], [y], s=70, facecolors="none", edgecolors=style.TEXT, linewidths=1.4, zorder=3)
        ax.text(-widest - 0.3, y, info["name_acronym"], ha="right", va="center", color=colour, fontsize=11,
                fontweight="bold")
        ax.text(widest + 0.3, y, f"P{g.grid} → P{g.finish}", va="center", color=style.MUTED, fontsize=10,
                family=style.DIGITS)
        ax.text(widest + 3.2, y, f"{g.net:+d}" if g.net else "0", va="center", ha="right", color=style.TEXT,
                fontsize=10.5, fontweight="bold", family=style.DIGITS)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(0.2, 0.065, "lost places", color=style.FAINT, fontsize=9)
    fig.text(0.8, 0.065, "gained places", color=style.FAINT, fontsize=9, ha="right")
    fig.text(0.95, 0.03, "Grid: first position of the race (OpenF1). Lap 1: order across the line. Finish: official "
             "classification. Retirements are left out.", color=style.FAINT, fontsize=8.5, ha="right")
    return fig


def facts(r, found, code):
    s = r.session
    return {"code": code, "event": r.meeting_name, "year": s["year"],
            "drivers": [{"name": r.drivers[g.driver]["name_acronym"], "grid": g.grid, "lap_one": g.lap_one,
                         "finish": g.finish, "net": g.net, "first_lap": g.first_lap} for g in found],
            "sources": ["OpenF1"]}


def main(argv=None):
    args = cli.parser("python -m pitwall.positions_gained", __doc__, "PW-017").parse_args(argv)
    r = cli.fetch(lambda: race.load(args.year, args.circuit))
    found = gains(race.grid(r.positions), race.running_order(r.laps), race.classification(r.result))
    print(style.save(render(r, found), facts(r, found, args.code), args.code,
                     f"{openf1.slug(r.session)}_positions-gained", args.out))
    for g in found:
        print(f"  {r.drivers[g.driver]['name_acronym']:<4}P{g.grid:<3}→ P{g.lap_one:<3}→ P{g.finish:<3}{g.net:+d}")


if __name__ == "__main__":
    main()
