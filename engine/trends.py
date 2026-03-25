"""
TrendPulse Engine — Trend Discovery
Pulls trending topics from multiple free platforms and cross-references them.
"""
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime

import requests
import certifi

from engine.config import (
    REDDIT_SUBS, GOOGLE_TRENDS_GEO, TREND_CORROBORATION_MIN, CATEGORIES
)

# Use certifi CA bundle (fixes missing system certs on some Windows setups)
SSL_VERIFY = certifi.where()

logger = logging.getLogger(__name__)

# Respectful request headers — don't pretend to be a browser
HEADERS = {
    "User-Agent": "TrendPulse/1.0 (Trend Research Bot; +https://github.com)",
    "Accept": "application/json",
}

# Rate limiting: minimum seconds between requests to the same domain
_last_request_time: dict[str, float] = {}
MIN_REQUEST_GAP = 2.0


@dataclass
class TrendSignal:
    """A single trending signal from one platform."""
    title: str
    platform: str
    score: float           # Normalized 0-1 relevance/momentum
    url: str = ""
    category_hint: str = ""
    raw_data: dict | None = None


@dataclass
class ValidatedTrend:
    """A trend corroborated across multiple platforms."""
    topic: str
    signals: list[TrendSignal]
    platforms: list[str]
    combined_score: float
    suggested_category: str
    discovered_at: str


def _rate_limit(domain: str):
    """Simple rate limiter per domain."""
    now = time.time()
    last = _last_request_time.get(domain, 0)
    gap = now - last
    if gap < MIN_REQUEST_GAP:
        time.sleep(MIN_REQUEST_GAP - gap)
    _last_request_time[domain] = time.time()


