import http.server, json, os, subprocess, sys, tempfile, threading, unittest, urllib.request
from datetime import datetime
from fairslot import sources as S, config as C, server
from fairslot.engine import run, verify_published

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALENDLY_CSV = ("Invitee Name,Invitee Email,Event Type Name,Start Date & Time,Invitee Created At\n"
                "Anna K,anna@x.com,Court 1,2026-11-20 20:00,2026-11-18 09:00\n"
                "Borys,BORYS@x.com,Court 1,2026-11-20 20:00,2026-11-18 09:05\n"
                "Anna K,anna@x.com,Court 1,2026-11-20 20:00,2026-11-18 10:00\n")
FORMS_RU = ("Отметка времени,Электронная почта,Дата и время,Корт,Напарник,Уровень\n"
            "18.11.2026 9:05:12,Dave@x.com,20.11.2026 21:00,Корт 2,erin@x.com,C+\n"
            "18.11.2026 9:07:00,erin@x.com,20.11.2026 21:00,Корт 2,,C\n")
ICS = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20261120T160000Z\r\nSUMMARY:Court\\, main\r\n"
       "ATTENDEE;CN=\"Anna K\";PARTSTAT=ACCEPTED:mailto:Anna@x.com\r\nATTENDEE;CN=Borys;PARTSTAT=DECLINED:mailto:b@x.com\r\n"
       "ATTENDEE;CN=Carla:mailto:carla@x.com\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:u2\r\nDTSTART;TZID=Asia/Dubai:20261121T190000\r\n"
       "SUMMARY:Court 2\r\nORGANIZER:mailto:o@x.com\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")


class Serve:
    """Tiny local web server that returns fixed text for a path."""
    def __init__(self, routes):
        outer = routes
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                body = outer.get(self.path)
                if body is None:
                    self.send_response(404); self.end_headers(); return
                if self.headers.get("Authorization") == "Bearer BAD":
                    self.send_response(401); self.end_headers(); return
                self.send_response(200); self.end_headers(); self.wfile.write(body.encode("utf-8"))
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def close(self): self.srv.shutdown(); self.srv.server_close()


class Mapping(unittest.TestCase):
    def test_calendly_headers(self):
        m = S.guess_mapping(["Invitee Name", "Invitee Email", "Event Type Name", "Start Date & Time", "Invitee Created At"])
        self.assertEqual((m["who"], m["start"], m["resource"], m["ts"]), ("Invitee Email", "Start Date & Time", "Event Type Name", "Invitee Created At"))
    def test_russian_forms(self):
        m = S.guess_mapping(["Отметка времени", "Электронная почта", "Дата и время", "Корт", "Напарник", "Уровень"])
        self.assertEqual((m["who"], m["start"], m["resource"], m["partners"], m["level"], m["ts"]), ("Электронная почта", "Дата и время", "Корт", "Напарник", "Уровень", "Отметка времени"))
    def test_missing_columns_readable_error(self):
        with self.assertRaises(S.SourceError) as e:
            S.records_from_rows([{"foo": "1"}])
        self.assertIn("foo", str(e.exception))
    def test_bad_date_names_row(self):
        with self.assertRaises(S.SourceError) as e:
            S.records_from_rows([{"email": "a@b.c", "start": "tomorrow evening"}])
        self.assertIn("tomorrow evening", str(e.exception))


