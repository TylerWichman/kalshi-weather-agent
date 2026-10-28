# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$139.50** (started at $100). Updated Oct 28 1:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-29 | DAL | Oct 28 11:00 AM ET | NO | 1 | 57¢ | open | +0.11 |
| 10-29 | AUS | Oct 28 9:00 AM ET | NO | 3 | 48¢ | open | +0.00 |
| 10-29 | DTW | Oct 28 9:00 AM ET | NO | 2 | 37¢ | open | +0.14 |
| 10-28 | HOU | Oct 27 4:00 PM ET | NO | 7 | 65¢ | open | +1.84 |
| 10-28 | MIA | Oct 27 1:00 PM ET | NO | 7 | 28¢ | open | +3.54 |
| 10-28 | SATX | Oct 27 12:00 PM ET | NO | 7 | 61¢ | open | +1.28 |
| 10-28 | AUS | Oct 27 11:00 AM ET | NO | 8 | 55¢ | open | +2.18 |
| 10-27 | AUS | Oct 26 5:00 PM ET | NO | 7 | 65¢ | won | +2.33 |
| 10-27 | OKC | Oct 26 3:00 PM ET | NO | 13 | 28¢ | won | +9.17 |
| 10-27 | SATX | Oct 26 1:00 PM ET | NO | 10 | 44¢ | won | +5.42 |
| 10-26 | DEN | Oct 25 10:00 AM ET | NO | 7 | 50¢ | lost | -3.63 |
| 10-26 | MIA | Oct 25 10:00 AM ET | NO | 19 | 24¢ | lost | -4.81 |
| 10-26 | SEA | Oct 25 10:00 AM ET | NO | 3 | 29¢ | lost | -0.92 |
| 10-25 | MIN | Oct 24 8:00 PM ET | NO | 1 | 21¢ | lost | -0.23 |
| 10-25 | ABQ | Oct 24 2:00 PM ET | NO | 4 | 44¢ | lost | -1.83 |
| 10-25 | DEN | Oct 24 10:00 AM ET | NO | 7 | 50¢ | won | +3.37 |
| 10-24 | MIA | Oct 23 10:00 PM ET | NO | 4 | 58¢ | won | +1.61 |
| 10-24 | DEN | Oct 23 1:00 PM ET | NO | 6 | 42¢ | won | +3.37 |
| 10-23 | ABQ | Oct 22 11:00 PM ET | NO | 1 | 14¢ | lost | -0.15 |
| 10-23 | MIN | Oct 22 10:00 PM ET | NO | 9 | 53¢ | won | +4.07 |
| 10-23 | WPB | Oct 22 5:00 PM ET | NO | 1 | 36¢ | lost | -0.38 |
| 10-23 | MIA | Oct 22 3:00 PM ET | NO | 3 | 32¢ | lost | -1.01 |
| 10-22 | MIA | Oct 21 8:00 PM ET | NO | 10 | 46¢ | won | +5.22 |
| 10-22 | LV | Oct 21 5:00 PM ET | NO | 3 | 34¢ | won | +1.93 |
| 10-22 | DEN | Oct 21 4:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 10-22 | PHX | Oct 21 1:00 PM ET | NO | 1 | 26¢ | won | +0.72 |
| 10-22 | WPB | Oct 21 11:00 AM ET | NO | 12 | 37¢ | lost | -4.64 |
| 10-21 | LV | Oct 20 9:00 PM ET | NO | 7 | 61¢ | won | +2.61 |
| 10-21 | ABQ | Oct 20 8:00 PM ET | NO | 3 | 62¢ | won | +1.09 |
| 10-21 | WPB | Oct 20 8:00 PM ET | NO | 9 | 50¢ | lost | -4.66 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
