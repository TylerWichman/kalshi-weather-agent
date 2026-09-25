# KXRAIN sandbox: three arms, pre-registered together

Written and committed **2026-09-25, before any sandbox analysis was run.** This file sets
out the rules shared by all three arms. Each arm has its own pre-registration:

| arm | file | what it checks |
|---|---|---|
| 1 `baseline` | `01-baseline.md` | once a day, 00:00 UTC on the contract date (the Gate 2 rule, re-run in the sandbox) |
| 2 `fixed` | `02-fixed-times.md` | four fixed times: 12:00 and 18:00 UTC the day before, then 00:00 and 04:00 UTC on the contract date |
| 3 `trigger` | `03-move-trigger.md` | every hour from 12:00 UTC the day before to 04:00 UTC on the contract date, but it only evaluates a market after its mid has moved ≥ 10¢ since that market's last evaluation |

The rules are the same as the main pre-registration (`docs/phase3-kxrain-preregistration.md`)
and spec v3 §9.5. The mechanism and go/no-go are fixed here. Nothing is changed after
results are seen. A negative result is never followed by a looser rule. A positive
number that comes from a mechanism other than the one registered is not accepted.

---

## 1. Isolation from Gate 2

Gate 2 (`docs/phase3-kxrain-preregistration.md`, test `26SEP27`–`26OCT24`) is **not
changed in any way.** Its rule, code, config, data, state branch, workflows, paper account
and dashboard are left alone, and none of them reads anything the sandbox produces.

| | Gate 2 | sandbox |
|---|---|---|
| code | `master` | branch `sandbox` (a fork of `master` at `aea3dc1`; later changes to `master` are not merged in) |
| config | `config/kxrain_frozen.json` | `config/sandbox/<arm>_frozen.json`. Arm 1 holds a **copy** of Gate 2's α, β. |
| analysis data | `data/candidates.sqlite` | `data/sandbox.sqlite`. Development rows are copied in once through a **read-only** connection, and test candles are loaded straight into it. |
| live state | branch `state` | branches `sbx-state-baseline`, `sbx-state-fixed`, `sbx-state-trigger`, one per arm |
| paper account | `paper_trades` on `state` | a separate $100 mock account per arm, on that arm's own branch |
| dashboard | GitHub Pages from `state` | a separate page per arm, stored on that arm's own branch |
| Actions | `kxrain-nightly`, `kxrain-update`, concurrency group `kxrain-state` | `sandbox-<arm>`, concurrency group `sandbox-<arm>` |

The only file the sandbox adds to `master` is one workflow file per arm. GitHub runs
scheduled workflows only from the default branch. Each of those files checks out the
`sandbox` branch and never touches `state`.

**Load on Kalshi's API.** Gate 2 fetches books at 23:51 and 23:56 UTC and trades at
00:00:30. The sandbox fetches in the gap between them: arm 1 at 23:57:30, arm 2 at
23:58:00, arm 3 at 23:58:30. It also paces requests at about 6 per second, against Gate 2's
15, so the sandbox cannot use up Gate 2's rate limit.

**The arms are isolated from each other too.** Each has its own workflow, its own state
branch, its own ledger and its own book snapshots. No arm reads another arm's state. The
only thing they share is the development data.

## 2. What is already known, disclosed before anything is run

- **Seen:** the Gate 1 development results (`docs/phase3-kxrain-gate1.md`). That covers
  the 00:00 UTC out-of-fold result (+0.45¢, all trades NO), the fitted curve (α −0.32,
  β 1.17), the market reliability table at 00:00 UTC (YES overpriced, most of all at a
  30–50¢ mid), and the reliability table at 12:00 UTC **on the contract date**.
- **Not seen:** any development price or outcome at any other hour. That includes every
  sandbox check time except 00:00 UTC on the contract date. Before this was written, only
  the *number* of hourly candles per UTC hour was counted, to confirm the data exists.
  About 2,600 candles per hour exist, fewer at 07–09 UTC, which fall before the next
  event opens.
- So arm 1's development number is already known, and so is arm 2's 00:00 check. That is
  why the development gate (§5) is an early kill only, and why the verdict rests on data
  that does not exist yet.

## 3. Shared execution rules

Everything in §3 of the main pre-registration carries over unless an arm says otherwise:
every city, taker only, the real quadratic taker fee, a 3¢ margin, a 5–95¢ band on the
side bought, held to settlement, and 1 contract per trade for the per-contract statistic.

- **Price at a check time *t*.** The hourly candle whose period ends at *t*: its
  `yes_bid_close` and `yes_ask_close`. Missing candle, a one-sided quote (bid 0 or
  ask 100) or a crossed quote means no check for that market at *t*.
- **At most one position per market per arm.** Once an arm holds a market, later checks
  cannot add to it, reverse it or exit it.
- **All check times are before the climate day begins.** The NWS climate day starts at
  local-standard midnight, which is 05:00 UTC in the Eastern zone and later everywhere
  else. The last check is 04:00 UTC on the contract date. So no check price can contain
  an observation of the day being settled. The main pre-registration (§5 diagnostic,
  §6) says apparent edge after observations exist is leakage or a stale candle, not
  opportunity, and "rain already fell" detection is deliberately not registered. The
  sandbox keeps to that.

## 4. Test data

| set | events | notes |
|---|---|---|
| Development | `KXRAIN-26JUL15` … `26SEP23` | same as Gate 1. Used only for the early kill and for fitting curves |
| Warm-up | `26SEP28`, `26SEP29` | the pipeline runs, and the paper accounts trade if frozen in time. **Never scored** |
| **Test** | **`26SEP30` … `26OCT27`, 28 events** | fixed end. No early stop and no extension, whatever the interim results show |

