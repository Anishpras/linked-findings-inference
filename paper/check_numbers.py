#!/usr/bin/env python3
"""Check every number in paper/main.tex against the project's own files.

paper/NUMBERS.md lists each number printed in the paper, one table row each:

    | ID | Context | Printed | Source | Locator | Format |

- Context: text that must appear on the same source line of main.tex as the printed text
  (after the light normalisation in `norm`). It pins a number to its table row or sentence.
- Printed: the text as it appears in the paper.
- Source: a human-readable pointer (file and row).
- Locator: a Python expression over the helpers below. It re-reads the source file (a result
  CSV, a Markdown result file, JSON, the protocol, the example spec, or git history) and returns
  one value or a tuple of values.
- Format: a template that turns the located value(s) into the printed text, e.g.
  `{+r4} [{r4}, {r4}]`. Tokens: r<n> round to n decimals, p<n> percent with n decimals,
  i integer, c integer with thousands commas, s string; flags + (explicit plus sign),
  a (absolute value), n (negate).

The check fails if:
1. a located value does not format to the printed text;
2. a rounding is ambiguous because the source value is itself rounded (for example a
   four-decimal 0.5755 cannot be rounded to three decimals) or is an exact tie;
3. a printed text is not found on a line of main.tex that also holds its context;
4. any numeral in main.tex (from \\begin{document} to the bibliography, outside the tikz figure,
   whose coordinates have their own rows) does not lie inside an occurrence of some row's printed
   text on a line that also holds that row's context.

Standard library only. Usage: python3 paper/check_numbers.py [-v]
"""
import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from pathlib import Path

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
TEX = PAPER / "main.tex"
NUMBERS = PAPER / "NUMBERS.md"


class CheckError(Exception):
    pass


class Num:
    """A value known to lie in [v - e, v + e]; e = 0 for exact values.

    k is the number of decimals of the source string when the value was read directly from a
    rounded decimal string; printing it with k or more decimals reproduces the source digits."""

    __slots__ = ("v", "e", "k")

    def __init__(self, v, e=0, k=None):
        self.v = Fraction(v)
        self.e = Fraction(e)
        self.k = k

    def _bin(self, o):
        return o if isinstance(o, Num) else num(o)

    def __add__(self, o):
        o = self._bin(o)
        return Num(self.v + o.v, self.e + o.e)

    __radd__ = __add__

    def __sub__(self, o):
        o = self._bin(o)
        return Num(self.v - o.v, self.e + o.e)

    def __rsub__(self, o):
        return self._bin(o) - self

    def __neg__(self):
        return Num(-self.v, self.e, self.k)

    def __abs__(self):
        return Num(abs(self.v), self.e, self.k)

    def __mul__(self, o):
        o = self._bin(o)
        return Num(self.v * o.v, abs(self.v) * o.e + abs(o.v) * self.e + self.e * o.e)

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._bin(o)
        if o.v - o.e <= 0 <= o.v + o.e:
            raise CheckError("division by an interval that contains 0")
        v = self.v / o.v
        corners = [(self.v + s * self.e) / (o.v + t * o.e) for s in (-1, 1) for t in (-1, 1)]
        return Num(v, max(abs(c - v) for c in corners))

    def __rtruediv__(self, o):
        return self._bin(o) / self

    def __lt__(self, o):
        o = self._bin(o)
        if self.v + self.e < o.v - o.e:
            return True
        if self.v - self.e >= o.v + o.e:
            return False
        raise CheckError("comparison is ambiguous within rounding error")

    def __gt__(self, o):
        return self._bin(o) < self

    def __repr__(self):
        return f"Num({float(self.v)!r} +/- {float(self.e)!r})"


DEC_RE = re.compile(r"^[+-]?\d+\.\d+$")
INT_RE = re.compile(r"^[+-]?\d+$")
FRAC_RE = re.compile(r"^[+-]?\d+/\d+$")


