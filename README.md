# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$98.93** (started at $100). Updated Nov 1 9:20 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-02 | PIT | Nov 1 9:00 AM ET | NO | 7 | 63¢ | open | -0.05 |
| 11-02 | DAL | Nov 1 9:00 AM ET | NO | 3 | 42¢ | open | -0.12 |
| 11-01 | TPA | Oct 31 11:00 PM ET | NO | 1 | 19¢ | open | -0.02 |
| 11-01 | CHI | Oct 31 6:00 PM ET | NO | 5 | 60¢ | open | -0.09 |
| 11-01 | SFO | Oct 31 2:00 PM ET | NO | 20 | 23¢ | open | -0.25 |
| 11-01 | STL | Oct 31 2:00 PM ET | NO | 11 | 20¢ | open | +6.47 |
| 11-01 | LEX | Oct 31 1:00 PM ET | NO | 4 | 29¢ | open | -0.42 |
| 11-01 | NOLA | Oct 31 1:00 PM ET | NO | 10 | 47¢ | open | -0.18 |
| 11-01 | ATL | Oct 31 11:00 AM ET | NO | 26 | 17¢ | open | -0.26 |
| 11-01 | IND | Oct 31 11:00 AM ET | NO | 9 | 50¢ | open | +0.02 |
| 10-31 | SFO | Oct 30 11:00 PM ET | NO | 6 | 68¢ | open | -0.10 |
| 10-31 | CLL | Oct 30 9:00 PM ET | NO | 11 | 32¢ | lost | -3.69 |
| 10-31 | OKC | Oct 30 9:00 PM ET | NO | 13 | 35¢ | lost | -4.76 |
| 10-31 | NOLA | Oct 30 6:00 PM ET | NO | 6 | 16¢ | lost | -1.02 |
| 10-31 | HOU | Oct 30 5:00 PM ET | NO | 1 | 20¢ | lost | -0.22 |
| 10-31 | TPA | Oct 30 5:00 PM ET | NO | 1 | 56¢ | lost | -0.58 |
| 10-31 | ABQ | Oct 30 4:00 PM ET | NO | 5 | 50¢ | won | +2.41 |
| 10-31 | PHX | Oct 30 3:00 PM ET | NO | 2 | 13¢ | lost | -0.28 |
| 10-31 | SATX | Oct 30 2:00 PM ET | NO | 2 | 59¢ | won | +0.78 |
| 10-31 | SGF | Oct 30 2:00 PM ET | NO | 2 | 23¢ | lost | -0.49 |
| 10-31 | MKE | Oct 30 12:00 PM ET | NO | 26 | 18¢ | lost | -4.95 |
| 10-31 | AUS | Oct 30 11:00 AM ET | NO | 1 | 56¢ | lost | -0.58 |
| 10-31 | CHI | Oct 30 10:00 AM ET | NO | 9 | 24¢ | lost | -2.28 |
| 10-31 | LV | Oct 30 10:00 AM ET | NO | 11 | 43¢ | open | -0.19 |
| 10-31 | DAL | Oct 30 9:00 AM ET | NO | 10 | 47¢ | won | +5.12 |
| 10-31 | WPB | Oct 30 9:00 AM ET | NO | 4 | 28¢ | won | +2.82 |
| 10-30 | OKC | Oct 30 12:00 AM ET | NO | 20 | 23¢ | lost | -4.85 |
| 10-30 | MIA | Oct 29 8:00 PM ET | NO | 13 | 35¢ | won | +8.24 |
| 10-30 | DAL | Oct 29 7:00 PM ET | NO | 13 | 36¢ | lost | -4.89 |
| 10-30 | WPB | Oct 29 5:00 PM ET | NO | 2 | 20¢ | lost | -0.43 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
