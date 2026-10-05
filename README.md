# Sandbox arm 3: move trigger

Watches every hour from 8 AM ET the day before the rain day until midnight ET as it begins. It evaluates a market only after its price has moved 10¢ or more since that market's last evaluation.

**Dashboard:** https://raw.githack.com/TylerWichman/kalshi-weather-agent/sbx-state-trigger/index.html

Mock account **$71.48** (started at $100). Updated Oct 4 11:20 PM ET.

| Rain day | City | Bought | Side | Contracts | Paid | Status | P&L |
|---|---|--:|---|--:|--:|---|--:|
| 10-05 | ATL | Oct 4 9:00 AM ET | NO | 15 | 31¢ | open | +5.92 |
| 10-04 | NYC | Oct 3 8:00 PM ET | NO | 16 | 29¢ | open | -0.24 |
| 10-04 | PVD | Oct 3 8:00 PM ET | NO | 8 | 57¢ | open | -0.14 |
| 10-04 | DC | Oct 3 6:00 PM ET | NO | 4 | 28¢ | open | -0.06 |
| 10-04 | DAL | Oct 3 5:00 PM ET | NO | 2 | 45¢ | open | -0.04 |
| 10-04 | AUS | Oct 3 3:00 PM ET | NO | 9 | 52¢ | open | -0.16 |
| 10-04 | CLL | Oct 3 3:00 PM ET | NO | 1 | 49¢ | open | -0.02 |
| 10-04 | HOU | Oct 3 1:00 PM ET | NO | 10 | 47¢ | open | -0.18 |
| 10-03 | MIA | Oct 2 10:00 PM ET | NO | 14 | 34¢ | won | +9.02 |
| 10-03 | CLL | Oct 2 6:00 PM ET | NO | 6 | 42¢ | lost | -2.63 |
| 10-03 | AUS | Oct 2 2:00 PM ET | NO | 33 | 14¢ | won | +28.10 |
| 10-03 | DC | Oct 2 2:00 PM ET | NO | 1 | 22¢ | lost | -0.24 |
| 10-03 | SATX | Oct 2 1:00 PM ET | NO | 4 | 24¢ | won | +2.98 |
| 10-03 | MIN | Oct 2 12:00 PM ET | NO | 12 | 39¢ | lost | -4.88 |
| 10-02 | TTN | Oct 2 12:00 AM ET | NO | 1 | 45¢ | lost | -0.47 |
| 10-02 | NYC | Oct 1 10:00 PM ET | NO | 1 | 38¢ | won | +0.60 |
| 10-02 | ATL | Oct 1 9:00 PM ET | NO | 7 | 68¢ | won | +2.13 |
| 10-02 | DC | Oct 1 6:00 PM ET | NO | 8 | 60¢ | lost | -4.94 |
| 10-02 | PHIL | Oct 1 5:00 PM ET | NO | 8 | 60¢ | lost | -4.94 |
| 10-02 | CHI | Oct 1 2:00 PM ET | NO | 8 | 55¢ | won | +3.46 |
| 10-02 | OKC | Oct 1 2:00 PM ET | NO | 1 | 58¢ | lost | -0.60 |
| 10-02 | EWR | Oct 1 1:00 PM ET | NO | 6 | 52¢ | lost | -3.23 |
| 10-02 | MIA | Oct 1 1:00 PM ET | NO | 36 | 13¢ | lost | -4.97 |
| 10-02 | BOS | Oct 1 11:00 AM ET | NO | 8 | 59¢ | won | +3.14 |
| 10-02 | PIT | Oct 1 11:00 AM ET | NO | 36 | 13¢ | lost | -4.97 |
| 10-02 | PVD | Oct 1 11:00 AM ET | NO | 6 | 52¢ | lost | -3.23 |
| 10-01 | NOLA | Sep 30 6:00 PM ET | NO | 14 | 32¢ | lost | -4.70 |
| 09-30 | DAL | Sep 29 7:00 PM ET | NO | 12 | 37¢ | lost | -4.64 |
| 09-30 | DEN | Sep 29 7:00 PM ET | NO | 24 | 19¢ | lost | -4.82 |
| 09-30 | HOU | Sep 29 4:00 PM ET | NO | 1 | 38¢ | won | +0.60 |

Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; not Gate 2.