The first check that touches the test set is 2026-09-29 12:00 UTC (arms 2 and 3). **Every
frozen config must be committed before then.** An arm not frozen in time is not run.

The test overlaps Gate 2's test on 25 of its 28 days. Arm 1 is the same rule as Gate 2,
so its verdict duplicates Gate 2's evidence and adds nothing to it. **Gate 2 alone decides
the original rule.** Arm 1 exists as the sandbox's control (§6).

## 5. Development gate (early kill; can stop an arm, cannot start trading)

Arms 2 and 3 fit their curves on the development set, then apply their rules
**out of fold**, leaving one calendar week out at a time, exactly as in Gate 1. **If the
out-of-fold mean net P&L per contract is ≤ 0, that arm is NO-GO and is not run forward.**
Otherwise the curves are refit on all development days and frozen. Arm 1 has no
development gate: it is Gate 1, already run (+0.45¢).

## 6. Go/no-go: the tighter bar for three arms at once

Three arms tested on one forward period give three chances to find a false winner. The
market-making test (CLOSEOUT §3.4) showed how a strong-looking number (t = +21.9) can come
from a mechanism nobody registered. The bar is tightened for multiplicity, and the family
of claims is counted in full:

- the three arm-level GO tests (arms 1, 2, 3), and
- two comparisons: arm 2 against arm 1, and arm 3 against arm 1.

That is **5 confirmatory claims at a family-wise error rate of 5%**. Bonferroni gives
**α = 0.01 per claim**, so every interval that decides anything below is a
**two-sided 99% day-block bootstrap interval** with 20,000 resamples. Gate 2 used 95% and
10,000. The family stays at 5 even if the development gate kills an arm. A dead arm does
not loosen the bar for the others.

### An arm is GO only if all of these hold on the 28 test events

1. **Profitable per contract, at the corrected level.** Mean net P&L per trade > 0, and
   the lower end of the **99%** day-block bootstrap interval is > 0.
2. **Frequent.** At least **100 trades**. There is no extension: fewer is NO-GO.
3. **Worth operating.** At least **$5 net per test day** on average, with each trade sized
   to the contracts shown at the best price in that arm's own book snapshot. The snapshot
   is the latest one taken 60–600 s before the check time, capped at 100 contracts. **If
   more than 10% of trades have no such snapshot, criterion 3 fails.** Unlike Gate 2
   there is no extension: a criterion that cannot be evaluated counts as failed. So an
   infrastructure outage can cause a NO-GO. That risk is accepted up front and is not a
   reason to re-run.
4. **Stable.** Net P&L is positive in both halves of the test, split at the median day.
5. **The registered mechanism.** Every side with ≥ 20% of the arm's test trades has mean
   net > 0 on its own. No single day contributes more than 25% of total net P&L, and no
   single city more than 40%. Each arm file adds an arm-specific check here.

Any failure is NO-GO. There is no partial GO, no "works at 18:00 only", and no re-run with
another threshold, check time, margin or band.

### "Better than the baseline" is a separate, harder claim

Arm *k* (2 or 3) is declared **better than baseline** only if arm *k* is GO **and** the
99% paired day-block interval of (arm *k* daily net − arm 1 daily net) lies entirely
above zero. Daily net is measured at 1 contract per trade over all 28 test days, and a day
with no trades counts as 0. Days are resampled together for both arms. If two arms are GO
and neither passes this comparison, **they are not ranked**, whatever their point
estimates say. A higher point estimate is not a win.

### Power, stated now

Gate 1's day-block interval was ±4.8¢ at 95% over 57 days. Scaled to 28 days and to 99%,
the interval is about **±9¢ per contract**. A GO needs a true edge of roughly that size,
and the only estimate so far is +0.45¢. **The honest prior is NO-GO for every arm.** The
sandbox can rule an idea out cheaply. It is unlikely to rule one in.

## 7. Paper accounts and dashboards (display only)

Each arm has a $100 mock account that trades its frozen rule live. At each check time it
takes one order-book snapshot, fetched 150/120/90 s before the check (arms 1/2/3). It
applies the rule to that book at the check time, fills at the best price for at most $5
per trade including the fee, and holds to settlement. A check run more than 5 minutes late
is recorded as **missed**, never traded late. A snapshot fetch still running at the check
time is discarded, as in Amendment 3.

Each arm publishes its own dashboard page from its own state branch. **The verdict never
reads the paper accounts.** It is computed from candles (§3) and the arm's snapshots
(criterion 3) by `scripts/sandbox_gates.py verdict`, run **once** after `26OCT27`
settles. Nothing on a dashboard changes a rule or a date.

## 8. Not in this program

- **Early exit on a profit threshold** (it pays a second taker fee). The owner raised it on
  2026-09-25, but it is not part of these three arms. Every arm holds to settlement, and
  an exit rule would need its own registration.
- **Choosing the best single time** out of a scan. Arm 2 checks all four of its times.
  It does not pick one after seeing which did best.
- Anything after the climate day begins (§3), maker execution, and weather models.

---

## Amendment 1 (2026-09-25, display only, before any test-period data exists)

At the owner's request, the three paper accounts go live **now**. They trade every check
from the first one after this commit (events from `26SEP26`) and keep running after the
test ends. Each dashboard shows the account as one continuous live account, with no
warm-up or test labels.

**The verdict does not change.** It still scores only `26SEP30`–`26OCT27`, from candles
and each arm's own snapshots, and it never reads the paper ledger (§7). The days before
`26SEP30` are the pipeline's shakeout: they must show the checks running and the
snapshots landing, and they count toward nothing. If the shakeout shows a pipeline
fault, it is fixed before 2026-09-29 12:00 UTC. A fault found later is reported with the
verdict. It is never a reason to change a rule.
