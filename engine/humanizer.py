"""
TrendPulse Engine — Humanizer (Anti-AI-Detection)
Analyzes generated content for AI-detection signals and adjusts if needed.
"""
import logging
import math
import re
from collections import Counter

from engine.config import (
    HUMANIZER_ENABLED, PERPLEXITY_THRESHOLD, BURSTINESS_MIN, MAX_REGEN_ATTEMPTS
)

logger = logging.getLogger(__name__)

# Overused AI phrases — if too many appear, content looks AI-generated
AI_CLICHES = [
    "dive into", "game-changer", "in today's world", "fast-paced",
    "it's worth noting", "buckle up", "landscape", "leverage",
    "harness the power", "at the end of the day", "needless to say",
    "in this article", "without further ado", "let's explore",
    "in conclusion", "to sum up", "all in all", "the bottom line",
    "it goes without saying", "stay tuned", "exciting times",
    "cutting-edge", "revolutionary", "groundbreaking", "seamless",
    "robust", "holistic", "synergy", "paradigm shift",
    "navigate the complexities", "ever-evolving", "delve into",
    "multifaceted", "it is important to note", "rest assured",
    "at its core", "when it comes to", "serves as",
]


def calculate_burstiness(text: str) -> float:
    """
    Measure sentence-length variation (burstiness).
    Humans write with high variation; AI tends to be more uniform.
    Returns coefficient of variation (higher = more human-like).
    """
    sentences = re.split(r'[.!?]+', text)
    lengths = [len(s.split()) for s in sentences if s.strip()]
    if len(lengths) < 3:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std = math.sqrt(variance)
    return std / mean  # Coefficient of variation


def calculate_vocabulary_richness(text: str) -> float:
    """
    Type-token ratio: unique words / total words.
    Higher = richer vocabulary = more human-like.
    """
    words = re.findall(r'\b[a-z]+\b', text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def count_ai_cliches(text: str) -> int:
    """Count occurrences of known AI cliché phrases."""
    text_lower = text.lower()
    return sum(1 for phrase in AI_CLICHES if phrase in text_lower)


def estimate_perplexity_proxy(text: str) -> float:
    """
    Approximate "uniformity" score without a real LM.
    Uses word frequency distribution — AI text tends to have
    more uniform word distribution than human text.
    Lower = more uniform = more AI-like.
    """
    words = re.findall(r'\b[a-z]+\b', text.lower())
    if len(words) < 50:
        return 100.0  # Too short to judge
    freq = Counter(words)
    total = len(words)
    # Shannon entropy
    entropy = -sum((c / total) * math.log2(c / total) for c in freq.values() if c > 0)
    # Normalize to a 0-100 scale (typical English text: entropy ~9-11)
    return entropy * 10


def analyze_content(text: str) -> dict:
    """
    Full humanness analysis. Returns a report.
    """
    burstiness = calculate_burstiness(text)
    vocab_richness = calculate_vocabulary_richness(text)
    cliche_count = count_ai_cliches(text)
    perplexity_proxy = estimate_perplexity_proxy(text)

    # Score: 0 (very AI) to 100 (very human)
    score = 0.0
    score += min(25, burstiness * 40)                # Burstiness contributes up to 25
    score += min(25, vocab_richness * 50)             # Vocab richness up to 25
    score += max(0, 25 - cliche_count * 5)            # Clichés reduce score
    score += min(25, (perplexity_proxy - 50) * 0.5)   # Entropy contributes up to 25

    passes = (
        burstiness >= BURSTINESS_MIN
        and cliche_count <= 3
        and perplexity_proxy >= PERPLEXITY_THRESHOLD
    )

    return {
        "burstiness": round(burstiness, 3),
        "vocabulary_richness": round(vocab_richness, 3),
        "ai_cliche_count": cliche_count,
        "perplexity_proxy": round(perplexity_proxy, 1),
        "humanness_score": round(score, 1),
        "passes": passes,
        "issues": _identify_issues(burstiness, cliche_count, perplexity_proxy),
    }


def _identify_issues(burstiness: float, cliches: int, perplexity: float) -> list[str]:
    """Identify specific issues for the regeneration prompt."""
    issues = []
    if burstiness < BURSTINESS_MIN:
        issues.append("Sentence lengths are too uniform — vary between short punchy sentences and longer analytical ones")
    if cliches > 3:
        issues.append(f"Contains {cliches} AI cliché phrases — replace with natural, specific language")
    if perplexity < PERPLEXITY_THRESHOLD:
        issues.append("Word choice is too predictable — use more varied vocabulary and phrasing")
    return issues


def build_humanization_instructions(analysis: dict) -> str:
    """Build specific instructions for regeneration based on analysis."""
    if analysis["passes"]:
        return ""
    instructions = "\n\nCRITICAL REVISION NEEDED — the content reads too much like AI:\n"
    for issue in analysis["issues"]:
        instructions += f"- {issue}\n"
    instructions += """
Additional humanization rules:
- Mix sentence lengths dramatically: some 3-5 word sentences, some 25+ word sentences.
- Use contractions (don't, won't, it's) instead of formal alternatives.
- Include one or two colloquial expressions naturally.
- Vary paragraph lengths (some 1 sentence, some 4-5 sentences).
- Start some sentences with "And" or "But" — real writers do this.
- Include a brief personal-style observation or aside.
"""
    return instructions
