"""
TrendPulse Engine — Page Builder
Injects generated content into HTML templates and updates site structure.
"""
import json
import logging
import re
import html
from datetime import datetime
from pathlib import Path

from engine.config import (
    SITE_DIR, TEMPLATE_DIR, ARTICLES_DIR, DATA_DIR,
    GA4_MEASUREMENT_ID, SITE_NAME, SITE_URL, CATEGORIES
)

logger = logging.getLogger(__name__)


def _read_template(name: str) -> str:
    """Read an HTML template file."""
    path = TEMPLATE_DIR / name
    return path.read_text(encoding="utf-8")


def _escape(text: str) -> str:
    """Escape text for safe HTML attribute insertion."""
    return html.escape(text, quote=True)


def build_article_page(article: dict) -> str:
    """Build a complete article HTML page from template + article data."""
    template = _read_template("article-template.html")

    published_dt = datetime.fromisoformat(article["generated_at"])
    published_human = published_dt.strftime("%b %d, %Y")
    published_iso = published_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Estimate read time
    read_time = max(1, article.get("word_count", 1200) // 250)

    # Title short (for breadcrumb)
    title_short = article["title"][:50] + "..." if len(article["title"]) > 50 else article["title"]

    # Category slug
    category_slug = article["category"].lower().replace(" ", "-")

    # Placeholder for related articles and sidebar — populated later
    related_html = _build_related_placeholder()
    trending_html = _build_trending_placeholder()

    # Replace all template variables
    replacements = {
        "{{TITLE}}": _escape(article["title"]),
        "{{META_DESCRIPTION}}": _escape(article.get("meta_description", "")),
        "{{CANONICAL_URL}}": f"{SITE_URL}/articles/{article['slug']}.html",
        "{{OG_IMAGE}}": "",  # Generated articles won't have images initially
        "{{PUBLISHED_ISO}}": published_iso,
        "{{PUBLISHED_HUMAN}}": published_human,
        "{{CATEGORY}}": _escape(article["category"].title()),
        "{{CATEGORY_SLUG}}": category_slug,
        "{{TITLE_SHORT}}": _escape(title_short),
        "{{READ_TIME}}": str(read_time),
        "{{ANSWER_BOX}}": article.get("answer_box", ""),
        "{{CONTENT}}": article["content_html"],
        "{{RELATED_ARTICLES}}": related_html,
        "{{TRENDING_SIDEBAR}}": trending_html,
        "G-XXXXXXXXXX": GA4_MEASUREMENT_ID,
    }

    page = template
    for key, val in replacements.items():
        page = page.replace(key, val)

    return page


def _build_related_placeholder() -> str:
    """Build minimal placeholder for related articles."""
    return "<!-- Related articles populated on next build -->"


def _build_trending_placeholder() -> str:
    """Build placeholder for trending sidebar."""
    return "<li><a href='/'>More trending articles coming soon</a></li>"


def save_article_page(article: dict, page_html: str):
    """Save the article HTML file to the articles directory."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ARTICLES_DIR / f"{article['slug']}.html"
    filepath.write_text(page_html, encoding="utf-8")
    logger.info("Saved article page: %s", filepath)
    return filepath


def update_index(articles: list[dict]):
    """
    Rebuild the homepage index.html with the latest articles.
    Reads existing articles from data/articles.json and rebuilds the grid.
    """
    index_path = SITE_DIR / "index.html"
    index_html = index_path.read_text(encoding="utf-8")

    # Build the featured article (latest)
    if articles:
        latest = articles[0]
        featured_html = _build_featured_card(latest)
        # Replace featured article section
        index_html = re.sub(
            r'<article class="featured-article">.*?</article>',
            featured_html,
            index_html,
            flags=re.DOTALL,
        )

    # Build article grid cards
    grid_cards = ""
    for art in articles[:9]:  # Show up to 9 on homepage
        grid_cards += _build_article_card(art)

    # Replace grid content
    index_html = re.sub(
        r'(<div class="article-grid" id="article-grid">).*?(</div>\s*</section>)',
        rf'\1\n{grid_cards}\n\2',
        index_html,
        flags=re.DOTALL,
    )

    # Build category sections
    for cat in CATEGORIES:
        cat_articles = [a for a in articles if a.get("category") == cat][:3]
        cat_cards = "".join(_build_article_card(a) for a in cat_articles)
        index_html = re.sub(
            rf'(<div class="article-grid" id="{cat}-grid">).*?(</div>)',
            rf'\1\n{cat_cards}\n\2',
            index_html,
            flags=re.DOTALL,
        )

    index_path.write_text(index_html, encoding="utf-8")
    logger.info("Updated index.html with %d articles", len(articles))


def _build_featured_card(article: dict) -> str:
    """Build featured article HTML."""
    dt = datetime.fromisoformat(article["generated_at"])
    read_time = max(1, article.get("word_count", 1200) // 250)
    return f'''<article class="featured-article">
      <img class="featured-article__image" src="https://placehold.co/800x533?text={_escape(article['category'].title())}" alt="{_escape(article['title'])}" loading="eager" width="800" height="533">
      <div class="featured-article__body">
        <span class="article-card__category">{_escape(article['category'].title())}</span>
        <h2 class="featured-article__title">
          <a href="/articles/{article['slug']}.html">{_escape(article['title'])}</a>
        </h2>
        <p class="featured-article__excerpt">{_escape(article.get('meta_description', ''))}</p>
        <div class="article-card__meta">
          <time datetime="{dt.strftime('%Y-%m-%d')}">{dt.strftime('%b %d, %Y')}</time>
          <span>&middot;</span>
          <span>{read_time} min read</span>
        </div>
      </div>
    </article>'''


def _build_article_card(article: dict) -> str:
    """Build a single article card for the grid."""
    dt = datetime.fromisoformat(article["generated_at"])
    read_time = max(1, article.get("word_count", 1200) // 250)
    excerpt = article.get("meta_description", article.get("answer_box", ""))
    return f'''
        <article class="article-card">
          <img class="article-card__image" src="https://placehold.co/600x338?text={_escape(article['category'].title())}" alt="{_escape(article['title'])}" loading="lazy" width="600" height="338">
          <div class="article-card__body">
            <span class="article-card__category">{_escape(article['category'].title())}</span>
            <h3 class="article-card__title"><a href="/articles/{article['slug']}.html">{_escape(article['title'])}</a></h3>
            <p class="article-card__excerpt">{_escape(excerpt)}</p>
            <div class="article-card__meta">
              <time datetime="{dt.strftime('%Y-%m-%d')}">{dt.strftime('%b %d, %Y')}</time>
              <span>&middot;</span>
              <span>{read_time} min read</span>
            </div>
          </div>
        </article>'''


def update_sitemap(articles: list[dict]):
    """Update sitemap.xml with all article URLs."""
    sitemap_path = SITE_DIR / "sitemap.xml"
    urls = [
        '  <url>\n    <loc>/</loc>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>',
    ]
    for cat in CATEGORIES:
        urls.append(f'  <url>\n    <loc>/category-{cat}.html</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>')

    for art in articles:
        dt = datetime.fromisoformat(art["generated_at"]).strftime("%Y-%m-%d")
        urls.append(
            f'  <url>\n    <loc>/articles/{art["slug"]}.html</loc>\n'
            f'    <lastmod>{dt}</lastmod>\n    <changefreq>monthly</changefreq>\n'
            f'    <priority>0.6</priority>\n  </url>'
        )

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(urls)
    sitemap += "\n</urlset>\n"
    sitemap_path.write_text(sitemap, encoding="utf-8")
    logger.info("Updated sitemap.xml with %d URLs", len(urls))


def build_category_pages(articles: list[dict]):
    """Build/update category pages."""
    template = _read_template("category-template.html")
    for cat in CATEGORIES:
        cat_articles = [a for a in articles if a.get("category") == cat]
        cards = "".join(_build_article_card(a) for a in cat_articles)

        page = template
        page = page.replace("{{CATEGORY}}", cat.title())
        page = page.replace("{{CATEGORY_LOWER}}", cat)
        page = page.replace("{{CATEGORY_SLUG}}", cat)
        page = page.replace("{{ARTICLE_CARDS}}", cards)
        page = page.replace("G-XXXXXXXXXX", GA4_MEASUREMENT_ID)

        filepath = SITE_DIR / f"category-{cat}.html"
        filepath.write_text(page, encoding="utf-8")
        logger.info("Updated category page: %s", filepath)
