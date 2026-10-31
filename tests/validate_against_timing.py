"""Check the method against official timing on real sessions (needs network; not part of `pytest`).

Two checks, both before any pinning to official timing:
- metres: where the two cars' fitted distances put them at their official sector 1, sector 2 and finish crossings;
  the lines don't move, so any disagreement is measurement error;
- seconds: the gap at one sector line, after pinning the cars only to the other sector line and the finish.

  uv run python -m tests.validate_against_timing
"""
from datetime import datetime, timezone

import numpy as np

from pitwall import circuits, distance, openf1, speed_chart, telemetry

SESSIONS = [
    ("Mexico City", "FP1"), ("Mexico City", "FP2"), ("Austin", "Q"), ("Miami", "SQ"), ("Singapore", "Q"),
    ("Singapore", "SQ"), ("Baku", "Q"), ("Monza", "Q"), ("Monza", "FP1"), ("Baku", "FP2"),
    ("Spa-Francorchamps", "Q"), ("Zandvoort", "Q"), ("Silverstone", "Q"), ("Suzuka", "Q"), ("Monte Carlo", "Q"),
]


def held_out_errors(session, best, fast_n, slow_n):
    """Gap error at each sector line when that line is left out of the pinning."""
    line = circuits.circuit(session["circuit_key"], session["year"]).line
    a, b = (speed_chart._run(session, best[n], line) for n in (fast_n, slow_n))
    ca, cb = speed_chart._crossings(a.lap), speed_chart._crossings(b.lap)
    errors = []
    for checked, kept in ((0, 1), (1, 0)):
        anchors_a, anchors_b = [(0.0, 0.0)], [(0.0, 0.0)]
        for k in (kept, 2):
            shared = (np.interp(ca[k], a.t, a.d) + np.interp(cb[k], b.t, b.d)) / 2
            anchors_a.append((ca[k], shared))
            anchors_b.append((cb[k], shared))
        fast = telemetry.Trace(a.t, distance.pin(a.t, a.d, anchors_a), a.speed)
        slow = telemetry.Trace(b.t, distance.pin(b.t, b.d, anchors_b), b.speed)
        gap = telemetry.delta(fast, slow)
        at_line = np.interp(ca[checked], fast.t, fast.distance)
        errors.append(float(np.interp(at_line, fast.distance, gap)) - (cb[checked] - ca[checked]))
    return errors


def main(year=2026):
    sessions = openf1.get("sessions", year=year)
    metres, seconds = [], []
    for circuit, code in SESSIONS:
        try:
            session = openf1.match_session(sessions, circuit, code, datetime.now(timezone.utc))
            drivers, best = openf1.session_laps(session)
            pair = openf1.pick_drivers(best, drivers, [])
            c = speed_chart.compare(session, "", drivers, best, pair)
            fast_n, slow_n = sorted(pair, key=lambda n: best[n]["lap_duration"])
            errors = held_out_errors(session, best, fast_n, slow_n)
        except openf1.DataNotFound as error:
            print(f"{circuit:18} {code:3} skipped: {error}")
            continue
        metres += [abs(m) for m in c.quality.line_disagreement_m]
        seconds += [abs(e) for e in errors]
        print(f"{circuit:18} {code:3} {c.fast.name}-{c.slow.name}  apart at lines "
              f"{' '.join(f'{m:+.1f}' for m in c.quality.line_disagreement_m)} m  "
              f"held-out gap error {' '.join(f'{e:+.3f}' for e in errors)} s")
    m, s = np.array(metres), np.array(seconds)
    print(f"\n{len(m)} line crossings: median {np.median(m):.1f} m, 90% under {np.percentile(m, 90):.1f} m, worst {m.max():.1f} m")
    print(f"{len(s)} held-out sector gaps: median {np.median(s):.3f} s, worst {s.max():.3f} s")


if __name__ == "__main__":
    main()
