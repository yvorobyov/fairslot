"""Allocation engine. Pure functions, standard library only, deterministic for a given seed.

Data shapes (plain dicts, so any front-end can produce them):

slot         {"id": "2026-11-20T20:00-c1", "start": "2026-11-20T20:00", "end": "...",
              "resource": "court1", "levels": ["intermediate","advanced"]  # optional pool}
member       {"level": "intermediate"}                       (members: {member_id: {...}})
application  {"id": "a1", "slot": <slot id>, "members": ["m1","m2"], "open": true,
              "avoid": ["m9"], "want": ["m3"], "ts": "2026-11-17T09:00"}
history      [{"member": "m1", "start": "2026-11-10T20:00", "result": "won"|"played"|"lost"}]
"""
import hashlib
import re
import json
from datetime import datetime, timedelta


# ---------------------------------------------------------------- helpers
def _dt(s):
    """Parse ISO-8601 on every supported Python (3.9's fromisoformat rejects 'Z' and spaces)."""
    if isinstance(s, datetime):
        return s
    s = str(s).strip().replace(" ", "T", 1)
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    return d.replace(tzinfo=None) if d.tzinfo else d  # compare as wall-clock time


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def draw_key(seed, slot_id, app_id, weight):
    """Efraimidis-Spirakis key: u ** (1/weight). Larger key wins. Anyone can recompute it."""
    h = hashlib.sha256(f"{seed}|{slot_id}|{app_id}".encode()).digest()
    u = (int.from_bytes(h[:8], "big") + 1) / (2 ** 64 + 1)
    return u ** (1.0 / weight)


def member_weight(cfg, member, history, now):
    w = cfg["weights"]
    start = now - timedelta(days=w["window_days"])
    mine = sorted((h for h in history if h["member"] == member), key=lambda h: h["start"])
    recent_wins = sum(1 for h in mine if h["result"] in ("won", "played") and _dt(h["start"]) >= start)
    streak = 0
    for h in reversed(mine):
        if h["result"] == "lost":
            streak += 1
        else:
            break
    val = w["base"] / (1 + w["recent_win_penalty"] * recent_wins) * (1 + w["loss_streak_boost"] * streak)
    return max(w["min"], min(w["max"], val))


_CYR, _LAT = "АВЕКМНОРСТХУаеорсух", "ABEKMHOPCTXYaeopcyx"
_LOOK = {ord(a): b for a, b in zip(_CYR, _LAT)}


def norm_level(s):
    """Level labels are compared forgivingly: case, spaces, 5.0 = 5, Cyrillic look-alike letters (С = C)."""
    s = str(s or "").strip().translate(_LOOK).lower().replace("ё", "е").replace(",", ".")
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"^(-?\d+)\.0+$", r"\1", s)


def levels_ok(cfg, members, ids):
    pol = cfg["levels"]["policy"]
    if pol == "any":
        return True
    pos = {norm_level(n): i for i, n in enumerate(cfg["levels"]["names"])}
    idx = []
    for m in ids:
        lv = norm_level(members.get(m, {}).get("level"))
        if lv not in pos:
            return False if pol == "same" else True  # unknown level: lenient for adjacent
        idx.append(pos[lv])
    spread = max(idx) - min(idx) if idx else 0
    return spread <= (0 if pol == "same" else cfg["levels"].get("max_gap", 1))


def pool_ok(slot, members, ids):
    pool = slot.get("levels")
    pool = {norm_level(x) for x in (pool or [])}
    return not pool or all(norm_level(members.get(m, {}).get("level")) in pool for m in ids)


