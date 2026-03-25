"""
TrendPulse Engine — Configuration
All settings in one place. Edit this file to customize the engine.
"""
import os
from pathlib import Path

# ── Paths ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_ROOT / "site"
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATE_DIR = SITE_DIR  # Templates live in site/
ARTICLES_DIR = SITE_DIR / "articles"

# ── Ollama ──
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:latest")
OLLAMA_TEMPERATURE = 0.75  # Slight creativity, not too random
OLLAMA_NUM_CTX = 8192      # Context window

# ── Content ──
MIN_WORD_COUNT = 1200
MAX_WORD_COUNT = 2000
MAX_ARTICLES_PER_DAY = 2   # Ramp up slowly to look organic
CATEGORIES = ["sports", "tech", "products", "news"]

# ── Trend Discovery ──
# Subreddits to monitor (JSON endpoint: reddit.com/r/{sub}/hot.json)
REDDIT_SUBS = [
    "technology", "gadgets", "sports", "nba", "nfl", "soccer",
    "BuyItForLife", "deals", "news", "worldnews", "todayilearned",
]
# Google Trends geo (US by default)
GOOGLE_TRENDS_GEO = "US"
# Minimum number of platforms a trend must appear on to qualify
TREND_CORROBORATION_MIN = 2

# ── Self-Learning ──
HIGH_CTR_THRESHOLD = 1.35     # 35% above average → extract success pattern
HIGH_BOUNCE_THRESHOLD = 0.70  # 70% → diagnose failure
PROMPT_ROLLBACK_WINDOW = 5    # Revert prompt if 5 articles underperform
EPISODIC_MEMORY_SIZE = 50     # Keep last N articles in memory

# ── Publishing ──
SITE_NAME = "TrendPulse"
SITE_URL = os.environ.get("SITE_URL", "")  # Set after GitHub Pages setup
GA4_MEASUREMENT_ID = os.environ.get("GA4_ID", "G-XXXXXXXXXX")
GIT_REMOTE = os.environ.get("GIT_REMOTE", "origin")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")

# ── Humanizer (anti-AI-detection) ──
HUMANIZER_ENABLED = True
PERPLEXITY_THRESHOLD = 30.0   # If below this, content is too uniform → regenerate
BURSTINESS_MIN = 0.4          # Minimum sentence-length variation
MAX_REGEN_ATTEMPTS = 3        # Max regeneration attempts before accepting

# ── Analytics (GA4 + Search Console) ──
GA4_CREDENTIALS_FILE = os.environ.get("GA4_CREDENTIALS", "")
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
