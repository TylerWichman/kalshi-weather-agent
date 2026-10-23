# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$112.98** (started at $100). Updated Oct 22 10:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-23 | MIN | Oct 22 10:00 PM ET | NO | 9 | 53¢ | open | -0.25 |
| 10-23 | WPB | Oct 22 5:00 PM ET | NO | 1 | 36¢ | open | +0.08 |
| 10-23 | MIA | Oct 22 3:00 PM ET | NO | 3 | 32¢ | open | +0.22 |
| 10-22 | MIA | Oct 21 8:00 PM ET | NO | 10 | 46¢ | open | +4.72 |
| 10-22 | LV | Oct 21 5:00 PM ET | NO | 3 | 34¢ | open | +1.90 |
| 10-22 | DEN | Oct 21 4:00 PM ET | NO | 7 | 63¢ | open | +1.91 |
| 10-22 | PHX | Oct 21 1:00 PM ET | NO | 1 | 26¢ | open | +0.71 |
| 10-22 | WPB | Oct 21 11:00 AM ET | NO | 12 | 37¢ | open | -0.20 |
| 10-21 | LV | Oct 20 9:00 PM ET | NO | 7 | 61¢ | won | +2.61 |
| 10-21 | ABQ | Oct 20 8:00 PM ET | NO | 3 | 62¢ | won | +1.09 |
| 10-21 | WPB | Oct 20 8:00 PM ET | NO | 9 | 50¢ | lost | -4.66 |
| 10-21 | SFO | Oct 20 3:00 PM ET | NO | 4 | 32¢ | won | +2.65 |
| 10-21 | PHX | Oct 20 1:00 PM ET | NO | 14 | 30¢ | won | +9.59 |
| 10-20 | WPB | Oct 20 12:00 AM ET | NO | 10 | 47¢ | lost | -4.88 |
| 10-20 | ABQ | Oct 19 11:00 PM ET | NO | 7 | 66¢ | lost | -4.73 |
| 10-20 | MIA | Oct 19 6:00 PM ET | NO | 8 | 55¢ | lost | -4.54 |
| 10-19 | MIA | Oct 18 10:00 PM ET | NO | 10 | 47¢ | won | +5.12 |
| 10-19 | ABQ | Oct 18 7:00 PM ET | NO | 8 | 57¢ | won | +3.30 |
| 10-18 | WPB | Oct 17 3:00 PM ET | NO | 23 | 20¢ | won | +18.14 |
| 10-17 | LEX | Oct 16 10:00 PM ET | NO | 6 | 60¢ | lost | -3.71 |
| 10-17 | PVD | Oct 16 10:00 PM ET | NO | 23 | 20¢ | lost | -4.86 |
| 10-17 | EWR | Oct 16 1:00 PM ET | NO | 10 | 48¢ | won | +5.02 |
| 10-17 | PHIL | Oct 16 1:00 PM ET | NO | 8 | 19¢ | lost | -1.61 |
| 10-17 | TTN | Oct 16 1:00 PM ET | NO | 11 | 40¢ | lost | -4.59 |
| 10-17 | DC | Oct 16 12:00 PM ET | NO | 26 | 18¢ | lost | -4.95 |
| 10-17 | NYC | Oct 16 12:00 PM ET | NO | 10 | 48¢ | lost | -4.98 |
| 10-16 | CLL | Oct 16 12:00 AM ET | NO | 15 | 31¢ | lost | -4.88 |
| 10-16 | MIN | Oct 16 12:00 AM ET | NO | 21 | 22¢ | lost | -4.88 |
| 10-16 | LEX | Oct 15 6:00 PM ET | NO | 13 | 26¢ | lost | -3.56 |
| 10-16 | SATX | Oct 15 4:00 PM ET | NO | 7 | 63¢ | won | +2.47 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
