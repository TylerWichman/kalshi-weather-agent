# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$124.07** (started at $100). Updated Oct 15 12:28 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-15 | PIT | Oct 14 8:00 PM ET | NO | 8 | 55¢ | open | +0.10 |
| 10-15 | DC | Oct 14 7:00 PM ET | NO | 9 | 8¢ | open | +0.49 |
| 10-15 | LEX | Oct 14 3:00 PM ET | NO | 12 | 21¢ | open | -0.62 |
| 10-15 | DAL | Oct 14 1:00 PM ET | NO | 7 | 65¢ | open | -1.94 |
| 10-15 | PHIL | Oct 14 1:00 PM ET | NO | 3 | 51¢ | open | +0.75 |
| 10-15 | IND | Oct 14 11:00 AM ET | NO | 36 | 13¢ | open | -2.45 |
| 10-15 | MIA | Oct 14 11:00 AM ET | NO | 6 | 44¢ | open | +0.31 |
| 10-15 | CMH | Oct 14 9:00 AM ET | NO | 7 | 29¢ | open | +0.73 |
| 10-14 | PHIL | Oct 13 11:00 PM ET | NO | 7 | 61¢ | open | -0.12 |
| 10-14 | CLL | Oct 13 9:00 PM ET | NO | 2 | 52¢ | open | -0.04 |
| 10-14 | MIA | Oct 13 9:00 PM ET | NO | 1 | 67¢ | open | -0.02 |
| 10-14 | DET | Oct 13 10:00 AM ET | NO | 13 | 35¢ | open | +8.11 |
| 10-14 | AUS | Oct 13 9:00 AM ET | NO | 1 | 49¢ | open | +0.48 |
| 10-13 | PHX | Oct 12 6:00 PM ET | NO | 3 | 54¢ | lost | -1.68 |
| 10-13 | PVD | Oct 12 3:00 PM ET | NO | 2 | 57¢ | lost | -1.18 |
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

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
