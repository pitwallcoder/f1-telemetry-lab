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


def headline(drivers, ranked):
    top = ranked[0][1]
    names = [style.surname(drivers.get(n, {})) for n, kmh in ranked if kmh == top]
    if len(names) > 3:
        return f"{len(names)} drivers were fastest through the speed trap: {top} km/h"
    who = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
    return f"{who} {'was' if len(names) == 1 else 'were'} fastest through the speed trap: {top} km/h"


def render(context, drivers, ranked):
    fig = style.story_figure(headline(drivers, ranked), context,
                             "The highest speed each driver reached at the speed trap, the fastest point of the lap")
    top = ranked[0][1]
    rows = []
    for n, kmh in ranked:
        info = drivers.get(n, {"name_acronym": str(n)})
        rows.append((info, [(0, style.surname(info), style.TEXT, {"fontweight": "bold"}),
                            (0.2, f"{kmh} km/h", style.TEXT, {"family": style.DIGITS, "ha": "right", "fontweight": "bold"}),
                            (0.28, "fastest" if kmh == top else f"{kmh - top} km/h", style.PURPLE if kmh == top
                             else style.MUTED, {"family": style.DIGITS, "ha": "right", "fontsize": 12})]))
    style.tower(fig, rows)
    fig.text(0.95, 0.04, "Official speed trap · data: OpenF1 · a tow from the car ahead can add several km/h",
             color=style.FAINT, fontsize=9, ha="right")
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
