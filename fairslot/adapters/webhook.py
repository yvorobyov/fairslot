"""Optional: POST the published result to any URL (chat bot, spreadsheet script, static site)."""
import json
import urllib.request


def post(url, result, timeout=15):
    req = urllib.request.Request(url, data=json.dumps(result).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status
