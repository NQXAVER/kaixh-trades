# For Grok

Hey Grok, this is the shared repo for Xavier's site. Claude maintains it. Here's how you can add to it.

1. **Your section:** "Grok / X Pulse" on the Desk tab, stored in `data/desk/today.json` → `grok` and saved per day in `data/deskdays/YYYY-MM-DD.json`. Shape:
   `{"at": ISO time, "pulse": "...", "bias": "risk-on|risk-off|mixed — reason", "items": ["who (~time ET): what"], "trump": "...", "watch": "...", "forSite": ["..."]}`
2. **Adding anything:** in Xavier's Grok chat, start a message with `FOR SITE:`. Claude picks it up at the next refresh and adds it to the site.
3. **Code changes:** write the change in the chat as a `FOR SITE:` message with the file name and the exact code. Claude reviews it and commits it.
4. **Reading the site:** everything is public at https://github.com/NQXAVER/kaixh-trades (data in `data/`). Read `data/reviews/` and `data/journal/` to stay in sync on Xavier's trading.
