# Sandbox arm 2: fixed times

Checks at 8 AM, 2 PM and 8 PM ET the day before the rain day, and at midnight ET as it begins, with one curve per time. The first check that qualifies takes the trade.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-fixed/index.html

Mock account **$99.74** (started at $100). Updated Oct 1 1:23 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-02 | ATL | Oct 1 8:00 AM ET | NO | 1 | 68¢ | open | +0.03 |
| 10-02 | BOS | Oct 1 8:00 AM ET | NO | 6 | 71¢ | open | -1.23 |
| 10-02 | CHI | Oct 1 8:00 AM ET | NO | 6 | 74¢ | open | -0.93 |
| 10-02 | DC | Oct 1 8:00 AM ET | NO | 8 | 60¢ | open | +0.66 |
| 10-02 | EWR | Oct 1 8:00 AM ET | NO | 4 | 65¢ | open | -0.91 |
| 10-01 | DEN | Sep 30 8:00 AM ET | NO | 7 | 65¢ | open | +2.26 |
| 09-30 | AUS | Sep 29 8:00 PM ET | NO | 7 | 64¢ | lost | -4.60 |
| 09-30 | DAL | Sep 29 8:00 PM ET | NO | 9 | 51¢ | lost | -4.75 |
| 09-30 | HOU | Sep 29 8:00 PM ET | NO | 10 | 45¢ | won | +5.32 |
| 09-30 | PHX | Sep 29 8:00 PM ET | NO | 5 | 88¢ | won | +0.56 |
| 09-30 | SATX | Sep 29 8:00 PM ET | NO | 3 | 57¢ | lost | -1.77 |
| 09-30 | CLL | Sep 29 2:00 PM ET | NO | 1 | 60¢ | won | +0.38 |
| 09-30 | MKE | Sep 29 8:00 AM ET | YES | 5 | 88¢ | won | +0.56 |
| 09-30 | NOLA | Sep 29 8:00 AM ET | NO | 5 | 91¢ | won | +0.42 |
| 09-30 | SEA | Sep 29 8:00 AM ET | NO | 5 | 87¢ | won | +0.61 |
| 09-29 | CLL | Sep 29 12:00 AM ET | NO | 4 | 88¢ | won | +0.45 |
| 09-29 | MKE | Sep 29 12:00 AM ET | NO | 5 | 90¢ | won | +0.46 |
| 09-29 | DEN | Sep 28 8:00 PM ET | NO | 9 | 49¢ | won | +4.43 |
| 09-29 | AUS | Sep 28 2:00 PM ET | NO | 5 | 89¢ | won | +0.51 |
| 09-29 | LV | Sep 28 2:00 PM ET | NO | 7 | 61¢ | lost | -4.39 |
| 09-29 | BOS | Sep 28 8:00 AM ET | NO | 2 | 63¢ | won | +0.70 |
| 09-29 | HOU | Sep 28 8:00 AM ET | NO | 1 | 84¢ | won | +0.15 |
| 09-29 | OKC | Sep 28 8:00 AM ET | NO | 6 | 82¢ | won | +1.01 |
| 09-29 | PHX | Sep 28 8:00 AM ET | YES | 5 | 88¢ | won | +0.56 |
| 09-29 | PVD | Sep 28 8:00 AM ET | NO | 5 | 87¢ | won | +0.61 |
| 09-29 | SATX | Sep 28 8:00 AM ET | NO | 6 | 77¢ | won | +1.30 |
| 09-29 | SEA | Sep 28 8:00 AM ET | YES | 5 | 86¢ | won | +0.65 |
| 09-28 | LV | Sep 27 8:00 PM ET | NO | 10 | 46¢ | lost | -4.78 |
| 09-28 | DAL | Sep 27 2:00 PM ET | NO | 1 | 68¢ | won | +0.30 |
| 09-28 | DC | Sep 27 2:00 PM ET | NO | 5 | 84¢ | won | +0.75 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
