"""
TrendPulse Engine — Self-Learner
Uses Ollama to analyze its own performance, evolve prompts, and auto-pivot niches.
"""
import json
import logging
from datetime import datetime

import requests

from engine.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_CTX,
    HIGH_CTR_THRESHOLD, HIGH_BOUNCE_THRESHOLD,
    PROMPT_ROLLBACK_WINDOW, CATEGORIES
)
from engine import memory

logger = logging.getLogger(__name__)


def _call_ollama_json(system_prompt: str, user_prompt: str) -> dict | None:
    """Call Ollama and parse JSON response."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": OLLAMA_NUM_CTX},
        "format": "json",
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        return json.loads(content)
    except Exception as e:
        logger.error("Self-learner Ollama call failed: %s", e)
        return None


# ── Performance Review ──

def run_performance_review() -> dict | None:
    """
    Feed performance data to Ollama and get analysis.
    This is the core self-learning cycle.
    """
    articles = memory.get_recent_articles(10)
    if not articles:
        logger.info("No articles to review yet")
        return None

    # Only review articles that have performance data
    reviewed = [a for a in articles if a.get("performance")]
    if not reviewed:
        logger.info("No performance data available yet")
        return None

    success_templates = memory.get_success_templates()
    negative_constraints = memory.get_negative_constraints()

    system = """You are a content strategist reviewing your own past work. You must analyze article performance data and provide specific, actionable improvements.

Return a JSON object with these fields:
{
  "new_success_patterns": [
    {"hook_pattern": "description of what worked", "title_pattern": "title format", "reason": "why it worked", "score": 0.0-1.0}
  ],
  "new_negative_constraints": ["specific patterns to avoid"],
  "prompt_suggestions": {"change_description": "what to change in the content generation prompt", "reasoning": "why this change should help"},
  "niche_recommendations": {"prioritize": ["categories to do more of"], "deprioritize": ["categories to do less of"], "reasoning": "data-driven explanation"},
  "style_adjustments": {"key": "value pairs of style changes"},
  "overall_assessment": "2-3 sentence summary of current performance"
}"""

    user = f"""Here are my last {len(reviewed)} articles with performance data:

{json.dumps([{
    'title': a['title'],
    'category': a['category'],
    'word_count': a.get('word_count', 0),
    'performance': a.get('performance', {}),
    'generated_at': a['generated_at'],
} for a in reviewed], indent=2)}

Current success templates: {json.dumps(success_templates[:5], indent=2)}
Current negative constraints: {json.dumps(negative_constraints[:10], indent=2)}

Analyze the performance patterns. What's working? What's failing? How should I evolve my content strategy?"""

    result = _call_ollama_json(system, user)
    if result:
        logger.info("Performance review complete: %s", result.get("overall_assessment", ""))
    return result


# ── Apply Self-Learning Results ──

def apply_learning(review: dict):
    """Apply the results of a performance review to the memory system."""
    if not review:
        return

    # Add new success patterns
    for pattern in review.get("new_success_patterns", []):
        memory.add_success_template(pattern)

    # Add new negative constraints
    for constraint in review.get("new_negative_constraints", []):
        memory.add_negative_constraint(constraint)

    # Evolve prompt version
    prompt_suggestions = review.get("prompt_suggestions", {})
    if prompt_suggestions.get("change_description"):
        current_version = memory.get_current_prompt_version()
        # Increment version
        try:
            major, minor = current_version.split(".")
            new_version = f"{major}.{int(minor) + 1}"
        except ValueError:
            new_version = "1.1"

        memory.add_prompt_version(
            version=new_version,
            changes=prompt_suggestions["change_description"],
            reasoning=prompt_suggestions.get("reasoning", ""),
        )

    # Log the evolution
    memory.log_evolution({
        "type": "performance_review",
        "review_summary": review.get("overall_assessment", ""),
        "changes_applied": {
            "new_success_patterns": len(review.get("new_success_patterns", [])),
            "new_negative_constraints": len(review.get("new_negative_constraints", [])),
            "prompt_evolved": bool(prompt_suggestions.get("change_description")),
            "niche_adjustments": review.get("niche_recommendations", {}),
        },
    })

    logger.info("Applied self-learning results")


# ── Hook Pattern Extraction (for high-CTR articles) ──

def extract_hook_pattern(article: dict) -> dict | None:
    """Use Ollama to extract the hook pattern from a high-performing article."""
    system = """Analyze this high-performing article and extract its success pattern.
