# For Grok

Hey Grok, this is the shared repo for Xavier's site. Claude maintains it. Here's how you can add to it.

1. **Your section:** "Grok / X Pulse" is stored in `data/desk/grok.json` and, for that New York date, under the `grok` key of `data/deskdays/YYYY-MM-DD.json`. Never write `data/deskdays/TODAY.json`. Shape (top-level fields copy the latest report; `reports` is the whole day, oldest first):
   `{"date":"YYYY-MM-DD","at":"<latest ISO>","pulse":"...","bias":"risk-on|risk-off|mixed — reason","items":["who (~time ET): what"],"trump":"...","watch":"...","forSite":[],"reports":[{"at":"<ISO>","pulse":"...","bias":"...","items":["..."],"trump":"...","watch":"...","forSite":[]}]}`
   Each run appends one object to `reports` and does not replace the list. If `date` is not today in New York, start a new list for today. When Claude saves a desk day, copy `grok` from `data/desk/grok.json`, not from `today.json`. The X Pulse tab shows that day's reports, newest first, and clears at midnight New York time. Past days stay on the Calendar.
2. **Adding anything:** in Xavier's Grok chat, start a message with `FOR SITE:`. Claude picks it up at the next refresh and adds it to the site.
3. **Code changes:** write the change in the chat as a `FOR SITE:` message with the file name and the exact code. Claude reviews it and commits it.
4. **Reading the site:** everything is public at https://github.com/NQXAVER/kaixh-trades (data in `data/`). Read `data/reviews/` and `data/journal/` to stay in sync on Xavier's trading.
5. **Earnings results:** `data/desk/earnings-live.json` is written automatically by Grok's X Pulse routine. Shape: `{"date":"YYYY-MM-DD","at":"<ISO>","items":[{"ticker":"MSFT","company":"Microsoft (MSFT)","date":"YYYY-MM-DD","when":"BMO|AMC","status":"reported|upcoming","reaction":"+4% AH","sentiment":"Bullish|Bearish|Mixed","why":"..."}]}`. Claude should not overwrite this file. Claude's `today.json` `earnings` list stays the base list. A live item with the same ticker and date replaces that base row; a new ticker and date is added.
6. **Account spending:** `data/spend/history.json` and `data/spend/purchases.json` are now written automatically by Grok's Account spending watch routine. Claude should not edit them by hand.
7. **Discipline reminders:** `data/desk/reminders.json` is Grok-owned data. Shape: `{"updatedAt":"<ISO>","reminders":[{"text":"...","tag":"..."}]}`. The Desk card reads this file from `main`. Claude should not edit it by hand.
