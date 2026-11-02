"""Qualifying ladder: every driver's gap to pole, built sector by sector from official timing.

  uv run python -m pitwall.quali_ladder 2026 "Mexico City" --code PW-003
  uv run python -m pitwall.quali_ladder 2026 Miami SQ --code PW-004
"""
import argparse
import sys
from dataclasses import dataclass

from pitwall import openf1, style
from pitwall.speed_chart import FALLBACK_COLOUR, lap_time

SEGMENTS = ("Q1", "Q2", "Q3")
SPRINT_SEGMENTS = ("SQ1", "SQ2", "SQ3")


@dataclass(frozen=True)
class Row:
    position: int
    name: str
    colour: str
    segment: str  # the last part of qualifying the driver set a time in; it decides the classification
    lap: dict

    def sectors(self):
        return [self.lap[f"duration_sector_{i}"] for i in (1, 2, 3)]


def ladder(results, laps, drivers, segments=SEGMENTS):
    """Rows in official order, each with the lap that set the driver's classifying time."""
    rows = []
    for result in sorted((r for r in results if r["position"]), key=lambda r: r["position"]):
        timed = [(segment, t) for segment, t in zip(segments, result["duration"] or []) if t]
        if not timed:
            continue
        segment, seconds = timed[-1]
        number = result["driver_number"]
        lap = next((lap for lap in reversed(laps) if lap["driver_number"] == number and openf1.complete(lap)
                    and openf1.same_lap_time(lap["lap_duration"], seconds)), None)
        info = drivers.get(number, {})
        name = info.get("name_acronym", str(number))
        if lap is None:
            raise openf1.DataNotFound(f"OpenF1 has no lap with sectors for {name}'s {segment} time {seconds}")
        rows.append(Row(result["position"], name, info.get("team_colour") or FALLBACK_COLOUR, segment, lap))
    if not rows:
        raise openf1.DataNotFound("OpenF1 has no qualifying result for this session yet")
    return rows


def sector_gaps(row, pole):
    return [mine - theirs for mine, theirs in zip(row.sectors(), pole.sectors())]


def from_session(year, circuit, session_code):
    session = openf1.find_session(year, circuit, session_code)
    key, cache = session["session_key"], openf1.settled(session)
    drivers = {d["driver_number"]: d for d in openf1.get("drivers", cache=cache, session_key=key)}
    rows = ladder(openf1.get("session_result", cache=cache, session_key=key),
                  openf1.get("laps", cache=cache, session_key=key), drivers,
                  SPRINT_SEGMENTS if session_code == "SQ" else SEGMENTS)
    return session, openf1.meeting_name(session), rows


def render(session, meeting_name, rows, code):
    pole = rows[0]
    fig = style.figure()
    style.context_line(fig, code, f"{session['year']} {meeting_name} · {session['session_name']}")
    big = {"fontsize": 26, "fontweight": "bold"}
    style.text_row(fig, 0.04, 0.85, [(pole.name, f"#{pole.colour}", big),
                                     (lap_time(pole.lap["lap_duration"]), style.TEXT, big),
                                     ("POLE", style.MUTED, {"fontsize": 12})])
    fig.text(0.04, 0.808, "Gap to pole · each driver's classifying lap · official timing · "
             "sectors vs pole's, white = faster", fontsize=10, color=style.MUTED)
    bg, bars, table = (_rows_axes(fig, x0, x1, rows) for x0, x1 in ((0.03, 0.97), (0.12, 0.60), (0.60, 0.95)))
    _stripes(bg, rows)
    _bars(bars, rows, pole)
    _sectors(table, rows, pole)
    style.footer(fig, "data: OpenF1")
    return fig


def _rows_axes(fig, x0, x1, rows):
    ax = fig.add_axes([x0, 0.11, x1 - x0, 0.66])
    style.style_axes(ax)
    ax.set_facecolor("none")
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_yticks([])
    return ax


def _stripes(ax, rows):
    ax.axis("off")
    ax.set_xlim(0, 1)
    for y in range(1, len(rows), 2):
        ax.axhspan(y - 0.5, y + 0.5, color=style.GRID, alpha=0.6, linewidth=0)
    for y in [y for y in range(1, len(rows)) if rows[y].segment != rows[y - 1].segment]:
        ax.axhline(y - 0.5, color=style.FAINT, linewidth=0.8, linestyle=":")
        ax.annotate(f"{rows[y].segment} time", (0.585, y - 0.5), xytext=(0, -2), textcoords="offset points",
                    ha="right", va="top", fontsize=7.5, color=style.MUTED)


