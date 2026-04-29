import logging
import hashlib
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo

import feedparser
from fastapi import FastAPI, Query
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from dateutil import parser as date_parser
from textblob import TextBlob

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("advanced_market_news_service")

# =============================================================================
# APP
# =============================================================================
app = FastAPI(title="Advanced Market News Service v2")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

# =============================================================================
# CONFIG
# =============================================================================
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_DAYS_LIMIT = 180
MAX_DAYS_LIMIT = 3650

REQUEST_TIMEOUT_SECONDS = 12
RETRY_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 1.0

CACHE_TTL_SECONDS = 120
CACHE_MAX_ITEMS = 500

# Simple in-memory TTL cache:
# cache_key -> {"expires_at": epoch_seconds, "payload": dict}
_QUERY_CACHE: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# SYMBOL MAPPINGS
# =============================================================================
SYMBOL_ALIASES: Dict[str, List[str]] = {
    "RELIANCE": ["Reliance Industries", "RIL", "Mukesh Ambani"],
    "SBIN": ["State Bank of India", "SBI"],
    "HDFCBANK": ["HDFC Bank"],
    "ICICIBANK": ["ICICI Bank"],
    "TCS": ["Tata Consultancy Services", "TCS"],
    "INFY": ["Infosys"],
    "ADANIENT": ["Adani Enterprises", "Adani"],
    "ADANIPORTS": ["Adani Ports"],
    "BHARTIARTL": ["Bharti Airtel", "Airtel"],
    "ITC": ["ITC Ltd", "ITC Limited"],
    "ASIANPAINT": ["Asian Paints"],
    "KOTAKBANK": ["Kotak Mahindra", "Kotak Bank"],
    "LT": ["Larsen & Toubro", "L&T", "L and T"],
    "AXISBANK": ["Axis Bank"],
    "BAJFINANCE": ["Bajaj Finance"],
    "M&M": ["Mahindra & Mahindra", "Mahindra and Mahindra", "M and M", "M M"],
    "SUNPHARMA": ["Sun Pharmaceutical", "Sun Pharma"],
    "MARUTI": ["Maruti Suzuki"],
    "TITAN": ["Titan Company", "Titan"],
}

# =============================================================================
# FEEDS
# =============================================================================
RSS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "https://www.thehindubusinessline.com/markets/stock-markets/feeder/default.rss",
    "https://www.financialexpress.com/market/stock-market/feed/",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/marketsNews",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.investing.com/rss/news_25.rss",
    "https://feeds.feedburner.com/ndtvprofit-latest",
    "https://www.livemint.com/rss/markets",
]

# =============================================================================
# FINANCE SENTIMENT LEXICON
# =============================================================================
BULLISH_PHRASES = {
    "beats estimates": 0.45,
    "strong growth": 0.35,
    "profit rises": 0.30,
    "surges": 0.28,
    "rallies": 0.25,
    "upgrades": 0.30,
    "raises guidance": 0.40,
    "record high": 0.25,
    "expands margin": 0.30,
    "sees upside": 0.22,
    "buyback": 0.20,
    "dividend": 0.18,
    "order win": 0.18,
    "expansion": 0.15,
    "growth": 0.10,
}

BEARISH_PHRASES = {
    "misses estimates": -0.45,
    "profit falls": -0.35,
    "slumps": -0.28,
    "falls": -0.22,
    "downgrades": -0.30,
    "cuts guidance": -0.40,
    "loss widens": -0.35,
    "lawsuit": -0.20,
    "probe": -0.22,
    "weak demand": -0.25,
    "margin pressure": -0.28,
    "selloff": -0.30,
    "decline": -0.10,
    "correction": -0.15,
}

# =============================================================================
# HELPERS
# =============================================================================
def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_text(text: str) -> str:
    text = clean_html(text).lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def compact_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(text))

