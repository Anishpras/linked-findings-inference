# Linked-findings inference pilot

This pilot asks whether several minimal, structured findings about a fictional household can reveal a hidden reserve band (low, medium or high) that none of them contains. It compares one release (A, B), two linked releases (C), the linked releases after a declared coarsening (D), and the report-checklist answers alone (E). It also measures what useful report information each design loses.

`PROTOCOL.md` is the specification and lists every pre-freeze clarification under "Revisions". All data are synthetic and fictional. The code uses the Python standard library only (3.9–3.14) and needs no network.

## One command

```
python3 run_pilot.py
```

This scores the test split (3,000 households per scenario). It refuses to run unless the current files match the latest `FREEZE.json` entry. It exits 0 only if every validation check passes. A run takes about 1 minute on a 12-core laptop.

Other modes:

| Command | Purpose |
|---|---|
| `python3 run_pilot.py --split dev` | development run on the dev split; writes `results_dev/` |
| `python3 run_pilot.py --freeze --freeze-label v1.0` | records SHA-256 of the protocol, fixtures and every source file; requires a passing dev run with identical files |
| `python3 run_pilot.py --check-reproducible` | runs the full pipeline twice in temporary directories, compares every output byte, and checks against the committed `results/output_manifest.json` |

## Where outputs go

- `results/` holds the summaries: `summary_inference.csv`, `summary_paired.csv`, `summary_utility.csv`, `hypotheses.csv`, `controls.csv`, `population_oracle.csv` and `worked_cases.md`. It also holds `validation.json`, `run_info.json` and `output_manifest.json` (SHA-256 of every output file).
- `results/per_case_*.csv` and `data/<scenario>/` (households and the exact attacker inputs) are large. They are not kept in git. The command regenerates them byte for byte, and `output_manifest.json` lists their hashes.

## Layout

| Path | Contents |
|---|---|
| `lfi/spec.py` | single source of truth (distributions, scenarios, views, vocabulary, hyperparameters) |
| `lfi/generator.py`, `lfi/views.py`, `lfi/checklist.py` | generator, releases and coarsening, checklist and renderers |
| `lfi/attacker.py` | standalone attacker, run as `python3 -I` in an empty temp directory with input on stdin only |
| `lfi/isolate.py` | the launcher for the attacker |
| `lfi/oracle.py` | exact Bayes ceiling by full enumeration |
| `lfi/metrics.py`, `lfi/validate.py`, `lfi/report.py`, `lfi/pipeline.py` | measures, checks, outputs and orchestration |
| `fixtures/` | six hand-checked households and hand-computed attacker known answers |
| `tests/` | unit tests and the four mutation tests |
