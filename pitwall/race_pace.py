"""Race pace: every classified driver's representative laps, fuel-corrected, ranked by median.

  uv run python -m pitwall.race_pace 2026 "Mexico City" --code PW-010
"""
import argparse
import statistics
import sys
from dataclasses import dataclass

import numpy as np
from matplotlib.patches import FancyBboxPatch

from pitwall import openf1, race, style

# Typical estimate of the time a lap's remaining fuel costs; laps are shown as if run on an empty tank.
FUEL_S_PER_LAP = 0.035
# A lap this much slower than the driver's own median is traffic, a mistake, damage or a flag, not pace.
SLOW_LAP_RATIO = 1.03


@dataclass(frozen=True)
class Pace:
    driver: int
    median: float
    laps: list  # (lap number, fuel-corrected seconds, compound)


def representative_laps(laps, pits, excluded, compounds):
    """driver -> [(lap, seconds, compound)] without excluded (driver, lap) pairs, in- and out-laps or laps after a stop."""
    pit_laps = {(p["driver_number"], p["lap_number"]) for p in pits}
    out = {}
    for lap in laps:
        driver, number = lap["driver_number"], lap["lap_number"]
        if (not lap.get("lap_duration") or (driver, number) in excluded or lap.get("is_pit_out_lap")
                or (driver, number) in pit_laps or (driver, number - 1) in pit_laps):
            continue
        out.setdefault(driver, []).append((number, lap["lap_duration"], compounds.get((driver, number))))
    return out


def fuel_corrected(seconds, lap, total_laps, s_per_lap=FUEL_S_PER_LAP):
    return seconds - s_per_lap * (total_laps - lap)


def driver_pace(driver, laps, total_laps):
    corrected = [(lap, fuel_corrected(t, lap, total_laps), c) for lap, t, c in laps]
    median = statistics.median(t for _, t, _ in corrected)
    kept = [x for x in corrected if x[1] < median * SLOW_LAP_RATIO]
    return Pace(driver, statistics.median(t for _, t, _ in kept), kept)


def ranking(r):
    excluded = race.unrepresentative_laps(r.laps, race.neutralisations(r.messages))
    total = max(lap["lap_number"] for lap in r.laps)
    classified = race.classification(r.result)
    laps = representative_laps(r.laps, r.pits, excluded, race.compound_by_lap(r.stints))
    if not any(d in laps for d in classified):
        raise openf1.DataNotFound("No classified driver has representative laps in this race")
    return sorted((driver_pace(d, laps[d], total) for d in classified if d in laps), key=lambda p: p.median)


def render(r, paces):
    s, best = r.session, paces[0].median
    fig = style.race_figure(f"{s['year']} {r.meeting_name} · Race pace (fuel-corrected)")
    ax = style.bare_axes(fig, [0.07, 0.25, 0.9, 0.62])
    times = np.concatenate([[t for _, t, _ in p.laps] for p in paces])
    lo, hi = np.floor(times.min() * 2) / 2, np.ceil(times.max() * 2) / 2
    ticks = np.arange(lo, hi + 0.01, 0.5)
    for y in ticks:
        ax.axhline(y, color=style.GRID, linewidth=0.7, zorder=0)
    rng = np.random.default_rng(7)  # fixed jitter: the same chart on every run
    for i, p in enumerate(paces):
        _box(ax, i, p, style.team_colour(r.drivers[p.driver]), rng)
    ax.set_xlim(-0.7, len(paces) - 0.3)
    ax.set_ylim(hi + 0.1, lo - 0.15)
    ax.set_yticks(ticks)
    ax.set_yticklabels([style.lap_time(v) for v in ticks], family=style.DIGITS, fontsize=9.5)
    ax.set_xticks([])
    ax.text(-0.65, lo - 0.08, "faster", color=style.FAINT, fontsize=9, va="top")
    _table(fig, r, paces, best)
    _legend(fig, paces)
    return fig