Return JSON:
{
  "hook_pattern": "describe the opening hook style (e.g., 'direct stat comparison', 'contrarian take', 'breaking news angle')",
  "title_pattern": "describe the title format (e.g., 'question format with specific subject', 'X vs Y comparison')",
  "content_structure": "describe the article structure that worked",
  "reason": "why this combination likely drove high engagement",
  "score": 0.8
}"""

    user = f"""Title: {article['title']}
Category: {article['category']}
Word count: {article.get('word_count', 0)}
Performance: {json.dumps(article.get('performance', {}))}

Article opening (first 500 chars):
{article.get('content_md', '')[:500]}"""

    return _call_ollama_json(system, user)


# ── Failure Diagnosis (for high-bounce articles) ──

def diagnose_failure(article: dict) -> dict | None:
    """Use Ollama to diagnose why an article had high bounce rate."""
    system = """Analyze this underperforming article and diagnose why it failed.
Return JSON:
{
  "diagnosis": "what went wrong (e.g., 'title promised comparison but article only covered one product')",
  "constraint": "specific rule to add to avoid this in the future",
  "category": "message_mismatch | thin_content | wrong_audience | poor_structure | stale_topic"
}"""

    user = f"""Title: {article['title']}
Category: {article['category']}
Word count: {article.get('word_count', 0)}
Performance: {json.dumps(article.get('performance', {}))}

