"""
TrendPulse Engine — Three-Tier Memory System
Working Memory, Episodic Memory, and Success Templates.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from engine.config import DATA_DIR, EPISODIC_MEMORY_SIZE

logger = logging.getLogger(__name__)


def _load_json(filename: str) -> list | dict:
    """Load a JSON file from the data directory."""
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_json(filename: str, data):
    """Save data to a JSON file in the data directory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Working Memory ──

def get_working_memory() -> dict:
    """Get current working state (active trends, drafts)."""
    data = _load_json("working_memory.json")
    return data if isinstance(data, dict) else {"trends": [], "drafts": []}


def update_working_memory(trends: list[dict] | None = None, drafts: list[dict] | None = None):
    """Update working memory with current trends and/or drafts."""
    current = get_working_memory()
    if trends is not None:
        current["trends"] = trends
    if drafts is not None:
        current["drafts"] = drafts
    current["updated_at"] = datetime.utcnow().isoformat()
    _save_json("working_memory.json", current)


# ── Episodic Memory (Article History) ──

def get_articles() -> list[dict]:
    """Get all articles from episodic memory."""
    data = _load_json("articles.json")
    return data if isinstance(data, list) else []


def add_article(article: dict):
    """Add an article to episodic memory, maintaining the size limit."""
    articles = get_articles()
    articles.insert(0, article)  # Most recent first
    if len(articles) > EPISODIC_MEMORY_SIZE:
        articles = articles[:EPISODIC_MEMORY_SIZE]
    _save_json("articles.json", articles)
    logger.info("Added article to memory: %s (total: %d)", article.get("title", ""), len(articles))


def get_recent_articles(n: int = 10) -> list[dict]:
    """Get the N most recent articles."""
    return get_articles()[:n]


def update_article_performance(slug: str, performance: dict):
    """Update an article's performance data."""
    articles = get_articles()
    for art in articles:
        if art.get("slug") == slug:
            art["performance"] = performance
            _save_json("articles.json", articles)
            return True
    return False


# ── Success Templates ──

def get_success_templates() -> list[dict]:
    """Get learned high-CTR patterns."""
    data = _load_json("success_templates.json")
    return data if isinstance(data, list) else []


def add_success_template(template: dict):
    """Add a new success template."""
    templates = get_success_templates()
    templates.append({
        **template,
        "added_at": datetime.utcnow().isoformat(),
    })
    # Keep top 20 templates by score
    templates.sort(key=lambda t: t.get("score", 0), reverse=True)
    templates = templates[:20]
    _save_json("success_templates.json", templates)
    logger.info("Added success template: %s", template.get("hook_pattern", ""))


# ── Negative Constraints ──

def get_negative_constraints() -> list[str]:
    """Get patterns to avoid."""
    data = _load_json("negative_constraints.json")
    return data if isinstance(data, list) else []


def add_negative_constraint(constraint: str):
    """Add a negative constraint."""
    constraints = get_negative_constraints()
    if constraint not in constraints:
        constraints.append(constraint)
        _save_json("negative_constraints.json", constraints)
        logger.info("Added negative constraint: %s", constraint)


# ── Prompt Versions ──

def get_prompt_versions() -> list[dict]:
    """Get prompt version history."""
    data = _load_json("prompt_versions.json")
    return data if isinstance(data, list) else []


def add_prompt_version(version: str, changes: str, reasoning: str):
    """Record a new prompt version."""
    versions = get_prompt_versions()
    versions.append({
        "version": version,
        "changes": changes,
        "reasoning": reasoning,
        "created_at": datetime.utcnow().isoformat(),
        "performance_after": None,  # Filled in after evaluation
    })
    _save_json("prompt_versions.json", versions)
    logger.info("New prompt version: %s", version)


def get_current_prompt_version() -> str:
    """Get the latest prompt version string."""
    versions = get_prompt_versions()
    return versions[-1]["version"] if versions else "1.0"


# ── Evolution Log ──

def get_evolution_log() -> list[dict]:
    """Get the full evolution audit trail."""
    data = _load_json("evolution_log.json")
    return data if isinstance(data, list) else []


def log_evolution(event: dict):
    """Log a self-modification event."""
    log = get_evolution_log()
    log.append({
        **event,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # Keep last 100 events
    if len(log) > 100:
        log = log[-100:]
    _save_json("evolution_log.json", log)


# ── Performance Data ──

def get_performance_data() -> list[dict]:
    """Get analytics performance data."""
    data = _load_json("performance.json")
    return data if isinstance(data, list) else []


def save_performance_data(data: list[dict]):
    """Save analytics performance data."""
    _save_json("performance.json", data)
