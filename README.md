# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$129.01** (started at $100). Updated Nov 12 5:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-13 | DTW | Nov 12 1:00 PM ET | NO | 11 | 41¢ | open | -0.08 |
| 11-13 | CHI | Nov 12 11:00 AM ET | NO | 1 | 43¢ | open | +0.08 |
| 11-12 | DC | Nov 11 9:00 PM ET | NO | 11 | 41¢ | open | -4.48 |
| 11-12 | IND | Nov 11 9:00 PM ET | NO | 8 | 55¢ | open | -0.14 |
| 11-12 | WPB | Nov 11 9:00 PM ET | NO | 12 | 37¢ | open | +7.00 |
| 11-12 | MKE | Nov 11 7:00 PM ET | NO | 8 | 60¢ | open | +2.50 |
| 11-12 | CHI | Nov 11 4:00 PM ET | NO | 11 | 42¢ | open | +1.35 |
| 11-12 | MIA | Nov 11 11:00 AM ET | NO | 8 | 38¢ | open | +4.34 |
| 11-11 | CMH | Nov 10 11:00 PM ET | NO | 17 | 27¢ | won | +12.17 |
| 11-11 | WPB | Nov 10 11:00 PM ET | NO | 17 | 27¢ | lost | -4.83 |
| 11-11 | HOU | Nov 10 10:00 PM ET | NO | 58 | 8¢ | lost | -4.94 |
| 11-11 | DTW | Nov 10 4:00 PM ET | NO | 7 | 62¢ | won | +2.54 |
| 11-11 | CHI | Nov 10 1:00 PM ET | NO | 14 | 34¢ | lost | -4.98 |
| 11-11 | MKE | Nov 10 1:00 PM ET | NO | 8 | 55¢ | won | +3.46 |
| 11-11 | MIA | Nov 10 8:00 AM ET | NO | 7 | 61¢ | won | +2.61 |
| 11-10 | AUS | Nov 9 5:00 PM ET | NO | 8 | 56¢ | lost | -4.62 |
| 11-10 | DAL | Nov 9 2:00 PM ET | NO | 7 | 63¢ | lost | -4.53 |
| 11-10 | HOU | Nov 9 9:00 AM ET | NO | 11 | 42¢ | lost | -4.81 |
| 11-10 | SATX | Nov 9 9:00 AM ET | NO | 14 | 33¢ | lost | -4.84 |
| 11-09 | MIA | Nov 8 8:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 11-09 | HOU | Nov 8 1:00 PM ET | NO | 22 | 21¢ | lost | -4.88 |
| 11-09 | CLL | Nov 8 9:00 AM ET | NO | 11 | 41¢ | won | +6.30 |
| 11-08 | DAL | Nov 7 8:00 PM ET | NO | 5 | 48¢ | won | +2.51 |
| 11-08 | MIA | Nov 7 7:00 PM ET | NO | 7 | 64¢ | won | +2.40 |
| 11-08 | HOU | Nov 7 11:00 AM ET | NO | 13 | 35¢ | won | +8.24 |
| 11-07 | SATX | Nov 6 9:00 PM ET | NO | 1 | 9¢ | won | +0.90 |
| 11-07 | WPB | Nov 6 8:00 PM ET | NO | 8 | 56¢ | won | +3.38 |
| 11-07 | CLL | Nov 6 2:00 PM ET | NO | 3 | 55¢ | won | +1.29 |
| 11-06 | ABQ | Nov 5 3:00 PM ET | NO | 3 | 48¢ | lost | -1.50 |
| 11-06 | PIT | Nov 5 12:00 PM ET | NO | 8 | 59¢ | lost | -4.86 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
