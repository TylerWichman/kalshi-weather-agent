# Running the KXRAIN collectors on a Windows cloud server

> **Superseded (2026-09-24):** AWS requires a card even on the Free plan, so collection
> runs on GitHub Actions instead. See `docs/github-actions.md`. Kept for reference.

**Why:** Gate 2 needs a KXRAIN order-book snapshot in the 10 minutes before 00:00 UTC
on each of 45 days (through 2026-11-10). A cloud server is always on, never sleeps, and
restarts itself after Windows updates. The laptop can then be used or switched off
freely.

**Cost: $0 out of pocket, if the steps below are followed.**

- A new AWS account on the **Free plan** gets $100 in credits, up to $200 with AWS's
  onboarding tasks. A Free-plan account **cannot be billed**: when the credits run out
  or 6 months pass, AWS closes it instead of charging.
- A Lightsail Windows server is **$14/month** (the 2 GB plan; prices as of September 2026). About **$25 of credit** covers
  the test.
- Lightsail's older "3 months free" trial no longer exists; the credits replaced it.

**Hard deadline:** have the server collecting before **Saturday 2026-09-26, 7:50 PM
Eastern** (23:50 UTC), the first test decision window. The laptop keeps collecting
until the server is confirmed, so nothing is lost if this slips.

---

## 1. Create the AWS account (about 10 min)

1. Go to <https://aws.amazon.com/free> and choose **Create a Free Account**.
2. When asked to choose a plan, pick **Free plan**, not Paid. This is what guarantees
   no charges.
3. AWS asks for a card and a phone number to verify identity. The Free plan does not
   charge it.

## 2. Create the server (about 5 min, then about 5 min for it to boot)

1. Open <https://lightsail.aws.amazon.com> and click **Create instance**.
2. **Region:** pick one near you, e.g. *Virginia (us-east-1)*.
3. **Platform:** *Microsoft Windows*. **Blueprint:** *OS Only* → **Windows Server 2022**.
4. **Network type:** *Dual-stack* (IPv4 + IPv6). Do not choose IPv6-only: Remote Desktop
   and Kalshi's API need IPv4.
5. **Plan:** the **$14/month** plan. Check that the plan card says **2 GB** of memory. The
   $9.50 plan also works, but Remote Desktop is sluggish on it; the credits cover either.
6. **Name:** `kalshi-collector`. Click **Create instance**.
7. **Lock down Remote Desktop:** open the instance → **Networking** → under IPv4
   firewall, edit the **RDP** rule → tick **Restrict to IP address** → choose your
   current IP. Do the same for IPv6 (or delete the IPv6 RDP rule). Only your home
   connection can then reach the login screen.

## 3. Connect with Remote Desktop

1. On the instance page, **Connect** tab → **Retrieve default password**, and copy it.
   Use the **public IPv4 address** shown there.
2. On the laptop, open **Remote Desktop Connection** (Start → type "remote"). The
   browser connection in Lightsail works too, but it cannot copy files.
3. Computer: the public IP. User: `Administrator`. Password: the one from step 1.
4. After you are in, change the password: Ctrl+Alt+End → **Change a password**.

## 4. Copy the project over and run setup (about 20 min, mostly waiting)

1. On the laptop, copy `dist\kalshi-server.zip` (Ctrl+C in Explorer).
2. In the Remote Desktop window, paste it onto the server's `C:\` drive (Ctrl+V).
3. On the server, right-click the zip → **Extract All** → extract to
   `C:\kalshi-weather-agent`. It must end up as `C:\kalshi-weather-agent\src\...`,
   not nested one folder deeper.
4. Start → type "PowerShell" → right-click → **Run as administrator**, and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\kalshi-weather-agent\deploy\setup_server.ps1
   ```

   **Optional phone alerts (free, no account):** install the **ntfy** app on your
   phone and subscribe to a topic name that nobody could guess, such as
   `kalshi-rain-` followed by 12 random letters. Then run setup with it:

   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\kalshi-weather-agent\deploy\setup_server.ps1 -AlertTopic kalshi-rain-xxxxxxxxxxxx
   ```

   You will get one "OK" message a day at 01:00 UTC, and an immediate one if anything
   breaks. **If the daily OK stops arriving, the server itself is down.**

5. Setup installs Python, sets the server clock to UTC, reloads the KXRAIN, WTI and
   natgas history from Kalshi's API (about 15 min), registers the collectors, runs them
   once and prints **SETUP COMPLETE**.
6. Close the Remote Desktop window. The collectors keep running with nobody logged in.

## 5. Switch the laptop off it

Once setup prints SETUP COMPLETE, tell Claude. The laptop's collector tasks will then be
removed and its power settings restored to what they were before (sleep after 45 min
on AC, lid close = sleep, wake timers off).

## 6. At the end (after 2026-11-10 settles)

1. Remote Desktop into the server and run in PowerShell:
   `powershell -ExecutionPolicy Bypass -File C:\kalshi-weather-agent\deploy\export_db.ps1`
2. Copy the `candidates-*.sqlite` file from the server's Desktop to the laptop and
   replace `data\candidates.sqlite` with it. Then run
   `python scripts/rain_calibration.py gate2` once. Gate 2 can also run on the server
   itself, where numpy is already installed.
3. **Delete the Lightsail instance** (instance → Delete). Nothing is charged either
   way on the Free plan, but deleting it stops the credits draining.

## Checking on it at any time

Remote Desktop in and run:

```powershell
cd C:\kalshi-weather-agent; C:\Python312\python.exe -m src.candidates health
```

Logs are in `C:\kalshi-weather-agent\data\logs\`.
