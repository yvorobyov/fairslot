import json, os, random, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta
from fairslot import config as C
from fairslot.engine import run, verify_published, _dt
from fairslot.adapters import csv_backend as B, links

LV9 = ["D-", "D", "D+", "D+Strong", "C-", "C-Strong", "C", "C+", "C+Strong"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")


class Dates(unittest.TestCase):
    def test_formats(self):
        for s in ("2026-11-20T20:00", "2026-11-20 20:00", "2026-11-20T20:00:00Z", "2026-11-20T20:00:00+04:00"):
            self.assertEqual(_dt(s), datetime(2026, 11, 20, 20, 0))


class Csv(unittest.TestCase):
    def test_bom_and_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.csv")
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                f.write("id,level\nАня,beginner\nBob,advanced\n")
            self.assertEqual(B.read_members(p), {"Аня": {"level": "beginner", "name": ""}, "Bob": {"level": "advanced", "name": ""}})
            r = {"allocations": [{"slot": "s", "members": ["Аня"], "open_seats": 1}]}
            out = os.path.join(d, "o.csv"); B.write_allocations(out, r)
            with open(out, encoding="utf-8") as f:
                self.assertIn("Аня", f.read())

    def test_links(self):
        slots = [{"id": "s 1", "start": "2026-11-20T20:00", "resource": "c1"}]
        r = {"allocations": [{"slot": "s 1", "members": ["a b", "c"]}]}
        u = links.render(r, slots, "https://x/{date}/{time}?o={owner}&s={slot_id}")[0]["url"]
        self.assertEqual(u, "https://x/2026-11-20/20:00?o=a%20b&s=s%201")


class Cli(unittest.TestCase):
    def sh(self, *a):
        env = dict(os.environ, PYTHONPATH=ROOT)
        return subprocess.run([sys.executable, "-m", "fairslot", *a], capture_output=True, text=True, env=env, cwd=ROOT)

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            r = self.sh("run", "--profile", "owner_controlled", "--slots", f"{EX}/slots.csv", "--apps", f"{EX}/applications.csv",
                        "--members", f"{EX}/members.csv", "--history", f"{EX}/history.csv", "--seed", "demo",
                        "--now", "2026-11-19T12:00", "--out", out, "--csv", os.path.join(d, "r.csv"))
            self.assertEqual(r.returncode, 0, r.stderr)
            v = self.sh("verify", out); self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            data["audit"]["slots"]["d1-2000-c1"][0]["key"] = 0.5
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f)
            self.assertEqual(self.sh("verify", out).returncode, 1)

    def test_presets_and_sim(self):
        self.assertEqual(self.sh("presets").returncode, 0)
        r = self.sh("sim", "--seeds", "1", "--weeks", "1", "--profiles", "late_lottery")
        self.assertEqual(r.returncode, 0, r.stderr)


class Invariants(unittest.TestCase):
    """Random communities x every preset x random combinations: the hard rules must never break."""

    def world(self, rnd, cfg):
        lv = cfg["levels"]["names"]
        members = {f"m{i}": {"level": rnd.choice(lv)} for i in range(rnd.randint(4, 25))}
        base = datetime(2026, 11, 16)
        slots = [{"id": f"s{d}-{h}", "start": (base + timedelta(days=d, hours=18 + h)).isoformat()}
                 for d in range(rnd.randint(1, 8)) for h in range(rnd.randint(1, 3))]
        apps = []
        for i in range(rnd.randint(1, 60)):
            n = rnd.randint(1, cfg["team"]["max_size"])
            ids = rnd.sample(list(members), min(n, len(members)))
            apps.append({"id": f"a{i}", "slot": rnd.choice(slots)["id"], "members": ids, "ts": f"{i:04d}",
                         "open": rnd.random() < .6, "avoid": rnd.sample(list(members), rnd.randint(0, 2)),
                         "want": rnd.sample(list(members), rnd.randint(0, 2))})
        hist = [{"member": rnd.choice(list(members)), "start": (base - timedelta(days=rnd.randint(1, 20))).isoformat(),
                 "result": rnd.choice(["won", "lost", "played"])} for _ in range(rnd.randint(0, 30))]
        return slots, apps, members, hist

    def check(self, cfg, slots, apps, members, hist, res):
        by_app = {a["id"]: a for a in apps}
        by_slot = {s["id"]: s for s in slots}
        seen = set()
        day, week = {}, {}
        for h in hist:
            if h["result"] in ("won", "played"):
                d = _dt(h["start"])
                day[(h["member"], d.date())] = day.get((h["member"], d.date()), 0) + 1
                week[(h["member"], d.isocalendar()[:2])] = week.get((h["member"], d.isocalendar()[:2]), 0) + 1
        for al in sorted(res["allocations"], key=lambda a: by_slot[a["slot"]]["start"]):
            g = al["members"]
            self.assertLessEqual(len(g), cfg["seats_per_slot"]); self.assertEqual(len(g), len(set(g)))
            self.assertNotIn(al["slot"], seen); seen.add(al["slot"])
            ids = [m for a in al["apps"] for m in by_app[a]["members"]]
            self.assertEqual(sorted(ids), sorted(g))
            if cfg["levels"]["policy"] != "any" and len(al["apps"]) > 1:
                names = cfg["levels"]["names"]
                owner = by_app[al["owner_app"]]["members"]
                for a in al["apps"][1:]:
                    idx = [names.index(members[m]["level"]) for m in owner + by_app[a]["members"]]
                    self.assertLessEqual(max(idx) - min(idx), 0 if cfg["levels"]["policy"] == "same" else cfg["levels"]["max_gap"])
            for a in al["apps"][1:]:
                if cfg["team"]["avoid_lists"]:
                    self.assertFalse(set(by_app[a]["members"]) & set(by_app[al["owner_app"]]["avoid"]))
                    self.assertFalse(set(by_app[a]["avoid"]) & set(by_app[al["owner_app"]]["members"]))
                self.assertTrue(by_app[al["owner_app"]]["open"] and by_app[a]["open"])
            d = _dt(by_slot[al["slot"]]["start"])
            for m in g:
                self.assertLess(day.get((m, d.date()), 0), cfg["caps"]["per_day"])
                self.assertLess(week.get((m, d.isocalendar()[:2]), 0), cfg["caps"]["per_week"])
                day[(m, d.date())] = day.get((m, d.date()), 0) + 1
                week[(m, d.isocalendar()[:2])] = week.get((m, d.isocalendar()[:2]), 0) + 1
        self.assertEqual(verify_published(res)[0], True)

    def test_random(self):
        rnd = random.Random(7)
        profiles = C.presets()
        for it in range(300):
            if it % 2:
                cfg = C.load(rnd.choice(profiles))
            else:
                cfg = C.load({"order": rnd.choice(["weighted_random", "priority_fifo"]),
                              "draw_hours_before": rnd.choice([6, 24, 72, 500]),
                              "team": {"max_size": rnd.randint(1, 4), "allow_open_seats": rnd.random() < .7},
                              "levels": {"policy": rnd.choice(["any", "adjacent", "same"]), "max_gap": rnd.randint(0, 3), "names": rnd.choice([["beginner", "intermediate", "advanced"], LV9])},
                              "caps": {"per_day": rnd.randint(1, 2), "per_week": rnd.randint(1, 4),
                                       "max_applications_week": rnd.randint(1, 6)}})
            slots, apps, members, hist = self.world(rnd, cfg)
            res = run(cfg, slots, apps, members, hist, seed=str(it), now="2026-11-16T12:00")
            self.check(cfg, slots, apps, members, hist, res)


if __name__ == "__main__":
    unittest.main()