def _box(ax, i, p, colour, rng):
    t = np.array([x for _, x, _ in p.laps])
    q1, q3 = np.percentile(t, [25, 75])
    ax.add_patch(FancyBboxPatch((i - 0.3, q1), 0.6, q3 - q1, boxstyle="round,pad=0,rounding_size=0.06",
                                facecolor=colour, alpha=0.28, edgecolor=colour, linewidth=1.4, zorder=2))
    ax.plot([i, i], [t.min(), q1], color=colour, linewidth=1.1, zorder=2)
    ax.plot([i, i], [q3, t.max()], color=colour, linewidth=1.1, zorder=2)
    ax.plot([i - 0.3, i + 0.3], [p.median, p.median], color=style.TEXT, linewidth=2, zorder=4)
    ax.scatter(i + rng.uniform(-0.2, 0.2, len(t)), t, s=9, linewidths=0, alpha=0.85, zorder=3,
               c=[style.TYRES.get(c, style.MUTED) for _, _, c in p.laps])


def _table(fig, r, paces, best):
    n = len(paces)
    fig.text(0.03, 0.18, "median", color=style.FAINT, fontsize=8.5)
    fig.text(0.03, 0.15, "gap", color=style.FAINT, fontsize=8.5)
    for i, p in enumerate(paces):
        x = 0.07 + 0.9 * (i + 0.7) / (n + 0.4)
        info = r.drivers[p.driver]
        fig.text(x, 0.215, info["name_acronym"], color=style.team_colour(info), fontsize=11.5, fontweight="bold", ha="center")
        fig.text(x, 0.18, style.lap_time(p.median), color=style.TEXT, fontsize=9.5, ha="center", family=style.DIGITS)
        fig.text(x, 0.15, "fastest" if i == 0 else f"+{p.median - best:.3f}", color=style.PURPLE if i == 0 else style.MUTED,
                 fontsize=9.5, ha="center", family=style.DIGITS)
        fig.text(x, 0.12, f"{len(p.laps)} laps", color=style.FAINT, fontsize=8, ha="center")


def _legend(fig, paces):
    used = {c for p in paces for _, _, c in p.laps}
    for k, compound in enumerate(c for c in style.TYRES if c in used):
        fig.text(0.07 + k * 0.07, 0.065, "●", color=style.TYRES[compound], fontsize=11, family="DejaVu Sans")
        fig.text(0.085 + k * 0.07, 0.067, compound.title(), color=style.MUTED, fontsize=9)
    fig.text(0.97, 0.067, "Representative laps: no lap 1, pit in/out, VSC, SC, red flag or restart laps, nor laps 3% slower "
             f"than the driver's median. Fuel-corrected at ~{FUEL_S_PER_LAP} s/lap. Box: middle 50% · white: median",
             color=style.FAINT, fontsize=8.5, ha="right")


def facts(r, paces, code):
    s, best = r.session, paces[0].median
    return {
        "code": code, "event": r.meeting_name, "session": s["session_name"], "year": s["year"],
        "drivers": [{"name": r.drivers[p.driver]["name_acronym"], "median_s": round(p.median, 3),
                     "gap_s": round(p.median - best, 3), "laps": len(p.laps)} for p in paces],
        "method": {"fuel_s_per_lap": FUEL_S_PER_LAP, "slow_lap_ratio": SLOW_LAP_RATIO,
                   "neutralisations": [{"kind": p.kind, "first_lap": p.first_lap, "last_lap": p.last_lap}
                                       for p in race.neutralisations(r.messages)]},
        "precision": {"medians": "estimate: fuel correction is a typical value, not measured"},
        "sources": ["OpenF1"],
    }


def save(fig, r, paces, code, out_dir="out"):
    return style.save(fig, facts(r, paces, code), code, f"{openf1.slug(r.session)}_pace", out_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pitwall.race_pace", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("year", type=int)
    parser.add_argument("circuit", help="official circuit short name, e.g. 'Mexico City', Monza")
    parser.add_argument("--code", default="PW-DRAFT", help="series code for the output folder, e.g. PW-010")
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    try:
        r = race.load(args.year, args.circuit)
        paces = ranking(r)
    except openf1.DataNotFound as error:
        sys.exit(f"error: {error}")
    print(save(render(r, paces), r, paces, args.code, args.out))
    for p in paces:
        print(f"  {r.drivers[p.driver]['name_acronym']:<4}{style.lap_time(p.median)}  +{p.median - paces[0].median:.3f}  ({len(p.laps)} laps)")


if __name__ == "__main__":
    main()
