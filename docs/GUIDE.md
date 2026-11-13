# Guide for organizers

## 1. Prepare four tables (CSV)

Export from Google Sheets or Excel as CSV, or type them in the page.

**Slots** (`id,start,end,resource,levels`)
```
id,start,end,resource,levels
fri-1930-c1,2026-11-20T19:30,2026-11-20T21:00,court1,
```
`id` is any unique text. `start` is `YYYY-MM-DDTHH:MM`, local time. `levels` is optional: list the levels allowed on this slot, for example `D;D+`.

**Members** (`id,level`)
```
id,level
Anna,D
Borys,C+
```
Use a short id or nickname. Levels must match the names in your profile.

**Applications** (`id,slot,members,open,avoid,want,ts`)
```
id,slot,members,open,avoid,want,ts
a1,fri-1930-c1,Anna|Filip,yes,,,2026-11-18T09:00
```
* `members`: everyone in the team, separated by `|`. One name is an individual application.
* `open`: `yes` if free seats may be filled by other applicants.
* `avoid`: people the applicant does not want in the group. `want`: people they would like.
* `ts`: when the application arrived. It orders equal cases and the weekly application limit.

**History** (optional, `member,start,result`)
```
member,start,result
Borys,2026-11-12T20:00,lost
```
`result` is `won`, `played` or `lost`. Without history all weights are equal.

Several values in one cell: separate with `|` or `;`. If your Excel uses `;` as the column separator, use `|` inside cells.

## 2. Choose rules

Pick a ready profile, then change single settings if needed. See [PROFILES.md](PROFILES.md) and [SETTINGS.md](SETTINGS.md).

## 3. Announce the seed

Choose a public seed before applications close, for example a number from a public source or a phrase announced in the group chat. Nobody, including you, may change it afterwards.

## 4. Run

Browser: open `fairslot.html`, paste or drop the tables, enter the seed and the draw time, press **Run the draw**.
Command line: see the README.

Slots further away than `draw_hours_before` are skipped and listed as "too early".

## 5. Read the result

Each slot shows its group, the slot holder, free seats and the waitlist. If you entered a link template, every group gets a ready booking link. Template fields: `{date}`, `{time}`, `{resource}`, `{owner}`, `{members}`, `{slot_id}`, `{start}`. Example: `https://calendly.com/you/court?date={date}&time={time}&name={owner}`.

Send each holder the link; the holder presses the final button. fairslot never books by itself.

## 6. Publish and verify

Press **Download result.json** (or **Copy JSON**) and post the file next to the announcement. Anyone opens the **Verify** tab, pastes the file and sees either "verified" or the first mismatch. The file contains ids, weights and keys, no other personal data.

## 7. After the draw

* The slot holder asks to replace a player: check the replacement with `fairslot.substitution.check_swap` (Python) or decide by the profile's rule.
* Seats still free shortly before the game: `market_seats` lists them for first-come claims; `claim_seat` checks level and "do not put me with".
