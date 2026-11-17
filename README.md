# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$131.83** (started at $100). Updated Nov 17 5:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-18 | SEA | Nov 17 3:00 PM ET | NO | 1 | 30¢ | open | +0.01 |
| 11-17 | ABQ | Nov 16 9:00 PM ET | NO | 11 | 42¢ | open | -1.18 |
| 11-17 | LV | Nov 16 4:00 PM ET | NO | 2 | 27¢ | open | +1.41 |
| 11-17 | SAN | Nov 16 1:00 PM ET | NO | 7 | 63¢ | open | +2.40 |
| 11-16 | LAX | Nov 15 11:00 PM ET | NO | 18 | 26¢ | won | +13.07 |
| 11-16 | SEA | Nov 15 9:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 11-16 | CLL | Nov 15 7:00 PM ET | NO | 7 | 63¢ | lost | -4.53 |
| 11-16 | DAL | Nov 15 4:00 PM ET | NO | 8 | 60¢ | won | +3.06 |
| 11-16 | LV | Nov 15 4:00 PM ET | NO | 8 | 60¢ | lost | -4.94 |
| 11-16 | HOU | Nov 15 2:00 PM ET | NO | 17 | 28¢ | lost | -5.00 |
| 11-16 | NOLA | Nov 15 2:00 PM ET | NO | 14 | 17¢ | lost | -2.52 |
| 11-15 | NOLA | Nov 14 9:00 PM ET | NO | 2 | 51¢ | lost | -1.06 |
| 11-15 | PIT | Nov 14 9:00 PM ET | NO | 14 | 20¢ | lost | -2.96 |
| 11-14 | SFO | Nov 13 10:00 PM ET | NO | 7 | 63¢ | lost | -4.53 |
| 11-14 | LAX | Nov 13 7:00 PM ET | NO | 11 | 35¢ | lost | -4.03 |
| 11-14 | DAL | Nov 13 4:00 PM ET | NO | 36 | 13¢ | lost | -4.97 |
| 11-14 | CLL | Nov 13 2:00 PM ET | NO | 10 | 48¢ | lost | -4.98 |
| 11-14 | OKC | Nov 13 2:00 PM ET | NO | 42 | 11¢ | lost | -4.91 |
| 11-14 | PIT | Nov 13 2:00 PM ET | NO | 8 | 13¢ | won | +6.89 |
| 11-13 | ABQ | Nov 12 11:00 PM ET | NO | 9 | 51¢ | lost | -4.75 |
| 11-13 | DTW | Nov 12 1:00 PM ET | NO | 11 | 41¢ | won | +6.30 |
| 11-13 | CHI | Nov 12 11:00 AM ET | NO | 1 | 43¢ | won | +0.55 |
| 11-12 | DC | Nov 11 9:00 PM ET | NO | 11 | 41¢ | won | +6.30 |
| 11-12 | IND | Nov 11 9:00 PM ET | NO | 8 | 55¢ | lost | -4.54 |
| 11-12 | WPB | Nov 11 9:00 PM ET | NO | 12 | 37¢ | won | +7.36 |
| 11-12 | MKE | Nov 11 7:00 PM ET | NO | 8 | 60¢ | won | +3.06 |
| 11-12 | CHI | Nov 11 4:00 PM ET | NO | 11 | 42¢ | won | +6.19 |
| 11-12 | MIA | Nov 11 11:00 AM ET | NO | 8 | 38¢ | won | +4.82 |
| 11-11 | CMH | Nov 10 11:00 PM ET | NO | 17 | 27¢ | won | +12.17 |
| 11-11 | WPB | Nov 10 11:00 PM ET | NO | 17 | 27¢ | lost | -4.83 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
