"""
TrendPulse Engine — Analytics Reader
Pulls performance data from Google Analytics 4 and Search Console (both free).
Stub implementation — activate once GA4 property is set up.
"""
import json
import logging
from datetime import datetime, timedelta

from engine.config import GA4_CREDENTIALS_FILE, GA4_PROPERTY_ID
from engine import memory

logger = logging.getLogger(__name__)


def is_analytics_configured() -> bool:
    """Check if GA4 credentials are set up."""
    return bool(GA4_CREDENTIALS_FILE and GA4_PROPERTY_ID)


def fetch_analytics(days: int = 7) -> list[dict]:
    """
    Fetch page-level analytics from GA4.
    Returns list of {page, pageviews, avg_duration, bounce_rate, ctr}.

    NOTE: This requires setting up a GA4 service account. Steps:
    1. Go to console.cloud.google.com → Create project
    2. Enable "Google Analytics Data API"
    3. Create a Service Account → download JSON key
    4. In GA4 → Admin → Property Access → add the service account email
    5. Set GA4_CREDENTIALS and GA4_PROPERTY_ID env vars
    """
    if not is_analytics_configured():
        logger.info("GA4 not configured. Using stub data.")
        return _get_stub_data()

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric
        )
        import os
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GA4_CREDENTIALS_FILE

        client = BetaAnalyticsDataClient()
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
            ],
        )
        response = client.run_report(request)

        results = []
        for row in response.rows:
            page = row.dimension_values[0].value
            if "/articles/" not in page:
                continue
            slug = page.split("/articles/")[-1].replace(".html", "")
            results.append({
                "slug": slug,
                "page": page,
                "pageviews": int(row.metric_values[0].value),
                "avg_duration": float(row.metric_values[1].value),
                "bounce_rate": float(row.metric_values[2].value),
            })

        logger.info("Fetched analytics for %d pages", len(results))
        return results

    except ImportError:
        logger.warning("google-analytics-data not installed. Run: pip install google-analytics-data google-auth")
        return _get_stub_data()
    except Exception as e:
        logger.error("GA4 fetch error: %s", e)
        return _get_stub_data()


def fetch_search_console_ctr(days: int = 7) -> dict[str, float]:
    """
    Fetch CTR per page from Google Search Console.
    Returns {slug: ctr}.

    NOTE: Requires similar service account setup with Search Console API.
    """
    if not is_analytics_configured():
        return {}

    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            GA4_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        response = service.searchanalytics().query(
            siteUrl=f"sc-domain:your-domain.com",  # Update with actual domain
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["page"],
                "rowLimit": 100,
            },
        ).execute()

        ctr_map = {}
        for row in response.get("rows", []):
            page = row["keys"][0]
            if "/articles/" in page:
                slug = page.split("/articles/")[-1].replace(".html", "").rstrip("/")
                ctr_map[slug] = row.get("ctr", 0)

        return ctr_map

    except Exception as e:
        logger.warning("Search Console fetch failed: %s", e)
        return {}


def update_article_performance():
    """
    Merge analytics + Search Console data and update article memory.
    """
    analytics = fetch_analytics()
    ctr_data = fetch_search_console_ctr()

    updated = 0
    for entry in analytics:
        slug = entry["slug"]
        perf = {
            "pageviews": entry["pageviews"],
            "avg_duration": entry["avg_duration"],
            "bounce_rate": entry["bounce_rate"],
            "ctr": ctr_data.get(slug, 0),
            "fetched_at": datetime.utcnow().isoformat(),
        }
        if memory.update_article_performance(slug, perf):
            updated += 1

    logger.info("Updated performance for %d articles", updated)
    memory.save_performance_data(analytics)
    return updated


def _get_stub_data() -> list[dict]:
    """Return empty stub when GA4 isn't configured."""
    return []
