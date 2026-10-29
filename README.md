# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$130.55** (started at $100). Updated Oct 29 1:40 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-30 | HOU | Oct 29 1:00 PM ET | NO | 10 | 45¢ | open | +0.22 |
| 10-30 | ABQ | Oct 29 11:00 AM ET | NO | 2 | 44¢ | open | -0.14 |
| 10-30 | LAX | Oct 29 11:00 AM ET | NO | 10 | 47¢ | open | -0.38 |
| 10-30 | LV | Oct 29 10:00 AM ET | NO | 2 | 54¢ | open | -0.10 |
| 10-30 | CLL | Oct 29 9:00 AM ET | NO | 3 | 34¢ | open | -0.35 |
| 10-29 | MIA | Oct 29 12:00 AM ET | NO | 4 | 51¢ | open | +0.29 |
| 10-29 | SATX | Oct 28 10:00 PM ET | NO | 22 | 13¢ | open | -0.18 |
| 10-29 | MKE | Oct 28 6:00 PM ET | NO | 2 | 50¢ | open | -0.04 |
| 10-29 | WPB | Oct 28 4:00 PM ET | NO | 1 | 51¢ | open | -0.02 |
| 10-29 | DAL | Oct 28 11:00 AM ET | NO | 1 | 57¢ | open | -0.23 |
| 10-29 | AUS | Oct 28 9:00 AM ET | NO | 3 | 48¢ | open | -0.06 |
| 10-29 | DTW | Oct 28 9:00 AM ET | NO | 2 | 37¢ | open | +0.60 |
| 10-28 | HOU | Oct 27 4:00 PM ET | NO | 7 | 65¢ | won | +2.33 |
| 10-28 | MIA | Oct 27 1:00 PM ET | NO | 7 | 28¢ | lost | -2.06 |
| 10-28 | SATX | Oct 27 12:00 PM ET | NO | 7 | 61¢ | won | +2.61 |
| 10-28 | AUS | Oct 27 11:00 AM ET | NO | 8 | 55¢ | won | +3.46 |
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

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
