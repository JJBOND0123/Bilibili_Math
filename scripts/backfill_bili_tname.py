"""
Backfill `videos.bili_tname` (and optionally `videos.bili_tid`) in MySQL.

Reason:
- In some environments, Bilibili `/x/web-interface/view` returns `tid` but `tname` is empty.
- The search API `/x/web-interface/search/type` returns `typeid/typename`, which we can use to fill.

It runs in two phases:
1) DB-only: infer `tid -> tname` from already-filled rows and batch update missing ones.
2) Network: for remaining tids, pick one sample bvid, fetch its typename once, then batch update.

Usage:
  python scripts/backfill_bili_tname.py
"""

import os
import sys
import time

import pymysql
import requests

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from spider.bilibili_api import COOKIE, DB_CONFIG, build_headers
from spider.utils import parse_count


def main() -> None:
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=2")
        conn.commit()

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM videos WHERE bili_tname IS NULL OR bili_tname=''")
            missing_count = cursor.fetchone()["c"]
        if not missing_count:
            print("No missing bili_tname rows.")
            return

        session = requests.Session()
        headers = build_headers(COOKIE)
        url = "https://api.bilibili.com/x/web-interface/search/type"

        # Phase 1: DB-only mapping (tid -> most common tname in DB).
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT bili_tid AS tid, bili_tname AS tname, COUNT(*) AS c
                FROM videos
                WHERE bili_tname IS NOT NULL AND bili_tname<>'' AND bili_tid IS NOT NULL AND bili_tid<>0
                GROUP BY bili_tid, bili_tname
                ORDER BY bili_tid, c DESC
                """
            )
            rows = cursor.fetchall()

        best_by_tid: dict[int, str] = {}
        for row in rows:
            tid = int(row["tid"] or 0)
            if tid and tid not in best_by_tid:
                best_by_tid[tid] = str(row["tname"] or "").strip()

        db_updated = 0
        with conn.cursor() as cursor:
            for tid, tname in best_by_tid.items():
                if not tname:
                    continue
                cursor.execute(
                    """
                    UPDATE videos
                    SET bili_tname=%s
                    WHERE (bili_tname IS NULL OR bili_tname='') AND bili_tid=%s
                    """,
                    (tname, tid),
                )
                db_updated += cursor.rowcount
        conn.commit()
        print(f"Phase1 (DB) updated: {db_updated}")

        # Phase 2: per-tid network lookup using one sample bvid.
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT bili_tid AS tid
                FROM videos
                WHERE (bili_tname IS NULL OR bili_tname='') AND bili_tid IS NOT NULL AND bili_tid<>0
                ORDER BY tid
                """
            )
            missing_tids = [int(r["tid"]) for r in cursor.fetchall()]

        api_updated = 0
        for tid in missing_tids:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT bvid
                        FROM videos
                        WHERE (bili_tname IS NULL OR bili_tname='') AND bili_tid=%s
                        LIMIT 1
                        """,
                        (tid,),
                    )
                    one = cursor.fetchone()
                if not one:
                    continue

                bvid = one["bvid"] if isinstance(one, dict) else one[0]
                resp = session.get(
                    url,
                    headers=headers,
                    params={"search_type": "video", "keyword": str(bvid), "page": 1, "page_size": 1},
                    timeout=15,
                    verify=False,
                )
                if resp.status_code != 200:
                    time.sleep(2.0)
                    continue

                payload = resp.json() or {}
                if payload.get("code") != 0:
                    time.sleep(1.0)
                    continue

                data = payload.get("data") or {}
                items = data.get("result") or []
                if not isinstance(items, list) or not items:
                    continue

                item = items[0] or {}
                tname = (item.get("typename") or "").strip()
                typeid = parse_count(item.get("typeid", 0))
                if not tname or not typeid:
                    continue

                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE videos
                        SET bili_tname=%s
                        WHERE (bili_tname IS NULL OR bili_tname='') AND bili_tid=%s
                        """,
                        (tname, tid),
                    )
                    api_updated += cursor.rowcount
                conn.commit()
                print(f"tid={tid} -> {tname}, updated {cursor.rowcount}")
                time.sleep(0.4)
            except Exception as e:
                print("fail_tid", tid, e)
                time.sleep(2.0)

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM videos WHERE bili_tname IS NULL OR bili_tname=''")
            remaining = cursor.fetchone()["c"]
        print(f"Done. start_missing={missing_count}, updated={db_updated + api_updated}, remaining={remaining}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

