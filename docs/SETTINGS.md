# Settings

A profile is a JSON file. Missing keys take the defaults below. Unknown values are rejected on load.

| Key | Default | Meaning |
|---|---|---|
| `order` | `weighted_random` | `weighted_random`: seeded draw, verifiable. `priority_fifo`: no randomness; higher weight first, then earlier `ts`. |
| `draw_hours_before` | 72 | A slot is drawn only when it starts within this many hours of the draw time. |
| `seats_per_slot` | 4 | Players per slot. |
| `team.max_size` | 4 | Largest team in one application. 1 = individual applications only. |
| `team.allow_open_seats` | true | Teams may mark free seats as open to other applicants. |
| `team.avoid_lists` | true | Respect "do not put me with". |
| `team.want_lists` | true | Prefer people from "want" when filling seats. |
| `levels.names` | beginner, intermediate, advanced | Level names from weakest to strongest. Use your own grading. |
| `levels.policy` | `adjacent` | `any`: ignore levels. `adjacent`: within `max_gap` steps. `same`: one level only. |
| `levels.max_gap` | 1 | Largest distance, in steps of `levels.names`, between players of one group. |
| `caps.per_day` | 1 | Games per person per day. |
| `caps.per_week` | 3 | Games per person per ISO week. |
| `caps.max_applications_week` | 3 | Applications per person per week. Later ones are rejected. |
| `weights.recent_win_penalty` | 0.5 | Weight is divided by `1 + penalty × wins` in the window. |
| `weights.loss_streak_boost` | 0.25 | Weight is multiplied by `1 + boost × consecutive losses`. |
| `weights.min`, `weights.max` | 0.2, 4.0 | Weight limits. |
| `weights.window_days` | 28 | How far back wins count. |
| `substitution.policy` | `owner_picks` | `owner_picks`: the holder names the replacement. `waitlist_opt_in`: from the waitlist, group agrees. `waitlist_auto`: first fitting waitlisted person. `none`: no changes. |
| `substitution.change_deadline_hours` | 3 | Group is frozen this long before the start. |
| `substitution.late_release_hours` | 6 | Free seats become first-come this long before the start. |
| `substitution.market_requires_level_fit` | true | Market claims must satisfy the level rule. |
| `waitlist` | `opt_in` | `none`, `opt_in` or `auto`. |

How levels work: a team of friends is never split or checked against itself. The level rule applies when other applicants are added to free seats.

Example profile:
```json
{
  "draw_hours_before": 24,
  "levels": {"names": ["D-","D","D+","D+Strong","C-","C-Strong","C","C+","C+Strong"], "policy": "adjacent", "max_gap": 2},
  "caps": {"per_day": 1, "per_week": 3}
}
```