def make_cache_key(symbol: Optional[str], limit: int, days_limit: int) -> str:
    raw = f"{symbol or '__all__'}|{limit}|{days_limit}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def get_cached_payload(cache_key: str) -> Optional[dict]:
    entry = _QUERY_CACHE.get(cache_key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _QUERY_CACHE.pop(cache_key, None)
        return None
    return entry["payload"]

def set_cached_payload(cache_key: str, payload: dict) -> None:
    if len(_QUERY_CACHE) >= CACHE_MAX_ITEMS:
        # Cheap cleanup: remove expired items first, then oldest arbitrary items.
        now = time.time()
        expired_keys = [k for k, v in _QUERY_CACHE.items() if v["expires_at"] <= now]
        for k in expired_keys:
            _QUERY_CACHE.pop(k, None)
        if len(_QUERY_CACHE) >= CACHE_MAX_ITEMS:
            for k in list(_QUERY_CACHE.keys())[:50]:
                _QUERY_CACHE.pop(k, None)

    _QUERY_CACHE[cache_key] = {
        "expires_at": time.time() + CACHE_TTL_SECONDS,
        "payload": payload,
    }

def download_feed(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return resp.read()

def fetch_feed_with_retry(url: str) -> feedparser.FeedParserDict:
    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            raw = download_feed(url)
            feed = feedparser.parse(raw)
            return feed
        except Exception as e:
            last_error = e
            logger.warning(f"Feed fetch attempt {attempt}/{RETRY_ATTEMPTS} failed for {url}: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_SLEEP_SECONDS)
    raise last_error  # type: ignore[misc]

def parse_entry_date(entry: dict) -> Optional[datetime]:
    # Best path: parsed time tuple fields from feedparser
    for key in ("published_parsed", "updated_parsed", "created_parsed", "date_parsed"):
        t = entry.get(key)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=UTC).astimezone(IST)
                return dt
            except Exception:
                pass

    # Fallback: parse string fields
    for key in ("published", "updated", "created", "date"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = date_parser.parse(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(IST)
        except Exception:
            continue

    return None

def keyword_matches(text: str, keyword: str) -> bool:
    norm_text = normalize_text(text)
    raw_text = text.lower()
    norm_kw = normalize_text(keyword)
    compact_kw = compact_text(keyword)

    if not norm_kw:
        return False

    # For short symbols and abbreviations use token boundaries.
    if len(compact_kw) <= 4:
        pattern = rf"\b{re.escape(norm_kw)}\b"
        if re.search(pattern, norm_text):
            return True
        pattern_raw = rf"\b{re.escape(keyword.lower().strip())}\b"
        return re.search(pattern_raw, raw_text) is not None

    # For longer names, normalized containment is enough.
    if norm_kw in norm_text:
        return True

    # Fallback to compact match for symbols with punctuation like M&M.
    if compact_kw and compact_kw in compact_text(text):
        return True

    return False

def build_symbol_keywords(symbol: Optional[str]) -> Tuple[List[str], str]:
    if not symbol:
        return [], ""

    symbol_u = symbol.upper().strip()
    aliases = SYMBOL_ALIASES.get(symbol_u, [])
    keywords = [symbol_u] + aliases

    # Add cleaned forms for punctuation-heavy symbols
    if symbol_u == "M&M":
        keywords.extend(["M and M", "Mahindra and Mahindra", "Mahindra & Mahindra"])

    # De-duplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        k = kw.strip()
        if not k:
            continue
        key = k.lower()
        if key not in seen:
            seen.add(key)
            unique_keywords.append(k)

    return unique_keywords, symbol_u

def compute_sentiment(text: str) -> Tuple[float, str, List[str]]:
    cleaned = clean_html(text)
    norm = normalize_text(cleaned)

    # Base sentiment from TextBlob
    try:
        base_score = float(TextBlob(cleaned).sentiment.polarity)
    except Exception:
        base_score = 0.0

    # Finance-aware adjustment
    bonus = 0.0
    reasons: List[str] = []

    for phrase, weight in BULLISH_PHRASES.items():
        if phrase in norm:
            bonus += weight
            reasons.append(f"bullish phrase: {phrase}")

    for phrase, weight in BEARISH_PHRASES.items():
        if phrase in norm:
            bonus += weight
            reasons.append(f"bearish phrase: {phrase}")

    combined = (base_score * 0.55) + (bonus * 0.45)
    combined = max(-1.0, min(1.0, combined))
    combined = round(combined, 3)

    if combined >= 0.22:
        label = "Bullish"
    elif combined >= 0.08:
        label = "Slightly Bullish"
    elif combined <= -0.22:
        label = "Bearish"
    elif combined <= -0.08:
        label = "Slightly Bearish"
    else:
        label = "Neutral"

    return combined, label, reasons

def generate_hash(item: Dict[str, Any]) -> str:
    unique_string = (
        (item.get("link") or "").strip() +
        "|" +
        (item.get("title") or "").strip().lower() +
        "|" +
        (item.get("source") or "").strip().lower()
    )
    return hashlib.md5(unique_string.encode("utf-8")).hexdigest()

def infer_relevance(
    item: Dict[str, Any],
    symbol: Optional[str],
    matched_term: Optional[str],
    published_date: Optional[datetime],
    days_limit: int,
    sentiment_score: float
) -> float:
    score = 0.0

    if symbol:
        if matched_term:
            if matched_term.upper().strip() == symbol.upper().strip():
                score += 3.0
            else:
                score += 2.0
        else:
            score -= 4.0

    # Recency: newest should rank higher
    if published_date:
        age_days = max(0.0, (datetime.now(IST) - published_date).total_seconds() / 86400.0)
        recency_factor = max(0.0, 1.0 - (age_days / max(days_limit, 1)))
        score += recency_factor * 2.0

    # Slight boost for strong sentiment magnitude
    score += min(abs(sentiment_score), 1.0) * 0.25

    # Small source quality heuristic
    source = (item.get("source") or "").lower()
    if "reuters" in source:
        score += 0.4
    elif "business standard" in source or "financial express" in source:
        score += 0.2

    return round(score, 3)

def matches_symbol(item_text: str, symbol: str) -> Tuple[bool, Optional[str], str]:
    keywords, symbol_u = build_symbol_keywords(symbol)
    if not keywords:
        return True, None, "no-symbol-filter"

    for kw in keywords:
        if keyword_matches(item_text, kw):
            match_type = "symbol" if kw.upper().strip() == symbol_u else "alias"
            return True, kw, match_type

    return False, None, "no-match"

# =============================================================================
# ROUTES
# =============================================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "advanced-news-service-v2",
        "cache_items": len(_QUERY_CACHE),
        "timezone": "Asia/Kolkata",
    }

@app.get("/debug/feeds")
def debug_feeds():
    return {
        "status": "success",
        "feed_count": len(RSS_FEEDS),
        "feeds": RSS_FEEDS,
        "aliases": SYMBOL_ALIASES,
    }

@app.get("/news")
def get_news(
    symbol: Optional[str] = Query(None, description="Stock symbol filter, e.g. RELIANCE"),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    days_limit: int = Query(DEFAULT_DAYS_LIMIT, ge=1, le=MAX_DAYS_LIMIT, description="Lookback window in days"),
    include_sentiment_reason: bool = Query(True, description="Include sentiment reasons"),
):
    cache_key = make_cache_key(symbol, limit, days_limit)
    cached = get_cached_payload(cache_key)
    if cached is not None:
        return {
            "status": "success",
            "source": "cache",
            **cached,
        }

    all_entries: List[Dict[str, Any]] = []
    seen_hashes = set()
    cutoff_date = datetime.now(IST) - timedelta(days=days_limit)

    feeds_ok = 0
    feeds_failed = 0

    symbol_u = symbol.upper().strip() if symbol else None

    for url in RSS_FEEDS:
        try:
            feed = fetch_feed_with_retry(url)
            feeds_ok += 1

            if not getattr(feed, "entries", None):
                logger.info(f"Feed returned 0 entries: {url}")
                continue

            source_title = feed.feed.get("title", "Unknown Source")

            for entry in feed.entries:
                title = clean_html(entry.get("title", "") or "")
                summary = clean_html(entry.get("summary", "") or entry.get("description", "") or "")
                link = (entry.get("link") or "").strip()

                if not title and not summary:
                    continue

                published_date = parse_entry_date(entry)
                if not published_date:
                    # Don’t throw away the entry silently unless it is truly unusable.
                    # If the user wants the freshest possible feed, unknown dates are still not ideal,
                    # so we skip them in symbol-specific mode and allow them in general mode.
                    if symbol_u:
                        continue
                else:
                    if published_date < cutoff_date:
                        continue

                text_content = f"{title} {summary}".strip()

                if symbol_u:
                    ok, matched_term, match_type = matches_symbol(text_content, symbol_u)
                    if not ok:
                        continue
                else:
                    matched_term = None
                    match_type = "general"

                sentiment_score, sentiment_label, sentiment_reasons = compute_sentiment(text_content)

                item = {
                    "title": title,
                    "link": link,
                    "published": published_date.isoformat() if published_date else None,
                    "summary": summary,
                    "source": source_title,
                    "matched_symbol": symbol_u,
                    "matched_term": matched_term,
                    "match_type": match_type,
                    "sentiment_score": sentiment_score,
                    "sentiment_label": sentiment_label,
                }

                relevance_score = infer_relevance(
                    item=item,
                    symbol=symbol_u,
                    matched_term=matched_term,
                    published_date=published_date,
                    days_limit=days_limit,
                    sentiment_score=sentiment_score,
                )
                item["relevance_score"] = relevance_score

                if include_sentiment_reason:
                    item["sentiment_reason"] = sentiment_reasons

                item_hash = generate_hash(item)
                if item_hash in seen_hashes:
                    continue

                seen_hashes.add(item_hash)
                all_entries.append(item)

        except Exception as e:
            feeds_failed += 1
            logger.error(f"Error parsing feed {url}: {e}")

    # Sort:
    # 1) relevance score (especially important for symbol filtered queries)
    # 2) published date newest first
    def sort_key(x: Dict[str, Any]):
        published = x.get("published")
        try:
            dt = datetime.fromisoformat(published) if published else datetime.min.replace(tzinfo=IST)
        except Exception:
            dt = datetime.min.replace(tzinfo=IST)
        return (x.get("relevance_score", 0.0), dt)

    all_entries.sort(key=sort_key, reverse=True)

    payload = {
        "count": len(all_entries),
        "query": {
            "symbol": symbol_u,
            "limit": limit,
            "days_limit": days_limit,
        },
        "feed_stats": {
            "feeds_ok": feeds_ok,
            "feeds_failed": feeds_failed,
            "total_feeds": len(RSS_FEEDS),
        },
        "data": all_entries[:limit],
    }

    set_cached_payload(cache_key, payload)

    return {
        "status": "success",
        "source": "live",
        **payload,
    }

@app.get("/debug/item-match")
def debug_item_match(
    symbol: str = Query(...),
    text: str = Query(..., description="Headline or combined text to test matching"),
):
    keywords, symbol_u = build_symbol_keywords(symbol)
    matches = []
    for kw in keywords:
        if keyword_matches(text, kw):
            matches.append(kw)

    sentiment_score, sentiment_label, sentiment_reasons = compute_sentiment(text)

    return {
        "status": "success",
        "symbol": symbol_u,
        "keywords": keywords,
        "matched_keywords": matches,
        "matched": len(matches) > 0,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "sentiment_reason": sentiment_reasons,
        "normalized_text": normalize_text(text),
    }

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7007)