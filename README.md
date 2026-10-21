# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$94.95** (started at $100). Updated Oct 20 10:41 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-21 | LV | Oct 20 9:00 PM ET | NO | 7 | 61¢ | open | -1.03 |
| 10-21 | ABQ | Oct 20 8:00 PM ET | NO | 3 | 62¢ | open | +0.10 |
| 10-21 | WPB | Oct 20 8:00 PM ET | NO | 9 | 50¢ | open | +0.65 |
| 10-21 | SFO | Oct 20 3:00 PM ET | NO | 4 | 32¢ | open | -0.07 |
| 10-21 | PHX | Oct 20 1:00 PM ET | NO | 14 | 30¢ | open | -1.75 |
| 10-20 | WPB | Oct 20 12:00 AM ET | NO | 10 | 47¢ | open | -0.18 |
| 10-20 | ABQ | Oct 19 11:00 PM ET | NO | 7 | 66¢ | open | -0.11 |
| 10-20 | MIA | Oct 19 6:00 PM ET | NO | 8 | 55¢ | open | -0.14 |
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
| 10-16 | DTW | Oct 15 2:00 PM ET | NO | 10 | 17¢ | lost | -1.80 |
| 10-16 | DAL | Oct 15 1:00 PM ET | NO | 10 | 45¢ | won | +5.32 |
| 10-16 | MIA | Oct 15 1:00 PM ET | NO | 12 | 39¢ | lost | -4.88 |
| 10-16 | CHI | Oct 15 12:00 PM ET | NO | 7 | 45¢ | lost | -3.28 |
| 10-16 | TPA | Oct 15 12:00 PM ET | NO | 1 | 40¢ | won | +0.58 |
| 10-16 | MKE | Oct 15 10:00 AM ET | NO | 6 | 24¢ | lost | -1.52 |
| 10-15 | PIT | Oct 14 8:00 PM ET | NO | 8 | 55¢ | won | +3.46 |
| 10-15 | DC | Oct 14 7:00 PM ET | NO | 9 | 8¢ | lost | -0.77 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
