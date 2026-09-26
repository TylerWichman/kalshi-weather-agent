# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$96.12** (started at $100). Updated Sep 26 12:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 09-27 | MIN | Sep 26 12:00 PM ET | NO | 8 | 59¢ | open | -0.38 |
| 09-26 | OKC | Sep 25 10:00 PM ET | NO | 13 | 29¢ | open | -0.19 |
| 09-26 | DC | Sep 25 7:00 PM ET | NO | 11 | 18¢ | open | -1.66 |
| 09-26 | MIA | Sep 25 7:00 PM ET | NO | 10 | 48¢ | open | +2.12 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
