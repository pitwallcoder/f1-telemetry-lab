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
5. **Zones**: the gap is read only where it is measurable (from 60% of top speed up) and the lap is split where
   it turns, ignoring wiggles under 0.025 s and trimming flat ends. A zone runs from one turn to the next, so it
   marks where one driver actually took time off the other. The chart shows up to three zones for the faster driver
   and two for the slower one; the rest adds up to the lap gap.

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
