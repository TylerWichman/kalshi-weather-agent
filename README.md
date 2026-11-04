# Sandbox arm 3: move trigger

Watches every hour from 7 AM ET the day before the rain day until 11 PM ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$127.95** (started at $100). Updated Nov 4 5:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 11-05 | MKE | Nov 4 4:00 PM ET | NO | 13 | 34¢ | open | -0.47 |
| 11-05 | NYC | Nov 4 3:00 PM ET | NO | 2 | 17¢ | open | +0.02 |
| 11-05 | PVD | Nov 4 3:00 PM ET | NO | 1 | 51¢ | open | -0.02 |
| 11-05 | EWR | Nov 4 2:00 PM ET | NO | 29 | 16¢ | open | +1.17 |
| 11-05 | TTN | Nov 4 2:00 PM ET | NO | 19 | 14¢ | open | -0.55 |
| 11-05 | ATL | Nov 4 1:00 PM ET | NO | 12 | 39¢ | open | -1.16 |
| 11-05 | MIN | Nov 4 9:00 AM ET | NO | 11 | 42¢ | open | -0.74 |
| 11-04 | NOLA | Nov 3 4:00 PM ET | NO | 10 | 45¢ | open | +5.22 |
| 11-04 | TPA | Nov 3 12:00 PM ET | NO | 9 | 40¢ | open | +3.35 |
| 11-04 | WPB | Nov 3 10:00 AM ET | NO | 4 | 38¢ | open | +1.97 |
| 11-03 | IND | Nov 2 11:00 PM ET | NO | 2 | 60¢ | won | +0.76 |
| 11-03 | TPA | Nov 2 10:00 PM ET | NO | 1 | 30¢ | won | +0.68 |
| 11-03 | DEN | Nov 2 12:00 PM ET | NO | 8 | 59¢ | won | +3.14 |
| 11-02 | NOLA | Nov 1 9:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 11-02 | SGF | Nov 1 9:00 PM ET | NO | 4 | 64¢ | won | +1.37 |
| 11-02 | CMH | Nov 1 4:00 PM ET | NO | 9 | 51¢ | lost | -4.75 |
| 11-02 | CHI | Nov 1 1:00 PM ET | NO | 11 | 39¢ | won | +6.52 |
| 11-02 | DAL | Nov 1 9:00 AM ET | NO | 3 | 42¢ | won | +1.68 |
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

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
