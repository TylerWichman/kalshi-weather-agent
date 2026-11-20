# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$122.58** (started at $100). Updated Nov 20 2:03 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-20 | TPA | Nov 19 2:00 PM ET | NO | 19 | 25¢ | open | +1.08 |
| 11-20 | WPB | Nov 19 10:00 AM ET | NO | 16 | 29¢ | open | +7.60 |
| 11-19 | TPA | Nov 18 3:00 PM ET | NO | 10 | 35¢ | open | -0.16 |
| 11-19 | LV | Nov 18 1:00 PM ET | NO | 10 | 19¢ | open | -0.11 |
| 11-18 | TPA | Nov 17 10:00 PM ET | NO | 23 | 20¢ | lost | -4.86 |
| 11-18 | ABQ | Nov 17 8:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 11-18 | SEA | Nov 17 3:00 PM ET | NO | 1 | 30¢ | won | +0.68 |
| 11-17 | ABQ | Nov 16 9:00 PM ET | NO | 11 | 42¢ | lost | -4.81 |
| 11-17 | LV | Nov 16 4:00 PM ET | NO | 2 | 27¢ | won | +1.43 |
| 11-17 | SAN | Nov 16 1:00 PM ET | NO | 7 | 63¢ | open | -0.12 |
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

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
