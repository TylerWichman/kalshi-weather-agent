"""Live 15-min crypto dashboard: polls Kalshi + Coinbase, serves http://127.0.0.1:8715

    py -3.12 -m crypto15m.live

Every poll is logged to data/crypto15m/live_<YYYYMMDD>.jsonl so the live record can be
scored later exactly like the backfill (forward test).

Signal = the model's fair price minus the price you'd pay (ask + taker fee). The
thresholds below are placeholders until the backtest sets them; the page says so.
"""

import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .common import COINBASE, COINS, DATA, append_jsonl, fair_yes, fee, get, kalshi

PORT = 8715
HERE = os.path.dirname(os.path.abspath(__file__))
BACKTEST = os.path.join(DATA, "backtest.json")

# Edge thresholds in dollars per contract (after fee). Replaced by backtest.json if present.
THRESH = {"signal": 0.04, "strong": 0.08}
VOL_WINDOW_MIN = 60

state = {c: {"coin": c, "spot": None, "spot_ts": None, "ticks": deque(maxlen=3600),
             "vol1m": None, "market": None, "basis": None, "basis_src": None,
             "recent": [], "signal_log": deque(maxlen=40), "error": None}
         for c in COINS}
lock = threading.Lock()


def now():
    return time.time()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def f(x):
    return None if x in (None, "") else float(x)


# ---------------------------------------------------------------- pollers

def poll_spot():
    while True:
        for c, cfg in COINS.items():
            try:
                d = get(f"{COINBASE}/products/{cfg['product']}/ticker", min_gap=0.05, retries=2)
                p, t = float(d["price"]), now()
                with lock:
                    s = state[c]
                    s["spot"], s["spot_ts"] = p, t
                    s["ticks"].append((t, p))
            except Exception as e:
                state[c]["error"] = f"spot: {e}"
        time.sleep(2)


def poll_vol():
    """Realized 1-minute log-return stdev over the last hour, refreshed every minute."""
    while True:
        for c, cfg in COINS.items():
            try:
                d = get(f"{COINBASE}/products/{cfg['product']}/candles?granularity=60",
                        min_gap=0.1, retries=4) or []
                closes = [r[4] for r in sorted(d)][-(VOL_WINDOW_MIN + 1):]
                rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0]
                if len(rets) > 10:
                    m = sum(rets) / len(rets)
                    v = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
                    with lock:
                        state[c]["vol1m"] = v
                        state[c]["candles"] = sorted(d)[-120:]
            except Exception as e:
                state[c]["error"] = f"vol: {e}"
        time.sleep(60)


def poll_recent():
    """Last settled windows per coin: the streak / reversal features."""
    while True:
        for c, cfg in COINS.items():
            try:
                d = kalshi(f"/markets?series_ticker={cfg['series']}&status=settled&limit=12",
                           min_gap=0.1, retries=4)
                rows = [{"ticker": m["ticker"], "result": m.get("result"),
                         "strike": m.get("floor_strike"), "settle": f(m.get("expiration_value")),
                         "close": m["close_time"]} for m in d.get("markets", [])]
                with lock:
                    state[c]["recent"] = rows
                    state[c]["error"] = None
            except Exception as e:
                state[c]["error"] = f"recent: {e}"
        time.sleep(45)


def spot_near(c, t, span=30):
    """Mean of our Coinbase ticks within `span` seconds before t (for the basis)."""
    xs = [p for (u, p) in state[c]["ticks"] if t - span <= u <= t]
    return sum(xs) / len(xs) if xs else None


def candle_close_before(c, t):
    rows = [r for r in state[c].get("candles", []) if r[0] + 60 <= t]
    return rows[-1][4] if rows else None


def poll_kalshi():
    while True:
        for c, cfg in COINS.items():
            try:
                d = kalshi(f"/markets?series_ticker={cfg['series']}&status=open&limit=5",
                           min_gap=0.1, retries=4)
                tsf = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
                # Right after a close Kalshi still lists the finished market as open for a
                # while; skip anything already closed or not yet open.
                t0 = now()
                ms = sorted((m for m in d.get("markets", [])
                             if tsf(m["close_time"]) > t0 and tsf(m["open_time"]) <= t0),
                            key=lambda m: m["close_time"])
                if not ms:
                    with lock:
                        state[c]["market"], state[c]["model"] = None, None
                    continue
                m = ms[0]
                close_t, open_t = tsf(m["close_time"]), tsf(m["open_time"])
                ob = kalshi(f"/markets/{m['ticker']}/orderbook?depth=5", min_gap=0.1, retries=4) or {}
                book = ob.get("orderbook_fp", {})
                mk = {"ticker": m["ticker"], "open": open_t, "close": close_t,
                      "strike": m.get("floor_strike"),
                      "yes_bid": f(m.get("yes_bid_dollars")), "yes_ask": f(m.get("yes_ask_dollars")),
                      "last": f(m.get("last_price_dollars")), "volume": f(m.get("volume_fp")),
                      "book_yes": book.get("yes_dollars", [])[-5:],
                      "book_no": book.get("no_dollars", [])[-5:]}
                with lock:
                    s = state[c]
                    if not s["market"] or s["market"]["ticker"] != mk["ticker"]:
                        s["basis"], s["basis_src"] = None, None
                        s["window"] = deque(maxlen=600)
                    s["market"] = mk
                    if s["basis"] is None and mk["strike"]:
                        # Strike = CF index 60-s avg before open. Compare with our own
                        # Coinbase ticks in that minute; fall back to the 1-min candle.
                        ref = spot_near(c, open_t, 60)
                        src = "ticks"
                        if ref is None:
                            ref, src = candle_close_before(c, open_t + 1), "candle"
                        if ref:
                            s["basis"], s["basis_src"] = mk["strike"] / ref, src
                            # Seed the chart with 1-min candle closes since open.
                            seed = [{"t": r[0] + 60, "spot": r[4] * s["basis"], "fair": None,
                                     "ask": None, "bid": None}
                                    for r in s.get("candles", []) if open_t < r[0] + 60 < now()]
                            s["window"].extend(seed)
                    compute(c)
                    s["error"] = None
            except Exception as e:
                state[c]["error"] = f"kalshi: {e}"
        time.sleep(3)


