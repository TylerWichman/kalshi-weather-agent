# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$118.25** (started at $100). Updated Oct 30 5:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-31 | HOU | Oct 30 5:00 PM ET | NO | 1 | 20¢ | open | -0.04 |
| 10-31 | TPA | Oct 30 5:00 PM ET | NO | 1 | 56¢ | open | +0.07 |
| 10-31 | ABQ | Oct 30 4:00 PM ET | NO | 5 | 50¢ | open | -1.34 |
| 10-31 | PHX | Oct 30 3:00 PM ET | NO | 2 | 13¢ | open | +0.02 |
| 10-31 | SATX | Oct 30 2:00 PM ET | NO | 2 | 59¢ | open | +0.28 |
| 10-31 | SGF | Oct 30 2:00 PM ET | NO | 2 | 23¢ | open | -0.01 |
| 10-31 | MKE | Oct 30 12:00 PM ET | NO | 26 | 18¢ | open | +2.33 |
| 10-31 | AUS | Oct 30 11:00 AM ET | NO | 1 | 56¢ | open | +0.16 |
| 10-31 | CHI | Oct 30 10:00 AM ET | NO | 9 | 24¢ | open | -0.84 |
| 10-31 | LV | Oct 30 10:00 AM ET | NO | 11 | 43¢ | open | -2.39 |
| 10-31 | DAL | Oct 30 9:00 AM ET | NO | 10 | 47¢ | open | -2.08 |
| 10-31 | WPB | Oct 30 9:00 AM ET | NO | 4 | 28¢ | open | -0.50 |
| 10-30 | OKC | Oct 30 12:00 AM ET | NO | 20 | 23¢ | open | -0.25 |
| 10-30 | MIA | Oct 29 8:00 PM ET | NO | 13 | 35¢ | open | +3.69 |
| 10-30 | DAL | Oct 29 7:00 PM ET | NO | 13 | 36¢ | open | -0.21 |
| 10-30 | WPB | Oct 29 5:00 PM ET | NO | 2 | 20¢ | open | -0.03 |
| 10-30 | HOU | Oct 29 1:00 PM ET | NO | 10 | 45¢ | open | -4.58 |
| 10-30 | ABQ | Oct 29 11:00 AM ET | NO | 2 | 44¢ | open | -0.14 |
| 10-30 | LAX | Oct 29 11:00 AM ET | NO | 10 | 47¢ | open | +3.82 |
| 10-30 | LV | Oct 29 10:00 AM ET | NO | 2 | 54¢ | open | -0.04 |
| 10-30 | CLL | Oct 29 9:00 AM ET | NO | 3 | 34¢ | open | -0.05 |
| 10-29 | MIA | Oct 29 12:00 AM ET | NO | 4 | 51¢ | won | +1.89 |
| 10-29 | SATX | Oct 28 10:00 PM ET | NO | 22 | 13¢ | lost | -3.04 |
| 10-29 | MKE | Oct 28 6:00 PM ET | NO | 2 | 50¢ | lost | -1.04 |
| 10-29 | WPB | Oct 28 4:00 PM ET | NO | 1 | 51¢ | lost | -0.53 |
| 10-29 | DAL | Oct 28 11:00 AM ET | NO | 1 | 57¢ | won | +0.41 |
| 10-29 | AUS | Oct 28 9:00 AM ET | NO | 3 | 48¢ | lost | -1.50 |
| 10-29 | DTW | Oct 28 9:00 AM ET | NO | 2 | 37¢ | lost | -0.78 |
| 10-28 | HOU | Oct 27 4:00 PM ET | NO | 7 | 65¢ | won | +2.33 |
| 10-28 | MIA | Oct 27 1:00 PM ET | NO | 7 | 28¢ | lost | -2.06 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
