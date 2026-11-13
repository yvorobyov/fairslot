"""Turn winners into booking links for ANY booking tool that supports URL parameters
(Calendly, Cal.com, a Google Form with prefilled answers, your own page...).

The engine never books anything by itself. It produces one ready link per winning group;
a human (or your own script) presses the final button.  Template placeholders:
{slot_id} {start} {date} {time} {resource} {members} {owner}
"""
from ..engine import _dt
from urllib.parse import quote


def render(result, slots, template, quote_values=True):
    by_id = {s["id"]: s for s in slots}
    q = (lambda v: quote(str(v), safe="")) if quote_values else str
    out = []
    for al in result["allocations"]:
        s = by_id[al["slot"]]
        d = _dt(s["start"])
        out.append({"slot": al["slot"], "url": template.format(
            slot_id=q(s["id"]), start=q(s["start"]), date=d.strftime("%Y-%m-%d"), time=d.strftime("%H:%M"),
            resource=q(s.get("resource", "")), members=q(",".join(al["members"])), owner=q(al["members"][0]))})
    return out
