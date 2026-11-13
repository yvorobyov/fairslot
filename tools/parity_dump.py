"""Generate random worlds + the Python engine's answers, so the JS engine can be checked against them."""
import json, random, sys
from datetime import datetime, timedelta
sys.path.insert(0, ".")
from fairslot import config as C
from fairslot.engine import run
rnd = random.Random(11); out = []
for it in range(400):
    cfg = C.load(rnd.choice(C.presets())) if it % 2 else C.load({"order": rnd.choice(["weighted_random", "priority_fifo"]), "draw_hours_before": rnd.choice([6, 24, 72, 500]),
        "team": {"max_size": rnd.randint(1, 4), "allow_open_seats": rnd.random() < .7, "avoid_lists": rnd.random() < .8, "want_lists": rnd.random() < .8},
        "levels": {"policy": rnd.choice(["any", "adjacent", "same"]), "max_gap": rnd.randint(0, 3), "names": rnd.choice([["beginner", "intermediate", "advanced"], ["D-", "D", "D+", "D+Strong", "C-", "C-Strong", "C", "C+", "C+Strong"]])}, "caps": {"per_day": rnd.randint(1, 2), "per_week": rnd.randint(1, 4), "max_applications_week": rnd.randint(1, 6)}})
    lv = cfg["levels"]["names"]; mem = {f"m{i}": {"level": rnd.choice(lv)} for i in range(rnd.randint(4, 25))}
    base = datetime(2026, 11, 16)
    slots = [{"id": f"s{d}-{h}", "start": (base + timedelta(days=d, hours=18 + h)).isoformat(timespec="minutes")} for d in range(rnd.randint(1, 9)) for h in range(rnd.randint(1, 3))]
    for s in slots:
        if rnd.random() < .15: s["levels"] = rnd.sample(lv, 2)
    apps = []
    for i in range(rnd.randint(1, 70)):
        ids = rnd.sample(list(mem), min(rnd.randint(1, 4), len(mem)))
        apps.append({"id": f"a{i}", "slot": rnd.choice(slots)["id"], "members": ids, "ts": f"{rnd.randint(0,50):04d}", "open": rnd.random() < .6,
                     "avoid": rnd.sample(list(mem), rnd.randint(0, 2)), "want": rnd.sample(list(mem), rnd.randint(0, 2))})
    hist = [{"member": rnd.choice(list(mem)), "start": (base - timedelta(days=rnd.randint(1, 30))).isoformat(timespec="minutes"), "result": rnd.choice(["won", "lost", "played"])} for _ in range(rnd.randint(0, 40))]
    now = "2026-11-16T12:00"; seed = f"seed{it}"
    res = run(cfg, slots, apps, mem, hist, seed=seed, now=now)
    out.append({"cfg": cfg, "slots": slots, "apps": apps, "mem": mem, "hist": hist, "seed": seed, "now": now, "res": res})
json.dump(out, open(sys.argv[1], "w"))
print(len(out), "worlds")