class Parsing(unittest.TestCase):
    def test_dates(self):
        for s, want in [("2026-11-20 20:00", "2026-11-20T20:00"), ("2026-11-20T16:00:00Z", "2026-11-20T20:00"), ("2026-11-20T20:00:00+04:00", "2026-11-20T20:00"),
                        ("20.11.2026 21:00", "2026-11-20T21:00"), ("11/20/2026 8:30 PM", "2026-11-20T20:30")]:
            self.assertEqual(S.parse_when(s, 4).strftime("%Y-%m-%dT%H:%M"), want, s)
        self.assertIsNone(S.parse_when("nope"))
    def test_calendly_csv_dedupe_and_case(self):
        inp = S.build_inputs(S.records_from_rows(S.parse_csv_text(CALENDLY_CSV)))
        self.assertEqual(len(inp["applications"]), 2)
        self.assertIn("borys@x.com", inp["members"]); self.assertTrue(any("несколько раз" in w for w in inp["warnings"]))
        self.assertEqual(inp["slots"][0]["start"], "2026-11-20T20:00")
    def test_forms_partner_and_level(self):
        inp = S.build_inputs(S.records_from_rows(S.parse_csv_text(FORMS_RU)))
        a = inp["applications"][0]
        self.assertEqual(a["members"], ["dave@x.com", "erin@x.com"]); self.assertEqual(inp["members"]["dave@x.com"]["level"], "C+")
    def test_semicolon_csv(self):
        rows = S.parse_csv_text("email;start\nA@b.c;2026-11-20 20:00\n")
        self.assertEqual(rows[0]["email"], "A@b.c")
    def test_ics(self):
        recs = S.parse_ics(ICS, utc_offset=4)
        self.assertEqual([(r["who"], r["start"]) for r in recs], [("anna@x.com", "2026-11-20T20:00"), ("carla@x.com", "2026-11-20T20:00"), ("o@x.com", "2026-11-21T19:00")])
        self.assertEqual(recs[0]["resource"], "Court, main")
    def test_google_sheet_url(self):
        self.assertEqual(S.google_sheet_csv_url("https://docs.google.com/spreadsheets/d/ABC123/edit#gid=77"), "https://docs.google.com/spreadsheets/d/ABC123/export?format=csv&gid=77")
        self.assertEqual(S.google_sheet_csv_url("https://example.com/a.csv"), "https://example.com/a.csv")


class Calendly(unittest.TestCase):
    def fake(self, url, headers=None):
        self.assertEqual((headers or {}).get("Authorization"), "Bearer TOK")
        if url.endswith("/users/me"):
            return json.dumps({"resource": {"uri": "https://api.calendly.com/users/U1"}})
        if "/scheduled_events?" in url and "page_token=2" not in url:
            return json.dumps({"collection": [{"uri": "https://api.calendly.com/scheduled_events/E1", "name": "Court 1", "start_time": "2026-11-20T16:00:00.000000Z"}],
                               "pagination": {"next_page": "https://api.calendly.com/scheduled_events?page_token=2"}})
        if "page_token=2" in url:
            return json.dumps({"collection": [{"uri": "https://api.calendly.com/scheduled_events/E2", "name": "Court 2", "start_time": "2026-11-20T17:30:00.000000Z"}], "pagination": {"next_page": None}})
        if "/E1/invitees" in url:
            return json.dumps({"collection": [{"name": "Anna K", "email": "Anna@x.com", "created_at": "2026-11-18T05:00:00.000000Z",
                                               "questions_and_answers": [{"question": "Partner (+1)", "answer": "Filip"}, {"question": "Your level", "answer": "D+"}]},
                                              {"name": "Borys", "email": "b@x.com", "created_at": "2026-11-18T05:05:00Z", "questions_and_answers": []}]})
        if "/E2/invitees" in url:
            return json.dumps({"collection": [{"name": "Carla", "email": "c@x.com", "created_at": "2026-11-18T06:00:00Z", "questions_and_answers": []}]})
        raise AssertionError("unexpected url " + url)
    def test_api(self):
        res = S.load({"type": "calendly", "token": "TOK", "utc_offset": 4}, http=self.fake, now=datetime(2026, 11, 19, 12, 0))
        self.assertEqual(res["counts"] if "counts" in res else len(res["applications"]), 3)
        a1 = res["applications"][0]
        self.assertEqual(a1["members"], ["anna@x.com", "Filip"]); self.assertEqual(res["members"]["anna@x.com"]["level"], "D+")
        self.assertEqual(sorted(s["start"] for s in res["slots"]), ["2026-11-20T20:00", "2026-11-20T21:30"])
    def test_missing_token(self):
        with self.assertRaises(S.SourceError): S.load({"type": "calendly", "token": ""}, http=self.fake)