def num(x):
    """Read a value. Integers and fractions are exact; a decimal string is taken as rounded."""
    if isinstance(x, Num):
        return x
    if isinstance(x, bool):
        raise CheckError(f"not a number: {x!r}")
    if isinstance(x, (int, Fraction)):
        return Num(x)
    if isinstance(x, float):
        raise CheckError("floats are not accepted; read numbers from their source strings")
    s = str(x).strip()
    if INT_RE.match(s) or FRAC_RE.match(s):
        return Num(Fraction(s))
    if DEC_RE.match(s):
        k = len(s.split(".")[1])
        return Num(Fraction(s), Fraction(1, 2 * 10 ** k), k)
    raise CheckError(f"not a number: {x!r}")


def X(x):
    """A decimal string that is exact by construction (a design parameter, e.g. '0.15')."""
    s = str(x).strip()
    k = len(s.split(".")[1]) if "." in s else 0
    return Num(Fraction(s), 0, k)


F = Fraction


def _to_decimal(fr):
    with localcontext() as ctx:
        ctx.prec = 80
        return Decimal(fr.numerator) / Decimal(fr.denominator)


def _round(fr, n):
    q = Decimal(1).scaleb(-n)
    with localcontext() as ctx:
        ctx.prec = 80
        return _to_decimal(fr).quantize(q, rounding=ROUND_HALF_UP)


def _is_tie(fr, n):
    scaled = fr * 10 ** n
    return (scaled - int(scaled)) in (Fraction(1, 2), Fraction(-1, 2))


def rnd(x, n):
    """Round a Num to n decimals, refusing ambiguous roundings."""
    x = num(x)
    if x.k is not None and n >= x.k:
        return _round(x.v, n)
    if x.e == 0:
        if _is_tie(x.v, n):
            raise CheckError(f"exact tie when rounding {x.v} to {n} decimals")
        return _round(x.v, n)
    lo, hi = _round(x.v - x.e, n), _round(x.v + x.e, n)
    if lo != hi:
        raise CheckError(f"ambiguous rounding of {x!r} to {n} decimals ({lo} or {hi})")
    return hi.copy_abs() if hi == 0 else hi


TOKEN_RE = re.compile(r"\{([+an]*)([rpics])(\d*)\}")


def fmt(template, values):
    if not isinstance(values, tuple):
        values = (values,)
    values = list(values)
    out, pos, used = [], 0, 0
    for m in TOKEN_RE.finditer(template):
        out.append(template[pos:m.start()])
        pos = m.end()
        flags, kind, digits = m.group(1), m.group(2), m.group(3)
        if used >= len(values):
            raise CheckError(f"template {template!r} needs more values than the locator gave")
        val = values[used]
        used += 1
        if kind == "s":
            out.append(str(val))
            continue
        x = num(val)
        if "n" in flags:
            x = -x
        if "a" in flags:
            x = abs(x)
        if kind == "r":
            d = rnd(x, int(digits))
            s = format(d, "f")
            if s.startswith("-") and d == 0:
                raise CheckError(f"value rounds to negative zero: {x!r}")
            if "+" in flags and d > 0:
                s = "+" + s
            out.append(s)
        elif kind == "p":
            y = x * 100
            if x.k is not None:
                y.k = max(x.k - 2, 0)
            d = rnd(y, int(digits))
            out.append(format(d, "f") + "%")
        elif kind in "ic":
            if x.e != 0 or x.v.denominator != 1:
                raise CheckError(f"not an exact integer: {x!r}")
            i = x.v.numerator
            out.append(f"{i:,}" if kind == "c" else str(i))
    out.append(template[pos:])
    if used != len(values):
        raise CheckError(f"template {template!r} used {used} of {len(values)} values")
    return "".join(out)


_CSV = {}


def _rows(path):
    if path not in _CSV:
        with open(ROOT / path, newline="", encoding="utf-8") as fh:
            _CSV[path] = list(csv.DictReader(fh))
    return _CSV[path]


