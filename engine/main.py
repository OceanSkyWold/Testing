"""
TrendPulse Engine — Main Orchestrator
Runs the full Perceive-Reason-Plan-Act-Observe cycle.

Usage:
  python -m engine.main                # Full cycle: discover, generate, build, publish
  python -m engine.main --dry-run      # Generate without pushing to git
  python -m engine.main --trends-only  # Only discover trends, don't generate
  python -m engine.main --learn        # Only run the self-learning cycle
  python -m engine.main --test-learn   # Test self-learner with mock data
"""
import argparse
import json
import logging
import random
import sys
from datetime import datetime

from engine.config import (
    MAX_ARTICLES_PER_DAY, DATA_DIR, HUMANIZER_ENABLED, MAX_REGEN_ATTEMPTS
)
from engine.trends import discover_trends, trends_to_json
from engine.generator import generate_article
from engine.humanizer import analyze_content, build_humanization_instructions
from engine.builder import (
    build_article_page, save_article_page,
    update_index, update_sitemap, build_category_pages
)
from engine.publisher import init_repo, publish
from engine import memory
from engine.self_learner import run_self_learning_cycle, test_with_mock_data, get_niche_weights
from engine.analytics import update_article_performance, is_analytics_configured

# ── Logging Setup ──

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("engine.main")


def perceive() -> list[dict]:
    """
    PERCEIVE: Gather current trend data and analytics.
    """
    logger.info("═══ PERCEIVE ═══")

    # Fetch analytics if configured
    if is_analytics_configured():
        logger.info("Fetching analytics data...")
        update_article_performance()

    # Discover trends
    logger.info("Discovering trends across platforms...")
    validated_trends = discover_trends()
    trend_data = trends_to_json(validated_trends)

    # Save to working memory
    memory.update_working_memory(trends=trend_data)

    logger.info("Perceived %d validated trends", len(trend_data))
    return trend_data


def reason(trends: list[dict]) -> dict | None:
    """
    REASON: Analyze performance, run self-learning if data exists.
    Returns style adjustments from the learning cycle.
    """
    logger.info("═══ REASON ═══")

    articles = memory.get_recent_articles(10)
    articles_with_perf = [a for a in articles if a.get("performance")]

    if articles_with_perf:
        logger.info("Running self-learning cycle on %d reviewed articles...", len(articles_with_perf))
        review = run_self_learning_cycle()
        if review:
            logger.info("Self-learning assessment: %s", review.get("overall_assessment", ""))
            return review.get("style_adjustments")
    else:
        logger.info("No performance data yet — skipping self-learning")

    return None


def plan(trends: list[dict]) -> list[dict]:
    """
    PLAN: Select the best trends to write about today.
    Applies niche weights from self-learning.
    """
    logger.info("═══ PLAN ═══")

    if not trends:
        logger.warning("No trends available to plan with")
        return []

    # Get niche weights (from self-learner)
    weights = get_niche_weights()
    logger.info("Niche weights: %s", {k: f"{v:.2f}" for k, v in weights.items()})

    # Check what we've already published today
    today = datetime.utcnow().strftime("%Y-%m-%d")
    todays_articles = [
        a for a in memory.get_articles()
        if a.get("generated_at", "").startswith(today)
    ]
    remaining_slots = MAX_ARTICLES_PER_DAY - len(todays_articles)

    if remaining_slots <= 0:
        logger.info("Already published %d articles today (max: %d). Skipping.",
                     len(todays_articles), MAX_ARTICLES_PER_DAY)
        return []

    # Check which topics we've already covered (avoid duplicates)
    existing_topics = {a.get("topic", "").lower() for a in memory.get_articles()}

    # Score and rank trends
    candidates = []
    for trend in trends:
        topic = trend["topic"]
        if topic.lower() in existing_topics:
            continue
        cat = trend.get("suggested_category", "news")
        weight = weights.get(cat, 0.25)
        weighted_score = trend["combined_score"] * (1 + weight)
        candidates.append({**trend, "weighted_score": weighted_score})

    candidates.sort(key=lambda t: t["weighted_score"], reverse=True)
    selected = candidates[:remaining_slots]

    logger.info("Planned %d articles for today", len(selected))
    for s in selected:
        logger.info("  → [%s] %s (score: %.3f)", s["suggested_category"], s["topic"], s["weighted_score"])

    return selected


