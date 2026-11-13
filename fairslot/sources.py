"""Automatic import of applications from the tools people already use.

Every source is turned into the same neutral *records*, then into the engine inputs
(slots, applications, members). Standard library only; nothing is written to the source.

Source types (the `type` field of a source spec):
  csv_url       any CSV by link. Google Sheets links are converted automatically.
  google_sheet  same as csv_url (a Google Sheets link, shared "anyone with the link can view")
  ics_url       any calendar feed (.ics): Google Calendar, Outlook, Apple, Cal.com, Calendly feeds
  calendly      Calendly API v2, read-only, personal access token
  json_url      a JSON list of objects by link, columns detected like a CSV
  csv_text      CSV pasted as text (used by the browser page)
"""
import csv
import hashlib
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

# Column names people use, in several languages. Matching ignores case and punctuation.
SYNONYMS = {
    "who": ["email", "e-mail", "invitee email", "почта", "эл почта", "электронная почта", "name", "invitee name", "имя", "ник", "player", "игрок", "member", "id"],
    "name": ["name", "invitee name", "имя", "фио", "full name"],
    "start": ["start", "start date time", "start date & time", "start time", "event start", "datetime", "date time", "дата и время", "начало", "slot", "слот", "date", "дата"],
    "time": ["time", "время"],
    "resource": ["event type", "event type name", "court", "корт", "resource", "ресурс", "location", "площадка", "event name", "event"],
    "partners": ["partners", "partner", "guests", "guest", "+1", "напарник", "напарники", "партнер", "партнёр", "гости", "с кем", "team", "команда"],
    "open": ["open", "открыто", "открытые места", "accept strangers"],
    "avoid": ["avoid", "не ставить", "не хочу играть с"],
    "want": ["want", "хочу играть с", "prefer"],
    "ts": ["ts", "timestamp", "отметка времени", "created", "created at", "invitee created at", "booked at", "время подачи"],
    "level": ["level", "уровень", "grade"],
}
YES = {"1", "true", "yes", "y", "да", "д", "+", "ok", "ок"}


class SourceError(Exception):
    """Message is written for the person running the draw."""


def _norm(s):
    return re.sub(r"[^\w+&]+", " ", str(s or "").strip().lower()).strip()


def guess_mapping(headers):
    """Map our fields to the headers found in a table. Returns {field: header}."""
    nh = {h: _norm(h) for h in headers}
    out = {}
    for field, names in SYNONYMS.items():
        for want in names:  # earlier synonyms win
            hit = [h for h, n in nh.items() if n == _norm(want) and h not in out.values()]
            if hit:
                out[field] = hit[0]
                break
    return out


