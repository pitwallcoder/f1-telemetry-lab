# f1-telemetry-lab

The code behind **Pit Wall Notes** by [@pitwallcoder](https://x.com/pitwallcoder): one chart per idea, built from
public F1 telemetry, with the code to reproduce it.

## Speed-trace comparison

Two drivers' fastest valid laps of a session: speed, time gap along the lap, and where each of them gained time.

```bash
uv run python -m pitwall 2026 "Mexico City" FP1 --code PW-001        # the session's top two
uv run python -m pitwall 2026 "Mexico City" Q LEC VER --code PW-005  # two drivers, by acronym or number
```

Each run writes to `out/<code>/`:

- a 1600×900 PNG that states measured facts only: lap times and official sector gaps as on a timing screen, the
  speed traces, the gap along the lap, and the zones where each driver gained time, each zone in the team colour
  of the driver who gained there;
- a JSON file with the same facts (lap and sector times, zones with speeds at braking and minimum speeds, data
  quality), for writing the post around the chart. Interpretation lives in the post, not in the chart.

### Names

Names are exact: one official name per circuit and session, no aliases.

**Sessions** — our code for F1's official session name:

| Code | Session |
|---|---|
| `FP1` | Practice 1 |
| `FP2` | Practice 2 |
| `FP3` | Practice 3 |
| `SQ` | Sprint Qualifying (called Sprint Shootout in 2023) |
| `S` | Sprint |
| `Q` | Qualifying |
| `R` | Race |

Pre-season testing is not covered.

**Circuits** — OpenF1's `circuit_short_name`. A mistyped circuit is rejected with the list for that season. 2026:

Sakhir · Melbourne · Shanghai · Suzuka · Jeddah · Miami · Montreal · Monte Carlo · Catalunya · Spielberg ·
Silverstone · Spa-Francorchamps · Hungaroring · Zandvoort · Monza · Madring · Baku · Kuala Lumpur · Singapore ·
Austin · Mexico City · Interlagos · Las Vegas · Lusail · Yas Marina Circuit

### How the gap is measured

OpenF1 gives speed and position at ~4 Hz each, on separate clocks, with no distance channel. Distance has to be
built, and how it is built decides the precision.

1. **Laps**: each driver's fastest lap with all three sectors timed that race control did not delete. Deletions
   are matched by the deleted time; race control's "LAP n" is OpenF1's lap n − 1, used only when no time is given.
2. **Distance by fusion** (`pitwall/distance.py`): integrated speed has the right shape but drifts and is wrecked
   by a single bad sample; positions projected onto the official track line (MultiViewer) don't drift but scatter
   by ~3–10 m. A least-squares fit keeps the shape of the first and the level of the second (a correction every
   6 s), and finds the ~0.1 s clock offset between the two streams.
3. **Pinned to official timing**: both cars cross the same sector and finish lines, so each is held at the lines'
   shared position at its official crossing time, and the gap curve passes exactly through the official sector
   and lap gaps.
4. **Gap**: time difference at the same track distance, smoothed over 100 m.
5. **Zones**: the lap is split where the gap turns, read only where it is measurable (from 60% of top speed up)
   and ignoring wiggles under 0.025 s, and also where each long straight ends, since straight-line time builds up
   slowly and corner time quickly. Every zone where either driver gained 0.05 s or more is shown, named by its
   corners ("T4–T6") or, for a straight, by the corners either side ("T3→T4"); the rest adds up to the lap gap.

### Precision

`uv run python -m tests.validate_against_timing` checks the method on 15 sessions at 12 circuits, before pinning
to official timing:

- the gap at each sector line, pinned only to the other line and the finish: **median 0.022 s, worst 0.178 s**
  (30 lines);
- where the two cars are at their official crossings: median 1.5 m apart, 90% under 4.3 m (45 lines).

For comparison, integrating speed alone (what most tools do) measured a median of 0.043 s and a worst case of
2.4 s on 22 of those lines during development.

- Sector and lap gaps are official and exact. Zone gains are good to about **±0.05 s**: shown with 3 decimals so
  the column adds up, read them as hundredths.
- Inside slow corners the gap line can swing ±0.2 s from noise at 4 Hz, so the chart draws it faded there and
  zones are only cut where the gap is measurable.
- When a session's data is noisier than 90% of those 15, the command prints a warning.
- Tried and rejected, with numbers: aligning on corners (no gain), matching raw positions (0.10 s), integrating
  the pace difference (0.09 s, 2.3 s worst), weighting positions by speed (no gain).

## Qualifying ladder

Every driver's gap to pole in a qualifying (`Q`, default) or sprint qualifying (`SQ`) session, sector by sector.

```bash
uv run python -m pitwall.quali_ladder 2026 "Mexico City" --code PW-003
```

Official timing only, so every number is exact. Drivers are in official order; each one's time is the one that
classified them, from the last part of qualifying they set a time in (a dotted line marks where that changes from
Q3 to Q2 and Q1). Each bar is the lap gap; beside it sit the lap time and each sector minus pole's, with sectors
faster than pole's in white and the best of these laps in each sector in purple (the session's fastest sector
can come from a lap that did not classify the driver). Writes a PNG and a JSON with the same facts to `out/<code>/`.

## Race charts

Charts of a Grand Prix, all from official timing, with the race-control periods worked out from the race
itself: a VSC, safety car or red flag runs from the message that starts it to the one that ends it, by lap of the
leader (a safety car that becomes a red flag ends the lap before).

