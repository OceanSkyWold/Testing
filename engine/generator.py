"""
TrendPulse Engine — Content Generator (Ollama)
Generates SEO-optimized articles using local Ollama with dynamic prompts.
"""
import json
import logging
from datetime import datetime

import requests
import markdown

from engine.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE, OLLAMA_NUM_CTX,
    MIN_WORD_COUNT, MAX_WORD_COUNT, SITE_NAME, DATA_DIR
)

logger = logging.getLogger(__name__)


# ── Base System Prompt (Information Gain Framework) ──

BASE_SYSTEM_PROMPT = """You are an expert content writer for {site_name}, a website covering trending topics in sports, tech, products, and news.

YOUR WRITING PHILOSOPHY — "Information Gain":
- NEVER simply summarize what's already available online.
- Every article MUST add unique value: original synthesis, cross-source analysis, a fresh angle, or a practical takeaway readers can't find elsewhere.
- Write as if you're an experienced journalist/analyst with genuine insight into the topic.

STRUCTURE REQUIREMENTS:
1. Start with a "Quick Answer" — a 1-2 sentence standalone summary that could be a featured snippet. Return it inside the tag <answer_box>...</answer_box>
2. Use proper heading hierarchy: one H2 per major section, H3 for subsections.
3. Open with a compelling hook — NOT "In today's fast-paced world..." or any generic opener.
4. Include concrete details: numbers, dates, names, comparisons.
5. End with a forward-looking conclusion or actionable takeaway.

TONE & STYLE:
- Confident, knowledgeable, but accessible. Not academic, not clickbait.
- Use contractions naturally. Vary sentence length — mix short punchy sentences with longer analytical ones.
- Use active voice predominantly.
- Include occasional colloquialisms or natural speech patterns to sound human.
- Avoid these overused AI phrases: "game-changer", "dive into", "landscape", "leverage", "in today's world", "it's worth noting", "buckle up", "stay tuned".

OUTPUT FORMAT:
- Write in Markdown.
- Start with the <answer_box> tag, then the article body.
- Target {min_words}-{max_words} words.
- Include at least 3 H2 sections and appropriate H3 subsections.
- Do NOT include the article title — it will be added separately.

ANTI-SLOP RULES:
- No filler paragraphs. Every paragraph must advance the reader's understanding.
- No vague claims without specifics.
- No repetitive restating of the topic.
- No excessive use of transition words.
"""

# ── Dynamic Prompt Builder ──

def build_prompt(
    topic: str,
    category: str,
    success_templates: list[dict] | None = None,
    negative_constraints: list[str] | None = None,
    style_adjustments: dict | None = None,
) -> tuple[str, str]:
    """
    Build the system prompt and user prompt dynamically.
    Injects learned success patterns and negative constraints.
    Returns (system_prompt, user_prompt).
    """
    system = BASE_SYSTEM_PROMPT.format(
        site_name=SITE_NAME,
        min_words=MIN_WORD_COUNT,
        max_words=MAX_WORD_COUNT,
    )

    # Inject success templates (few-shot examples from self-learner)
    if success_templates:
        system += "\n\nSUCCESS PATTERNS (proven high-performing hooks and structures):\n"
        for tmpl in success_templates[:5]:  # Top 5 only
            system += f"- Hook style: {tmpl.get('hook_pattern', 'N/A')}\n"
            system += f"  Title format: {tmpl.get('title_pattern', 'N/A')}\n"
            system += f"  Why it worked: {tmpl.get('reason', 'N/A')}\n"

    # Inject negative constraints (patterns that led to high bounce rates)
    if negative_constraints:
        system += "\n\nAVOID THESE PATTERNS (they caused high bounce rates):\n"
        for constraint in negative_constraints[:10]:
            system += f"- {constraint}\n"

    # Inject style adjustments from self-learner
    if style_adjustments:
        system += "\n\nSTYLE ADJUSTMENTS (learned from performance data):\n"
        for key, val in style_adjustments.items():
            system += f"- {key}: {val}\n"

    # Category-specific guidance
    category_guidance = {
        "sports": "Include relevant stats, records, and player context. Reference recent game results when applicable.",
        "tech": "Include technical specifics — model numbers, specs, benchmarks. Compare with competitors.",
        "products": "Include pricing context, alternatives, and who each product is best for. Be honest about drawbacks.",
        "news": "Provide context for why this matters. Connect to broader trends. Include multiple perspectives.",
    }
    if category in category_guidance:
        system += f"\n\nCATEGORY-SPECIFIC ({category.upper()}):\n{category_guidance[category]}\n"

    user = f"""Write a comprehensive, original article about this trending topic:

TOPIC: {topic}
CATEGORY: {category}
DATE: {datetime.utcnow().strftime('%B %d, %Y')}

Remember: Add UNIQUE VALUE. Don't just summarize — analyze, compare, synthesize, and provide insight that readers can't easily find elsewhere."""

    return system, user


# ── Ollama API ──

