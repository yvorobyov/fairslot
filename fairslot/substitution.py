"""What happens AFTER the draw: swaps, cancellations and open seats.

The draw decides who gets a slot. Real groups change their minds, so this module gives the
slot holder control (policy "owner_picks") instead of pushing a stranger from a waitlist
onto the group.  Every function returns (ok, reason) or a ranked list; nothing mutates state
except the explicit apply_* helpers.
"""
from datetime import datetime, timedelta

from .engine import _dt, levels_ok, pool_ok


def _frozen(cfg, slot, now):
    return _dt(slot["start"]) - _dt(now) < timedelta(hours=cfg["substitution"]["change_deadline_hours"])


def check_swap(cfg, allocation, slot, out_member, in_member, members, now,
               in_consents=True, group_approves=True):
    """May `in_member` replace `out_member` in this allocation?"""
    sub = cfg["substitution"]
    if sub["policy"] == "none":
        return False, "substitutions are disabled"
    if _frozen(cfg, slot, now):
        return False, "group is frozen (too close to the start)"
    if out_member not in allocation["members"]:
        return False, "member is not in this group"
    if in_member in allocation["members"]:
        return False, "already in the group"
    if not in_consents:
        return False, "replacement has not accepted"
    if sub["policy"] == "waitlist_opt_in" and not group_approves:
        return False, "group has not approved"
    rest = [m for m in allocation["members"] if m != out_member]
    if in_member in allocation.get("avoid", []):
        return False, "avoided by the holder"
    if not levels_ok(cfg, members, rest + [in_member]):
        return False, "level mismatch"
    if not pool_ok(slot, members, [in_member]):
        return False, "outside the slot's level pool"
    return True, "ok"


def apply_swap(allocation, out_member, in_member):
    allocation["members"] = [in_member if m == out_member else m for m in allocation["members"]]
    return allocation


def waitlist_candidates(cfg, allocation, slot, waitlist_members, members, now):
    """Ranked waitlist people who could legally join (order = their draw order)."""
    out = []
    for m in waitlist_members:
        ok, _ = check_swap(cfg, allocation, slot, allocation["members"][-1], m, members, now,
                           True, True)
        if ok:
            out.append(m)
    return out


def market_seats(cfg, allocations, slots_by_id, now):
    """Open seats that become first-come once late_release_hours is reached."""
    rel = timedelta(hours=cfg["substitution"]["late_release_hours"])
    out = []
    for al in allocations:
        if al["open_seats"] > 0 and _dt(slots_by_id[al["slot"]]["start"]) - _dt(now) <= rel:
            out.append({"slot": al["slot"], "seats": al["open_seats"]})
    return out


def claim_seat(cfg, allocation, slot, member, members, now):
    """First-come claim of an open seat on the market."""
    if allocation["open_seats"] <= 0:
        return False, "no open seats"
    if _frozen(cfg, slot, now):
        return False, "group is frozen"
    if member in allocation["members"]:
        return False, "already in the group"
    if member in allocation.get("avoid", []):
        return False, "avoided by the holder"
    if cfg["substitution"]["market_requires_level_fit"] and not levels_ok(
            cfg, members, allocation["members"] + [member]):
        return False, "level mismatch"
    if not pool_ok(slot, members, [member]):
        return False, "outside the slot's level pool"
    return True, "ok"


def apply_claim(allocation, member):
    allocation["members"].append(member)
    allocation["open_seats"] -= 1
    return allocation
