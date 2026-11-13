"""Read/write plain CSV: works with Google Forms/Sheets exports, Excel, or a hand-made list."""
import csv
import re


def _list(v):
    return [x.strip() for x in re.split(r"[;|,]", v or "") if x.strip()]


def _bool(v):
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "да")


def read_slots(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{"id": r["id"], "start": r["start"], "end": r.get("end", ""),
                 "resource": r.get("resource", ""), **({"levels": _list(r["levels"])} if r.get("levels") else {})}
                for r in csv.DictReader(f)]


def read_members(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["id"]: {"level": r.get("level", ""), "name": r.get("name", "")} for r in csv.DictReader(f)}


def read_applications(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{"id": r["id"], "slot": r["slot"], "members": _list(r["members"]), "open": _bool(r.get("open")),
                 "avoid": _list(r.get("avoid")), "want": _list(r.get("want")), "ts": r.get("ts", "")}
                for r in csv.DictReader(f)]


def read_history(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{"member": r["member"], "start": r["start"], "result": r["result"]} for r in csv.DictReader(f)]


def write_allocations(path, result):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["slot", "members", "open_seats"])
        for a in result["allocations"]:
            w.writerow([a["slot"], ";".join(a["members"]), a["open_seats"]])
