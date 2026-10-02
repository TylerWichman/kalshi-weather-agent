# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$56.66** (started at $100). Updated Oct 2 1:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-03 | SATX | Oct 2 1:00 PM ET | NO | 4 | 24¢ | open | -0.02 |
| 10-03 | MIN | Oct 2 12:00 PM ET | NO | 12 | 39¢ | open | -0.68 |
| 10-02 | TTN | Oct 2 12:00 AM ET | NO | 1 | 45¢ | open | -0.07 |
| 10-02 | NYC | Oct 1 10:00 PM ET | NO | 1 | 38¢ | open | -0.08 |
| 10-02 | ATL | Oct 1 9:00 PM ET | NO | 7 | 68¢ | open | +0.59 |
| 10-02 | DC | Oct 1 6:00 PM ET | NO | 8 | 60¢ | open | -2.14 |
| 10-02 | PHIL | Oct 1 5:00 PM ET | NO | 8 | 60¢ | open | -2.06 |
| 10-02 | CHI | Oct 1 2:00 PM ET | NO | 8 | 55¢ | open | +3.38 |
| 10-02 | OKC | Oct 1 2:00 PM ET | NO | 1 | 58¢ | open | -0.02 |
| 10-02 | EWR | Oct 1 1:00 PM ET | NO | 6 | 52¢ | open | -1.13 |
| 10-02 | MIA | Oct 1 1:00 PM ET | NO | 36 | 13¢ | open | -0.29 |
| 10-02 | BOS | Oct 1 11:00 AM ET | NO | 8 | 59¢ | open | -2.38 |
| 10-02 | PIT | Oct 1 11:00 AM ET | NO | 36 | 13¢ | open | -0.29 |
| 10-02 | PVD | Oct 1 11:00 AM ET | NO | 6 | 52¢ | open | -1.37 |
| 10-01 | NOLA | Sep 30 6:00 PM ET | NO | 14 | 32¢ | lost | -4.70 |
| 09-30 | DAL | Sep 29 7:00 PM ET | NO | 12 | 37¢ | lost | -4.64 |
| 09-30 | DEN | Sep 29 7:00 PM ET | NO | 24 | 19¢ | lost | -4.82 |
| 09-30 | HOU | Sep 29 4:00 PM ET | NO | 1 | 38¢ | won | +0.60 |
| 09-30 | AUS | Sep 29 3:00 PM ET | NO | 9 | 52¢ | lost | -4.84 |
| 09-30 | SATX | Sep 29 12:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 09-30 | MIA | Sep 29 11:00 AM ET | NO | 4 | 18¢ | lost | -0.77 |
| 09-29 | BOS | Sep 28 11:00 PM ET | NO | 8 | 58¢ | won | +3.22 |
| 09-29 | OKC | Sep 28 11:00 PM ET | NO | 2 | 60¢ | won | +0.76 |
| 09-29 | LV | Sep 28 6:00 PM ET | NO | 1 | 54¢ | lost | -0.56 |
| 09-29 | DEN | Sep 28 5:00 PM ET | NO | 8 | 56¢ | won | +3.38 |
| 09-28 | DAL | Sep 27 8:00 PM ET | NO | 3 | 47¢ | won | +1.53 |
| 09-28 | PHIL | Sep 27 7:00 PM ET | NO | 20 | 10¢ | lost | -2.13 |
| 09-28 | PHX | Sep 27 7:00 PM ET | NO | 31 | 15¢ | lost | -4.93 |
| 09-28 | LV | Sep 27 4:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 09-28 | DEN | Sep 27 11:00 AM ET | NO | 7 | 61¢ | won | +2.61 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
