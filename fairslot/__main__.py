import argparse
import json
import sys

from . import config as C
from .adapters import csv_backend as B
from .adapters import links
from .engine import run, verify_published
from . import sim


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fairslot", description="Configurable, verifiable slot allocation")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("presets", help="list built-in profiles")
    r = sp.add_parser("run", help="run a draw from CSV files")
    r.add_argument("--profile", default=None, help="preset name or path to a JSON profile")
    r.add_argument("--slots", required=True); r.add_argument("--apps", required=True)
    r.add_argument("--members", required=True); r.add_argument("--history")
    r.add_argument("--seed", required=True, help="PUBLIC seed, announced before applications close")
    r.add_argument("--now"); r.add_argument("--out", default="result.json")
    r.add_argument("--csv"); r.add_argument("--link-template")
    v = sp.add_parser("verify", help="verify a published result.json with no private data")
    v.add_argument("result")
    s = sp.add_parser("sim", help="compare profiles on a synthetic community")
    s.add_argument("--profiles", nargs="*"); s.add_argument("--residents", type=int, default=50)
    s.add_argument("--weeks", type=int, default=4); s.add_argument("--seeds", type=int, default=3)
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:
            pass
    a = ap.parse_args(argv)
    if a.cmd == "presets":
        for p in C.presets():
            print(f"{p:18} {C.load(p).get('_about', '')}")
    elif a.cmd == "run":
        cfg = C.load(a.profile)
        slots = B.read_slots(a.slots)
        res = run(cfg, slots, B.read_applications(a.apps), B.read_members(a.members),
                  B.read_history(a.history) if a.history else [], seed=a.seed, now=a.now)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        if a.csv:
            B.write_allocations(a.csv, res)
        if a.link_template:
            for row in links.render(res, slots, a.link_template):
                print(row["slot"], row["url"])
        print(f"{len(res['allocations'])} groups -> {a.out}", file=sys.stderr)
    elif a.cmd == "verify":
        with open(a.result, encoding="utf-8-sig") as f:
            ok, why = verify_published(json.load(f))
        print("OK" if ok else "FAILED", why); return 0 if ok else 1
    elif a.cmd == "sim":
        rows = sim.compare(a.profiles, sim.Scenario(residents=a.residents, weeks=a.weeks), a.seeds)
        cols = ["profile", "never_won_%", "gini_of_wins", "seat_fill_%", "mixed_level_groups_%", "games"]
        print(" | ".join(f"{c:>20}" for c in cols))
        for r_ in rows:
            print(" | ".join(f"{r_[c]:>20}" for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
