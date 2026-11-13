import json
import os
import shutil
import subprocess
import tempfile
import unittest

from fairslot import config, engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def world(scale, labels):
    cfg = config.load({"levels": {"names": scale, "policy": "same", "max_gap": "auto"}, "team": {"max_size": 1}})
    slots = [{"id": "s1", "start": "2026-11-20T19:30", "end": "", "resource": "c1"}]
    members = {"m%d" % i: {"level": l, "name": ""} for i, l in enumerate(labels)}
    apps = [{"id": "a%d" % i, "slot": "s1", "members": ["m%d" % i], "open": True, "avoid": [], "want": [], "ts": "2026-11-18T09:0%d" % i} for i in range(len(labels))]
    return cfg, slots, apps, members


class Scales(unittest.TestCase):
    def test_ranges_and_auto_gap(self):
        self.assertEqual(config.load({"levels": {"names": "1-7"}})["levels"]["names"], [str(i) for i in range(1, 8)])
        self.assertEqual(len(config.load({"levels": {"names": "1-100"}})["levels"]["names"]), 100)
        self.assertEqual(config.load({"levels": {"names": "A-F"}})["levels"]["names"], list("ABCDEF"))
        self.assertEqual(config.load({"levels": {"names": "1-100", "max_gap": "auto"}})["levels"]["max_gap"], 20)
        self.assertEqual(config.load({"levels": {"names": ["x", "y"], "max_gap": 0}})["levels"]["max_gap"], 0)
        with self.assertRaises(ValueError):
            config.load({"levels": {"names": "7-1"}})

    def test_labels_are_matched_forgivingly(self):
        # Cyrillic С, lower case, spaces and 5.0 = 5 are the same level
        cfg, slots, apps, members = world("C-, C, C+", ["С", "c", " C "])
        res = engine.run(cfg, slots, apps, members, [], "seed", "2026-11-19T12:00")
        self.assertEqual(sorted(res["allocations"][0]["members"]), ["m0", "m1", "m2"])
        cfg, slots, apps, members = world("1-7", ["5.0", "5", "5,0"])
        res = engine.run(cfg, slots, apps, members, [], "seed", "2026-11-19T12:00")
        self.assertEqual(len(res["allocations"][0]["members"]), 3)

    def test_different_levels_stay_apart_in_same_mode(self):
        cfg, slots, apps, members = world("A-D", ["A", "B"])
        res = engine.run(cfg, slots, apps, members, [], "seed", "2026-11-19T12:00")
        self.assertEqual(len(res["allocations"][0]["members"]), 1)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_browser_engine_agrees(self):
        cfg, slots, apps, members = world("А-Д", ["А", "а", "Б", "В", "A"])
        py = engine.run(cfg, slots, apps, members, [], "seed", "2026-11-19T12:00")
        html = open(os.path.join(ROOT, "fairslot.html"), encoding="utf-8").read()
        src = html[html.index("/*ENGINE*/"):html.index("/*END-ENGINE*/")]
        js = src + "\nconst cfg=FS.load(%s);console.log(JSON.stringify(FS.run(cfg,%s,%s,%s,[],'seed','2026-11-19T12:00').allocations));" % (
            json.dumps({"levels": {"names": "А-Д", "policy": "same", "max_gap": "auto"}, "team": {"max_size": 1}}), json.dumps(slots), json.dumps(apps), json.dumps(members))
        f = os.path.join(tempfile.mkdtemp(), "t.js")
        open(f, "w", encoding="utf-8").write(js)
        out = subprocess.run(["node", f], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), py["allocations"])


if __name__ == "__main__":
    unittest.main()
