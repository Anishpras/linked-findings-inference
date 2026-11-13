#!/usr/bin/env python3
"""Linked-findings inference pilot: single reproduction command (see PROTOCOL.md, README.md).

    python3 run_pilot.py --split dev            # development run, scores the dev split -> results_dev/
    python3 run_pilot.py --freeze               # record SHA-256 of protocol, fixtures, sources (FREEZE.json)
    python3 run_pilot.py                        # frozen run, scores the test split -> results/
    python3 run_pilot.py --check-reproducible   # run the pipeline twice in temp dirs, compare every byte

Exit code 0 only if every validation check passes. The test split is scored only when the
current files match the latest FREEZE.json entry. Standard library only; no network.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lfi import pipeline, report, spec  # noqa: E402

FREEZE = ROOT / "FREEZE.json"
DEFAULT_OUT = {"test": "results", "dev": "results_dev"}
COPY_FOR_REPRO = ["run_pilot.py", "PROTOCOL.md", "README.md", "FREEZE.json", "lfi", "fixtures", "tests"]


def frozen_files():
    files = ["PROTOCOL.md", "run_pilot.py"]
    for sub, pattern in (("fixtures", "*.json"), ("lfi", "*.py"), ("tests", "*.py")):
        files += sorted("%s/%s" % (sub, p.name) for p in (ROOT / sub).glob(pattern))
    return files


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def current_hashes():
    return OrderedDict((f, sha256_file(ROOT / f)) for f in frozen_files())


def load_freeze():
    if not FREEZE.exists():
        return OrderedDict([("history", [])])
    return json.loads(FREEZE.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def freeze_status(hashes):
    history = load_freeze()["history"]
    if not history:
        return OrderedDict([("frozen", False), ("matches", False), ("label", None)])
    latest = history[-1]
    mismatched = [f for f, h in latest["sha256"].items() if hashes.get(f) != h]
    not_covered = [f for f in hashes if f not in latest["sha256"]]
    return OrderedDict([("frozen", True), ("label", latest["label"]), ("frozen_at_utc", latest["frozen_at_utc"]),
                        ("matches", not mismatched and not not_covered), ("mismatched", mismatched),
                        ("not_covered", not_covered)])


def do_freeze(args):
    hashes = current_hashes()
    info = ROOT / DEFAULT_OUT["dev"] / "run_info.json"
    if not info.exists():
        print("Refusing to freeze: no dev run found. Run `python3 run_pilot.py --split dev` first.")
        return 2
    dev = json.loads(info.read_text(encoding="utf-8"))
    if not dev.get("validation_all_ok"):
        print("Refusing to freeze: the last dev run did not pass every check.")
        return 2
    if dev.get("sha256") != hashes:
        changed = [f for f in hashes if dev.get("sha256", {}).get(f) != hashes[f]]
        print("Refusing to freeze: files changed since the last passing dev run: %s" % changed)
        return 2
    payload = load_freeze()
    payload["history"].append(OrderedDict([
        ("label", args.freeze_label),
        ("frozen_at_utc", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")),
        ("fixture_version", spec.FIXTURE_VERSION),
        ("note", args.freeze_note),
        ("sha256", hashes),
    ]))
    FREEZE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("Appended freeze entry %s (%d files) to FREEZE.json" % (args.freeze_label, len(hashes)))
    return 0


def _tree_bytes(base):
    out = OrderedDict()
    for d in ("results", "results_dev", "data"):
        root = Path(base) / d
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.name not in ("reproducibility_check.json", ".DS_Store"):
                    out["%s/%s" % (d, p.relative_to(root).as_posix())] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def do_check_reproducible(args):
    """Check 10: run the whole pipeline twice in fresh temporary copies of the project and compare
    every output byte (results and data). Also compare the first run with the hashes committed in
    <results>/output_manifest.json, which cover the large files that are not kept in git."""
    split = args.split
    out_name = DEFAULT_OUT[split]
    runs = []
    for k in (1, 2):
        tmp = Path(tempfile.mkdtemp(prefix="lfi-repro-%d-" % k))
        for name in COPY_FOR_REPRO:
            src = ROOT / name
            if src.is_dir():
                shutil.copytree(str(src), str(tmp / name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif src.exists():
                shutil.copyfile(str(src), str(tmp / name))
        t0 = time.time()
        proc = subprocess.run([sys.executable, "run_pilot.py", "--split", split], cwd=str(tmp),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print("run %d: exit %d in %.0f s" % (k, proc.returncode, time.time() - t0))
        runs.append((tmp, proc.returncode, _tree_bytes(tmp)))
    (_t1, rc1, h1), (_t2, rc2, h2) = runs
    diff_runs = sorted(f for f in set(h1) | set(h2) if h1.get(f) != h2.get(f))
    committed_path = ROOT / out_name / "output_manifest.json"
    if committed_path.exists():
        committed = json.loads(committed_path.read_text(encoding="utf-8"))
        diff_committed = sorted(f for f, e in committed.items() if h1.get(f) != e["sha256"])
        not_in_committed = sorted(f for f in h1 if f not in committed and f != "%s/output_manifest.json" % out_name)
    else:
        committed, diff_committed, not_in_committed = None, [], []
    ok = rc1 == 0 and rc2 == 0 and len(h1) > 0 and not diff_runs
    result = OrderedDict([
        ("check", "10_reproducibility_two_full_runs_in_temp_dirs"),
        ("split", split), ("python_version", sys.version.split()[0]),
        ("files_compared", len(h1)), ("exit_codes", [rc1, rc2]),
        ("runs_identical", not diff_runs), ("differing_files", diff_runs[:50]),
        ("committed_manifest_found", committed is not None),
        ("committed_manifest_files", 0 if committed is None else len(committed)),
        ("matches_committed_manifest", committed is not None and not diff_committed and not not_in_committed),
        ("files_differing_from_committed_manifest", diff_committed[:50]),
        ("files_missing_from_committed_manifest", not_in_committed[:50]),
        ("ok", ok and committed is not None and not diff_committed and not not_in_committed),
    ])
    for t, _rc, _h in runs:
        shutil.rmtree(str(t), ignore_errors=True)
    (ROOT / out_name).mkdir(exist_ok=True)
    report.write_json(ROOT / out_name / "reproducibility_check.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=spec.SCORED_SPLITS, default="test", help="scored split (default: test)")
    ap.add_argument("--out", default=None, help="output directory (default: results/ or results_dev/)")
    ap.add_argument("--freeze", action="store_true", help="append current hashes to FREEZE.json")
    ap.add_argument("--freeze-label", default="v1.0")
    ap.add_argument("--freeze-note", default="")
    ap.add_argument("--check-reproducible", action="store_true",
                    help="run the full pipeline twice in temporary directories and compare every output byte")
    args = ap.parse_args(argv)

    if args.freeze:
        return do_freeze(args)
    if args.check_reproducible:
        return do_check_reproducible(args)

    hashes = current_hashes()
    status = freeze_status(hashes)
    if args.split == "test" and not status["matches"]:
        print("Refusing to score the test split: current files do not match the latest FREEZE.json entry.")
        print("  freeze status: %s" % json.dumps(status))
        return 2
    out = ROOT / (args.out or DEFAULT_OUT[args.split])
    t0 = time.time()
    all_ok, checks, text = pipeline.run(args.split, out, ROOT / "data", {"current": hashes, "status": status})
    report.write_json(out / "output_manifest.json", report.manifest(out, ROOT / "data"))
    print(text)
    print("Freeze: %s" % ("matches %s" % status["label"] if status["matches"] else
                          ("not frozen" if not status["frozen"] else "does not match %s" % status["label"])))
    print("Outputs: %s/ and data/ (%.0f s)" % (out.name, time.time() - t0))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