Article opening (first 500 chars):
{article.get('content_md', '')[:500]}"""

    return _call_ollama_json(system, user)


# ── Prompt Rollback Check ──

def check_prompt_rollback() -> bool:
    """
    If the last N articles (PROMPT_ROLLBACK_WINDOW) underperformed
    after a prompt version change, rollback to the previous version.
    Returns True if rollback was performed.
    """
    versions = memory.get_prompt_versions()
    if len(versions) < 2:
        return False

    articles = memory.get_recent_articles(PROMPT_ROLLBACK_WINDOW)
    recent_with_perf = [a for a in articles if a.get("performance")]
    if len(recent_with_perf) < PROMPT_ROLLBACK_WINDOW:
        return False  # Not enough data to judge

    current_version = versions[-1]["version"]
    articles_on_current = [
        a for a in recent_with_perf
        if a.get("prompt_version") == current_version
    ]

    if len(articles_on_current) < PROMPT_ROLLBACK_WINDOW:
        return False

    # Check if all recent articles underperformed
    all_articles = memory.get_articles()
    avg_ctr = _calculate_avg_metric(all_articles, "ctr")
    if avg_ctr == 0:
        return False

    recent_avg_ctr = _calculate_avg_metric(articles_on_current, "ctr")
    if recent_avg_ctr < avg_ctr * 0.8:  # 20% below average
        logger.warning(
            "Prompt version %s underperforming (CTR: %.2f vs avg %.2f). Rolling back.",
            current_version, recent_avg_ctr, avg_ctr
        )
        # Rollback: re-add previous version as new version
        prev = versions[-2]
        memory.add_prompt_version(
            version=f"{current_version}-rollback",
            changes=f"Rollback to {prev['version']} due to underperformance",
            reasoning=f"CTR dropped to {recent_avg_ctr:.2f} (avg: {avg_ctr:.2f}) over {PROMPT_ROLLBACK_WINDOW} articles",
        )
        memory.log_evolution({
            "type": "prompt_rollback",
            "from_version": current_version,
            "to_version": prev["version"],
            "reason": f"CTR {recent_avg_ctr:.2f} vs avg {avg_ctr:.2f}",
        })
        return True

    return False


def _calculate_avg_metric(articles: list[dict], metric: str) -> float:
    """Calculate average of a performance metric across articles."""
    values = [
        a.get("performance", {}).get(metric, 0)
        for a in articles
        if a.get("performance", {}).get(metric) is not None
    ]
    return sum(values) / len(values) if values else 0.0


# ── Niche Weight Adjustment ──

def get_niche_weights() -> dict[str, float]:
    """
    Calculate category weights based on performance.
    Better-performing categories get higher weights.
    """
    articles = memory.get_articles()
    if not articles:
        # Equal weights by default
        return {cat: 1.0 / len(CATEGORIES) for cat in CATEGORIES}

    cat_scores: dict[str, list[float]] = {cat: [] for cat in CATEGORIES}
    for art in articles:
        cat = art.get("category", "")
        perf = art.get("performance", {})
        if cat in cat_scores and perf:
            # Combined score: CTR weight + inverse bounce rate
            ctr = perf.get("ctr", 0)
            bounce = perf.get("bounce_rate", 0.5)
            score = ctr * (1 - bounce)
            cat_scores[cat].append(score)

    # Calculate average score per category
    weights = {}
    for cat in CATEGORIES:
        scores = cat_scores[cat]
        if scores:
            weights[cat] = sum(scores) / len(scores)
        else:
            weights[cat] = 0.5  # Default for untested categories

    # Normalize to sum to 1
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


# ── Full Self-Learning Cycle ──

def run_self_learning_cycle():
    """
    Execute the complete self-learning cycle:
    1. Check for prompt rollback
    2. Analyze high-performers → extract patterns
    3. Analyze failures → add constraints
    4. Run full performance review
    5. Apply learnings
    """
    logger.info("Starting self-learning cycle...")

    # Step 1: Check rollback
    if check_prompt_rollback():
        logger.warning("Prompt rollback performed")

    # Step 2: Extract patterns from high performers
    articles = memory.get_articles()
    all_with_perf = [a for a in articles if a.get("performance")]
    if all_with_perf:
        avg_ctr = _calculate_avg_metric(all_with_perf, "ctr")
        threshold = avg_ctr * HIGH_CTR_THRESHOLD

        for art in all_with_perf[:10]:
            ctr = art.get("performance", {}).get("ctr", 0)
            if ctr > threshold and not art.get("pattern_extracted"):
                pattern = extract_hook_pattern(art)
                if pattern:
                    memory.add_success_template(pattern)
                    art["pattern_extracted"] = True

        # Step 3: Diagnose failures
        for art in all_with_perf[:10]:
            bounce = art.get("performance", {}).get("bounce_rate", 0)
            if bounce > HIGH_BOUNCE_THRESHOLD and not art.get("failure_diagnosed"):
                diagnosis = diagnose_failure(art)
                if diagnosis and diagnosis.get("constraint"):
                    memory.add_negative_constraint(diagnosis["constraint"])
                    art["failure_diagnosed"] = True

    # Step 4: Full performance review
    review = run_performance_review()

    # Step 5: Apply learnings
    if review:
        apply_learning(review)

    logger.info("Self-learning cycle complete")
    return review


# ── CLI Test Mode ──

def test_with_mock_data():
    """Test self-learner with mock performance data."""
    mock_articles = [
        {
            "title": "Why the NBA's New Play-In Format Changes Everything",
            "slug": "nba-play-in-format-changes",
            "category": "sports",
            "word_count": 1450,
            "content_md": "The NBA's play-in tournament isn't just a scheduling tweak...",
            "generated_at": "2026-03-20T10:00:00",
            "prompt_version": "1.0",
            "performance": {"ctr": 0.08, "bounce_rate": 0.35, "pageviews": 450, "avg_duration": 180},
        },
        {
            "title": "RTX 5070 vs RTX 4080: The Real-World Benchmark Showdown",
            "slug": "rtx-5070-vs-4080-benchmarks",
            "category": "tech",
            "word_count": 1800,
            "content_md": "Forget the marketing slides. We ran both cards through...",
            "generated_at": "2026-03-21T10:00:00",
            "prompt_version": "1.0",
            "performance": {"ctr": 0.12, "bounce_rate": 0.28, "pageviews": 890, "avg_duration": 240},
        },
        {
            "title": "10 Things You Need This Spring",
            "slug": "spring-products-2026",
            "category": "products",
            "word_count": 900,
            "content_md": "Spring is here and it's time to refresh your...",
            "generated_at": "2026-03-22T10:00:00",
            "prompt_version": "1.0",
            "performance": {"ctr": 0.03, "bounce_rate": 0.78, "pageviews": 120, "avg_duration": 45},
        },
    ]

    # Save mock data
    for art in mock_articles:
        memory.add_article(art)

    logger.info("Mock data loaded. Running self-learning cycle...")
    return run_self_learning_cycle()
