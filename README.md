# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$129.20** (started at $100). Updated Nov 9 12:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-10 | HOU | Nov 9 9:00 AM ET | NO | 11 | 42¢ | open | -0.74 |
| 11-10 | SATX | Nov 9 9:00 AM ET | NO | 14 | 33¢ | open | +2.16 |
| 11-09 | MIA | Nov 8 8:00 PM ET | NO | 7 | 63¢ | open | -0.19 |
| 11-09 | HOU | Nov 8 1:00 PM ET | NO | 22 | 21¢ | open | -0.26 |
| 11-09 | CLL | Nov 8 9:00 AM ET | NO | 11 | 41¢ | open | +1.13 |
| 11-08 | DAL | Nov 7 8:00 PM ET | NO | 5 | 48¢ | won | +2.51 |
| 11-08 | MIA | Nov 7 7:00 PM ET | NO | 7 | 64¢ | won | +2.40 |
| 11-08 | HOU | Nov 7 11:00 AM ET | NO | 13 | 35¢ | won | +8.24 |
| 11-07 | SATX | Nov 6 9:00 PM ET | NO | 1 | 9¢ | won | +0.90 |
| 11-07 | WPB | Nov 6 8:00 PM ET | NO | 8 | 56¢ | won | +3.38 |
| 11-07 | CLL | Nov 6 2:00 PM ET | NO | 3 | 55¢ | won | +1.29 |
| 11-06 | ABQ | Nov 5 3:00 PM ET | NO | 3 | 48¢ | lost | -1.50 |
| 11-06 | PIT | Nov 5 12:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |
| 11-05 | MIA | Nov 4 11:00 PM ET | NO | 7 | 61¢ | lost | -4.39 |
| 11-05 | PHIL | Nov 4 11:00 PM ET | NO | 9 | 13¢ | lost | -1.25 |
| 11-05 | SEA | Nov 4 9:00 PM ET | NO | 7 | 66¢ | won | +2.27 |
| 11-05 | TPA | Nov 4 9:00 PM ET | NO | 5 | 56¢ | won | +2.11 |
| 11-05 | BOS | Nov 4 7:00 PM ET | NO | 8 | 56¢ | won | +3.38 |
| 11-05 | OKC | Nov 4 6:00 PM ET | NO | 31 | 15¢ | lost | -4.93 |
| 11-05 | MKE | Nov 4 4:00 PM ET | NO | 13 | 34¢ | lost | -4.63 |
| 11-05 | NYC | Nov 4 3:00 PM ET | NO | 2 | 17¢ | lost | -0.36 |
| 11-05 | PVD | Nov 4 3:00 PM ET | NO | 1 | 51¢ | won | +0.47 |
| 11-05 | EWR | Nov 4 2:00 PM ET | NO | 29 | 16¢ | lost | -4.92 |
| 11-05 | TTN | Nov 4 2:00 PM ET | NO | 19 | 14¢ | lost | -2.83 |
| 11-05 | ATL | Nov 4 1:00 PM ET | NO | 12 | 39¢ | won | +7.12 |
| 11-05 | MIN | Nov 4 9:00 AM ET | NO | 11 | 42¢ | lost | -4.81 |
| 11-04 | NOLA | Nov 3 4:00 PM ET | NO | 10 | 45¢ | won | +5.32 |
| 11-04 | TPA | Nov 3 12:00 PM ET | NO | 9 | 40¢ | won | +5.24 |
| 11-04 | WPB | Nov 3 10:00 AM ET | NO | 4 | 38¢ | won | +2.41 |
| 11-03 | IND | Nov 2 11:00 PM ET | NO | 2 | 60¢ | won | +0.76 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
