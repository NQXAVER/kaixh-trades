# Kaixh Trades

Xavier's NQ/MNQ trading desk: news, live NQ/ES, economic calendar, earnings, Notion journal reviews, Discord accountability check-ins, daily habits and trading rules, and a calendar that keeps every day.

Live site: https://nqxaver.github.io/kaixh-trades/

## Who does what
- **Claude** builds the site, refreshes the news (≈7 AM, 9 AM, 4 PM, 8 PM, 10 PM ET), reviews the Notion journal at 12 PM ET (screenshots, TradingView aftermath, Discord check-in), and commits everything here.
- **Grok** covers live X (Twitter): the "Grok / X Pulse" section. Claude checks in with Grok in Xavier's Grok chat at every refresh. Anything written there starting with `FOR SITE:` gets added at the next refresh. See `GROK.md`.
- **Xavier** checks off habits and rules, answers review questions and writes reflections on the site. The site saves straight to this repo.

## Data (all JSON, one file per day, nothing is ever deleted)
| Folder | What |
|---|---|
| `data/desk/today.json` | Current news, NQ/ES snapshot, calendar, earnings, Grok pulse |
| `data/deskdays/YYYY-MM-DD.json` | That day's news + Grok pulse, kept forever |
| `data/journal/YYYY-MM-DD_<id>.json` | Snapshot of each Notion Live Journal entry |
| `data/reviews/YYYY-MM-DD.json` | Claude's review, questions, answers, reflection |
| `data/rules/YYYY-MM-DD.json` | Trading rules followed/broken that day |
| `data/habits/YYYY-MM-DD.json` | Daily tasks checked that day |
| `data/spend/purchases.json` | Lucid account purchases Claude refreshes |
| `data/spend/history.json` | All-firm purchases, refunds, and tool fees. The Spending tab merges this with `purchases.json` by order number and keeps the copy from the file with the later `updatedAt`. A null amount was not in the email and is not counted as $0. |