def _match(path, filters):
    conds = [f.split("=", 1) for f in filters.split(";") if f.strip()]
    rows = _rows(path)
    for k, _ in conds:
        if rows and k not in rows[0]:
            raise CheckError(f"{path}: no column {k!r}")
    return [r for r in rows if all(r[k] == v for k, v in conds)]


def csvv(path, filters, cols):
    """The value(s) of `cols` (comma-separated) in the rows of `path` matching `filters`
    (k=v;k=v). Duplicate rows are allowed only if they agree."""
    rows = _match(path, filters)
    if not rows:
        raise CheckError(f"{path}: no row matches {filters!r}")
    out = []
    for c in cols.split(","):
        if c not in rows[0]:
            raise CheckError(f"{path}: no column {c!r}")
        vals = {r[c] for r in rows}
        if len(vals) != 1:
            raise CheckError(f"{path}: rows matching {filters!r} disagree on {c!r}")
        out.append(vals.pop())
    return out[0] if len(out) == 1 else tuple(out)


def ncsv(path, filters=""):
    """Number of rows of `path` matching `filters`."""
    return Num(len(_match(path, filters)))


_TEXT = {}


def _text(path):
    if path not in _TEXT:
        _TEXT[path] = (ROOT / path).read_text(encoding="utf-8")
    return _TEXT[path]


def rx(path, pattern, *groups):
    """Capture group(s) of the first match of `pattern` in a text file."""
    m = re.search(pattern, _text(path), re.M)
    if not m:
        raise CheckError(f"{path}: pattern not found: {pattern!r}")
    groups = groups or (1,)
    vals = tuple(m.group(g) for g in groups)
    return vals[0] if len(vals) == 1 else vals


def has(path, text, value=None):
    """Return `value` (default: `text`) if `text` occurs verbatim in the file."""
    if text not in _text(path):
        raise CheckError(f"{path}: text not found: {text!r}")
    return text if value is None else value


def js(path, *keys):
    """A value inside a JSON file; a key of the form 'name=value' selects from a list."""
    obj = json.loads(_text(path))
    for key in keys:
        if isinstance(key, str) and "=" in key and isinstance(obj, list):
            k, v = key.split("=", 1)
            hits = [o for o in obj if str(o.get(k)) == v]
            if len(hits) != 1:
                raise CheckError(f"{path}: {len(hits)} entries with {key!r}")
            obj = hits[0]
        else:
            obj = obj[key]
    return obj


def specmap(field, row=None, path="examples/household/spec.json"):
    """A probability row as a dict from value to exact probability."""
    fields = {f["name"]: f for f in js(path, "fields")}
    return dict(zip(fields[field]["values"], spec(field, row, path)))


def spec(field, row=None, path="examples/household/spec.json"):
    """A probability row of a field in a release_audit spec, as exact values."""
    fields = {f["name"]: f for f in js(path, "fields")}
    if field == "prior":
        vals = js(path, "target", "prior")
    elif row is None:
        vals = fields[field]["p"]
    else:
        vals = fields[field]["cpt"][row]
    return tuple(X(v) for v in vals)


def _git(*args):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def gtime(commit):
    return datetime.fromisoformat(_git("show", "-s", "--format=%aI", commit))


def gdate(commit):
    t = gtime(commit)
    return f"{t.day} {t.strftime('%B %Y')}"


def gelapsed(first, later):
    """Elapsed time between two commits as H:MM:SS."""
    secs = int((gtime(later) - gtime(first)).total_seconds())
    if secs < 0:
        raise CheckError("commits out of order")
    return f"{secs // 3600}:{secs // 60 % 60:02d}:{secs % 60:02d}"


def gsubject(commit):
    return _git("show", "-s", "--format=%s", commit)


def gshort(commit):
    return _git("rev-parse", "--short=7", commit)


def coords(pairs, n=4, labels=None):
    """Format (x, y) pairs as pgfplots coordinates, optionally with point labels."""
    parts = []
    for i, (x, y) in enumerate(pairs):
        s = f"({format(rnd(x, n), 'f')},{format(rnd(y, n), 'f')})"
        if labels:
            s += f" [{labels[i]}]"
        parts.append(s)
    return " ".join(parts)


