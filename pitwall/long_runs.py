"""Practice long runs: each driver's longest stint at race pace, fuel-corrected, with its tyre degradation.

  uv run python -m pitwall.long_runs 2026 "Interlagos" --code PW-016           # FP2
  uv run python -m pitwall.long_runs 2026 "Interlagos" --session FP1
"""
from dataclasses import dataclass

import numpy as np

from pitwall import cli, openf1, race, race_pace, style

MIN_LAPS = 5


@dataclass(frozen=True)
class Run:
    pace: race_pace.Pace  # fuel-corrected to the run's last lap
    compound: str
    degradation: float  # seconds lost per lap, fuel-corrected

    @property
    def driver(self):
        return self.pace.driver


def runs(laps, stints, excluded):
    """Each driver's stint with the most race-pace laps, if it has at least MIN_LAPS: no out-laps, excluded laps or
    laps 3% slower than the stint's fastest (cool-down laps, traffic, the in-lap). The fastest, not the median,
    because a qualifying run is mostly cool-down laps."""
    by_driver = {}
    for s in stints:
        stint_laps = [(x["lap_number"], x["lap_duration"], s["compound"]) for x in laps
                      if x["driver_number"] == s["driver_number"] and s["lap_start"] <= x["lap_number"] <= s["lap_end"]
                      and x.get("lap_duration") and not x.get("is_pit_out_lap")
                      and (x["driver_number"], x["lap_number"]) not in excluded]
        fastest = min((t for _, t, _ in stint_laps), default=0)
        stint_laps = [x for x in stint_laps if x[1] < fastest * race_pace.SLOW_LAP_RATIO]
        if len(stint_laps) < MIN_LAPS:
            continue
        pace = race_pace.driver_pace(s["driver_number"], stint_laps, stint_laps[-1][0])
        best = by_driver.get(s["driver_number"])
        if len(pace.laps) >= MIN_LAPS and (best is None or len(pace.laps) >= len(best.pace.laps)):
            n, t = zip(*[(lap, seconds) for lap, seconds, _ in pace.laps])
            by_driver[s["driver_number"]] = Run(pace, s["compound"], float(np.polyfit(n, t, 1)[0]))
    return list(by_driver.values())


def ranking(laps, stints, messages):
    found = runs(laps, stints, race.unrepresentative_laps(laps, race.neutralisations(messages)))
    if not found:
        raise openf1.DataNotFound(f"No driver did a long run of {MIN_LAPS}+ laps in this session")
    return sorted(found, key=lambda r: r.pace.median)


def headline(drivers, found):
    return f"{style.surname(drivers[found[0].driver])} had the best race pace on the long runs"


def render(context, drivers, found):
    fig = style.story_figure(headline(drivers, found), context,
                             "Average lap on each driver's longest run at race pace, adjusted for fuel · "
                             "tyre wear: time lost per lap as the tyres age")
    best, rows = found[0].pace.median, []
    for r in found:
        info, gap = drivers[r.driver], r.pace.median - best
        rows.append((info, [
            (0, style.surname(info), style.TEXT, {"fontweight": "bold"}),
            (0.17, style.lap_time(r.pace.median), style.TEXT, {"family": style.DIGITS, "ha": "right", "fontweight": "bold"}),
            (0.235, "fastest" if r is found[0] else f"+{gap:.3f}", style.PURPLE if r is found[0] else style.MUTED,
             {"family": style.DIGITS, "ha": "right", "fontsize": 12}),
            (0.255, "●", style.TYRES.get(r.compound, style.MUTED), {"family": "DejaVu Sans", "fontsize": 14}),
            (0.275, f"{len(r.pace.laps)} laps", style.MUTED, {"fontsize": 11}),
            (0.385, f"{r.degradation:+.2f} s/lap", style.MUTED, {"family": style.DIGITS, "ha": "right", "fontsize": 12}),
        ]))
    style.tower(fig, rows, top=0.7)
    for x in (0.05, 0.53):
        for dx, label, align in ((0.197, "AVERAGE", "right"), (0.262, "GAP", "right"), (0.282, "TYRE", "left"),
                                 (0.412, "TYRE WEAR", "right")):
            fig.text(x + dx, 0.755, label, color=style.FAINT, fontsize=8.5, fontweight="bold", ha=align)
    used = [c for c in style.TYRES if c in {r.compound for r in found}]
    for k, compound in enumerate(used):
        fig.text(0.05 + k * 0.08, 0.04, "●", color=style.TYRES[compound], fontsize=12, family="DejaVu Sans")
        fig.text(0.064 + k * 0.08, 0.042, compound.title(), color=style.MUTED, fontsize=10)
    fig.text(0.95, 0.04, "Practice: fuel loads and engine modes are unknown, so this is a guide, not a result · "
             "data: OpenF1", color=style.FAINT, fontsize=9, ha="right")
    return fig


def facts(session, drivers, found, code):
    return {"code": code, "year": session["year"], "circuit": session["circuit_short_name"],
            "session": session["session_name"],
            "drivers": [{"name": drivers[r.driver]["name_acronym"], "compound": r.compound,
                         "median_s": round(r.pace.median, 3), "degradation_s_per_lap": round(r.degradation, 3),
                         "laps": [n for n, _, _ in r.pace.laps]} for r in found],
            "method": {"min_laps": MIN_LAPS, "fuel_s_per_lap": race_pace.FUEL_S_PER_LAP,
                       "slow_lap_ratio": race_pace.SLOW_LAP_RATIO},
            "precision": {"medians": "estimate: fuel loads and engine modes are unknown in practice"},
            "sources": ["OpenF1"]}


def main(argv=None):
    parser = cli.parser("python -m pitwall.long_runs", __doc__, "PW-016")
    parser.add_argument("--session", default="FP2", choices=["FP1", "FP2", "FP3"])
    args = parser.parse_args(argv)
    s = cli.fetch(lambda: openf1.find_session(args.year, args.circuit, args.session))
    fetch = lambda endpoint: openf1.get(endpoint, cache=openf1.settled(s), session_key=s["session_key"])
    drivers = {d["driver_number"]: d for d in fetch("drivers")}
    found = cli.fetch(lambda: ranking(fetch("laps"), fetch("stints"), fetch("race_control")))
    fig = render(f"{s['year']} {openf1.meeting_name(s)} · {s['session_name']} · Long runs", drivers, found)
    print(style.save(fig, facts(s, drivers, found, args.code), args.code, f"{openf1.slug(s)}_long-runs", args.out))
    for r in found:
        print(f"  {drivers[r.driver]['name_acronym']:<4}{r.compound:<7}{style.lap_time(r.pace.median)}  "
              f"{r.degradation:+.3f}/lap  ({len(r.pace.laps)} laps)")


if __name__ == "__main__":
    main()