def call_ollama(system_prompt: str, user_prompt: str) -> str | None:
    """Call local Ollama API and return the generated text."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=300,  # 5 min — large models can be slow
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except Exception as e:
        logger.error("Ollama API error: %s", e)
        return None


# ── Title Generator ──

def generate_title(topic: str, category: str) -> str | None:
    """Generate a compelling, non-clickbait title for the article."""
    system = f"""You are a headline writer for {SITE_NAME}. Generate ONE article title.

RULES:
- Be specific and informative, not vague clickbait.
- Include the key topic/subject naturally.
- 50-70 characters ideal for search results.
- No ALL CAPS. No excessive punctuation.
- Avoid: "You Won't Believe", "This One Trick", "Everything You Need to Know".
- Good patterns: "Why X Matters for Y", "X vs Y: What the Data Shows", "The Real Reason Behind X", "X: What Changed and What's Next"

Return ONLY the title, nothing else."""

    user = f"Write a title for a {category} article about: {topic}"

    result = call_ollama(system, user)
    if result:
        # Clean up: remove quotes, extra whitespace
        return result.strip().strip('"\'').strip()
    return None


# ── Meta Description Generator ──

def generate_meta_description(topic: str, title: str) -> str | None:
    """Generate a unique meta description (150-160 chars)."""
    system = f"""Generate a meta description for a web article. RULES:
- 150-160 characters maximum
- Include the main topic naturally
- Compelling but honest — no clickbait
- Return ONLY the description, nothing else."""

    user = f"Title: {title}\nTopic: {topic}"

    result = call_ollama(system, user)
    if result:
        desc = result.strip().strip('"\'')
        if len(desc) > 160:
            desc = desc[:157] + "..."
        return desc
    return None


# ── Content Processing ──

def extract_answer_box(content: str) -> tuple[str, str]:
    """Extract <answer_box> content and return (answer_box, remaining_content)."""
    import re
    match = re.search(r'<answer_box>(.*?)</answer_box>', content, re.DOTALL)
    if match:
        answer = match.group(1).strip()
        remaining = content[:match.start()] + content[match.end():]
        return answer, remaining.strip()
    # If no answer box tag, use the first paragraph
    lines = content.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            return stripped, content
    return "", content


def markdown_to_html(md_content: str) -> str:
    """Convert markdown to HTML with extensions."""
    return markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'toc'],
        output_format='html5',
    )


def count_words(text: str) -> int:
    """Count words in text, stripping markdown/HTML."""
    import re
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'[#*_\[\]\(\)]', '', clean)
    return len(clean.split())


# ── Main Generation Pipeline ──

def generate_article(
    topic: str,
    category: str,
    success_templates: list[dict] | None = None,
    negative_constraints: list[str] | None = None,
    style_adjustments: dict | None = None,
) -> dict | None:
    """
    Full article generation pipeline:
    1. Build dynamic prompt
    2. Generate content via Ollama
    3. Generate title and meta description
    4. Process and return structured article data
    """
    logger.info("Generating article: topic='%s', category='%s'", topic, category)

    # Build dynamic prompt
    system_prompt, user_prompt = build_prompt(
        topic, category, success_templates, negative_constraints, style_adjustments
    )

    # Generate main content
    raw_content = call_ollama(system_prompt, user_prompt)
    if not raw_content:
        logger.error("Content generation failed for topic: %s", topic)
        return None

    # Check word count
    word_count = count_words(raw_content)
    if word_count < MIN_WORD_COUNT // 2:
        logger.warning("Generated content too short (%d words), retrying", word_count)
        raw_content = call_ollama(system_prompt, user_prompt + "\n\nIMPORTANT: Write at least 1200 words.")
        if not raw_content:
            return None
        word_count = count_words(raw_content)

    # Extract answer box
    answer_box, article_body = extract_answer_box(raw_content)

    # Convert to HTML
    html_content = markdown_to_html(article_body)

    # Generate title
    title = generate_title(topic, category)
    if not title:
        title = topic  # Fallback

    # Generate meta description
    meta_desc = generate_meta_description(topic, title)
    if not meta_desc:
        meta_desc = answer_box[:160] if answer_box else f"Trending analysis: {topic}"

    # Build slug
    import re
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]

    article = {
        "title": title,
        "slug": slug,
        "topic": topic,
        "category": category,
        "meta_description": meta_desc,
        "answer_box": answer_box,
        "content_html": html_content,
        "content_md": article_body,
        "word_count": word_count,
        "generated_at": datetime.utcnow().isoformat(),
        "model": OLLAMA_MODEL,
        "prompt_version": _get_prompt_version(),
    }

    logger.info("Article generated: '%s' (%d words)", title, word_count)
    return article


def _get_prompt_version() -> str:
    """Get current prompt version from version history."""
    version_file = DATA_DIR / "prompt_versions.json"
    if version_file.exists():
        versions = json.loads(version_file.read_text(encoding="utf-8"))
        if versions:
            return versions[-1].get("version", "1.0")
    return "1.0"
