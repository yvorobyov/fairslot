# fairslot

Fair, verifiable allocation of scarce booking slots: padel courts, meeting rooms, desks, halls.
It decides who gets which slot and shows the proof. It never books anything; a person presses the final button in the tool you already use (Calendly, Cal.com, Google Forms, a spreadsheet).

* One engine, every rule is a setting: draw timing, teams, player levels, "do not put me with", weekly limits, replacements.
* Anyone can verify a draw from the published file alone.
* Two ways to run it, same results:
  * **`fairslot.html`**: one file, open it in any browser. Works offline, nothing to install, nothing is sent anywhere.
  * **Command line**: Python 3.9 or newer, standard library only.

## Start in 2 minutes (browser)

1. Download `fairslot.html` and double-click it.
2. An example is preloaded. Press **Run the draw**.
3. Read the groups on the **Result** tab. Open **Verify**, press **Use current result**: the page recomputes the draw and confirms it.

Full walkthrough: [docs/GUIDE.md](docs/GUIDE.md) (Russian: [docs/GUIDE_RU.md](docs/GUIDE_RU.md)).

Automatic loading of applications (Google Sheet, calendar .ics, Calendly, CSV/JSON link): `python -m fairslot app`, see [docs/SOURCES.md](docs/SOURCES.md).

## Start in 2 minutes (command line)

```
python -m fairslot presets
python -m fairslot run --profile owner_controlled ^
  --slots examples/slots.csv --apps examples/applications.csv ^
  --members examples/members.csv --history examples/history.csv ^
  --seed "my-public-seed" --now 2026-11-19T12:00 --out result.json
python -m fairslot verify result.json
```
(Use `\` instead of `^` on macOS and Linux.)

## What you can set

| Question | Setting |
|---|---|
| How far ahead must people plan? | `draw_hours_before` |
| Random draw or fixed order? | `order` |
| Teams of friends, strangers added to free seats? | `team.max_size`, `team.allow_open_seats` |
| "Do not put me with X" | `team.avoid_lists` |
| Player levels in one group | `levels.names`, `levels.policy`, `levels.max_gap` |
| How often one person may play | `caps` |
| Stop the same people winning every time | `weights` |
| Someone cancels | `substitution.policy`, `substitution.change_deadline_hours` |
| Seats nobody took | `substitution.late_release_hours` |

All settings: [docs/SETTINGS.md](docs/SETTINGS.md). Ready profiles and when to use each: [docs/PROFILES.md](docs/PROFILES.md). Questions people ask: [docs/FAQ.md](docs/FAQ.md).

## How the draw works

1. Announce a public seed before applications close.
2. Each application gets a weight from its members' recent games: more recent wins lower it, a losing streak raises it, always within limits.
3. For each slot every application gets the key `u^(1/weight)`, where `u` comes from `sha256(seed|slot|application)`. The highest key wins.
4. If the winning team has free seats and allows others, open applications with a good level fit fill them in key order, never breaking "do not put me with" or the level rule.
5. `result.json` stores seed, weights and keys. `verify` recomputes them with no private data.

## Checks

`python -m unittest discover -s tests` runs the tests, including 300 random communities with every profile and random settings. `tools/parity_check.js` confirms the browser engine gives the same results as the Python one on 400 random cases.

## Limits

* The draw decides who gets a slot. Cancellations and swaps after the draw are checked by `fairslot.substitution` (Python); the browser page shows the rule but does not run swaps.
* The simulator (`python -m fairslot sim`) covers the draw only.
* A lottery cannot satisfy everyone. Compare profiles on your own numbers before you announce one.

MIT license. Jegor, 2026.
