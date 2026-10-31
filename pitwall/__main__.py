"""Speed-trace comparison chart for any session.

  uv run python -m pitwall 2026 "Mexico City" FP1 --code PW-001          # session's top two
  uv run python -m pitwall 2026 "Mexico City" Q LEC VER --code PW-004    # chosen drivers

Circuit and session names are the official ones listed in README.md.
"""
import argparse
import sys

from pitwall import openf1, speed_chart


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="python -m pitwall", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("year", type=int)
    parser.add_argument("circuit", help="official circuit short name, e.g. 'Mexico City', Monza")
    parser.add_argument("session", choices=openf1.SESSIONS, help="session code")
    parser.add_argument("drivers", nargs="*", help="two acronyms or numbers; default: the session's top two")
    parser.add_argument("--code", default="PW-DRAFT", help="series code shown on the chart, e.g. PW-002")
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    if len(args.drivers) not in (0, 2):
        parser.error("give exactly two drivers, or none for the session's top two")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        comparison = speed_chart.from_session(args.year, args.circuit, args.session, args.drivers)
    except openf1.DataNotFound as error:
        sys.exit(f"error: {error}")
    path = speed_chart.save(speed_chart.render(comparison, args.code), comparison, args.code, args.out)
    print(path)
    for tag, who, seconds, place in speed_chart.table(comparison):
        print(f"  {tag} {place:<14} {who} +{seconds:.3f}s")
    q = comparison.quality
    print(f"check: position fit ±{q.fit_residual_m[0]:.1f}/{q.fit_residual_m[1]:.1f} m, "
          f"cars apart at official lines {', '.join(f'{m:+.1f}' for m in q.line_disagreement_m)} m (pinned to 0)")
    if not q.trustworthy():
        print("warning: telemetry noisier than 90% of validated sessions; zones may be off by more than ±0.05 s")


if __name__ == "__main__":
    main()
