# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$143.25** (started at $100). Updated Oct 31 1:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-01 | NOLA | Oct 31 1:00 PM ET | NO | 10 | 47¢ | open | -0.48 |
| 11-01 | LEX | Oct 31 1:00 PM ET | NO | 4 | 29¢ | open | -0.10 |
| 11-01 | ATL | Oct 31 11:00 AM ET | NO | 26 | 17¢ | open | -0.52 |
| 11-01 | IND | Oct 31 11:00 AM ET | NO | 9 | 50¢ | open | -0.70 |
| 10-31 | SFO | Oct 30 11:00 PM ET | NO | 6 | 68¢ | open | +0.38 |
| 10-31 | CLL | Oct 30 9:00 PM ET | NO | 11 | 32¢ | open | -0.17 |
| 10-31 | OKC | Oct 30 9:00 PM ET | NO | 13 | 35¢ | open | +4.21 |
| 10-31 | NOLA | Oct 30 6:00 PM ET | NO | 6 | 16¢ | open | -0.06 |
| 10-31 | HOU | Oct 30 5:00 PM ET | NO | 1 | 20¢ | open | +0.38 |
| 10-31 | TPA | Oct 30 5:00 PM ET | NO | 1 | 56¢ | open | -0.02 |
| 10-31 | ABQ | Oct 30 4:00 PM ET | NO | 5 | 50¢ | open | +1.46 |
| 10-31 | PHX | Oct 30 3:00 PM ET | NO | 2 | 13¢ | open | -0.02 |
| 10-31 | SATX | Oct 30 2:00 PM ET | NO | 2 | 59¢ | open | +0.58 |
| 10-31 | SGF | Oct 30 2:00 PM ET | NO | 2 | 23¢ | open | -0.35 |
| 10-31 | MKE | Oct 30 12:00 PM ET | NO | 26 | 18¢ | open | +16.89 |
| 10-31 | AUS | Oct 30 11:00 AM ET | NO | 1 | 56¢ | open | -0.02 |
| 10-31 | CHI | Oct 30 10:00 AM ET | NO | 9 | 24¢ | open | -0.12 |
| 10-31 | LV | Oct 30 10:00 AM ET | NO | 11 | 43¢ | open | -3.05 |
| 10-31 | DAL | Oct 30 9:00 AM ET | NO | 10 | 47¢ | open | +4.72 |
| 10-31 | WPB | Oct 30 9:00 AM ET | NO | 4 | 28¢ | open | +0.70 |
| 10-30 | OKC | Oct 30 12:00 AM ET | NO | 20 | 23¢ | lost | -4.85 |
| 10-30 | MIA | Oct 29 8:00 PM ET | NO | 13 | 35¢ | won | +8.24 |
| 10-30 | DAL | Oct 29 7:00 PM ET | NO | 13 | 36¢ | lost | -4.89 |
| 10-30 | WPB | Oct 29 5:00 PM ET | NO | 2 | 20¢ | lost | -0.43 |
| 10-30 | HOU | Oct 29 1:00 PM ET | NO | 10 | 45¢ | lost | -4.68 |
| 10-30 | ABQ | Oct 29 11:00 AM ET | NO | 2 | 44¢ | lost | -0.92 |
| 10-30 | LAX | Oct 29 11:00 AM ET | NO | 10 | 47¢ | won | +5.12 |
| 10-30 | LV | Oct 29 10:00 AM ET | NO | 2 | 54¢ | lost | -1.12 |
| 10-30 | CLL | Oct 29 9:00 AM ET | NO | 3 | 34¢ | lost | -1.07 |
| 10-29 | MIA | Oct 29 12:00 AM ET | NO | 4 | 51¢ | won | +1.89 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
