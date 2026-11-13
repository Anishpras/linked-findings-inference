"""Command line: python3 -m release_audit ...

    python3 -m release_audit SPEC.json --out DIR             audit a spec (views, budget, design search)
    python3 -m release_audit --data RECORDS.csv --target COL [--spec SPEC.json] --out DIR
                                                            estimate the same tables from labelled records
    python3 -m release_audit SPEC.json --sample N --sample-out RECORDS.csv
                                                            draw labelled records from a spec (for testing)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

from . import audit_spec, model as model_mod, realdata, report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m release_audit", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="spec JSON (generator mode, or views/items for --data)")
    ap.add_argument("--out", default="release_audit_out", help="output directory")
    ap.add_argument("--spec", dest="spec_opt", help="spec JSON (same as the positional argument)")
    ap.add_argument("--data", help="labelled CSV for real-data mode")
    ap.add_argument("--target", help="target column for --data")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261113)
    ap.add_argument("--no-search", action="store_true", help="skip the release-design search")
    ap.add_argument("--no-budget", action="store_true", help="skip the per-field information budget")
    ap.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    ap.add_argument("--max-records", type=int, default=None, help="enumeration limit before Monte Carlo")
    ap.add_argument("--mc-samples", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None, help="draw N labelled records from the spec")
    ap.add_argument("--sample-out", default=None)
    args = ap.parse_args(argv)
    args.spec = args.spec or args.spec_opt
    t0 = time.time()
    if args.data:
        if not args.target:
            ap.error("--data needs --target")
        m = model_mod.load(args.spec) if args.spec else None
        rows = realdata.load_csv(args.data, args.target)
        res = realdata.run(rows, args.target, m, k=args.folds, seed=args.seed)
        report.realdata(args.out, res, args.target)
        print("Real-data audit of %d records written to %s/realdata.md (%.0f s)" % (len(rows), args.out, time.time() - t0))
        return 0
    if not args.spec:
        ap.error("give a spec, or --data with --target")
    m = model_mod.load(args.spec)
    if args.sample:
        targets, records = model_mod.sample(m, args.sample, args.seed)
        fields = m.released_fields()
        idx = [m.field_index[f.name] for f in fields]
        with open(args.sample_out or "records.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow([m.target] + [f.name for f in fields])
            for t, r in zip(targets, records):
                w.writerow([m.target_values[t]] + [m.fields[i].values[r[i]] for i in idx])
        print("Wrote %d records to %s" % (args.sample, args.sample_out or "records.csv"))
        return 0
    res = audit_spec(m, budget=not args.no_budget, search=not args.no_search, workers=args.workers,
                     max_records=args.max_records, mc_samples=args.mc_samples, seed=args.seed)
    report.audit(args.out, m, res["joint"], res["views"], res["budget"], res["search"])
    print("Audit of %s written to %s/report.md (%s, %.0f s)"
          % (m.name, args.out, "exact" if res["joint"].exact else "Monte Carlo", time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