# ---------------------------------------------------------------- main
def run(cfg, slots, applications, members, history=None, seed="", now=None):
    history = history or []
    slots = sorted(slots, key=lambda s: (s["start"], s["id"]))
    slot_by_id = {s["id"]: s for s in slots}
    now = _dt(now) if now else (_dt(slots[0]["start"]) if slots else datetime.now())
    caps = cfg["caps"]
    team = cfg["team"]
    rejected, not_due = [], []

    # --- per-member counters from history (day / ISO week)
    day_n, week_n = {}, {}

    def bump(m, start):
        d = _dt(start)
        day_n[(m, d.date())] = day_n.get((m, d.date()), 0) + 1
        wk = d.isocalendar()[:2]
        week_n[(m, wk)] = week_n.get((m, wk), 0) + 1

    for h in history:
        if h["result"] in ("won", "played"):
            bump(h["member"], h["start"])

    # --- validate applications
    apps, per_week_apps = [], {}
    for a in sorted(applications, key=lambda a: (a.get("ts", ""), a["id"])):
        a = dict(a)
        a.setdefault("members", [a.get("member")])
        a.setdefault("open", False)
        a.setdefault("avoid", [])
        a.setdefault("want", [])
        s = slot_by_id.get(a["slot"])
        if s is None:
            rejected.append({"app": a["id"], "reason": "unknown slot"}); continue
        if len(a["members"]) > team["max_size"]:
            rejected.append({"app": a["id"], "reason": "team too large"}); continue
        if len(set(a["members"])) != len(a["members"]):
            rejected.append({"app": a["id"], "reason": "duplicate member"}); continue
        if not team["avoid_lists"]:
            a["avoid"] = []
        if not team["want_lists"]:
            a["want"] = []
        if not team["allow_open_seats"]:
            a["open"] = False
        if not pool_ok(s, members, a["members"]):
            rejected.append({"app": a["id"], "reason": "level pool"}); continue
        wk = _dt(s["start"]).isocalendar()[:2]
        over = False
        for m in a["members"]:
            per_week_apps[(m, wk)] = per_week_apps.get((m, wk), 0) + 1
            if per_week_apps[(m, wk)] > caps["max_applications_week"]:
                over = True
        if over:
            rejected.append({"app": a["id"], "reason": "too many applications this week"}); continue
        apps.append(a)

    wcache = {}

    def weight(a):
        if a["id"] not in wcache:
            ws = [member_weight(cfg, m, history, now) for m in a["members"]]
            wcache[a["id"]] = sum(ws) / len(ws)
        return wcache[a["id"]]

    def can_play(m, start):
        d = _dt(start)
        return (day_n.get((m, d.date()), 0) < caps["per_day"]
                and week_n.get((m, d.isocalendar()[:2]), 0) < caps["per_week"])

    allocations, waitlist, audit_slots = [], {}, {}
    allocated_apps = set()
    horizon = timedelta(hours=cfg["draw_hours_before"])

    for s in slots:
        if _dt(s["start"]) - now > horizon:
            not_due.append(s["id"]); continue
        elig = [a for a in apps if a["slot"] == s["id"] and a["id"] not in allocated_apps
                and all(can_play(m, s["start"]) for m in a["members"])]
        if cfg["order"] == "weighted_random":
            keyed = [(draw_key(seed, s["id"], a["id"], weight(a)), a) for a in elig]
            keyed.sort(key=lambda t: (-t[0], t[1]["id"]))
        else:
            keyed = [(0.0, a) for a in sorted(elig, key=lambda a: (-weight(a), a.get("ts", ""), a["id"]))]
        audit_slots[s["id"]] = [{"app": a["id"], "weight": weight(a), "key": k} for k, a in keyed]
        if not keyed:
            continue
        win = keyed[0][1]
        group, group_apps = list(win["members"]), [win["id"]]
        avoid = set(win["avoid"])
        allocated_apps.add(win["id"])
        # --- top up open seats from other open applicants (never forced on a closed team)
        if win["open"]:
            def pref(item):
                k, a = item
                liked = bool(set(a["members"]) & set(win["want"])) or bool(set(a["want"]) & set(group))
                return (0 if liked else 1, -k) if cfg["order"] == "weighted_random" else (0 if liked else 1, 0)
            for k, a in sorted(keyed[1:], key=pref):
                if len(group) >= cfg["seats_per_slot"] or not a["open"]:
                    continue
                if len(group) + len(a["members"]) > cfg["seats_per_slot"] or set(a["members"]) & set(group):
                    continue
                if (avoid & set(a["members"])) or (set(a["avoid"]) & set(group)):
                    continue
                if not levels_ok(cfg, members, group + a["members"]):
                    continue
                group += a["members"]; group_apps.append(a["id"]); avoid |= set(a["avoid"])
                allocated_apps.add(a["id"])
        for m in group:
            bump(m, s["start"])
        allocations.append({
            "slot": s["id"], "members": group, "apps": group_apps,
            "owner_app": win["id"], "avoid": sorted(avoid),
            "open_seats": cfg["seats_per_slot"] - len(group) if win["open"] else 0,
        })
        waitlist[s["id"]] = [a["id"] for k, a in keyed if a["id"] not in allocated_apps] if cfg["waitlist"] != "none" else []

    return {
        "allocations": allocations, "waitlist": waitlist, "rejected": rejected, "not_due": not_due,
        "audit": {
            "seed": seed, "now": now.isoformat(), "order": cfg["order"],
            "config_sha256": _sha(cfg),
            "inputs_sha256": _sha({"slots": slots, "applications": applications, "history": history}),
            "slots": audit_slots,
        },
    }


# ---------------------------------------------------------------- verification
def verify_published(result):
    """Check a published result WITHOUT any private data: recompute every draw key from the
    seed + ids + published weights and make sure the published order is the sorted one."""
    a = result["audit"]
    if a["order"] != "weighted_random":
        return True, "priority order has no randomness to verify"
    for slot_id, rows in a["slots"].items():
        for r in rows:
            exp = draw_key(a["seed"], slot_id, r["app"], r["weight"])
            if abs(exp - r["key"]) > 1e-12:
                return False, f"key mismatch for {r['app']} on {slot_id}"
        keys = [r["key"] for r in rows]
        if keys != sorted(keys, reverse=True):
            return False, f"order of {slot_id} is not sorted by key"
    for al in result["allocations"]:
        rows = a["slots"].get(al["slot"], [])
        if rows and rows[0]["app"] != al["owner_app"]:
            return False, f"winner of {al['slot']} is not the top key"
    return True, "ok"
