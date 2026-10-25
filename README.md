# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$119.45** (started at $100). Updated Oct 25 1:00 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-26 | DEN | Oct 25 10:00 AM ET | NO | 7 | 50¢ | open | -0.06 |
| 10-26 | MIA | Oct 25 10:00 AM ET | NO | 19 | 24¢ | open | -3.29 |
| 10-26 | SEA | Oct 25 10:00 AM ET | NO | 3 | 29¢ | open | -0.17 |
| 10-25 | MIN | Oct 24 8:00 PM ET | NO | 1 | 21¢ | open | -0.02 |
| 10-25 | ABQ | Oct 24 2:00 PM ET | NO | 4 | 44¢ | open | +0.25 |
| 10-25 | DEN | Oct 24 10:00 AM ET | NO | 7 | 50¢ | open | +1.41 |
| 10-24 | MIA | Oct 23 10:00 PM ET | NO | 4 | 58¢ | won | +1.61 |
| 10-24 | DEN | Oct 23 1:00 PM ET | NO | 6 | 42¢ | won | +3.37 |
| 10-23 | ABQ | Oct 22 11:00 PM ET | NO | 1 | 14¢ | lost | -0.15 |
| 10-23 | MIN | Oct 22 10:00 PM ET | NO | 9 | 53¢ | won | +4.07 |
| 10-23 | WPB | Oct 22 5:00 PM ET | NO | 1 | 36¢ | lost | -0.38 |
| 10-23 | MIA | Oct 22 3:00 PM ET | NO | 3 | 32¢ | lost | -1.01 |
| 10-22 | MIA | Oct 21 8:00 PM ET | NO | 10 | 46¢ | won | +5.22 |
| 10-22 | LV | Oct 21 5:00 PM ET | NO | 3 | 34¢ | won | +1.93 |
| 10-22 | DEN | Oct 21 4:00 PM ET | NO | 7 | 63¢ | won | +2.47 |
| 10-22 | PHX | Oct 21 1:00 PM ET | NO | 1 | 26¢ | won | +0.72 |
| 10-22 | WPB | Oct 21 11:00 AM ET | NO | 12 | 37¢ | lost | -4.64 |
| 10-21 | LV | Oct 20 9:00 PM ET | NO | 7 | 61¢ | won | +2.61 |
| 10-21 | ABQ | Oct 20 8:00 PM ET | NO | 3 | 62¢ | won | +1.09 |
| 10-21 | WPB | Oct 20 8:00 PM ET | NO | 9 | 50¢ | lost | -4.66 |
| 10-21 | SFO | Oct 20 3:00 PM ET | NO | 4 | 32¢ | won | +2.65 |
| 10-21 | PHX | Oct 20 1:00 PM ET | NO | 14 | 30¢ | won | +9.59 |
| 10-20 | WPB | Oct 20 12:00 AM ET | NO | 10 | 47¢ | lost | -4.88 |
| 10-20 | ABQ | Oct 19 11:00 PM ET | NO | 7 | 66¢ | lost | -4.73 |
| 10-20 | MIA | Oct 19 6:00 PM ET | NO | 8 | 55¢ | lost | -4.54 |
| 10-19 | MIA | Oct 18 10:00 PM ET | NO | 10 | 47¢ | won | +5.12 |
| 10-19 | ABQ | Oct 18 7:00 PM ET | NO | 8 | 57¢ | won | +3.30 |
| 10-18 | WPB | Oct 17 3:00 PM ET | NO | 23 | 20¢ | won | +18.14 |
| 10-17 | LEX | Oct 16 10:00 PM ET | NO | 6 | 60¢ | lost | -3.71 |
| 10-17 | PVD | Oct 16 10:00 PM ET | NO | 23 | 20¢ | lost | -4.86 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