def rowd(path, filters):
    """The single row of `path` matching `filters`, as a dict."""
    rows = _match(path, filters)
    if len(rows) != 1:
        raise CheckError(f"{path}: {len(rows)} rows match {filters!r}")
    return rows[0]


def _key(x):
    if isinstance(x, Num):
        return ("n", x.v, x.e)
    if isinstance(x, (tuple, list)):
        return ("t",) + tuple(_key(y) for y in x)
    return ("s", str(x))


def same(*values):
    """Return the first value if all values are equal (numbers compared exactly), else fail."""
    keys = {_key(v) for v in values}
    if len(keys) != 1:
        raise CheckError(f"values that should be equal differ: {values!r}")
    return values[0]


def need(condition, value):
    """Return `value` if `condition` holds, else fail."""
    if not condition:
        raise CheckError("a stated condition does not hold in the source")
    return value


def frac_mean(values):
    vals = [num(v) for v in values]
    total = vals[0]
    for v in vals[1:]:
        total = total + v
    return total / len(vals)


NAMESPACE = {
    "csvv": csvv, "ncsv": ncsv, "rx": rx, "has": has, "js": js, "spec": spec, "specmap": specmap,
    "gdate": gdate, "gelapsed": gelapsed, "gsubject": gsubject, "gshort": gshort,
    "coords": coords, "num": num, "X": X, "F": F, "Num": Num, "mean": frac_mean,
    "rowd": rowd, "same": same, "need": need, "all": all, "any": any, "set": set,
    "_rows": _rows, "len": len, "min": min, "max": max, "sorted": sorted, "str": str,
    "tuple": tuple, "int": int, "abs": abs, "sum": sum, "range": range, "zip": zip,
}


def evaluate(locator):
    scope = dict(NAMESPACE)
    scope["__builtins__"] = {}
    try:
        return eval(locator, scope)
    except CheckError:
        raise
    except Exception as exc:
        raise CheckError(f"locator failed: {type(exc).__name__}: {exc}")