def _bars(ax, rows, pole):
    gaps = [row.lap["lap_duration"] - pole.lap["lap_duration"] for row in rows]
    for y, (row, gap) in enumerate(zip(rows, gaps)):
        ax.barh(y, gap, height=0.56, color=f"#{row.colour}", linewidth=0)
        ax.annotate("POLE" if row is pole else f"{gap:+.3f}", (gap, y), xytext=(6 if gap >= 0 else -6, 0),
                    textcoords="offset points", ha="left" if gap >= 0 else "right", va="center", fontsize=8.5, color=style.TEXT)
        ax.annotate(f"P{row.position:<3}{row.name}", (0, y), xycoords=("axes fraction", "data"), xytext=(-8, 0),
                    textcoords="offset points", ha="right", va="center", fontsize=9, color=f"#{row.colour}",
                    fontweight="bold")
    ax.axvline(0, color=style.FAINT, linewidth=0.8)
    ax.set_xlim(min(0, min(gaps)) * 1.18, max(max(gaps), 0.1) * 1.18)
    ax.set_xlabel("Gap to pole [s]")


def _sectors(ax, rows, pole):
    ax.axis("off")
    ax.set_xlim(0, 1)
    columns = (0.25, 0.50, 0.75, 1.0)
    for x, title in zip(columns, ("LAP", "S1", "S2", "S3")):
        ax.annotate(title, (x, 1), xycoords=("data", "axes fraction"), xytext=(0, 6), textcoords="offset points",
                    ha="right", fontsize=10, color=style.MUTED)
    for y, row in enumerate(rows):
        cells = [(lap_time(row.lap["lap_duration"]), style.TEXT if row is pole else style.MUTED, "normal")]
        if row is pole:
            cells += [(f"{s:.3f}", style.TEXT, "normal") for s in row.sectors()]
        else:
            cells += [(f"{g:+.3f}", style.TEXT if g < 0 else style.MUTED, "bold" if g < 0 else "normal")
                      for g in sector_gaps(row, pole)]
        for x, (text, colour, weight) in zip(columns, cells):
            ax.text(x, y, text, ha="right", va="center", fontsize=8.5, color=colour, fontweight=weight)


def facts(session, meeting_name, rows, code):
    pole = rows[0]
    return {
        "code": code, "event": meeting_name, "session": session["session_name"], "year": session["year"],
        "circuit": session["circuit_short_name"],
        "rows": [{"position": r.position, "name": r.name, "segment": r.segment, "lap_number": r.lap["lap_number"],
                  "lap_time": lap_time(r.lap["lap_duration"]), "sectors": r.sectors(),
                  "gap_to_pole_s": round(r.lap["lap_duration"] - pole.lap["lap_duration"], 3),
                  "sector_gaps_s": [round(g, 3) for g in sector_gaps(r, pole)]} for r in rows],
        "precision": {"lap_and_sectors": "official, exact"},
        "sources": ["OpenF1"],
    }


def save(fig, session, meeting_name, rows, code, out_dir="out"):
    return style.save(fig, facts(session, meeting_name, rows, code), code, f"{openf1.slug(session)}_ladder", out_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pitwall.quali_ladder", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("year", type=int)
    parser.add_argument("circuit", help="official circuit short name, e.g. 'Mexico City', Monza")
    parser.add_argument("session", nargs="?", default="Q", choices=("Q", "SQ"))
    parser.add_argument("--code", default="PW-DRAFT", help="series code shown on the chart, e.g. PW-003")
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    try:
        session, meeting_name, rows = from_session(args.year, args.circuit, args.session)
    except openf1.DataNotFound as error:
        sys.exit(f"error: {error}")
    print(save(render(session, meeting_name, rows, args.code), session, meeting_name, rows, args.code, args.out))
    for r in rows:
        gaps = " ".join(f"{g:+.3f}" for g in sector_gaps(r, rows[0]))
        print(f"  P{r.position:<3}{r.name} {r.segment} {lap_time(r.lap['lap_duration'])}  {gaps}")


if __name__ == "__main__":
    main()
