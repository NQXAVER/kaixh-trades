# Kaixh Trades

Xavier's NQ/MNQ trading desk: news, live NQ/ES, economic calendar, earnings, Notion journal reviews, Discord accountability check-ins, daily habits and trading rules, and a calendar that keeps every day.

Live site: https://nqxaver.github.io/kaixh-trades/

## Who does what
- **Claude** builds the site, writes the desk note and headlines in `data/desk/today.json` (≈7 AM, 9 AM, 4 PM, 8 PM, 10 PM ET, when the PC is on), reviews the Notion journal at 12 PM ET (screenshots, TradingView aftermath, Discord check-in), and commits everything here.
- **GitHub Actions** refreshes automatic headlines into `data/desk/feed.json` with no PC and no API key. The Desk tab merges that file with Claude's `news` list. See "Automatic headlines" below.
- **Grok** covers live X (Twitter): the "Grok / X Pulse" section. Claude checks in with Grok in Xavier's Grok chat at every refresh. Anything written there starting with `FOR SITE:` gets added at the next refresh. See `GROK.md`.
- **Xavier** checks off habits and rules, answers review questions and writes reflections on the site. The site saves straight to this repo.

## Data (all JSON, one file per day, nothing is ever deleted)
| Folder | What |
|---|---|
| `data/desk/today.json` | Current news, NQ/ES snapshot, calendar, earnings, Grok pulse. Claude owns this file. |
| `data/desk/feed.json` | Automatic headlines. The scheduled workflow owns this file. Do not hand-edit it. |
| `data/desk/news-rules.json` | Keyword lists for section, NQ impact, and risk lean. |
| `data/deskdays/YYYY-MM-DD.json` | That day's news + Grok pulse, kept forever |
| `data/journal/YYYY-MM-DD_<id>.json` | Snapshot of each Notion Live Journal entry |
| `data/reviews/YYYY-MM-DD.json` | Claude's review, questions, answers, reflection |
| `data/rules/YYYY-MM-DD.json` | Trading rules followed/broken that day |
| `data/habits/YYYY-MM-DD.json` | Daily tasks checked that day |
| `data/spend/purchases.json` | Lucid account purchases Claude refreshes |
| `data/spend/history.json` | All-firm purchases, refunds, and tool fees. The Spending tab merges this with `purchases.json` by order number and keeps the copy from the file with the later `updatedAt`. A null amount was not in the email and is not counted as $0. |

## Automatic headlines
`.github/workflows/desk-news.yml` runs on GitHub's servers. It reads free public RSS feeds (CNBC, MarketWatch, the Federal Reserve, BLS, BBC, Al Jazeera, NPR, the New York Times, the Guardian, OilPrice, EIA, UN News, and the Wall Street Journal), drops duplicates, and commits `data/desk/feed.json` only when the headline list changed. Reuters and AP do not offer a working free feed to this job. No API keys and no secrets.

Weekdays, every 30 minutes from 09:00–23:59 UTC (about 5 AM–8 PM ET in daylight time, 4 AM–7 PM ET in standard time). Weekday overnights, every 2 hours. Weekends, every 3 hours, plus Sunday 22:20 and 23:20 UTC around the futures reopen. It can also be run by hand (`workflow_dispatch`). Scheduled runs start after this workflow is on `main`.

Each headline is tagged with the lists in `data/desk/news-rules.json`:

- **Section.** The keyword group with the highest score wins (Geopolitics / War, Fed and Rates, Economic Data, Mega-cap Tech and Earnings, Energy and Oil, or Other Markets). Ties break in that priority order: war, then economic data, then the Fed, then energy, then tech, then other markets.
- **Impact.** High if the headline hits a tier-1 word (FOMC, CPI, PCE, payrolls, GDP, missiles, Hormuz, a ceasefire, and similar), an oil-shock pair (oil or Brent plus jump, plunge, attack, or fire), or a mega-cap name plus earnings, guidance, or IPO. War plus "nuclear" is also High. Fed, war, economic-data, and energy headlines that are not High are Medium. Everything else kept is Low.
- **Risk lean.** risk-off and risk-on phrases are counted separately. One side produces that lean. Both produce mixed. Neither produces no lean.

Those tags are an automatic guess, not advice. A headline Claude already rated keeps Claude's impact. The Grok pulse, economic calendar, earnings, and live NQ/ES quote are unchanged.
