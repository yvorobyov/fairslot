import argparse
import json
import sys

from . import config as C
from .adapters import csv_backend as B
from .adapters import links
from .engine import run, verify_published
from . import sim
from . import sources
from . import server


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
    f = sp.add_parser("fetch", help="download applications from a workspace source into CSV files")
    f.add_argument("--workspace", default="fairslot-workspace.json"); f.add_argument("--out", default=".")
    au = sp.add_parser("auto", help="fetch + draw + links in one command (for schedules and scripts)")
    au.add_argument("--workspace", default="fairslot-workspace.json"); au.add_argument("--out", default="result.json")
    au.add_argument("--seed"); au.add_argument("--now")
    ap_ = sp.add_parser("app", help="open the page with automatic loading from your apps")
    ap_.add_argument("--port", type=int, default=8765); ap_.add_argument("--workspace", default="fairslot-workspace.json")
    ap_.add_argument("--no-browser", action="store_true")
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
    elif a.cmd == "app":
        server.serve(a.port, a.workspace, not a.no_browser)
    elif a.cmd in ("fetch", "auto"):
        ws = server.load_workspace(a.workspace)
        try:
            inp = server.fetch_for_page(ws.get("source") or {}, ws)
        except sources.SourceError as e:
            print("ERROR:", e, file=sys.stderr); return 2
        for w in inp["warnings"]:
            print("warning:", w, file=sys.stderr)
        if a.cmd == "fetch":
            import os
            os.makedirs(a.out, exist_ok=True)
            for k, name in (("slots", "slots.csv"), ("apps", "applications.csv"), ("members", "members.csv")):
                with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="") as fh:
                    fh.write(inp["csv"][k])
            print("%d applications, %d slots -> %s" % (inp["counts"]["applications"], inp["counts"]["slots"], a.out))
        else:
            from datetime import datetime
            cfg = C.load(ws.get("profile"))
            now = a.now or ws.get("now") or datetime.now().strftime("%Y-%m-%dT%H:%M")
            seed = a.seed or ws.get("seed") or sources.auto_seed(inp["applications"], inp["slots"], now)
            res = run(cfg, inp["slots"], inp["applications"], inp["members"], [], seed=seed, now=now)
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=1)
            print("seed:", seed)
            for al in res["allocations"]:
                print(al["slot"], ", ".join(al["members"]))
            if ws.get("link_template"):
                for row in links.render(res, inp["slots"], ws["link_template"]):
                    print(row["slot"], row["url"])
    elif a.cmd == "sim":
        rows = sim.compare(a.profiles, sim.Scenario(residents=a.residents, weeks=a.weeks), a.seeds)
        cols = ["profile", "never_won_%", "gini_of_wins", "seat_fill_%", "mixed_level_groups_%", "games"]
        print(" | ".join(f"{c:>20}" for c in cols))
        for r_ in rows:
            print(" | ".join(f"{r_[c]:>20}" for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