# ------------------------------------------------------------------ http
def http_get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=dict({"User-Agent": "fairslot/0.1"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SourceError("Доступ закрыт (%s). Проверьте токен или откройте доступ к файлу «всем, у кого есть ссылка»." % e.code)
        if e.code == 404:
            raise SourceError("Ссылка не найдена (404). Проверьте адрес.")
        raise SourceError("Сервер ответил ошибкой %s." % e.code)
    except urllib.error.URLError as e:
        raise SourceError("Нет соединения с источником: %s" % getattr(e, "reason", e))
    except ValueError:
        raise SourceError("Некорректная ссылка.")


def google_sheet_csv_url(url):
    m = re.match(r"https://docs\.google\.com/spreadsheets/d/(?:e/)?([\w-]+)", url or "")
    if not m or "output=csv" in url or "format=csv" in url:
        return url
    gid = re.search(r"[#&?]gid=(\d+)", url)
    if "/d/e/" in url:  # "published to the web" link
        return url.split("?")[0].rsplit("/", 1)[0] + "/pub?output=csv" + ("&gid=" + gid.group(1) if gid else "")
    return "https://docs.google.com/spreadsheets/d/%s/export?format=csv%s" % (m.group(1), "&gid=" + gid.group(1) if gid else "")


# ------------------------------------------------------------------ parsing
def parse_csv_text(text):
    text = (text or "").lstrip("﻿")
    if not text.strip():
        return []
    first = text.splitlines()[0]
    delim = ";" if first.count(";") > first.count(",") else ("\t" if "\t" in first else ",")
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]


def parse_when(s, utc_offset=0):
    """Many date formats -> naive local datetime. Values ending in Z or +hh:mm are shifted to local time."""
    s = str(s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::(\d{2}))?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?$", s)
    if m:
        d = datetime.fromisoformat(m.group(1) + "T" + m.group(2))
        tz = m.group(4)
        if tz == "Z":
            d += timedelta(hours=utc_offset)
        elif tz:
            sign = 1 if tz[0] == "+" else -1
            hh, mm = int(tz[1:3]), int(tz[-2:])
            d += timedelta(hours=utc_offset) - timedelta(hours=sign * hh, minutes=sign * mm)
        return d
    for f in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M",
              "%Y/%m/%d %H:%M", "%d %b %Y %H:%M", "%b %d, %Y %I:%M %p", "%m/%d/%Y %I:%M %p", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def _flag(v):
    return str(v or "").strip().lower() in YES


def _list(v):
    return [x.strip() for x in re.split(r"[;|,]", v or "") if x.strip()]


def records_from_rows(rows, mapping=None, utc_offset=0, default_open=True):
    """Turn table rows into neutral records. Raises SourceError with a readable reason."""
    if not rows:
        return []
    mp = dict(guess_mapping(list(rows[0].keys())))
    mp.update({k: v for k, v in (mapping or {}).items() if v})
    if "who" not in mp:
        raise SourceError("Не нашёл колонку с участником (email или имя). Колонки в таблице: %s" % ", ".join(rows[0].keys()))
    if "start" not in mp:
        raise SourceError("Не нашёл колонку с датой и временем слота. Колонки в таблице: %s" % ", ".join(rows[0].keys()))
    out = []
    for i, r in enumerate(rows, 2):
        when = parse_when(r.get(mp["start"]), utc_offset)
        if when and "time" in mp and mp["time"] != mp["start"] and when.hour == 0 and when.minute == 0:
            t = parse_when("2000-01-01 " + r.get(mp["time"], ""), 0) or None
            if t:
                when = when.replace(hour=t.hour, minute=t.minute)
        if when is None:
            if not any(r.values()):
                continue
            raise SourceError("Строка %d: не удалось прочитать дату и время «%s»." % (i, r.get(mp["start"])))
        who = (r.get(mp["who"]) or "").strip().lower() if "@" in (r.get(mp["who"]) or "") else (r.get(mp["who"]) or "").strip()
        if not who:
            continue
        ts = parse_when(r.get(mp.get("ts", ""), ""), utc_offset)
        out.append({
            "who": who, "name": (r.get(mp.get("name", "")) or "").strip(),
            "start": when.strftime("%Y-%m-%dT%H:%M"), "resource": (r.get(mp.get("resource", "")) or "").strip(),
            "partners": [p.lower() if "@" in p else p for p in _list(r.get(mp.get("partners", "")))],
            "open": _flag(r[mp["open"]]) if "open" in mp and r.get(mp["open"]) not in (None, "") else default_open,
            "avoid": _list(r.get(mp.get("avoid", ""))), "want": _list(r.get(mp.get("want", ""))),
            "ts": ts.strftime("%Y-%m-%dT%H:%M:%S") if ts else "%06d" % i, "level": (r.get(mp.get("level", "")) or "").strip(),
        })
    return out


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))