def act(planned: list[dict], style_adjustments: dict | None, dry_run: bool = False) -> list[dict]:
    """
    ACT: Generate articles, humanize, build pages, publish.
    """
    logger.info("═══ ACT ═══")

    if not planned:
        logger.info("Nothing to act on")
        return []

    success_templates = memory.get_success_templates()
    negative_constraints = memory.get_negative_constraints()
    published = []

    for trend in planned:
        topic = trend["topic"]
        category = trend["suggested_category"]

        # Generate article
        article = generate_article(
            topic=topic,
            category=category,
            success_templates=success_templates,
            negative_constraints=negative_constraints,
            style_adjustments=style_adjustments,
        )

        if not article:
            logger.error("Failed to generate article for: %s", topic)
            continue

        # Humanize check
        if HUMANIZER_ENABLED:
            for attempt in range(MAX_REGEN_ATTEMPTS):
                analysis = analyze_content(article["content_md"])
                logger.info("Humanness check (attempt %d): score=%.1f, passes=%s",
                            attempt + 1, analysis["humanness_score"], analysis["passes"])
                if analysis["passes"]:
                    break
                # Regenerate with humanization instructions
                logger.info("Regenerating with humanization instructions...")
                extra = build_humanization_instructions(analysis)
                article = generate_article(
                    topic=topic,
                    category=category,
                    success_templates=success_templates,
                    negative_constraints=negative_constraints + analysis["issues"],
                    style_adjustments=style_adjustments,
                )
                if not article:
                    break

        if not article:
            continue

        # Build HTML page
        page_html = build_article_page(article)
        save_article_page(article, page_html)

        # Save to memory
        memory.add_article(article)
        published.append(article)
        logger.info("✓ Built article: %s", article["title"])

    # Rebuild site structure
    if published:
        all_articles = memory.get_articles()
        update_index(all_articles)
        update_sitemap(all_articles)
        build_category_pages(all_articles)

        # Publish to git
        init_repo()
        titles = ", ".join(a["title"][:40] for a in published)
        publish(
            message=f"New articles: {titles}",
            dry_run=dry_run,
        )

    return published


def observe(published: list[dict], style_adjustments: dict | None):
    """
    OBSERVE: Log what happened and expected outcomes.
    """
    logger.info("═══ OBSERVE ═══")

    if not published:
        logger.info("No articles published in this cycle")
        return

    # Log the cycle
    memory.log_evolution({
        "type": "publish_cycle",
        "articles_published": len(published),
        "titles": [a["title"] for a in published],
        "categories": [a["category"] for a in published],
        "prompt_version": memory.get_current_prompt_version(),
        "style_adjustments_used": style_adjustments,
        "expected_outcome": "Monitoring for CTR and bounce rate in next cycle",
    })

    for article in published:
        logger.info("Published: [%s] %s (%d words)",
                     article["category"], article["title"], article.get("word_count", 0))

    logger.info("═══ CYCLE COMPLETE ═══")
    logger.info("Total articles in memory: %d", len(memory.get_articles()))
    logger.info("Success templates: %d", len(memory.get_success_templates()))
    logger.info("Negative constraints: %d", len(memory.get_negative_constraints()))
    logger.info("Prompt version: %s", memory.get_current_prompt_version())


# ── Entry Point ──

def main():
    parser = argparse.ArgumentParser(description="TrendPulse Autonomous Content Engine")
    parser.add_argument("--dry-run", action="store_true", help="Generate without pushing to git")
    parser.add_argument("--trends-only", action="store_true", help="Only discover trends")
    parser.add_argument("--learn", action="store_true", help="Only run self-learning cycle")
    parser.add_argument("--test-learn", action="store_true", help="Test self-learner with mock data")
    args = parser.parse_args()

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.test_learn:
        logger.info("Running self-learner test with mock data...")
        result = test_with_mock_data()
        if result:
            print(json.dumps(result, indent=2))
        return

    if args.learn:
        logger.info("Running self-learning cycle...")
        run_self_learning_cycle()
        return

    # Full cycle: Perceive → Reason → Plan → Act → Observe
    trends = perceive()

    if args.trends_only:
        print(json.dumps(trends, indent=2))
        return

    style_adjustments = reason(trends)
    planned = plan(trends)
    published = act(planned, style_adjustments, dry_run=args.dry_run)
    observe(published, style_adjustments)


if __name__ == "__main__":
    main()