# ---------------------------------------------------------------- model

def compute(c):
    s = state[c]
    mk, spot, vol = s["market"], s["spot"], s["vol1m"]
    if not mk or not spot or not vol or not mk["strike"]:
        s["model"] = None
        return
    t = now()
    left = mk["close"] - t
    basis = s["basis"] or 1.0
    adj = spot * basis
    sig_sec = vol / math.sqrt(60)
    obs_mean, obs_secs = None, 0
    if left <= 60:
        xs = [math.log(p * basis) for (u, p) in s["ticks"] if mk["close"] - 60 <= u <= t]
        if xs:
            obs_mean, obs_secs = sum(xs) / len(xs), min(60 - left, 60)
    p = fair_yes(adj, mk["strike"], left, sig_sec, obs_mean, obs_secs)
    ya, yb = mk["yes_ask"], mk["yes_bid"]
    na = (1 - yb) if yb is not None else None
    e_up = (p - ya - fee(ya)) if (p is not None and ya and 0 < ya < 1) else None
    e_dn = ((1 - p) - na - fee(na)) if (p is not None and na and 0 < na < 1) else None
    z = math.log(adj / mk["strike"]) / (sig_sec * math.sqrt(max(left, 1)))
    sig = "none"
    for side, e in (("UP", e_up), ("DOWN", e_dn)):
        if e is not None and e >= THRESH["strong"]:
            sig = f"STRONG {side}"
        elif e is not None and e >= THRESH["signal"] and sig == "none":
            sig = side
    model = {"fair": p, "edge_up": e_up, "edge_down": e_dn, "adj_spot": adj, "z": z,
             "secs_left": left, "signal": sig, "basis": basis, "ask_up": ya, "ask_down": na}
    s["model"] = model
    s.setdefault("window", deque(maxlen=600)).append(
        {"t": t, "spot": adj, "fair": p, "ask": ya, "bid": yb})
    prev = s["signal_log"][-1] if s["signal_log"] else None
    if sig != "none" and (not prev or prev["ticker"] != mk["ticker"] or prev["signal"] != sig):
        s["signal_log"].append({"t": t, "ticker": mk["ticker"], "signal": sig, "fair": p,
                                "ask": ya if "UP" in sig else na,
                                "edge": e_up if "UP" in sig else e_dn, "secs_left": left})
    append_jsonl(os.path.join(DATA, f"live_{datetime.now(timezone.utc):%Y%m%d}.jsonl"), [{
        "t": round(t, 2), "coin": c, "ticker": mk["ticker"], "spot": spot, "basis": basis,
        "strike": mk["strike"], "bid": yb, "ask": ya, "vol1m": vol, "fair": p,
        "left": round(left, 1)}])


# ---------------------------------------------------------------- server

def snapshot():
    with lock:
        out = {"now": now(), "thresholds": THRESH, "coins": {}}
        for c, s in state.items():
            out["coins"][c] = {
                "coin": c, "spot": s["spot"], "spot_ts": s["spot_ts"], "vol1m": s["vol1m"],
                "market": s["market"], "model": s.get("model"), "basis_src": s["basis_src"],
                "recent": s["recent"], "signals": list(s["signal_log"]),
                "window": list(s.get("window", []))[::2], "error": s["error"]}
    try:
        with open(BACKTEST, encoding="utf-8") as fh:
            out["backtest"] = json.load(fh)
    except Exception:
        out["backtest"] = None
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            self._send(json.dumps(snapshot()).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "dashboard.html"), "rb") as fh:
                self._send(fh.read(), "text/html; charset=utf-8")
        else:
            self.send_error(404)


def main():
    try:
        with open(BACKTEST, encoding="utf-8") as fh:
            bt = json.load(fh)
        THRESH.update(bt.get("thresholds", {}))
    except Exception:
        pass
    for fn in (poll_spot, poll_vol, poll_recent, poll_kalshi):
        threading.Thread(target=fn, daemon=True).start()
    print(f"dashboard: http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
