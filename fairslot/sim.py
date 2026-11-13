"""Monte Carlo comparison of profiles on a synthetic community. Not a promise about your
community: change the numbers in `Scenario` to match it, then compare profiles."""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import config as C
from .engine import run


@dataclass
class Scenario:
    residents: int = 50
    heavy_share: float = 0.15       # people who apply almost every day
    weeks: int = 4
    slots_per_day: int = 4          # prime-time slots (x courts)
    courts: int = 2
    team_share: float = 0.4         # share of applicants who apply as ready-made teams
    open_share: float = 0.7         # share of teams / singles that accept strangers
    start: str = "2026-11-16T00:00"


def _population(sc, rnd):
    names = ["beginner", "intermediate", "advanced"]
    members = {f"m{i}": {"level": rnd.choices(names, [0.3, 0.5, 0.2])[0]} for i in range(sc.residents)}
    heavy = set(rnd.sample(list(members), max(1, int(sc.residents * sc.heavy_share))))
    return members, heavy


def simulate(profile, sc=None, seed=1):
    sc = sc or Scenario()
    cfg = C.load(profile)
    rnd = random.Random(seed)
    members, heavy = _population(sc, rnd)
    history, wins, applied, mixed_groups, groups, filled, seats = [], {m: 0 for m in members}, {m: 0 for m in members}, 0, 0, 0, 0
    day0 = datetime.fromisoformat(sc.start)
    for day in range(sc.weeks * 7):
        d = day0 + timedelta(days=day)
        slots = [{"id": f"{d.date()}T{19 + h:02d}:00-c{c}", "start": (d + timedelta(hours=19 + h)).isoformat(),
                  "resource": f"c{c}"} for h in range(sc.slots_per_day) for c in range(sc.courts)]
        apps, n = [], 0
        for m in members:
            p = 0.8 if m in heavy else 0.08
            if rnd.random() > p:
                continue
            slot = rnd.choice(slots)
            grp = [m]
            if rnd.random() < sc.team_share:
                grp += rnd.sample([x for x in members if x != m], rnd.randint(1, 2))
            n += 1
            apps.append({"id": f"a{day}-{n}", "slot": slot["id"], "members": grp, "ts": f"{day:03d}-{n:03d}",
                         "open": rnd.random() < sc.open_share})
            for g in grp:
                applied[g] += 1
        now = d + timedelta(hours=18)
        res = run(cfg, slots, apps, members, history, seed=f"s{seed}-{day}", now=now)
        for al in res["allocations"]:
            groups += 1
            seats += cfg["seats_per_slot"]
            filled += len(al["members"])
            lv = {members[m]["level"] for m in al["members"]}
            mixed_groups += len(lv) > 1
            for m in al["members"]:
                wins[m] += 1
                history.append({"member": m, "start": next(s["start"] for s in slots if s["id"] == al["slot"]),
                                "result": "won"})
        won_apps = {a for al in res["allocations"] for a in al["apps"]}
        for a in apps:
            if a["id"] not in won_apps:
                for m in a["members"]:
                    history.append({"member": m, "start": slots[0]["start"], "result": "lost"})
    actives = [m for m in members if applied[m]]
    never = sum(1 for m in actives if wins[m] == 0)
    vals = sorted(wins[m] for m in actives) or [0]
    tot = sum(vals) or 1
    gini = sum((2 * (i + 1) - len(vals) - 1) * v for i, v in enumerate(vals)) / (len(vals) * tot)
    return {"profile": profile if isinstance(profile, str) else "custom",
            "active_people": len(actives), "never_won_%": round(100 * never / max(1, len(actives)), 1),
            "gini_of_wins": round(gini, 3), "seat_fill_%": round(100 * filled / max(1, seats), 1),
            "mixed_level_groups_%": round(100 * mixed_groups / max(1, groups), 1), "games": groups}


def compare(profiles=None, sc=None, seeds=3):
    rows = []
    for p in profiles or C.presets():
        rs = [simulate(p, sc, s) for s in range(1, seeds + 1)]
        avg = {k: round(sum(r[k] for r in rs) / len(rs), 3) for k in rs[0] if k != "profile"}
        avg["profile"] = p
        rows.append(avg)
    return rows
