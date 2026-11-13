# Ready profiles

List them with `python -m fairslot presets`. Pick one, then adjust.

| Profile | Use when | Cost |
|---|---|---|
| `strict_lottery` | Many more applicants than slots; people can plan 3 days ahead | Plans change; waitlist replacements annoy groups |
| `late_lottery` | People know their plans only a day ahead | Less time to organise; result must reach people quickly |
| `owner_controlled` | Groups care who they play with | The holder may favour friends; levels and caps still apply |
| `level_pools` | Levels must never mix | More groups stay incomplete |
| `fair_queue` | You want a rule that fits in one sentence | Early applicants win ties; nothing random to audit |
| `hybrid_market` | The community already trades slots in a chat | Someone has to watch the market |
| `individual_only` | Everyone is a stranger (desks, tools) | No preferences at all |

To make your own, copy a profile file from `fairslot/presets/`, change values, and pass the path with `--profile`. In the browser page choose a profile, change the fields, and copy the JSON from "Whole profile".
