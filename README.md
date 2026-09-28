# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$93.60** (started at $100). Updated Sep 27 10:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 09-28 | DAL | Sep 27 8:00 PM ET | NO | 3 | 47¢ | open | +0.21 |
| 09-28 | PHIL | Sep 27 7:00 PM ET | NO | 20 | 10¢ | open | +0.67 |
| 09-28 | PHX | Sep 27 7:00 PM ET | NO | 31 | 15¢ | open | -2.14 |
| 09-28 | LV | Sep 27 4:00 PM ET | NO | 8 | 59¢ | open | -0.78 |
| 09-28 | DEN | Sep 27 11:00 AM ET | NO | 7 | 61¢ | open | -2.08 |
| 09-27 | DAL | Sep 26 6:00 PM ET | NO | 9 | 53¢ | open | +3.62 |
| 09-27 | MIN | Sep 26 12:00 PM ET | NO | 8 | 59¢ | open | -0.14 |
| 09-26 | OKC | Sep 25 10:00 PM ET | NO | 13 | 29¢ | lost | -3.96 |
| 09-26 | DC | Sep 25 7:00 PM ET | NO | 11 | 18¢ | lost | -2.10 |
| 09-26 | MIA | Sep 25 7:00 PM ET | NO | 10 | 48¢ | won | +5.02 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
