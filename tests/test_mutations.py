"""Mutation tests (PROTOCOL.md section 8): each deliberately broken variant must be detected by
the corresponding validation check, and the unbroken pipeline must pass the same check."""
import json
import shutil
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock

from lfi import checklist, exposure, generator, spec, validate, views

ROOT = Path(__file__).resolve().parent.parent
SMALL = (("train", 180), ("dev", 60), ("test", 60))


def load(name):
    with open(str(ROOT / "fixtures" / name), encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=OrderedDict)


def small(scenario="main"):
    return generator.generate(scenario, n=300, split_sizes=SMALL)


def stdin_for(data, split_of_by_view=None, scored="test"):
    maps = views.build_view_maps(data)
    base = {h["id"]: h["split"] for h in data["households"]}
    stdin = OrderedDict()
    for v in maps:
        split_of = split_of_by_view[v] if split_of_by_view else base
        stdin[v] = views.attacker_stdin(data["households"], maps[v], split_of, scored, data["order_key"])
    return maps, stdin


class BandLeakedIntoRelease2(unittest.TestCase):
    def check(self, data):
        _maps, stdin = stdin_for(data)
        scans = OrderedDict((v, exposure.scan(b)) for v, b in stdin.items())
        return validate.check_band_removed("main", scans, False)[0]["ok"]

    def test_unmutated_passes(self):
        self.assertTrue(self.check(small()))

    def test_band_field_in_release2_is_detected(self):
        original = views.release2

        def leaky(raw, band, band_field=False):
            r = original(raw, band, band_field)
            r["r2.reserve_band"] = band
            return r
        with mock.patch.object(views, "release2", leaky):
            self.assertFalse(self.check(small()))

    def test_band_value_in_release2_is_detected(self):
        original = views.release2

        def leaky(raw, band, band_field=False):
            r = original(raw, band, band_field)
            r["r2.goal"] = band  # band value smuggled into an ordinary field
            return r
        with mock.patch.object(views, "release2", leaky):
            self.assertFalse(self.check(small()))


class SplitShuffledPerView(unittest.TestCase):
    def test_unmutated_passes(self):
        data = small()
        maps, stdin = stdin_for(data)
        self.assertTrue(validate.check_split_isolation("main", data, stdin, "test", maps)[0]["ok"])

    def test_per_view_split_is_detected(self):
        data = small()
        ids_by_index = {h["gen_index"]: h["id"] for h in data["households"]}
        per_view = {}
        for v in spec.VIEWS:  # the bug: each view gets its own shuffle
            s = generator.assign_splits(300, generator.subseed(spec.MASTER_SEED, "main", "split:" + v), SMALL)
            per_view[v] = {ids_by_index[i]: s[i] for i in range(300)}
        maps, stdin = stdin_for(data, per_view)
        self.assertFalse(validate.check_split_isolation("main", data, stdin, "test", maps)[0]["ok"])


class StrictRendererGuesses(unittest.TestCase):
    def test_unmutated_passes(self):
        self.assertTrue(all(r["ok"] for r in validate.check_hand_examples(load("hand_examples.json"))))

    def test_guessing_renderer_is_detected(self):
        original = checklist.render_strict

        def guessing(x):  # never abstains: replaces every abstention by a guess
            return OrderedDict((k, spec.DEFAULT_FILL[k] if a is None else a) for k, a in original(x).items())
        with mock.patch.object(checklist, "render_strict", guessing):
            self.assertFalse(all(r["ok"] for r in validate.check_hand_examples(load("hand_examples.json"))))
            data = small()
            unsupported = 0
            for h in data["households"]:
                ans = checklist.correct_answers(h["raw"])
                out = checklist.render("strict", views.make_view("A", h["raw"], h["band"]))
                unsupported += sum(checklist.outcome(ans[i], out[i]) == "unsupported" for i in spec.ITEMS)
            self.assertFalse(validate.check_strict_never_unsupported("main", unsupported)[0]["ok"])


class NbWithoutUnseenValueRule(unittest.TestCase):
    MARKER = "            return None  # UNSEEN-VALUE RULE: no factor for this field in this row\n"
    MUTANT = "            return (ALPHA, self.class_counts[band] + ALPHA * (len(seen or ()) + 1))\n"

    def test_unmutated_passes(self):
        res = validate.check_attacker_known_answers(load("attacker_known_answers.json"), ROOT / "lfi" / "attacker.py")
        self.assertTrue(res[0]["ok"], res[0]["detail"])

    def test_removed_rule_is_detected(self):
        src = (ROOT / "lfi" / "attacker.py").read_text(encoding="utf-8")
        self.assertEqual(src.count(self.MARKER), 1)
        tmp = Path(tempfile.mkdtemp(prefix="lfi-mutant-"))
        try:
            mutant = tmp / "attacker.py"
            mutant.write_text(src.replace(self.MARKER, self.MUTANT), encoding="utf-8")
            res = validate.check_attacker_known_answers(load("attacker_known_answers.json"), mutant)
            self.assertFalse(res[0]["ok"])
        finally:
            shutil.rmtree(str(tmp))


if __name__ == "__main__":
    unittest.main()
