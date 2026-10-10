# Sandbox arm 2: fixed times

Checks at 8 AM, 2 PM and 8 PM ET the day before the rain day, and at midnight ET as it begins, with one curve per time. The first check that qualifies takes the trade.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-fixed/index.html

Mock account **$74.52** (started at $100). Updated Oct 10 8:00 AM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-11 | ABQ | Oct 10 8:00 AM ET | NO | 5 | 84¢ | open | -0.10 |
| 10-11 | ATL | Oct 10 8:00 AM ET | NO | 7 | 67¢ | open | -0.25 |
| 10-11 | BOS | Oct 10 8:00 AM ET | YES | 5 | 88¢ | open | -0.09 |
| 10-11 | IND | Oct 10 8:00 AM ET | NO | 1 | 62¢ | open | -0.03 |
| 10-11 | LAX | Oct 10 8:00 AM ET | YES | 5 | 85¢ | open | -0.10 |
| 10-11 | MIA | Oct 10 8:00 AM ET | NO | 7 | 68¢ | open | -0.39 |
| 10-11 | PHX | Oct 10 8:00 AM ET | YES | 5 | 88¢ | open | -0.14 |
| 10-10 | MIA | Oct 10 12:00 AM ET | NO | 10 | 46¢ | open | +2.42 |
| 10-10 | IND | Oct 9 8:00 PM ET | NO | 11 | 43¢ | open | -1.07 |
| 10-10 | PIT | Oct 9 8:00 PM ET | NO | 5 | 83¢ | open | -0.95 |
| 10-10 | CMH | Oct 9 2:00 PM ET | NO | 4 | 86¢ | open | -2.56 |
| 10-10 | ABQ | Oct 9 8:00 AM ET | NO | 5 | 91¢ | open | -0.23 |
| 10-10 | DC | Oct 9 8:00 AM ET | NO | 5 | 86¢ | open | -0.85 |
| 10-10 | LAX | Oct 9 8:00 AM ET | NO | 6 | 77¢ | open | -0.44 |
| 10-10 | LV | Oct 9 8:00 AM ET | NO | 6 | 79¢ | open | -1.69 |
| 10-10 | NOLA | Oct 9 8:00 AM ET | NO | 6 | 70¢ | open | +1.41 |
| 10-10 | SEA | Oct 9 8:00 AM ET | NO | 5 | 86¢ | open | -0.05 |
| 10-09 | MIA | Oct 8 8:00 PM ET | NO | 8 | 57¢ | won | +3.30 |
| 10-09 | NOLA | Oct 8 8:00 PM ET | NO | 4 | 65¢ | open | -0.07 |
| 10-09 | ATL | Oct 8 8:00 AM ET | NO | 6 | 73¢ | lost | -4.47 |
| 10-09 | CHI | Oct 8 8:00 AM ET | NO | 6 | 65¢ | open | -0.10 |
| 10-09 | HOU | Oct 8 8:00 AM ET | NO | 5 | 93¢ | open | -0.03 |
| 10-09 | MKE | Oct 8 8:00 AM ET | NO | 1 | 80¢ | open | -0.02 |
| 10-09 | SEA | Oct 8 8:00 AM ET | YES | 1 | 86¢ | open | -0.01 |
| 10-08 | PVD | Oct 7 8:00 PM ET | NO | 5 | 90¢ | won | +0.46 |
| 10-08 | BOS | Oct 7 8:00 AM ET | NO | 5 | 83¢ | won | +0.80 |
| 10-08 | NOLA | Oct 7 8:00 AM ET | NO | 5 | 93¢ | won | +0.32 |
| 10-07 | HOU | Oct 6 8:00 AM ET | NO | 5 | 92¢ | won | +0.37 |
| 10-06 | MIA | Oct 6 12:00 AM ET | NO | 2 | 45¢ | won | +1.06 |
| 10-06 | HOU | Oct 5 8:00 AM ET | NO | 5 | 92¢ | won | +0.37 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