def _safe_get(url: str, params: dict | None = None, timeout: int = 15) -> dict | None:
    """GET with error handling and rate limiting."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    _rate_limit(domain)
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout, verify=SSL_VERIFY)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


# ── Platform: Reddit ──

def fetch_reddit_trends() -> list[TrendSignal]:
    """Fetch hot posts from configured subreddits."""
    signals: list[TrendSignal] = []
    for sub in REDDIT_SUBS:
        data = _safe_get(f"https://www.reddit.com/r/{sub}/hot.json", params={"limit": 10})
        if not data or "data" not in data:
            continue
        for post in data["data"].get("children", []):
            d = post.get("data", {})
            score_raw = d.get("score", 0)
            # Normalize: Reddit scores vary wildly. Log-scale normalization.
            import math
            norm_score = min(1.0, math.log1p(score_raw) / 12.0)  # ~160k = 1.0
            if norm_score < 0.3:
                continue  # Skip low-engagement posts
            signals.append(TrendSignal(
                title=d.get("title", ""),
                platform="reddit",
                score=norm_score,
                url=f"https://reddit.com{d.get('permalink', '')}",
                category_hint=_guess_category(sub),
            ))
    logger.info("Reddit: found %d signals", len(signals))
    return signals


def _guess_category(subreddit: str) -> str:
    """Map subreddit to our category."""
    mapping = {
        "technology": "tech", "gadgets": "tech",
        "sports": "sports", "nba": "sports", "nfl": "sports", "soccer": "sports",
        "BuyItForLife": "products", "deals": "products",
        "news": "news", "worldnews": "news", "todayilearned": "news",
    }
    return mapping.get(subreddit, "news")


# ── Platform: HackerNews ──

def fetch_hackernews_trends() -> list[TrendSignal]:
    """Fetch top stories from HN."""
    signals: list[TrendSignal] = []
    ids = _safe_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids:
        return signals
    for story_id in ids[:15]:
        story = _safe_get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not story or story.get("type") != "story":
            continue
        import math
        score_raw = story.get("score", 0)
        norm_score = min(1.0, math.log1p(score_raw) / 8.0)  # ~3000 = 1.0
        if norm_score < 0.3:
            continue
        signals.append(TrendSignal(
            title=story.get("title", ""),
            platform="hackernews",
            score=norm_score,
            url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            category_hint="tech",
        ))
    logger.info("HackerNews: found %d signals", len(signals))
    return signals


# ── Platform: Google Trends (pytrends) ──

def fetch_google_trends() -> list[TrendSignal]:
    """Fetch daily trending searches from Google Trends."""
    signals: list[TrendSignal] = []
    try:
        import os
        os.environ["REQUESTS_CA_BUNDLE"] = SSL_VERIFY
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.5)
        # Try daily trending searches first, fall back to realtime if needed
        try:
            trending = pytrends.trending_searches(pn='united_states')
        except Exception:
            trending = pytrends.realtime_trending_searches(pn='US')
        for i, row in trending.head(20).iterrows():
            query = row[0]
            # Google Trends doesn't give scores for daily trends, so rank-based
            norm_score = max(0.3, 1.0 - (i * 0.04))
            signals.append(TrendSignal(
                title=query,
                platform="google_trends",
                score=norm_score,
                url=f"https://trends.google.com/trends/explore?q={query}&geo={GOOGLE_TRENDS_GEO}",
                category_hint="",  # Unknown — will be classified later
            ))
    except Exception as e:
        logger.warning("Google Trends fetch failed: %s", e)
    logger.info("Google Trends: found %d signals", len(signals))
    return signals


# ── Platform: Wikipedia Pageviews (spike detection) ──

def fetch_wikipedia_spikes() -> list[TrendSignal]:
    """Fetch most-viewed Wikipedia articles (indicates public interest spikes)."""
    signals: list[TrendSignal] = []
    from datetime import timedelta
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")
    data = _safe_get(
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{yesterday}"
    )
    if not data or "items" not in data:
        return signals
    articles = data["items"][0].get("articles", [])
    # Skip generic pages
    skip = {"Main_Page", "Special:Search", "-", "Wikipedia:Main_Page"}
    for art in articles[:30]:
        title = art.get("article", "")
        if title in skip or title.startswith("Special:") or title.startswith("Wikipedia:"):
            continue
        views = art.get("views", 0)
        import math
        norm_score = min(1.0, math.log1p(views) / 16.0)  # ~9M = 1.0
        if norm_score < 0.3:
            continue
        signals.append(TrendSignal(
            title=title.replace("_", " "),
            platform="wikipedia",
            score=norm_score,
            url=f"https://en.wikipedia.org/wiki/{title}",
            category_hint="",
        ))
    logger.info("Wikipedia: found %d signals", len(signals))
    return signals


# ── Cross-Platform Corroboration ──

def _normalize_topic(text: str) -> str:
    """Rough normalization for fuzzy matching."""
    import re
    return re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()


def _topics_match(a: str, b: str) -> bool:
    """Check if two topic strings are about the same thing."""
    na, nb = _normalize_topic(a), _normalize_topic(b)
    if not na or not nb:
        return False
    # Exact match
    if na == nb:
        return True
    # One contains the other
    if na in nb or nb in na:
        return True
    # Word overlap > 50%
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / min(len(wa), len(wb))
    return overlap >= 0.5


def _classify_category(topic: str, hints: list[str]) -> str:
    """Determine best category from hints and keyword analysis."""
    # If hints agree, use that
    hint_counts = Counter(h for h in hints if h)
    if hint_counts:
        best_hint = hint_counts.most_common(1)[0][0]
        if best_hint in CATEGORIES:
            return best_hint

    # Keyword-based fallback
    t = topic.lower()
    sports_kw = {"nba", "nfl", "mlb", "game", "player", "team", "score", "coach",
                 "championship", "match", "league", "quarterback", "touchdown", "finals"}
    tech_kw = {"ai", "app", "software", "chip", "gpu", "apple", "google", "microsoft",
               "startup", "cyber", "hack", "data", "cloud", "robot", "model"}
    product_kw = {"buy", "deal", "price", "review", "best", "cheap", "sale",
                  "amazon", "product", "worth", "comparison"}

    words = set(t.split())
    scores = {
        "sports": len(words & sports_kw),
        "tech": len(words & tech_kw),
        "products": len(words & product_kw),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "news"


def discover_trends() -> list[ValidatedTrend]:
    """
    Main entry: fetch from all platforms, cross-reference, return validated trends.
    Only trends appearing on >= TREND_CORROBORATION_MIN platforms are returned.
    """
    all_signals: list[TrendSignal] = []

    # Fetch from all platforms
    all_signals.extend(fetch_reddit_trends())
    all_signals.extend(fetch_hackernews_trends())
    all_signals.extend(fetch_google_trends())
    all_signals.extend(fetch_wikipedia_spikes())

    logger.info("Total raw signals: %d", len(all_signals))

    # Group by topic (fuzzy matching)
    groups: list[list[TrendSignal]] = []
    used = [False] * len(all_signals)

    for i, sig_a in enumerate(all_signals):
        if used[i]:
            continue
        group = [sig_a]
        used[i] = True
        for j, sig_b in enumerate(all_signals):
            if used[j] or i == j:
                continue
            if _topics_match(sig_a.title, sig_b.title):
                group.append(sig_b)
                used[j] = True
        groups.append(group)

    # Filter by corroboration
    validated: list[ValidatedTrend] = []
    for group in groups:
        platforms = list({s.platform for s in group})
        if len(platforms) < TREND_CORROBORATION_MIN:
            continue
        # Pick the best title (longest, usually most descriptive)
        best_title = max(group, key=lambda s: len(s.title)).title
        combined_score = sum(s.score for s in group) / len(group)
        hints = [s.category_hint for s in group]
        category = _classify_category(best_title, hints)

        validated.append(ValidatedTrend(
            topic=best_title,
            signals=group,
            platforms=platforms,
            combined_score=combined_score,
            suggested_category=category,
            discovered_at=datetime.utcnow().isoformat(),
        ))

    # Sort by combined score
    validated.sort(key=lambda t: t.combined_score, reverse=True)
    logger.info("Validated trends (corroborated on %d+ platforms): %d",
                TREND_CORROBORATION_MIN, len(validated))
    return validated


def trends_to_json(trends: list[ValidatedTrend]) -> list[dict]:
    """Serialize trends for storage."""
    result = []
    for t in trends:
        d = {
            "topic": t.topic,
            "platforms": t.platforms,
            "combined_score": round(t.combined_score, 3),
            "suggested_category": t.suggested_category,
            "discovered_at": t.discovered_at,
            "signal_count": len(t.signals),
        }
        result.append(d)
    return result