def parse_ics(text, utc_offset=0, default_open=True, days_ahead=None, now=None):
    """Each VEVENT is a slot; each attendee (or the organizer if none) is one application."""
    out, ev = [], None
    for line in _unfold(text).split("\n"):
        if line == "BEGIN:VEVENT":
            ev = {"att": []}
        elif line == "END:VEVENT" and ev is not None:
            when = ev.get("start")
            if when:
                if days_ahead is not None and now and not (now <= when <= now + timedelta(days=days_ahead)):
                    ev = None
                    continue
                people = ev["att"] or ([ev["org"]] if ev.get("org") else [])
                for who, name in people:
                    out.append({"who": who, "name": name, "start": when.strftime("%Y-%m-%dT%H:%M"), "resource": ev.get("summary", ""),
                                "partners": [], "open": default_open, "avoid": [], "want": [], "ts": ev.get("created", "") or ev.get("uid", ""), "level": ""})
            ev = None
        elif ev is not None and ":" in line:
            key, _, val = line.partition(":")
            name, _, params = key.partition(";")
            name = name.upper()
            if name == "DTSTART":
                v = val.strip()
                if re.match(r"^\d{8}T\d{6}Z?$", v):
                    d = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
                    ev["start"] = d + timedelta(hours=utc_offset) if v.endswith("Z") else d
                elif re.match(r"^\d{8}$", v):
                    ev["start"] = datetime.strptime(v, "%Y%m%d")
            elif name == "SUMMARY":
                ev["summary"] = val.replace("\\,", ",").strip()
            elif name == "UID":
                ev["uid"] = val.strip()
            elif name == "CREATED":
                d = parse_when(re.sub(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?$", r"\1-\2-\3T\4:\5", val.strip()), utc_offset)
                ev["created"] = d.strftime("%Y-%m-%dT%H:%M:%S") if d else ""
            elif name in ("ATTENDEE", "ORGANIZER"):
                mail = re.sub(r"(?i)^mailto:", "", val.strip()).lower()
                cn = re.search(r'CN="?([^;":]+)"?', params)
                rec = (mail, cn.group(1).strip() if cn else "")
                if name == "ATTENDEE":
                    if "PARTSTAT=DECLINED" not in params.upper():
                        ev["att"].append(rec)
                else:
                    ev["org"] = rec
    return out


# ------------------------------------------------------------------ Calendly API v2 (read only)
def calendly_records(token, utc_offset=0, days_ahead=14, default_open=True, now=None, get=None):
    get = get or (lambda url: http_get(url, {"Authorization": "Bearer " + token, "Content-Type": "application/json"}))
    if not token:
        raise SourceError("Не указан токен Calendly (Integrations → API & Webhooks → Personal access tokens).")
    me = json.loads(get("https://api.calendly.com/users/me"))["resource"]["uri"]
    now = now or datetime.utcnow() + timedelta(hours=utc_offset)
    lo = (now - timedelta(hours=utc_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (now - timedelta(hours=utc_offset) + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://api.calendly.com/scheduled_events?" + urllib.parse.urlencode(
        {"user": me, "status": "active", "min_start_time": lo, "max_start_time": hi, "count": 100, "sort": "start_time:asc"})
    out, pages = [], 0
    while url and pages < 30:
        data = json.loads(get(url))
        for ev in data.get("collection", []):
            inv_url = ev["uri"] + "/invitees?count=100&status=active"
            invs = json.loads(get(inv_url)).get("collection", [])
            start = parse_when(ev["start_time"], utc_offset)
            for inv in invs:
                qa = {_norm(q.get("question")): (q.get("answer") or "") for q in inv.get("questions_and_answers", [])}
                partner = next((a for q, a in qa.items() if any(_norm(s) in q for s in SYNONYMS["partners"])), "")
                level = next((a for q, a in qa.items() if any(_norm(s) in q for s in SYNONYMS["level"])), "")
                created = parse_when(inv.get("created_at", ""), utc_offset)
                out.append({"who": (inv.get("email") or inv.get("name") or "").lower(), "name": inv.get("name", ""),
                            "start": start.strftime("%Y-%m-%dT%H:%M"), "resource": ev.get("name", ""),
                            "partners": [p.lower() if "@" in p else p for p in _list(partner)], "open": default_open, "avoid": [], "want": [],
                            "ts": created.strftime("%Y-%m-%dT%H:%M:%S") if created else "", "level": level.strip()})
        nxt = (data.get("pagination") or {}).get("next_page")
        url, pages = nxt, pages + 1
    return out


# ------------------------------------------------------------------ records -> engine inputs
def build_inputs(records, roster=None):
    """records -> {"slots","applications","members","warnings"}. Same person+slot twice keeps the earliest."""
    warnings, seen, apps, slots, members = [], {}, [], {}, {}
    for r in sorted(records, key=lambda r: (r["ts"], r["who"])):
        sid = "%s-%s" % (r["start"], re.sub(r"[^\w]+", "", r["resource"]).lower() or "slot")
        key = (r["who"], sid)
        if key in seen:
            warnings.append("%s записан(а) на %s несколько раз, учтена первая заявка." % (r["who"], r["start"].replace("T", " ")))
            continue
        seen[key] = True
        slots.setdefault(sid, {"id": sid, "start": r["start"], "end": "", "resource": r["resource"]})
        apps.append({"id": "a%d" % (len(apps) + 1), "slot": sid, "members": [r["who"]] + [p for p in r["partners"] if p != r["who"]],
                     "open": r["open"], "avoid": r["avoid"], "want": r["want"], "ts": r["ts"]})
        for m, nm, lv in [(r["who"], r["name"], r["level"])] + [(p, "", "") for p in r["partners"]]:
            cur = members.setdefault(m, {"level": "", "name": ""})
            cur["level"] = cur["level"] or lv
            cur["name"] = cur["name"] or nm
    for m, info in (roster or {}).items():
        members.setdefault(m, {"level": "", "name": ""}).update({k: v for k, v in info.items() if v})
    if not any(m["level"] for m in members.values()):
        warnings.append("Уровни игроков не найдены. Добавьте таблицу участников (id, level) или выберите правило уровней «не учитывать».")
    return {"slots": sorted(slots.values(), key=lambda s: (s["start"], s["id"])), "applications": apps, "members": members, "warnings": warnings}


def roster_from_rows(rows):
    out = {}
    for r in rows:
        mp = guess_mapping(list(r.keys()))
        who = (r.get(mp.get("who", "")) or "").strip()
        if who:
            who = who.lower() if "@" in who else who
            out[who] = {"level": (r.get(mp.get("level", "")) or "").strip(), "name": (r.get(mp.get("name", "")) or "").strip()}
    return out


# ------------------------------------------------------------------ one entry point
def load(spec, http=None, now=None):
    """spec: {"type", "url", "token", "days_ahead", "utc_offset", "default_open", "mapping", "text", "roster": {...}}"""
    http = http or http_get
    typ = spec.get("type")
    off = float(spec.get("utc_offset", 0) or 0)
    dflt = bool(spec.get("default_open", True))
    mapping = spec.get("mapping") or {}
    if typ in ("csv_url", "google_sheet"):
        rows = parse_csv_text(http(google_sheet_csv_url(spec.get("url", ""))))
        recs = records_from_rows(rows, mapping, off, dflt)
    elif typ == "csv_text":
        recs = records_from_rows(parse_csv_text(spec.get("text", "")), mapping, off, dflt)
    elif typ == "json_url":
        data = json.loads(http(spec.get("url", "")))
        data = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [])
        recs = records_from_rows([{str(k): "" if v is None else str(v) for k, v in d.items()} for d in data], mapping, off, dflt)
    elif typ == "ics_url":
        url = (spec.get("url") or "").replace("webcal://", "https://")
        recs = parse_ics(http(url), off, dflt, spec.get("days_ahead"), now or datetime.utcnow() + timedelta(hours=off))
    elif typ == "calendly":
        recs = calendly_records(spec.get("token", ""), off, int(spec.get("days_ahead", 14) or 14), dflt, now,
                                get=(lambda u: http(u, {"Authorization": "Bearer " + spec.get("token", "")})) if http is not http_get else None)
    else:
        raise SourceError("Неизвестный тип источника: %s" % typ)
    roster = None
    rs = spec.get("roster") or {}
    if rs.get("type") in ("csv_url", "google_sheet") and rs.get("url"):
        roster = roster_from_rows(parse_csv_text(http(google_sheet_csv_url(rs["url"]))))
    elif rs.get("text"):
        roster = roster_from_rows(parse_csv_text(rs["text"]))
    res = build_inputs(recs, roster)
    if not res["applications"]:
        res["warnings"].append("Заявок не найдено.")
    return res


# ------------------------------------------------------------------ helpers shared with the page
def to_csv_texts(inputs):
    def table(header, rows):
        b = io.StringIO()
        w = csv.writer(b, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
        return b.getvalue()
    return {
        "slots": table(["id", "start", "end", "resource", "levels"], [[s["id"], s["start"], s.get("end", ""), s.get("resource", ""), ""] for s in inputs["slots"]]),
        "apps": table(["id", "slot", "members", "open", "avoid", "want", "ts"],
                      [[a["id"], a["slot"], "|".join(a["members"]), "yes" if a["open"] else "no", "|".join(a["avoid"]), "|".join(a["want"]), a["ts"]] for a in inputs["applications"]]),
        "members": table(["id", "level", "name"], [[m, v.get("level", ""), v.get("name", "")] for m, v in inputs["members"].items()]),
    }


def auto_seed(applications, slots, now):
    """Public, recomputable seed: hash of the closed application list and the draw time."""
    lines = sorted("%s|%s|%s|%s|%s" % (a["id"], a["slot"], ",".join(sorted(a["members"])), "1" if a.get("open") else "0", a.get("ts", "")) for a in applications)
    lines += sorted("S|%s|%s" % (s["id"], s["start"]) for s in slots)
    return "auto-" + hashlib.sha256(("\n".join(lines) + "\nT|" + str(now)).encode("utf-8")).hexdigest()[:16]
