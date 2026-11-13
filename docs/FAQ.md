# Questions people ask

**I cannot know three days ahead what I will do.**
Lower `draw_hours_before` (profile `late_lottery`) and let the holder name replacements (`owner_picks`).

**I do not want a group of only beginners or only strong players.**
Set `levels.policy` and `levels.max_gap`. Friends who apply together are never split; the rule applies to strangers added to free seats.

**A stranger from the waitlist was put in our group.**
Use `owner_controlled` or `hybrid_market`: the holder names the replacement, or free seats go to a first-come list.

**Can I apply if a friend already won and added me?**
Every game counts against `caps` for each person no matter who applied for them.

**Can I choose who joins me?**
Mark the application `open` and fill `want`. Use `avoid` for people you do not want. Both are checked only when a group is formed.

**The same few people play every day.**
Use `caps` and `weights`: recent winners get a lower chance, repeated losers a higher one.

**Where is the proof the draw was fair?**
`result.json` holds the seed, every weight and every key. Anyone can recompute them on the Verify tab or with `python -m fairslot verify`.

**Can fairslot book the slot?**
No. It produces the winners and a ready link. A person confirms the booking.

**Does it work offline?**
Yes. `fairslot.html` and the command line need no internet.
