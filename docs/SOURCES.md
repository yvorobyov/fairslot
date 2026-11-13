# Loading applications automatically / Автозагрузка заявок

Run `python -m fairslot app` (Python 3.9+ only, no packages). A page opens at `127.0.0.1`. Pick a source, press **one button**. The same works without a window: `python -m fairslot auto` (for a schedule).

Запусти `python -m fairslot app` (нужен только Python 3.9+). Откроется страница. Выбери источник и нажми **одну кнопку**. Без окна: `python -m fairslot auto` (для запуска по расписанию).

| Source / Источник | What to paste / Что вставить | Works with / Подходит |
|---|---|---|
| Google Sheet | link, shared "anyone with the link can view" / ссылка, доступ «всем по ссылке» | Google Forms, Tally, Typeform, Airtable, Excel Online (anything that writes to a sheet / всё, что пишет в таблицу) |
| Calendar `.ics` | secret iCal link / секретная ссылка iCal | Google Calendar, Outlook, Apple, Cal.com, Acuity, Fantastical, any feed |
| Calendly | personal access token / персональный токен | Calendly bookings: partner and level from the booking questions / записи Calendly: партнёр и уровень из вопросов |
| CSV or JSON link | direct link / прямая ссылка | any service with export-by-link, your own script |
| Paste or file / Вставить или файл | CSV text or file / текст или файл CSV | anything: export, copy, paste / всё остальное: выгрузка и вставка |

## Columns / Колонки

Names are recognised in English and Russian (`name`/`имя`, `partner`/`партнёр`, `level`/`уровень`, `start`/`дата`, `email`, `created`/`создано`). Dates in common formats are accepted. No column mapping to set up.

## Calendly

1. Calendly → Integrations → API & webhooks → Personal access tokens → create, copy.
2. In fairslot choose **Calendly**, paste the token once. It is stored in `fairslot-workspace.json` on your computer (owner-only file) and used only to read bookings.
3. Add questions to the event type: «Partner» and «Level» so teams and levels arrive with the booking.

Availability of the API on the Free plan depends on Calendly's current plan rules: check it in your account. If the token option is not offered, use any other row of the table: a Google Form feeding a Sheet, the Calendar `.ics` link of the booking calendar, or Calendly's own CSV export pasted into the page. The draw itself never needs Calendly.

Calendly's API cancels a whole event, so fairslot does not cancel or book anything. It produces an announcement and, if you set a link template, a prefilled booking link for each winner. A person clicks it.

## Roster with levels / Список уровней

Optional second table (Google Sheet or CSV link): `id or email, level, name`. Without it levels come from the answers in the applications.

## Schedule / По расписанию

```
python -m fairslot auto --workspace fairslot-workspace.json --out result.json
```

Fetches, draws with an automatic public seed and prints the announcement. Put it in cron or Windows Task Scheduler.

## Privacy / Приватность

The helper listens on `127.0.0.1` only, requires a per-session token and checks the Host header. Tokens are masked when the page reads settings back. Without the helper the page works offline and sends nothing anywhere.