### Position chart

```bash
uv run python -m pitwall.race_positions 2026 "Mexico City" --code PW-009
```

Every driver's place at the end of every lap, from the order in which cars crossed the line, starting from the
grid. Lines in team colours, the teammate who started behind dashed; a circle with the compound letter where each
tyre set was fitted; neutralised laps shaded; × where a driver retired. The right-hand labels are the official
classification, starred when a time penalty dropped a driver below where he crossed the line.

### Race pace

```bash
uv run python -m pitwall.race_pace 2026 "Mexico City" --code PW-010
```

Every classified driver's representative laps, ranked by median: no lap 1, no neutralised laps and no restart lap
after a safety car or red flag, no laps into or out of the pits, and none more than 3% slower than the driver's
own median (traffic, mistakes, damage, local yellows). Laps are fuel-corrected at ~0.035 s per lap of fuel still
on board, a typical estimate rather than a measured figure, so medians are estimates. One box per driver (middle
50% of laps, median in white) with every lap as a dot coloured by compound.

The shared lap-by-lap logic is in `pitwall/race.py`; each chart module only turns it into a picture.

### The fight between two drivers

```bash
uv run python -m pitwall.race_gaps 2026 "Mexico City" --code PW-018     # the top two finishers
uv run python -m pitwall.race_gaps 2026 "Mexico City" LEC HAM
```

How far apart two drivers were at the end of every lap, from official line crossings: above the line the driver
classified ahead leads, below the other one. Each pit stop is marked with the tyres fitted and who pitted, and
VSC, safety car and red flag laps are shaded.

### Positions gained

```bash
uv run python -m pitwall.positions_gained 2026 "Mexico City" --code PW-017
```

Every classified driver's places gained (green) or lost (red) from the grid to the official result, or with
`--lap-one` to the order across the line at the end of lap 1. Retirements are left out.

## Teammate head-to-head

Who was classified ahead of his teammate, round by round, over a season: qualifying (`Q`) or the race (`R`).

```bash
uv run python -m pitwall.head_to_head 2026 Q --code PW-011
uv run python -m pitwall.head_to_head 2026 R --code PW-012
```

Teammates are paired per round from that weekend's entry list, so mid-season seat swaps get their own row. A
classified driver beats an unclassified teammate (DNF, DSQ, no time); rounds where neither is classified don't
count. Qualifying adds the median gap, taken in the last part of qualifying (Q3, else Q2, else Q1) both drivers
set a time in. Cancelled rounds and rounds with no published result are skipped.

## Practice long runs

```bash
uv run python -m pitwall.long_runs 2026 Interlagos --code PW-016            # FP2; --session FP1 or FP3
```

Each driver's longest stint at race pace: no out-laps, no laps under a VSC, safety car or red flag, and none more
than 3% slower than the stint's fastest (cool-down laps, traffic, the in-lap), so a qualifying run of push and
cool-down laps never counts. At least 5 laps. Laps are fuel-corrected to the run's last lap at ~0.035 s per lap and
degradation is the slope of a straight line through them. Fuel loads and engine modes in practice are unknown, so
the ranking is a guide, not a result. Drawn as a timing tower: average lap, gap, tyre, laps and tyre wear.

## Top speed

```bash
uv run python -m pitwall.top_speed 2026 "Las Vegas" Q --code PW-015
```

Each driver's best official speed-trap reading of the session, as a timing tower. OpenF1 has no reading on some laps (about 1 in 5);
the JSON also lists both intermediates.

## Minisector dominance

```bash
uv run python -m pitwall.minisectors 2026 "Mexico City" Q --code PW-019          # fastest of the top 2 teams
uv run python -m pitwall.minisectors 2026 "Mexico City" Q VER LEC
```

The drivers' fastest laps, measured as in the speed-trace comparison (distance by fusion, every lap pinned to the
official timing lines), the track split into 25 equal minisectors and each drawn in the colour of whoever was
quickest through it. A minisector where the top two are within 0.02 s, about what a few metres of position error
is worth at speed, is grey: too close to call.

## Track limits

```bash
uv run python -m pitwall.track_limits 2026 --code PW-014                              # the season so far
uv run python -m pitwall.track_limits 2026 --session "Mexico City" R --code PW-013    # one session
```

Laps and lap times race control deleted for track limits: by driver, and on the circuit map with a circle per
turn sized by deletions (one session), or by circuit (the season, every session including practice). Reinstated laps are not counted. OpenF1 files a few messages of an
earlier session of the weekend under a later one, so messages from before the session started are ignored.

### For readers who are not data people

The new charts share one layout (`style.story_figure`): the event in small capitals, the takeaway as the title,
worked out from the data ("Verstappen beat Hamilton by 0.8 s"), and one plain sentence on how to read the chart.
Drivers go by surname, rankings look like a timing tower, and technical caveats sit in the footer.

## Development

```bash
uv run pytest
```

The end-to-end tests replay recorded API responses that are not in the repo (third-party data); without them they
are skipped. Record them once with:

```bash
uv run python -m tests.record_fixture mexico_2026_fp1 2026 "Mexico City" FP1
```

`pitwall/net.py` is the only module that touches the network; tests swap it for recorded responses. Sessions that
ended more than 12 hours ago are cached in `.cache/`.

Data: [OpenF1](https://openf1.org) · track and corners: [MultiViewer](https://multiviewer.app). Not affiliated with
Formula 1. MIT licensed.
