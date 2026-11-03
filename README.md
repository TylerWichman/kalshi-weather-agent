# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$92.24** (started at $100). Updated Nov 3 7:40 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-03 | IND | Nov 2 11:00 PM ET | NO | 2 | 60¢ | open | +0.60 |
| 11-03 | TPA | Nov 2 10:00 PM ET | NO | 1 | 30¢ | open | -0.20 |
| 11-03 | DEN | Nov 2 12:00 PM ET | NO | 8 | 59¢ | open | +2.26 |
| 11-02 | NOLA | Nov 1 9:00 PM ET | NO | 7 | 63¢ | open | -0.12 |
| 11-02 | SGF | Nov 1 9:00 PM ET | NO | 4 | 64¢ | open | -0.07 |
| 11-02 | CMH | Nov 1 4:00 PM ET | NO | 9 | 51¢ | lost | -4.75 |
| 11-02 | CHI | Nov 1 1:00 PM ET | NO | 11 | 39¢ | open | -0.19 |
| 11-02 | DAL | Nov 1 9:00 AM ET | NO | 3 | 42¢ | open | -0.06 |
| 11-02 | PIT | Nov 1 9:00 AM ET | NO | 7 | 63¢ | won | +2.47 |
| 11-01 | TPA | Oct 31 11:00 PM ET | NO | 1 | 19¢ | lost | -0.21 |
| 11-01 | CHI | Oct 31 6:00 PM ET | NO | 5 | 60¢ | lost | -3.09 |
| 11-01 | SFO | Oct 31 2:00 PM ET | NO | 20 | 23¢ | lost | -4.85 |
| 11-01 | STL | Oct 31 2:00 PM ET | NO | 11 | 20¢ | won | +8.67 |
| 11-01 | LEX | Oct 31 1:00 PM ET | NO | 4 | 29¢ | lost | -1.22 |
| 11-01 | NOLA | Oct 31 1:00 PM ET | NO | 10 | 47¢ | lost | -4.88 |
| 11-01 | ATL | Oct 31 11:00 AM ET | NO | 26 | 17¢ | lost | -4.68 |
| 11-01 | IND | Oct 31 11:00 AM ET | NO | 9 | 50¢ | won | +4.34 |
| 10-31 | SFO | Oct 30 11:00 PM ET | NO | 6 | 68¢ | lost | -4.18 |
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

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
