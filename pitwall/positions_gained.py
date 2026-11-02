"""Positions gained: every classified driver's grid slot against where he was after lap 1 and at the flag.

  uv run python -m pitwall.positions_gained 2026 "Mexico City" --code PW-017
  uv run python -m pitwall.positions_gained 2026 "Mexico City" --lap-one     # grid to the end of lap 1
"""
from dataclasses import dataclass

from pitwall import cli, openf1, race, style

FINISH, LAP_ONE = "by the flag", "on the opening lap"


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


GAINED, LOST = "#22c55e", "#ef4444"


def headline(drivers, found, until):
    best = found[0]
    return f"{style.surname(drivers[best.driver])} gained the most places {until}: P{best.grid} to P{_end(best, until)}"


def _end(g, until):
    return g.lap_one if until == LAP_ONE else g.finish


def render(r, found, until):
    s = r.session
    found = sorted(found, key=lambda g: (-(g.grid - _end(g, until)), _end(g, until)))
    fig = style.story_figure(headline(r.drivers, found, until), f"{s['year']} {r.meeting_name} · Race · Positions gained",
                             "Starting position against " + ("the order at the end of lap 1" if until == LAP_ONE
                                                             else "the official result") + ". Green: places gained. "
                             "Red: places lost.")
    ax = style.bare_axes(fig, [0.25, 0.07, 0.5, 0.71])
    change = [g.grid - _end(g, until) for g in found]
    widest = max(map(abs, change)) + 0.5
    ax.set_xlim(-widest, widest)
    ax.set_ylim(len(found) - 0.4, -0.6)
    ax.axvline(0, color=style.FAINT, linewidth=0.8)
    for y, (g, k) in enumerate(zip(found, change)):
        info = r.drivers[g.driver]
        ax.barh(y, k, height=0.62, color=GAINED if k > 0 else LOST, linewidth=0)
        ax.scatter([-widest - 0.25], [y], marker="|", s=160, linewidths=4, color=style.team_colour(info), clip_on=False)
        ax.text(-widest - 0.6, y, style.surname(info), ha="right", va="center", color=style.TEXT, fontsize=12,
                fontweight="bold")
        ax.text(widest + 0.4, y, f"{k:+d}" if k else "=", va="center", color=GAINED if k > 0 else LOST if k else
                style.MUTED, fontsize=13, fontweight="bold", family=style.DIGITS)
        ax.text(widest + 2.6, y, f"P{g.grid} → P{_end(g, until)}", va="center", color=style.MUTED, fontsize=11.5,
                family=style.DIGITS)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(0.95, 0.03, "Retirements are left out · grid: first position of the race · data: OpenF1",
             color=style.FAINT, fontsize=9, ha="right")
    return fig


def facts(r, found, code):
    s = r.session
    return {"code": code, "event": r.meeting_name, "year": s["year"],
            "drivers": [{"name": r.drivers[g.driver]["name_acronym"], "grid": g.grid, "lap_one": g.lap_one,
                         "finish": g.finish, "net": g.net, "first_lap": g.first_lap} for g in found],
            "sources": ["OpenF1"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.positions_gained", __doc__, "PW-017")
    parser.add_argument("--lap-one", action="store_true", help="grid to the end of lap 1 instead of the result")
    args = parser.parse_args(argv)
    until = LAP_ONE if args.lap_one else FINISH
    r = cli.fetch(lambda: race.load(args.year, args.circuit))
    found = gains(race.grid(r.positions), race.running_order(r.laps), race.classification(r.result))
    print(style.save(render(r, found, until), facts(r, found, args.code), args.code,
                     f"{openf1.slug(r.session)}_positions-gained{'-lap-one' if args.lap_one else ''}", args.out))
    for g in found:
        print(f"  {r.drivers[g.driver]['name_acronym']:<4}P{g.grid:<3}→ P{g.lap_one:<3}→ P{g.finish:<3}{g.net:+d}")


if __name__ == "__main__":
    main()
