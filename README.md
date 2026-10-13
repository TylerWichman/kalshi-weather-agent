# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$126.05** (started at $100). Updated Oct 13 6:40 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-14 | DET | Oct 13 10:00 AM ET | NO | 13 | 35¢ | open | +0.05 |
| 10-14 | AUS | Oct 13 9:00 AM ET | NO | 1 | 49¢ | open | +0.05 |
| 10-13 | PHX | Oct 12 6:00 PM ET | NO | 3 | 54¢ | open | -0.06 |
| 10-13 | PVD | Oct 12 3:00 PM ET | NO | 2 | 57¢ | open | +0.50 |
| 10-12 | TTN | Oct 12 12:00 AM ET | NO | 2 | 53¢ | lost | -1.10 |
| 10-12 | HOU | Oct 11 11:00 PM ET | NO | 11 | 42¢ | lost | -4.81 |
| 10-12 | PHIL | Oct 11 9:00 PM ET | NO | 33 | 14¢ | lost | -4.90 |
| 10-12 | PHX | Oct 11 8:00 PM ET | NO | 3 | 37¢ | lost | -1.16 |
| 10-12 | CLL | Oct 11 6:00 PM ET | NO | 7 | 64¢ | won | +2.40 |
| 10-12 | EWR | Oct 11 1:00 PM ET | NO | 12 | 38¢ | won | +7.24 |
| 10-12 | NYC | Oct 11 12:00 PM ET | NO | 13 | 36¢ | won | +8.11 |
| 10-12 | PVD | Oct 11 11:00 AM ET | NO | 8 | 17¢ | lost | -1.44 |
| 10-12 | LV | Oct 11 10:00 AM ET | NO | 6 | 44¢ | won | +3.25 |
| 10-11 | MIA | Oct 10 4:00 PM ET | NO | 8 | 56¢ | lost | -4.62 |
| 10-11 | TPA | Oct 10 9:00 AM ET | NO | 2 | 54¢ | lost | -1.12 |
| 10-10 | TAM | Oct 9 8:00 PM ET | NO | 15 | 27¢ | won | +10.74 |
| 10-10 | PHX | Oct 9 12:00 PM ET | NO | 42 | 11¢ | lost | -4.91 |
| 10-10 | IND | Oct 9 11:00 AM ET | NO | 11 | 40¢ | lost | -4.59 |
| 10-10 | MIA | Oct 9 11:00 AM ET | NO | 15 | 31¢ | won | +10.12 |
| 10-10 | CMH | Oct 9 10:00 AM ET | NO | 7 | 31¢ | lost | -2.28 |
| 10-10 | LV | Oct 9 9:00 AM ET | NO | 7 | 65¢ | lost | -4.67 |
| 10-09 | SEA | Oct 8 7:00 PM ET | NO | 2 | 27¢ | lost | -0.57 |
| 10-09 | MIA | Oct 8 6:00 PM ET | NO | 8 | 60¢ | won | +3.06 |
| 10-09 | CHI | Oct 8 3:00 PM ET | NO | 11 | 43¢ | won | +6.08 |
| 10-09 | NOLA | Oct 8 2:00 PM ET | NO | 11 | 42¢ | won | +6.19 |
| 10-09 | ATL | Oct 8 11:00 AM ET | NO | 9 | 50¢ | lost | -4.66 |
| 10-08 | MIA | Oct 7 3:00 PM ET | NO | 39 | 12¢ | won | +34.03 |
| 10-06 | MIA | Oct 6 12:00 AM ET | NO | 2 | 45¢ | won | +1.06 |
| 10-05 | ATL | Oct 4 9:00 AM ET | NO | 15 | 31¢ | won | +10.12 |
| 10-04 | NYC | Oct 3 8:00 PM ET | NO | 16 | 29¢ | lost | -4.88 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