def norm(s):
    """Light normalisation of LaTeX source so printed numbers can be matched."""
    s = s.replace("\\textminus", "-")
    s = s.replace("$", "")
    s = s.replace("{,}", ",")
    s = s.replace("\\,", "")
    s = s.replace("\\%", "%")
    s = s.replace("\\_", "_")
    s = s.replace("\\&", "&")
    s = s.replace("~", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _cell(c):
    c = c.strip().replace("\\|", "|")
    if len(c) >= 2 and c.startswith("`") and c.endswith("`"):
        c = c[1:-1]
    return c


def parse_numbers():
    rows = []
    for lineno, line in enumerate(NUMBERS.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [_cell(c) for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        if len(cells) != 6 or cells[0] in ("ID", "") or set(cells[0]) <= set("-: "):
            continue
        rows.append({"line": lineno, "id": cells[0], "context": cells[1], "printed": cells[2],
                     "source": cells[3], "locator": cells[4], "format": cells[5]})
    return rows


def occurrences(line, printed):
    """Start positions of `printed` in `line` that are not part of a longer number."""
    hits, start = [], 0
    while True:
        i = line.find(printed, start)
        if i < 0:
            return hits
        start = i + 1
        before = line[i - 1] if i > 0 else ""
        after = line[i + len(printed): i + len(printed) + 2]
        if before and (before.isdigit() or before == "."):
            continue
        if printed[0].isdigit() and before and before in "-+" and line[max(0, i - 2):i] != "--":
            continue
        if printed[-1].isdigit() and after[:1].isdigit():
            continue
        if printed[-1].isdigit() and after[:1] in (".", ",") and after[1:2].isdigit():
            continue
        hits.append(i)


def found_on_line(line, printed):
    return bool(occurrences(line, printed))


NUM_TOKEN = re.compile(r"(?<![A-Za-z0-9_.\\])\d+(?:,\d{3})*(?:\.\d+)*(?![A-Za-z0-9_])")


def _drop_command(text, name, nargs):
    """Remove \\name, an optional (..) or [..] group, and nargs brace arguments."""
    out, i = [], 0
    pat = re.compile(r"\\" + name + r"(?![A-Za-z])")
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        j = m.end()
        while j < len(text) and text[j] in "([":
            close = ")" if text[j] == "(" else "]"
            j = text.index(close, j) + 1
        for _ in range(nargs):
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == "{":
                depth = 0
                while True:
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
        out.append(" ")
        i = j


def scan_text(raw):
    start = raw.index("\\begin{document}")
    end = raw.index("\\begin{thebibliography}")
    body = raw[start:end]
    body = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", body, flags=re.S)
    for name, nargs in (("label", 1), ("ref", 1), ("cite", 1), ("url", 1), ("href", 1),
                        ("setlength", 2), ("hspace", 1), ("vspace", 1), ("cmidrule", 1),
                        ("multicolumn", 2)):
        body = _drop_command(body, name, nargs)
    body = re.sub(r"\\begin\{(tabular|table|figure)\*?\}(\[[^\]]*\])?", " ", body)
    body = re.sub(r"\\\\\[[^\]]*\]", " ", body)
    body = re.sub(r"\d+(?:\.\d+)?(?:pt|em|ex|cm|mm|in)\b", " ", body)
    return norm(body)


def tex_tokens(text):
    return [m.group(0) for m in NUM_TOKEN.finditer(text)]


def main(argv):
    verbose = "-v" in argv
    raw = TEX.read_text(encoding="utf-8")
    try:
        raw.encode("ascii")
    except UnicodeEncodeError as exc:
        print(f"FAIL main.tex is not pure ASCII: {exc}")
        return 1
    lines = [norm(l) for l in raw.splitlines()]
    rows = parse_numbers()
    failures = []
    seen = set()
    for r in rows:
        if r["id"] in seen:
            failures.append(f"{r['id']}: duplicate ID")
        seen.add(r["id"])
        try:
            got = fmt(r["format"], evaluate(r["locator"]))
        except CheckError as exc:
            failures.append(f"{r['id']} (NUMBERS.md line {r['line']}): {exc}")
            continue
        if got != r["printed"]:
            failures.append(f"{r['id']}: source gives {got!r}, NUMBERS.md prints {r['printed']!r}")
            continue
        ctx = r["context"]
        if not any(ctx in ln and found_on_line(ln, r["printed"]) for ln in lines):
            failures.append(f"{r['id']}: {r['printed']!r} not found on a main.tex line containing {ctx!r}")
        elif verbose:
            print(f"ok   {r['id']:<28} {r['printed']}")
    scanned = scan_text(raw).splitlines()
    covered = [bytearray(len(line)) for line in scanned]
    for r in rows:
        for li, line in enumerate(scanned):
            if r["context"] in line:
                for i in occurrences(line, r["printed"]):
                    covered[li][i:i + len(r["printed"])] = b"\x01" * len(r["printed"])
    for li, line in enumerate(scanned):
        for m in NUM_TOKEN.finditer(line):
            if not all(covered[li][m.start():m.end()]):
                lo = max(0, m.start() - 50)
                failures.append(f"numeral {m.group(0)!r} in main.tex is not covered by any NUMBERS.md row: ...{line[lo:m.end() + 30]}...")
    n_tokens = len(tex_tokens(scan_text(raw)))
    if failures:
        for f in failures:
            print("FAIL", f)
        print(f"\n{len(failures)} failure(s); {len(rows)} NUMBERS.md rows; {n_tokens} numerals scanned in main.tex.")
        return 1
    print(f"OK: {len(rows)} numbers in NUMBERS.md re-derived from their source files and found in place in "
          f"main.tex; each of the {n_tokens} numerals in the body of main.tex lies inside one of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
