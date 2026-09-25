# KXRAIN collection on GitHub Actions

Runs in the **public** repo `TylerWichman/kalshi-weather-agent`. No server, no card.
Public repos get unlimited Actions minutes, which the nightly job needs because it
waits about 4 hours. The code, run logs and mock-trade ledger are publicly visible;
the ntfy topic is a repo secret and never appears in them. (The repo was private until
2026-09-25, when the 23:29 start proved too late; see below.)

| workflow | when (UTC) | does |
|---|---|---|
| **KXRAIN nightly** | 20:07, backup 21:37 | waits in-job for book snapshots at 23:51 and 23:56, the paper trade at 00:00:30, then an update |
| **KXRAIN update** | every 3 h at :13 | settles positions, marks to market, sends alerts; the 13:13 run sends the morning summary |

State that cannot be backfilled lives on the **`state` branch** as JSON lines: KXRAIN
book snapshots, the snapshot-run audit log, and the paper-trading ledger
(`src/actions.py`).

**Timing and the discard rule (pre-registration Amendment 3).** GitHub starts
scheduled jobs late, sometimes by over 2 hours: on the 09-25 night the 23:29 run
started at 01:45 and the warm-up night was missed. The job now starts about 4 hours
early and waits for the exact times. A snapshot
run starting within 60 s of 00:00 UTC, or still fetching at 00:00, is discarded and
logged. Gate 2 uses only snapshots stamped 23:50:00–23:59:00. A paper trade more than
5 minutes late becomes a missed night. Lateness shows up as a gap and an alert, never
as bad data.

## Watching it

- **Phone:** ntfy alerts, one per night's trades, one per settlement, and a morning
  summary.
- **GitHub:** repo → **Actions** → any run → the summary shows the account, the
  collector status and recent trades. This also works in the GitHub mobile app.
- **A failed job** also triggers GitHub's own failure email.

## Running a job by hand

Actions → *KXRAIN nightly* → **Run workflow** → `dryrun` takes one snapshot and places
no trade. *KXRAIN update* → **Run workflow** settles and marks now.

## Gate 2 (after the 2026-10-24 event settles)

On the laptop:

```
git fetch origin state && git worktree add ../kxrain-state origin/state
python -m src.actions import-state --state ../kxrain-state
python -m src.candidates history --series KXRAIN
python scripts/rain_calibration.py gate2
```

The first command brings the snapshots and ledger down. The history load re-fetches
the test events' candles and results from Kalshi. Gate 2 then runs **once**.

## The laptop

Paper trading and the health pop-up are disabled there, and its power settings are
back to normal. Its silent snapshot collectors still run whenever it happens to be
on, as a free backup; `import-state` merges without duplicates.
