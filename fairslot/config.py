"""Configuration: every rule of the allocation lives here, nothing is hard-coded.

A *profile* is a JSON file that overrides DEFAULTS. See fairslot/presets/*.json.
"""
import copy
import json
import os
import re

DEFAULTS = {
    # How applicants are ordered for a slot.
    #   "weighted_random" - seeded, publicly verifiable draw (weights from history)
    #   "priority_fifo"   - no randomness: weight first, then application time
    "order": "weighted_random",
    # Hours before slot start when the draw is allowed to run (a short horizon
    # means people do not have to know their plans 3 days ahead).
    "draw_hours_before": 72,
    "seats_per_slot": 4,
    "team": {
        "max_size": 4,            # 1 = pure individual lottery
        "allow_open_seats": True,  # a team may flag free seats as open to others
        "avoid_lists": True,       # "do not put me with X" (checked at group formation)
        "want_lists": True,        # "prefer X" (soft: used as tie-break when filling)
    },
    "levels": {
        "names": ["beginner", "intermediate", "advanced"],
        # any      - levels are ignored
        # adjacent - everyone in a group is at most one step apart
        # same     - everyone in a group has the same level
        "policy": "adjacent",
        # for policy "adjacent": how many steps apart players in one group may be
        # (names are ordered weakest to strongest; list them as your community grades them)
        "max_gap": 1,
    },
    "caps": {"per_day": 1, "per_week": 3, "max_applications_week": 3},
    "weights": {
        "base": 1.0,
        "recent_win_penalty": 0.5,   # weight /= 1 + penalty * wins in window
        "loss_streak_boost": 0.25,   # weight *= 1 + boost * consecutive losses
        "min": 0.2,
        "max": 4.0,
        "window_days": 28,
    },
    "substitution": {
        # owner_picks     - whoever holds the slot names the replacement
        # waitlist_opt_in - replacement comes from the waitlist, group approves
        # waitlist_auto   - first compatible waitlisted person is added
        # none            - no substitutions
        "policy": "owner_picks",
        "change_deadline_hours": 3,   # after this, the group is frozen
        "late_release_hours": 6,      # unfilled open seats go to a first-come market
        "market_requires_level_fit": True,
    },
    "waitlist": "opt_in",  # none | opt_in | auto
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out



def parse_levels(spec):
    """Level scale from a list, a comma list ("D, C, B") or a range ("1-7", "1-100", "1-5 step 0.5")."""
    if isinstance(spec, (list, tuple)):
        return [str(x).strip() for x in spec if str(x).strip()]
    s = str(spec or "").strip()
    if not s:
        return []
    if re.search(r"[,;|]", s):
        return [x.strip() for x in re.split(r"[,;|]", s) if x.strip()]
    L = re.fullmatch(r"([A-Za-zА-Яа-я])\s*(?:-|–|—|\.\.|to|до)\s*([A-Za-zА-Яа-я])", s, re.I)
    if L:
        a, b = ord(L.group(1)), ord(L.group(2))
        if b < a or b - a > 50:
            raise ValueError("levels range must go up")
        return [chr(c) for c in range(a, b + 1)]
    m = re.fullmatch(r"(-?(?:\d+(?:[.,]\d+)?|[.,]\d+))\s*(?:-|–|—|\.\.|to|до)\s*(-?(?:\d+(?:[.,]\d+)?|[.,]\d+))(?:\s*(?:step|by|шаг)\s*((?:\d+(?:[.,]\d+)?|[.,]\d+)))?", s, re.I)
    if not m:
        return s.split()
    lo, hi = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    step = float((m.group(3) or "1").replace(",", "."))
    if step <= 0 or hi < lo or (hi - lo) / step > 999:
        raise ValueError("levels range must go up, with a positive step and at most 1000 levels")
    n = int((hi - lo) / step + 1e-9) + 1
    fmt = lambda v: str(int(round(v))) if abs(v - round(v)) < 1e-9 else ("%g" % round(v, 6))
    return [fmt(lo + i * step) for i in range(n)]


def _normalize(cfg):
    lv = cfg["levels"]
    lv["names"] = parse_levels(lv["names"])
    if lv.get("max_gap") in ("auto", None):
        lv["max_gap"] = max(1, int(round(len(lv["names"]) / 5.0)))
    return cfg


def validate(cfg):
    errs = []
    if cfg["order"] not in ("weighted_random", "priority_fifo"):
        errs.append("order must be weighted_random or priority_fifo")
    if cfg["levels"]["policy"] not in ("any", "adjacent", "same"):
        errs.append("levels.policy must be any|adjacent|same")
    g = cfg["levels"]["max_gap"]
    if not isinstance(g, int) or isinstance(g, bool) or g < 0:
        errs.append("levels.max_gap must be a whole number >= 0")
    if len(set(cfg["levels"]["names"])) != len(cfg["levels"]["names"]):
        errs.append("levels.names must be unique")
    if cfg["substitution"]["policy"] not in ("owner_picks", "waitlist_opt_in", "waitlist_auto", "none"):
        errs.append("substitution.policy invalid")
    if cfg["waitlist"] not in ("none", "opt_in", "auto"):
        errs.append("waitlist invalid")
    if not 1 <= cfg["team"]["max_size"] <= cfg["seats_per_slot"]:
        errs.append("team.max_size must be between 1 and seats_per_slot")
    if cfg["weights"]["min"] <= 0 or cfg["weights"]["min"] > cfg["weights"]["max"]:
        errs.append("weights.min must be >0 and <= weights.max")
    if errs:
        raise ValueError("; ".join(errs))
    return cfg


def load(profile=None):
    """profile: None, a dict, a path to a JSON file, or the name of a preset."""
    if profile is None:
        return validate(_normalize(copy.deepcopy(DEFAULTS)))
    if isinstance(profile, dict):
        return validate(_normalize(_merge(DEFAULTS, profile)))
    path = profile
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "presets", profile + ".json")
    with open(path, encoding="utf-8") as f:
        return validate(_normalize(_merge(DEFAULTS, json.load(f))))


def presets():
    d = os.path.join(os.path.dirname(__file__), "presets")
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))
