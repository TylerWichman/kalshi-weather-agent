# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$83.22** (started at $100). Updated Sep 30 6:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-01 | NOLA | Sep 30 6:00 PM ET | NO | 14 | 32¢ | open | -0.50 |
| 09-30 | DAL | Sep 29 7:00 PM ET | NO | 12 | 37¢ | open | -0.20 |
| 09-30 | DEN | Sep 29 7:00 PM ET | NO | 24 | 19¢ | open | -0.26 |
| 09-30 | HOU | Sep 29 4:00 PM ET | NO | 1 | 38¢ | open | +0.54 |
| 09-30 | AUS | Sep 29 3:00 PM ET | NO | 9 | 52¢ | open | -0.16 |
| 09-30 | SATX | Sep 29 12:00 PM ET | NO | 8 | 59¢ | open | +1.06 |
| 09-30 | MIA | Sep 29 11:00 AM ET | NO | 4 | 18¢ | open | -0.05 |
| 09-29 | BOS | Sep 28 11:00 PM ET | NO | 8 | 58¢ | won | +3.22 |
| 09-29 | OKC | Sep 28 11:00 PM ET | NO | 2 | 60¢ | won | +0.76 |
| 09-29 | LV | Sep 28 6:00 PM ET | NO | 1 | 54¢ | lost | -0.56 |
| 09-29 | DEN | Sep 28 5:00 PM ET | NO | 8 | 56¢ | won | +3.38 |
| 09-28 | DAL | Sep 27 8:00 PM ET | NO | 3 | 47¢ | won | +1.53 |
| 09-28 | PHIL | Sep 27 7:00 PM ET | NO | 20 | 10¢ | lost | -2.13 |
| 09-28 | PHX | Sep 27 7:00 PM ET | NO | 31 | 15¢ | lost | -4.93 |
| 09-28 | LV | Sep 27 4:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 09-28 | DEN | Sep 27 11:00 AM ET | NO | 7 | 61¢ | won | +2.61 |
| 09-27 | DAL | Sep 26 6:00 PM ET | NO | 9 | 53¢ | won | +4.07 |
| 09-27 | MIN | Sep 26 12:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 09-26 | OKC | Sep 25 10:00 PM ET | NO | 13 | 29¢ | lost | -3.96 |
| 09-26 | DC | Sep 25 7:00 PM ET | NO | 11 | 18¢ | lost | -2.10 |
| 09-26 | MIA | Sep 25 7:00 PM ET | NO | 10 | 48¢ | won | +5.02 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
