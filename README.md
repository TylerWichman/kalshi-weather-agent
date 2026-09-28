# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$92.70** (started at $100). Updated Sep 28 6:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 09-29 | LV | Sep 28 6:00 PM ET | NO | 1 | 54¢ | open | -0.05 |
| 09-29 | DEN | Sep 28 5:00 PM ET | NO | 8 | 56¢ | open | -1.74 |
| 09-28 | DAL | Sep 27 8:00 PM ET | NO | 3 | 47¢ | open | +1.32 |
| 09-28 | PHIL | Sep 27 7:00 PM ET | NO | 20 | 10¢ | open | -0.13 |
| 09-28 | PHX | Sep 27 7:00 PM ET | NO | 31 | 15¢ | open | -0.28 |
| 09-28 | LV | Sep 27 4:00 PM ET | NO | 8 | 59¢ | open | +1.62 |
| 09-28 | DEN | Sep 27 11:00 AM ET | NO | 7 | 61¢ | open | +0.44 |
| 09-27 | DAL | Sep 26 6:00 PM ET | NO | 9 | 53¢ | won | +4.07 |
| 09-27 | MIN | Sep 26 12:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 09-26 | OKC | Sep 25 10:00 PM ET | NO | 13 | 29¢ | lost | -3.96 |
| 09-26 | DC | Sep 25 7:00 PM ET | NO | 11 | 18¢ | lost | -2.10 |
| 09-26 | MIA | Sep 25 7:00 PM ET | NO | 10 | 48¢ | won | +5.02 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
