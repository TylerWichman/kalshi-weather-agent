# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$57.34** (started at $100). Updated Oct 17 4:29 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-17 | LEX | Oct 16 10:00 PM ET | NO | 6 | 60¢ | open | -0.11 |
| 10-17 | PVD | Oct 16 10:00 PM ET | NO | 23 | 20¢ | open | -0.26 |
| 10-17 | EWR | Oct 16 1:00 PM ET | NO | 10 | 48¢ | open | -4.28 |
| 10-17 | PHIL | Oct 16 1:00 PM ET | NO | 8 | 19¢ | open | -0.09 |
| 10-17 | TTN | Oct 16 1:00 PM ET | NO | 11 | 40¢ | open | -0.19 |
| 10-17 | DC | Oct 16 12:00 PM ET | NO | 26 | 18¢ | open | -0.27 |
| 10-17 | NYC | Oct 16 12:00 PM ET | NO | 10 | 48¢ | open | -0.18 |
| 10-16 | CLL | Oct 16 12:00 AM ET | NO | 15 | 31¢ | open | -0.23 |
| 10-16 | MIN | Oct 16 12:00 AM ET | NO | 21 | 22¢ | open | -0.26 |
| 10-16 | LEX | Oct 15 6:00 PM ET | NO | 13 | 26¢ | open | -0.18 |
| 10-16 | SATX | Oct 15 4:00 PM ET | NO | 7 | 63¢ | open | -0.12 |
| 10-16 | DTW | Oct 15 2:00 PM ET | NO | 10 | 17¢ | open | -0.10 |
| 10-16 | DAL | Oct 15 1:00 PM ET | NO | 10 | 45¢ | open | -0.18 |
| 10-16 | MIA | Oct 15 1:00 PM ET | NO | 12 | 39¢ | open | -0.20 |
| 10-16 | CHI | Oct 15 12:00 PM ET | NO | 7 | 45¢ | open | -0.13 |
| 10-16 | TPA | Oct 15 12:00 PM ET | NO | 1 | 40¢ | open | -0.02 |
| 10-16 | MKE | Oct 15 10:00 AM ET | NO | 6 | 24¢ | open | -0.08 |
| 10-15 | PIT | Oct 14 8:00 PM ET | NO | 8 | 55¢ | won | +3.46 |
| 10-15 | DC | Oct 14 7:00 PM ET | NO | 9 | 8¢ | lost | -0.77 |
| 10-15 | LEX | Oct 14 3:00 PM ET | NO | 12 | 21¢ | lost | -2.66 |
| 10-15 | DAL | Oct 14 1:00 PM ET | NO | 7 | 65¢ | lost | -4.67 |
| 10-15 | PHIL | Oct 14 1:00 PM ET | NO | 3 | 51¢ | won | +1.41 |
| 10-15 | IND | Oct 14 11:00 AM ET | NO | 36 | 13¢ | lost | -4.97 |
| 10-15 | MIA | Oct 14 11:00 AM ET | NO | 6 | 44¢ | lost | -2.75 |
| 10-15 | CMH | Oct 14 9:00 AM ET | NO | 7 | 29¢ | won | +4.86 |
| 10-14 | PHIL | Oct 13 11:00 PM ET | NO | 7 | 61¢ | lost | -4.39 |
| 10-14 | CLL | Oct 13 9:00 PM ET | NO | 2 | 52¢ | lost | -1.08 |
| 10-14 | MIA | Oct 13 9:00 PM ET | NO | 1 | 67¢ | lost | -0.69 |
| 10-14 | DET | Oct 13 10:00 AM ET | NO | 13 | 35¢ | won | +8.24 |
| 10-14 | AUS | Oct 13 9:00 AM ET | NO | 1 | 49¢ | won | +0.49 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
