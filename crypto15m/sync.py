"""Bring data/crypto15m.sqlite up to date.

    py -3.12 -m crypto15m.sync

1. Backfill newly settled markets, their Kalshi minutes and Coinbase minutes (resumes).
2. Import the backfill files into SQLite.
3. Download the collector's hourly tick files from GitHub releases (c15m-data-*) and
   import any not yet imported.
"""

import glob
import json
import os
import subprocess

from . import backfill
from .common import COINS, DATA
from .store import connect, import_backfill, import_ticks, summary

TICKS = os.path.join(DATA, "ticks")


def download_releases():
    os.makedirs(TICKS, exist_ok=True)
    r = subprocess.run(["gh", "release", "list", "--limit", "200", "--json", "tagName"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gh release list failed: {r.stderr.strip()[:200]}")
        return
    tags = [t["tagName"] for t in json.loads(r.stdout or "[]") if t["tagName"].startswith("c15m-data-")]
    for tag in sorted(tags):
        subprocess.run(["gh", "release", "download", tag, "-p", "*.jsonl.gz", "-D", TICKS,
                        "--skip-existing"], capture_output=True, text=True)
    print(f"release files: {len(glob.glob(os.path.join(TICKS, '*.gz')))} on disk from {len(tags)} day(s)")


def main():
    backfill.main(list(COINS))
    con = connect()
    import_backfill(con)
    download_releases()
    n = sum(import_ticks(con, p) for p in sorted(glob.glob(os.path.join(TICKS, "*.jsonl.gz"))))
    print(f"imported {n} new tick rows")
    for k, v in summary(con).items():
        print(f"  {k:<14} {v}")


if __name__ == "__main__":
    main()