class RealHttp(unittest.TestCase):
    def test_csv_url_and_errors_and_roster(self):
        web = Serve({"/apps.csv": CALENDLY_CSV, "/roster.csv": "email,level,name\nanna@x.com,C,Anna\nborys@x.com,D,Borys\n", "/cal.ics": ICS})
        try:
            res = S.load({"type": "csv_url", "url": web.url + "/apps.csv", "roster": {"type": "csv_url", "url": web.url + "/roster.csv"}})
            self.assertEqual(res["members"]["anna@x.com"]["level"], "C"); self.assertEqual(res["members"]["borys@x.com"]["name"], "Borys")
            self.assertEqual(len(S.load({"type": "ics_url", "url": web.url + "/cal.ics", "utc_offset": 4})["applications"]), 3)
            with self.assertRaises(S.SourceError) as e: S.load({"type": "csv_url", "url": web.url + "/missing.csv"})
            self.assertIn("404", str(e.exception))
            with self.assertRaises(S.SourceError) as e: S.http_get(web.url + "/apps.csv", {"Authorization": "Bearer BAD"})
            self.assertIn("Доступ", str(e.exception))
            with self.assertRaises(S.SourceError): S.http_get("http://127.0.0.1:9/x")
        finally: web.close()
    def test_end_to_end_draw(self):
        web = Serve({"/f.csv": FORMS_RU + "19.11.2026 9:00:00,fay@x.com,20.11.2026 21:00,Корт 2,,C\n"})
        try:
            res = S.load({"type": "csv_url", "url": web.url + "/f.csv"})
            cfg = C.load({"levels": {"names": ["C", "C+"], "policy": "adjacent", "max_gap": 1}})
            now = "2026-11-20T10:00"; seed = S.auto_seed(res["applications"], res["slots"], now)
            out = run(cfg, res["slots"], res["applications"], res["members"], [], seed=seed, now=now)
            self.assertEqual(len(out["allocations"]), 1); self.assertTrue(verify_published(out)[0])
            self.assertEqual(seed, S.auto_seed(res["applications"], res["slots"], now))
        finally: web.close()


class Server(unittest.TestCase):
    def call(self, base, path, body, token=None, host=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **({"X-Fairslot-Token": token} if token else {}), **({"Host": host} if host else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
    def test_flow(self):
        web = Serve({"/apps.csv": CALENDLY_CSV}); d = tempfile.mkdtemp(); ws = os.path.join(d, "ws.json")
        h = server.make_handler(ws, "TKN"); srv = server.ThreadingHTTPServer(("127.0.0.1", 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        try:
            page = urllib.request.urlopen(base + "/").read().decode(); self.assertIn("window.FS_APP", page); self.assertIn("TKN", page)
            self.assertEqual(self.call(base, "/api/fetch", {}, None)[0], 403)
            self.assertEqual(self.call(base, "/api/fetch", {}, "TKN", host="evil.example")[0], 403)
            st, _ = self.call(base, "/api/workspace/save", {"source": {"type": "calendly", "token": "SECRET1"}, "utc_offset": 4}, "TKN"); self.assertEqual(st, 200)
            st, view = self.call(base, "/api/workspace/get", {}, "TKN")
            self.assertNotIn("SECRET1", json.dumps(view)); self.assertTrue(view["source"]["token_set"])
            st, _ = self.call(base, "/api/workspace/save", {"source": {"type": "calendly", "token": "", "days_ahead": 7}}, "TKN")
            with open(ws) as f: self.assertEqual(json.load(f)["source"]["token"], "SECRET1")  # blank keeps the saved token
            st, res = self.call(base, "/api/fetch", {"source": {"type": "csv_url", "url": web.url + "/apps.csv"}}, "TKN")
            self.assertEqual(res["counts"]["applications"], 2); self.assertIn("slots", res["csv"])
            st, res = self.call(base, "/api/fetch", {"source": {"type": "csv_url", "url": web.url + "/nope.csv"}}, "TKN")
            self.assertIn("404", res["error"])
        finally: srv.shutdown(); srv.server_close(); web.close()

    def test_cli_auto_and_fetch(self):
        web = Serve({"/apps.csv": CALENDLY_CSV}); d = tempfile.mkdtemp(); ws = os.path.join(d, "ws.json")
        with open(ws, "w") as f: json.dump({"source": {"type": "csv_url", "url": web.url + "/apps.csv"}, "profile": {"levels": {"policy": "any"}, "draw_hours_before": 9999}, "now": "2026-11-20T10:00",
                   "link_template": "https://x.example/{date}/{time}?o={owner}"}, f)
        env = dict(os.environ, PYTHONPATH=ROOT)
        try:
            r = subprocess.run([sys.executable, "-m", "fairslot", "auto", "--workspace", ws, "--out", os.path.join(d, "r.json")], capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("seed: auto-", r.stdout); self.assertIn("https://x.example/2026-11-20/20:00", r.stdout)
            with open(os.path.join(d, "r.json")) as f: self.assertTrue(verify_published(json.load(f))[0])
            r = subprocess.run([sys.executable, "-m", "fairslot", "fetch", "--workspace", ws, "--out", os.path.join(d, "o")], capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stderr); self.assertTrue(os.path.exists(os.path.join(d, "o", "applications.csv")))
        finally: web.close()


if __name__ == "__main__":
    unittest.main()
