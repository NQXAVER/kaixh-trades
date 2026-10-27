#!/usr/bin/env python3
"""Refresh data/desk/feed.json from free public RSS/Atom feeds.

The Desk tab merges this file with the news Claude writes in
data/desk/today.json. This script never edits today.json, grok.json,
the economic calendar, or earnings.

Impact and risk lean follow data/desk/news-rules.json. They are a
keyword guess for NQ, not trading advice. The Desk keeps High and Medium
headlines, plus an earnings report from a company that matters to NQ.
Low-impact lines and stories with no market link are left out of the
generated feed. Stored lean values stay risk-on / risk-off / mixed; the
page shows those as Bullish / Bearish / Mixed, or Unclear when neither
side matched.

  python3 scripts/refresh_desk_news.py --self-test
  python3 scripts/refresh_desk_news.py --dry-run
  python3 scripts/refresh_desk_news.py
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "data" / "desk" / "news-rules.json"
OUT_PATH = ROOT / "data" / "desk" / "feed.json"
ET_ZONE = ZoneInfo("America/New_York")
UA = "KaixhTradesDesk/1.0 (+https://github.com/NQXAVER/kaixh-trades)"
PER_FEED = 20
MAX_PER_SECTION = 10
MAX_ITEMS = 60

# keep=True: a headline from this feed is kept even when no keyword hits,
# and filed under default. Other feeds are dropped unless a section matches.
# Reuters and AP do not offer a working free feed from GitHub-hosted runners
# (reuters.com returns 401, AP's old host does not resolve). World and
# business coverage comes from the publisher feeds below.
FEEDS = [
    {"id": "fed-all", "label": "Federal Reserve", "default": "fed", "keep": True,
     "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    {"id": "fed-monetary", "label": "Federal Reserve", "default": "fed", "keep": True,
     "url": "https://www.federalreserve.gov/feeds/press_monetary.xml"},
    # BLS publishes this feed, but some networks (including this repo's
    # runners at times) get HTTP 403. A failure here does not blank the file.
    {"id": "bls", "label": "BLS", "default": "econ", "keep": True,
     "url": "https://www.bls.gov/feed/bls_latest.rss"},
    {"id": "cnbc-world", "label": "CNBC", "keep": False,
     "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html"},
    {"id": "cnbc-econ", "label": "CNBC", "default": "econ", "keep": False,
     "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"id": "cnbc-earn", "label": "CNBC", "default": "tech", "keep": True,
     "url": "https://www.cnbc.com/id/15839135/device/rss/rss.html"},
    {"id": "cnbc-finance", "label": "CNBC", "keep": False,
     "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},
    {"id": "cnbc-tech", "label": "CNBC", "keep": False,
     "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html"},
    {"id": "cnbc-energy", "label": "CNBC", "default": "energy", "keep": False,
     "url": "https://www.cnbc.com/id/19836768/device/rss/rss.html"},
    {"id": "cnbc-top", "label": "CNBC", "keep": False,
     "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"id": "mw-top", "label": "MarketWatch", "keep": False,
     "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"id": "mw-live", "label": "MarketWatch", "keep": False,
     "url": "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/"},
    {"id": "nyt-world", "label": "New York Times", "keep": False,
     "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"id": "nyt-biz", "label": "New York Times", "keep": False,
     "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"},
    {"id": "nyt-econ", "label": "New York Times", "keep": False,
     "url": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"},
    {"id": "bbc-world", "label": "BBC", "keep": False,
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"id": "bbc-biz", "label": "BBC", "keep": False,
     "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"id": "aj", "label": "Al Jazeera", "keep": False,
     "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"id": "npr-world", "label": "NPR", "keep": False,
     "url": "https://feeds.npr.org/1004/rss.xml"},
    {"id": "npr-biz", "label": "NPR", "keep": False,
     "url": "https://feeds.npr.org/1006/rss.xml"},
    {"id": "guard-world", "label": "The Guardian", "keep": False,
     "url": "https://www.theguardian.com/world/rss"},
    {"id": "guard-biz", "label": "The Guardian", "keep": False,
     "url": "https://www.theguardian.com/business/rss"},
    {"id": "guard-econ", "label": "The Guardian", "keep": False,
     "url": "https://www.theguardian.com/business/economics/rss"},
    {"id": "oilprice", "label": "OilPrice", "default": "energy", "keep": False,
     "url": "https://oilprice.com/rss/main"},
    {"id": "eia", "label": "EIA", "default": "energy", "keep": False,
     "url": "https://www.eia.gov/rss/todayinenergy.xml"},
    {"id": "un-peace", "label": "UN News", "keep": False,
     "url": "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml"},
    {"id": "wsj-markets", "label": "WSJ", "keep": False,
     "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"id": "wsj-biz", "label": "WSJ", "keep": False,
     "url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"},
]

# Documented examples. Keep these in sync with news-rules.json.
CASES = [
    ("US weighs more strikes on Iran as Hormuz traffic stalls", "war", "High", "risk-off"),
    ("Iran proposes to reopen Hormuz within seven days", "war", "High", "mixed"),
    ("FOMC holds rates and Powell sounds hawkish", "fed", "High", "risk-off"),
    ("Traders price a rate cut if inflation cools", "fed", "High", "risk-on"),
    ("Core PCE comes in hotter than expected", "econ", "High", "risk-off"),
    ("Jobless claims fall to 198,000", "econ", "Medium", None),
    ("Microsoft earnings beat and the company raises guidance", "tech", "High", "risk-on"),
    ("Apple shares drift ahead of next week", "tech", "Low", None),
    ("Brent jumps above $115 on a tanker fire", "energy", "High", "risk-off"),
    ("Brent slips as traders take profit", "energy", "Medium", "risk-on"),
    ("S&P 500 futures are little changed before the open", "markets", "Low", None),
    ("Nvidia leads a semiconductor rally", "tech", "Medium", "risk-on"),
    ("UPS earnings top estimates", "tech", "Medium", "risk-on"),
    ("Exxon profit rises as oil stays elevated", "energy", "Medium", None),
    ("Consumer confidence misses expectations", "econ", "Medium", "risk-off"),
    ("Gold holds near a record as the dollar firms", "markets", "Low", None),
    ("Fed Chair Warsh speaks after the decision", "fed", "High", None),
    ("Local theater announces a new season", None, None, None),
]


def load_rules() -> dict:
    with RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def word_hit(text: str, raw: str) -> bool:
    w = (raw or "").lower().strip()
    if not w or not text:
        return False
    if " " in w or "&" in w:
        return w in text
    return re.search(r"\b" + re.escape(w) + r"\b", text) is not None


def any_hit(text: str, words) -> bool:
    return any(word_hit(text, w) for w in (words or []))


def keyword_weight(entry) -> tuple[str, int]:
    if isinstance(entry, str):
        return entry, 1
    return str(entry.get("t") or ""), int(entry.get("w") or 1)


def section_score(text: str, section: dict) -> int:
    score = 0
    for entry in section.get("keywords") or []:
        token, weight = keyword_weight(entry)
        if word_hit(text, token):
            score += weight
    return score


def pick_section(text: str, rules: dict) -> tuple[str | None, int]:
    priority = rules.get("priority") or []
    best_id = None
    best_score = 0
    best_pri = 10**9
    for sec in rules.get("sections") or []:
        score = section_score(text, sec)
        if score <= 0:
            continue
        pri = priority.index(sec["id"]) if sec["id"] in priority else 50
        if score > best_score or (score == best_score and pri < best_pri):
            best_id, best_score, best_pri = sec["id"], score, pri
    return best_id, best_score


def guess_impact(text: str, section: str, rules: dict, from_keywords: bool = True) -> str:
    if any_hit(text, rules.get("highAny")):
        return "High"
    for rule in rules.get("highIf") or []:
        if section == rule.get("section") and any_hit(text, rule.get("any")):
            return "High"
    oil = rules.get("highOil") or {}
    if any_hit(text, oil.get("topics")) and any_hit(text, oil.get("moves")):
        return "High"
    cap = rules.get("highCap") or {}
    if any_hit(text, cap.get("names")) and any_hit(text, cap.get("events")):
        return "High"
    # A feed default (Fed press, BLS, the earnings wire) is not itself a
    # market move. Only a real keyword section promotes war, Fed, data, or oil.
    if from_keywords and section in (rules.get("mediumSections") or []):
        return "Medium"
    if any_hit(text, rules.get("mediumAny")):
        return "Medium"
    return "Low"


def guess_lean(text: str, rules: dict) -> str | None:
    off = any_hit(text, rules.get("riskOff"))
    on = any_hit(text, rules.get("riskOn"))
    if off and on:
        return "mixed"
    if off:
        return "risk-off"
    if on:
        return "risk-on"
    return None


def headline_text(title: str) -> str:
    return html.unescape(title or "").lower().replace("\u2019", "'").replace("\u2018", "'")


def is_nq_earnings(text: str, rules: dict) -> bool:
    """An earnings-style report from a company that matters to NQ."""
    names = rules.get("nqNames") or (rules.get("highCap") or {}).get("names") or []
    events = rules.get("earningsEvents") or ["earnings", "guidance", "results", "eps", "revenue", "profit"]
    return any_hit(text, names) and any_hit(text, events)


def classify_text(title: str, rules: dict, default: str | None = None, keep: bool = False):
    """Return section/impact/lean, or None when the headline should be dropped."""
    text = headline_text(title)
    if any_hit(text, rules.get("skip")) and not any_hit(text, rules.get("highAny")):
        return None
    section, score = pick_section(text, rules)
    from_keywords = bool(section) and score > 0
    if section is None:
        if not keep:
            return None
        section = default or "markets"
        from_keywords = False
    elif score <= 0:
        return None
    return {
        "section": section,
        "impact": guess_impact(text, section, rules, from_keywords=from_keywords),
        "lean": guess_lean(text, rules),
    }


def for_desk(title: str, rules: dict, default: str | None = None, keep: bool = False):
    """Headline the Desk should show, or None.

    High and Medium stay. A Low tag stays only when it is an NQ earnings
    report, and that report is shown as Medium. Everything else is left out.
    """
    tagged = classify_text(title, rules, default=default, keep=keep)
    if not tagged:
        return None
    if tagged["impact"] == "Low" and is_nq_earnings(headline_text(title), rules):
        tagged = dict(tagged)
        tagged["impact"] = "Medium"
    if tagged["impact"] not in ("High", "Medium"):
        return None
    return tagged


def self_test(rules: dict) -> int:
    failed = 0
    for title, section, impact, lean in CASES:
        got = classify_text(title, rules)
        if section is None:
            if got is not None:
                print(f"FAIL drop: {title}\n  got {got}")
                failed += 1
            else:
                print(f"ok   drop: {title}")
            continue
        if not got or got["section"] != section or got["impact"] != impact or got["lean"] != lean:
            print(f"FAIL {title}\n  want {section} {impact} {lean}\n  got  {got}")
            failed += 1
        else:
            print(f"ok   {section:8} {impact:6} {str(lean):8} {title}")
    extras = [
        ("Apple shares drift ahead of next week", False, None),
        ("Local theater announces a new season", False, None),
        ("US weighs more strikes on Iran as Hormuz traffic stalls", True, "High"),
        ("Microsoft earnings beat and the company raises guidance", True, "High"),
        ("Nvidia posts quarterly results after the close", True, "High"),
        ("45,000 Nvidia GPUs ship to a new data center", False, None),
        ("Community bank picnic scheduled for June", False, "keep-fed"),
    ]
    for title, should_keep, note in extras:
        if note == "keep-fed":
            got = for_desk(title, rules, default="fed", keep=True)
        else:
            got = for_desk(title, rules)
        kept = got is not None
        if kept != should_keep or (should_keep and got and note and note != "keep-fed" and got["impact"] != note):
            print(f"FAIL desk: {title}\n  want keep={should_keep} {note}\n  got  {got}")
            failed += 1
        else:
            print(f"ok   desk {str(kept):5} {title}")
    if failed:
        print(f"{failed} case(s) failed")
        return 1
    print(f"{len(CASES) + len(extras)} cases passed")
    return 0


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(node, name: str) -> str:
    for el in list(node):
        if local(el.tag) == name:
            return "".join(el.itertext()).strip()
    return ""


def child_link(node) -> str:
    for el in list(node):
        if local(el.tag) != "link":
            continue
        href = (el.get("href") or "").strip()
        if href:
            return href
        text = "".join(el.itertext()).strip()
        if text:
            return text
    return ""


def parse_when(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clean_title(title: str, source: str) -> str:
    title = re.sub(r"\s+", " ", html.unescape(title or "")).strip()
    if source:
        suffix = " - " + source
        if title.lower().endswith(suffix.lower()):
            title = title[: -len(suffix)].strip()
    return title


def norm_title(title: str) -> str:
    text = title.lower().replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def item_id(title: str) -> str:
    digest = hashlib.sha1(norm_title(title).encode("utf-8")).hexdigest()[:12]
    return "f" + digest


def tokens(title: str) -> set[str]:
    return {w for w in norm_title(title).split() if len(w) > 2}


def similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) > 24 and (a in b or b in a):
        return True
    ta, tb = tokens(a), tokens(b)
    if len(ta) < 3 or len(tb) < 3:
        return False
    inter = len(ta & tb)
    union = len(ta | tb)
    return union > 0 and inter / union >= 0.72


def et_label(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(ET_ZONE).strftime("%a %-I:%M %p")


def parse_feed(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", "replace")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    root = ET.fromstring(text)
    nodes = [el for el in root.iter() if local(el.tag) in ("item", "entry")]
    out = []
    for node in nodes[:PER_FEED]:
        title = child_text(node, "title")
        if not title:
            continue
        source = child_text(node, "source")
        title = clean_title(title, source)
        when = parse_when(child_text(node, "pubDate") or child_text(node, "published") or child_text(node, "updated") or child_text(node, "dc:date"))
        if when is None:
            for el in list(node):
                if local(el.tag) == "date":
                    when = parse_when("".join(el.itertext()))
                    if when:
                        break
        out.append({
            "title": title,
            "url": child_link(node),
            "source": source,
            "when": when,
        })
    return out


def fetch_feed(feed: dict) -> tuple[dict, list[dict], str | None]:
    browser_ua = "Mozilla/5.0 (compatible; KaixhTradesDesk/1.0; +https://github.com/NQXAVER/kaixh-trades)"

    def pull(user_agent: str):
        req = urllib.request.Request(feed["url"], headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.read()

    try:
        try:
            raw = pull(UA)
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            raw = pull(browser_ua)
        items = parse_feed(raw)
        return feed, items, None
    except Exception as exc:  # noqa: BLE001 - one bad feed must not blank the desk
        return feed, [], f"{type(exc).__name__}: {exc}"


def max_age(item: dict) -> timedelta:
    if item.get("impact") == "High":
        return timedelta(hours=96)
    if item.get("section") in ("war", "fed", "econ"):
        return timedelta(hours=72)
    return timedelta(hours=48)


def fresh(item: dict, now: datetime) -> bool:
    raw = item.get("publishedAt")
    if not raw:
        return True
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - when <= max_age(item)


def tag_item(title: str, source: str, url: str, when: datetime | None, rules: dict, feed: dict | None) -> dict | None:
    default = (feed or {}).get("default")
    keep = bool((feed or {}).get("keep"))
    tagged = for_desk(title, rules, default=default, keep=keep)
    if not tagged:
        return None
    when_utc = when.astimezone(timezone.utc) if when else None
    return {
        "id": item_id(title),
        "headline": title,
        "source": source or (feed or {}).get("label") or "",
        "url": url or "",
        "publishedAt": when_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if when_utc else "",
        "time": et_label(when_utc),
        "section": tagged["section"],
        "impact": tagged["impact"],
        "lean": tagged["lean"],
        "auto": True,
    }


def impact_rank(impact: str) -> int:
    return {"High": 0, "Medium": 1, "Low": 2}.get(impact or "", 2)


def display_index(section: str, rules: dict) -> int:
    ids = [row["id"] for row in rules.get("display") or []]
    return ids.index(section) if section in ids else 50


def sort_items(items: list[dict], rules: dict) -> list[dict]:
    def key(it: dict):
        return (
            display_index(it.get("section") or "", rules),
            impact_rank(it.get("impact") or ""),
            -(datetime.fromisoformat(it["publishedAt"].replace("Z", "+00:00")).timestamp() if it.get("publishedAt") else 0),
            it.get("headline") or "",
        )
    return sorted(items, key=key)


def dedupe(items: list[dict]) -> list[dict]:
    kept: list[dict] = []
    norms: list[str] = []
    for it in items:
        n = norm_title(it.get("headline") or "")
        if not n:
            continue
        if any(similar(n, prev) for prev in norms):
            continue
        kept.append(it)
        norms.append(n)
    return kept


def cap_items(items: list[dict], rules: dict) -> list[dict]:
    ranked = sorted(items, key=lambda it: (
        impact_rank(it.get("impact") or ""),
        -(datetime.fromisoformat(it["publishedAt"].replace("Z", "+00:00")).timestamp() if it.get("publishedAt") else 0),
    ))
    counts: dict[str, int] = {}
    chosen = []
    for it in ranked:
        sec = it.get("section") or "markets"
        if counts.get(sec, 0) >= MAX_PER_SECTION:
            continue
        counts[sec] = counts.get(sec, 0) + 1
        chosen.append(it)
        if len(chosen) >= MAX_ITEMS:
            break
    return sort_items(chosen, rules)


def load_previous() -> list[dict]:
    if not OUT_PATH.exists():
        return []
    try:
        with OUT_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    items = []
    for it in data.get("items") or []:
        if not it.get("headline"):
            continue
        items.append({
            "id": it.get("id") or item_id(it["headline"]),
            "headline": it["headline"],
            "source": it.get("source") or "",
            "url": it.get("url") or "",
            "publishedAt": it.get("publishedAt") or "",
            "time": it.get("time") or "",
            "section": it.get("section") or "markets",
            "impact": it.get("impact") or "Low",
            "lean": it.get("lean"),
            "auto": True,
        })
    return items


def retag(items: list[dict], rules: dict, now: datetime) -> list[dict]:
    out = []
    for it in items:
        when = None
        if it.get("publishedAt"):
            try:
                when = datetime.fromisoformat(it["publishedAt"].replace("Z", "+00:00"))
            except ValueError:
                when = None
        # Re-apply the keyword rules. A stored headline that no longer matches
        # is dropped, so a feed outage does not freeze a bad tag forever.
        tagged = tag_item(it["headline"], it.get("source") or "", it.get("url") or "", when, rules, None)
        if not tagged:
            continue
        tagged["id"] = it.get("id") or tagged["id"]
        if not fresh(tagged, now):
            continue
        out.append(tagged)
    return out


def signature(items: list[dict]) -> str:
    slim = [{
        "id": it.get("id"),
        "headline": it.get("headline"),
        "source": it.get("source"),
        "url": it.get("url"),
        "publishedAt": it.get("publishedAt"),
        "time": it.get("time"),
        "section": it.get("section"),
        "impact": it.get("impact"),
        "lean": it.get("lean"),
    } for it in items]
    return json.dumps(slim, ensure_ascii=False, sort_keys=True)


def build(rules: dict) -> tuple[list[dict], list[dict]]:
    now = datetime.now(timezone.utc)
    found: list[dict] = []
    sources = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_feed, feed) for feed in FEEDS]
        for fut in as_completed(futures):
            feed, rows, err = fut.result()
            sources.append({
                "id": feed["id"],
                "label": feed["label"],
                "ok": err is None,
                "items": len(rows),
                "error": err,
            })
            for row in rows:
                item = tag_item(row["title"], row["source"] or feed["label"], row["url"], row["when"], rules, feed)
                if not item:
                    continue
                if item.get("publishedAt") and not fresh(item, now):
                    continue
                found.append(item)
    previous = retag(load_previous(), rules, now)
    # Newer fetch wins on duplicates because it is listed first after a time sort
    # inside dedupe's input: put fresh fetches ahead of the stored file.
    found.sort(key=lambda it: it.get("publishedAt") or "", reverse=True)
    merged = dedupe(found + previous)
    merged = [it for it in merged if fresh(it, now)]
    return cap_items(merged, rules), sorted(sources, key=lambda s: s["id"])


def summarize(items: list[dict], sources: list[dict]) -> None:
    counts: dict[str, int] = {}
    for it in items:
        counts[it.get("section") or "?"] = counts.get(it.get("section") or "?", 0) + 1
    ok = sum(1 for s in sources if s["ok"])
    print(f"sources {ok}/{len(sources)} ok, headlines {len(items)} {counts}")
    for src in sources:
        if not src["ok"]:
            print(f"  FAIL {src['id']}: {src['error']}")
    for sec in ("war", "fed", "econ", "tech", "energy", "markets"):
        sample = [it for it in items if it.get("section") == sec][:3]
        for it in sample:
            lean = it.get("lean") or "-"
            print(f"  {sec:8} {it.get('impact'):6} {lean:8} {it.get('time'):12} {it.get('source')}: {it.get('headline')[:110]}")


def write_feed(items: list[dict], sources: list[dict], rules: dict) -> bool:
    """Write the file when the headline set changed. Return True if written."""
    previous_sig = None
    if OUT_PATH.exists():
        try:
            with OUT_PATH.open(encoding="utf-8") as f:
                previous_sig = signature(json.load(f).get("items") or [])
        except (OSError, json.JSONDecodeError):
            previous_sig = None
    if previous_sig == signature(items):
        print("feed unchanged")
        return False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "updatedAt": now,
        "generatedBy": "scripts/refresh_desk_news.py",
        "schedule": "Weekdays every 30 minutes from 09:00-23:59 UTC, weekday overnights every 2 hours, weekends every 3 hours, plus Sunday 22:20 and 23:20 UTC.",
        "disclaimer": rules.get("disclaimer") or "",
        "note": "Automatic headlines only. The Desk page merges these with news, calendar, earnings, and grok from data/desk/today.json. Claude keeps writing that file.",
        "sources": [{k: s[k] for k in ("id", "label", "ok", "items", "error")} for s in sources],
        "items": items,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {OUT_PATH.relative_to(ROOT)} ({len(items)} headlines)")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Refresh the Desk headline feed")
    parser.add_argument("--self-test", action="store_true", help="check keyword tags and exit")
    parser.add_argument("--dry-run", action="store_true", help="fetch and print, do not write")
    args = parser.parse_args(argv)
    rules = load_rules()
    if args.self_test:
        return self_test(rules)
    items, sources = build(rules)
    summarize(items, sources)
    ok = sum(1 for s in sources if s["ok"])
    if ok == 0:
        print("every feed failed; leaving the existing file alone", file=sys.stderr)
        return 1
    if args.dry_run:
        print("dry-run: no file written")
        return 0
    write_feed(items, sources, rules)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
