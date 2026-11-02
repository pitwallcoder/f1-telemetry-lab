"""Top speed: each driver's best speed-trap reading in a session.

  uv run python -m pitwall.top_speed 2026 "Las Vegas" Q --code PW-015
"""
from pitwall import cli, openf1, style

TRAPS = {"st_speed": "speed trap", "i1_speed": "intermediate 1", "i2_speed": "intermediate 2"}


def ranking(laps, trap):
    """[(driver, km/h)] fastest first; OpenF1 leaves a trap empty on some laps."""
    best = {}
    for lap in laps:
        if lap.get(trap):
            best[lap["driver_number"]] = max(best.get(lap["driver_number"], 0), lap[trap])
    if not best:
        raise openf1.DataNotFound(f"OpenF1 has no {TRAPS[trap]} speeds for this session")
    return sorted(best.items(), key=lambda kv: -kv[1])


def render(title, drivers, ranked):
    fig = style.race_figure(title)
    fig.text(0.5, 0.875, "Each driver's best speed-trap reading of the session (km/h)", color=style.MUTED,
             fontsize=11, ha="center")
    ax = style.bare_axes(fig, [0.12, 0.08, 0.8, 0.76])
    top, low = ranked[0][1], ranked[-1][1]
    ax.set_xlim(low - 3, top + 2)
    ax.set_ylim(len(ranked) - 0.4, -0.6)
    for x in range(int(low - 2), int(top) + 2):
        if x % 5 == 0:
            ax.axvline(x, color=style.GRID, linewidth=0.8, zorder=0)
            ax.text(x, len(ranked) - 0.1, str(x), color=style.FAINT, fontsize=8.5, ha="center", va="top",
                    family=style.DIGITS)
    for y, (n, kmh) in enumerate(ranked):
        colour = style.team_colour(drivers.get(n, {}))
        ax.plot([low - 3, kmh], [y, y], color=style.GRID, linewidth=1, zorder=1)
        ax.scatter([kmh], [y], s=90, color=colour, edgecolors=style.BG, linewidths=1.5, zorder=3)
        ax.text(low - 3.2, y, drivers.get(n, {}).get("name_acronym", str(n)), ha="right", va="center",
                color=colour, fontsize=10.5, fontweight="bold")
        ax.text(kmh + 0.35, y, f"{kmh}" if kmh == top else f"{kmh}  {kmh - top:+d}", va="center",
                color=style.TEXT if kmh == top else style.MUTED, fontsize=10, family=style.DIGITS)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(0.95, 0.03, "Official speed trap (OpenF1). Some laps have no reading. Tow and fuel load are not separated.",
             color=style.FAINT, fontsize=8.5, ha="right")
    return fig


def facts(session, drivers, laps, code):
    name = lambda n: drivers.get(n, {}).get("name_acronym", str(n))
    return {"code": code, "year": session["year"], "circuit": session["circuit_short_name"],
            "session": session["session_name"], "unit": "km/h",
            **{trap: [{"driver": name(n), "kmh": kmh} for n, kmh in ranking(laps, trap)] for trap in TRAPS
               if any(lap.get(trap) for lap in laps)},
            "sources": ["OpenF1"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.top_speed", __doc__, "PW-015")
    parser.add_argument("session", choices=openf1.SESSIONS, help="session code")
    args = parser.parse_args(argv)
    s = cli.fetch(lambda: openf1.find_session(args.year, args.circuit, args.session))
    cache = openf1.settled(s)
    laps = openf1.get("laps", cache=cache, session_key=s["session_key"])
    drivers = {d["driver_number"]: d for d in openf1.get("drivers", cache=cache, session_key=s["session_key"])}
    ranked = cli.fetch(lambda: ranking(laps, "st_speed"))
    fig = render(f"{s['year']} {openf1.meeting_name(s)} · {s['session_name']} · Top speed", drivers, ranked)
    print(style.save(fig, facts(s, drivers, laps, args.code), args.code, f"{openf1.slug(s)}_top-speed", args.out))
    for n, kmh in ranked[:5]:
        print(f"  {drivers.get(n, {}).get('name_acronym', n):<4}{kmh}")


if __name__ == "__main__":
    main()
