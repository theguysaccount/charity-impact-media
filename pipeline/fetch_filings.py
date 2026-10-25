#!/usr/bin/env python3
"""Download and parse every filing in data/work/needed.csv that the parse cache lacks.

  python3 pipeline/fetch_filings.py [--workers 24] [--irs-workers 6] [--limit N]

Cache: data/work/filings.jsonl.gz, one parsed return per line (see parse990.py), keyed by
object id and parser version. New results are appended to data/work/filings.part.jsonl.gz
as they arrive, so an interrupted run resumes where it stopped; the end of a run compacts
both into filings.jsonl.gz holding exactly the needed filings.

Data-lake filings come from S3 one file at a time. Filings that are only in the IRS
monthly batches are read out of the IRS zips with HTTP range requests (irszip.py), with
fewer workers to stay polite to apps.irs.gov. With CIM_XML_CACHE=1 (the default outside
GitHub Actions) the raw XML is also kept gzipped under data/raw/xml/ for re-parsing.
"""

import argparse
import csv
import gzip
import json
import multiprocessing as mp
import os
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irszip  # noqa: E402
from common import RAW, WORK, ensure_dir, http, open_text, write_json  # noqa: E402
from parse990 import PARSER_VERSION, parse  # noqa: E402

CACHE = os.path.join(WORK, "filings.jsonl.gz")
PART = os.path.join(WORK, "filings.part.jsonl.gz")
XML_CACHE = os.path.join(RAW, "xml")
KEEP_XML = os.environ.get("CIM_XML_CACHE", "0" if os.environ.get("GITHUB_ACTIONS") else "1") == "1"


def load_cache(paths):
    out = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a torn last line from an interrupted run
                    if r.get("rec", {}).get("v") == PARSER_VERSION:
                        out[r["oid"]] = r
        except (EOFError, OSError):
            pass  # truncated gzip member at the end of a part file: keep what was read
    return out


def xml_path(oid):
    return os.path.join(XML_CACHE, oid[-3:], oid + ".xml.gz")


def get_xml(item):
    oid = item["object_id"]
    p = xml_path(oid)
    if os.path.exists(p):
        with gzip.open(p, "rb") as f:
            return f.read()
    if item["source"] == "gt":
        last = None
        for i in range(5):
            try:
                with http(item["ref"], retries=1, timeout=120) as r:
                    data = r.read()
                break
            except RuntimeError as e:
                last = e
                time.sleep(2 * (i + 1))
        else:
            raise RuntimeError(f"fetch {oid}: {last}")
    else:
        data = irszip.read_member(item["zip_url"], item["entry"])
    if KEEP_XML:
        ensure_dir(os.path.dirname(p))
        tmp = p + f".tmp{os.getpid()}"
        with gzip.open(tmp, "wb", compresslevel=4) as f:
            f.write(data)
        os.replace(tmp, p)
    return data


def work(item):
    try:
        data = get_xml(item)
    except Exception as e:  # noqa: BLE001
        return item["object_id"], None, f"fetch: {e}"[:300]
    try:
        rec = parse(data)
    except Exception as e:  # noqa: BLE001
        return item["object_id"], None, f"parse: {e}"[:300]
    if rec is None:
        return item["object_id"], None, "not a Form 990"
    return item["object_id"], rec, ""


def locate_irs(items):
    """Attach (zip_url, entry) to IRS-only items using each batch's central directories."""
    by_batch = defaultdict(list)
    for it in items:
        base, batch = it["ref"].split("|")
        by_batch[(base, batch)].append(it)
    missing = []
    for (base, batch), its in sorted(by_batch.items()):
        members = {}
        for url in irszip.batch_zip_urls(base, batch):
            for name, entry in irszip.central_directory(url).items():
                members[name] = (url, entry)
        for it in its:
            hit = members.get(it["object_id"] + "_public.xml")
            if hit:
                it["zip_url"], it["entry"] = hit
            else:
                missing.append(it)
        print(f"  IRS batch {batch}: {len(its)} needed, {len(its) - sum(1 for m in missing if m in its)} located", file=sys.stderr)
    return [it for it in items if "zip_url" in it], missing


def run_pool(items, workers, cache, part, stats, errors, label):
    if not items:
        return
    t0, done = time.time(), 0
    with gzip.open(part, "at", encoding="utf-8") as out, mp.Pool(workers) as pool:
        for oid, rec, err in pool.imap_unordered(work, items, chunksize=4):
            done += 1
            if rec is not None:
                src = next_src[oid]
                row = {"oid": oid, "src": src, "rec": rec}
                cache[oid] = row
                out.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
                stats["fetched"] += 1
            else:
                stats["failed"] += 1
                errors.append({"oid": oid, "err": err})
            if done % 2000 == 0 or done == len(items):
                rate = done / max(1e-9, time.time() - t0)
                print(f"  {label}: {done}/{len(items)} ({rate:.0f}/s), failed {stats['failed']}", file=sys.stderr)
                out.flush()


next_src = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--irs-workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    with open_text(os.path.join(WORK, "needed.csv")) as f:
        needed = list(csv.DictReader(f))
    cache = load_cache([CACHE, PART])
    todo = [it for it in needed if it["object_id"] not in cache]
    if a.limit:
        todo = todo[:a.limit]
    for it in needed:
        next_src[it["object_id"]] = it["source"]
    stats = Counter(needed=len(needed), cached=len(needed) - len([1 for it in needed if it["object_id"] not in cache]))
    print(f"needed {len(needed)}, cached {stats['cached']}, to fetch {len(todo)}", file=sys.stderr)

    errors = []
    gt_items = [it for it in todo if it["source"] == "gt"]
    irs_items = [it for it in todo if it["source"] == "irs"]
    run_pool(gt_items, a.workers, cache, PART, stats, errors, "data lake")
    if irs_items:
        located, missing = locate_irs(irs_items)
        for it in missing:
            stats["failed"] += 1
            errors.append({"oid": it["object_id"], "err": "not found in the IRS batch zips"})
        run_pool(located, a.irs_workers, cache, PART, stats, errors, "IRS batches")

    # Compact: exactly the needed filings, in a stable order.
    want = {it["object_id"] for it in needed}
    tmp = CACHE + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as out:
        for oid in sorted(want):
            if oid in cache:
                out.write(json.dumps(cache[oid], separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, CACHE)
    if os.path.exists(PART):
        os.remove(PART)
    stats["in_cache"] = sum(1 for oid in want if oid in cache)
    reasons = Counter(e["err"].split(":")[0] for e in errors)
    out = {**stats, "failed_share": round(stats["failed"] / max(1, len(todo)), 4) if todo else 0.0,
           "fail_reasons": dict(reasons), "parser_version": PARSER_VERSION}
    write_json(os.path.join(WORK, "fetch_stats.json"), out)
    with open(os.path.join(WORK, "fetch_errors.jsonl"), "w", encoding="utf-8") as f:
        for e in errors:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(out), file=sys.stderr)


if __name__ == "__main__":
    main()
