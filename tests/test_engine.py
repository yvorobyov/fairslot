import copy
import unittest
from fairslot import config as C
from fairslot.engine import run, verify_published
from fairslot import substitution as S

SLOTS = [{"id": "s1", "start": "2026-11-20T20:00"}, {"id": "s2", "start": "2026-11-20T21:00"}]
MEM = {f"m{i}": {"level": l} for i, l in enumerate(["beginner", "beginner", "intermediate", "advanced", "advanced", "intermediate"])}


def app(i, slot, members, **kw):
    return {"id": i, "slot": slot, "members": members, "ts": f"{i}", **kw}


class T(unittest.TestCase):
    def cfg(self, **over):
        return C.load(over or None)

    def test_deterministic_and_verifiable(self):
        apps = [app(f"a{i}", "s1", [f"m{i}"], open=True) for i in range(6)]
        r1 = run(self.cfg(), SLOTS, apps, MEM, seed="x", now="2026-11-20T10:00")
        r2 = run(self.cfg(), SLOTS, apps, MEM, seed="x", now="2026-11-20T10:00")
        self.assertEqual(r1, r2)
        self.assertEqual(verify_published(r1), (True, "ok"))
        r1["audit"]["slots"]["s1"][0]["weight"] += 1
        self.assertFalse(verify_published(r1)[0])

    def test_closed_team_gets_no_strangers(self):
        apps = [app("t", "s1", ["m0", "m1"], open=False), app("x", "s1", ["m2"], open=True)]
        r = run(self.cfg(), SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        for al in r["allocations"]:
            if "m0" in al["members"]:
                self.assertEqual(al["members"], ["m0", "m1"])

    def test_avoid_list_respected(self):
        for seed in range(30):
            apps = [app("t", "s1", ["m0"], open=True, avoid=["m1"]), app("x", "s1", ["m1"], open=True),
                    app("y", "s1", ["m2"], open=True)]
            r = run(self.cfg(levels={"policy": "any"}), SLOTS, apps, MEM, seed=str(seed), now="2026-11-20T10:00")
            for al in r["allocations"]:
                self.assertFalse({"m0", "m1"} <= set(al["members"]))

    def test_level_policy(self):
        cfg = self.cfg(levels={"policy": "adjacent"})
        apps = [app("a", "s1", ["m0"], open=True), app("b", "s1", ["m3"], open=True)]  # beginner vs advanced
        r = run(cfg, SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        self.assertEqual(len(r["allocations"][0]["members"]), 1)

    def test_nine_levels_max_gap(self):
        lv = ["D-", "D", "D+", "D+Strong", "C-", "C-Strong", "C", "C+", "C+Strong"]
        mem = {"a": {"level": "D"}, "b": {"level": "D+Strong"}, "c": {"level": "C+Strong"}}
        for gap, expect in [(0, 1), (2, 2), (3, 2), (8, 3)]:
            cfg = C.load({"levels": {"names": lv, "policy": "adjacent", "max_gap": gap}})
            apps = [app("x", "s1", ["a"], open=True), app("y", "s1", ["b"], open=True), app("z", "s1", ["c"], open=True)]
            sizes = [len(al["members"]) for al in run(cfg, SLOTS, apps, mem, seed="1", now="2026-11-20T10:00")["allocations"]]
            self.assertGreaterEqual(sizes[0], 1)
            if gap == 0: self.assertEqual(sizes[0], 1)
            if gap == 8: self.assertEqual(sizes[0], 3)
        with self.assertRaises(ValueError):
            C.load({"levels": {"max_gap": -1}})
        with self.assertRaises(ValueError):
            C.load({"levels": {"names": ["a", "a"]}})

    def test_caps_per_day(self):
        apps = [app("a", "s1", ["m0"]), app("b", "s2", ["m0"])]
        r = run(self.cfg(), SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        self.assertEqual(sum("m0" in a["members"] for a in r["allocations"]), 1)

    def test_horizon(self):
        r = run(self.cfg(draw_hours_before=12), SLOTS, [app("a", "s1", ["m0"])], MEM, seed="1", now="2026-11-18T10:00")
        self.assertEqual(r["not_due"], ["s1", "s2"]); self.assertEqual(r["allocations"], [])

    def test_loss_streak_raises_weight(self):
        hist = [{"member": "m0", "start": f"2026-11-1{i}T20:00", "result": "lost"} for i in range(3)]
        wins = 0
        for seed in range(400):
            apps = [app("a", "s1", ["m0"]), app("b", "s1", ["m1"])]
            r = run(self.cfg(), SLOTS, apps, MEM, hist, seed=str(seed), now="2026-11-20T10:00")
            wins += r["allocations"][0]["owner_app"] == "a"
        self.assertGreater(wins, 220)

    def test_fifo_no_randomness(self):
        apps = [app("b", "s1", ["m1"], ts="2"), app("a", "s1", ["m0"], ts="1")]
        r = run(self.cfg(order="priority_fifo"), SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        self.assertEqual(r["allocations"][0]["owner_app"], "a")

    def test_team_too_large_and_unknown_slot(self):
        apps = [app("a", "s1", ["m0", "m1", "m2", "m3", "m4"]), app("b", "zzz", ["m0"])]
        r = run(self.cfg(), SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        self.assertEqual({x["reason"] for x in r["rejected"]}, {"team too large", "unknown slot"})

    def test_swap_owner_picks_and_frozen(self):
        cfg = self.cfg()
        al = {"slot": "s1", "members": ["m0", "m1"], "avoid": ["m5"], "open_seats": 0}
        s = SLOTS[0]
        self.assertTrue(S.check_swap(cfg, al, s, "m1", "m2", MEM, "2026-11-20T10:00")[0])
        self.assertFalse(S.check_swap(cfg, al, s, "m1", "m5", MEM, "2026-11-20T10:00")[0])   # avoided
        self.assertFalse(S.check_swap(cfg, al, s, "m1", "m3", MEM, "2026-11-20T10:00")[0])   # level
        self.assertFalse(S.check_swap(cfg, al, s, "m1", "m2", MEM, "2026-11-20T18:30")[0])   # frozen
        self.assertFalse(S.check_swap(C.load({"substitution": {"policy": "none"}}), al, s, "m1", "m2", MEM, "2026-11-20T10:00")[0])

    def test_market(self):
        cfg = self.cfg()
        al = [{"slot": "s1", "members": ["m0"], "open_seats": 3, "avoid": []}]
        by = {s["id"]: s for s in SLOTS}
        self.assertEqual(S.market_seats(cfg, al, by, "2026-11-20T10:00"), [])
        self.assertEqual(len(S.market_seats(cfg, al, by, "2026-11-20T15:00")), 1)
        ok, _ = S.claim_seat(cfg, al[0], SLOTS[0], "m1", MEM, "2026-11-20T15:00")
        self.assertTrue(ok)

    def test_all_presets_load_and_run(self):
        for p in C.presets():
            cfg = C.load(p)
            apps = [app(f"a{i}", "s1", [f"m{i}"], open=True) for i in range(5)]
            run(cfg, SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            C.load({"levels": {"policy": "nope"}})
        with self.assertRaises(ValueError):
            C.load({"team": {"max_size": 9}})

    def test_inputs_not_mutated(self):
        apps = [app("a", "s1", ["m0"])]
        before = copy.deepcopy(apps)
        run(self.cfg(), SLOTS, apps, MEM, seed="1", now="2026-11-20T10:00")
        self.assertEqual(apps, before)


if __name__ == "__main__":
    unittest.main()
