"""Glassdoor review collector: fetch raw reviews via ScrapFly (typeahead + BFF API). No scoring."""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, List

from app.config import get_settings
from app.models.glassdoor import GlassdoorReview

logger = logging.getLogger(__name__)

# Cap pages to conserve ScrapFly API limit (each BFF request = 1 credit)
MAX_SCRAPFLY_PAGES = 10
BFF_PAGE_SIZE = 5


def _reviews_url(employer_name: str, employer_id: str) -> str:
    """Build Glassdoor reviews page URL from employer name and ID."""
    slug = (employer_name or "").replace(" ", "-").strip() or "Company"
    return f"https://www.glassdoor.com/Reviews/{slug}-Reviews-E{employer_id}.htm"


def _parse_reviews_metadata(html: str) -> dict | None:
    """Parse employer_id and dynamic_profile_id from reviews page script tag."""
    match = re.search(r'"employer"\s*:\s*(\{[^}]+\})', html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return {
            "employer_id": int(data["id"]),
            "dynamic_profile_id": int(data["profileId"]),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.debug("glassdoor_metadata_parse_error error=%s", e)
        return None


def _bff_body(employer_id: int, dynamic_profile_id: int, page: int) -> str:
    """JSON body for Glassdoor BFF employer-reviews POST."""
    return json.dumps({
        "applyDefaultCriteria": True,
        "employerId": employer_id,
        "employmentStatuses": ["REGULAR", "PART_TIME"],
        "jobTitle": None,
        "goc": None,
        "location": {},
        "defaultLanguage": "eng",
        "language": "eng",
        "mlHighlightSearch": None,
        "onlyCurrentEmployees": False,
        "overallRating": None,
        "pageSize": BFF_PAGE_SIZE,
        "page": page,
        "preferredTldId": 0,
        "reviewCategories": [],
        "sort": "DATE",
        "textSearch": "",
        "worldwideFilter": False,
        "dynamicProfileId": dynamic_profile_id,
        "useRowProfileTldForRatings": True,
        "enableKeywordSearch": True,
    })


def _review_date_from_api(v: Any) -> datetime | None:
    """Parse review date from BFF (ISO string or ms timestamp)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            pass
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(int(v) / 1000.0 if int(v) > 1e12 else int(v))
        except (ValueError, OSError):
            pass
    return None


def _job_title_from_review(raw: dict, _root: dict | None = None) -> str:
    """Extract job title text; resolve __ref if present."""
    job = raw.get("jobTitle") or raw.get("jobTitleKey")
    if job is None:
        return ""
    if isinstance(job, str):
        return job
    if isinstance(job, dict):
        if "__ref" in job and _root:
            ref = job["__ref"]
            node = _root.get(ref, {}) if isinstance(_root, dict) else {}
            if isinstance(node, dict):
                return (node.get("text") or node.get("label") or "") or ""
        return (job.get("text") or job.get("label") or "") or ""
    return ""


def _map_bff_review_to_model(raw: dict, root: dict | None = None) -> GlassdoorReview | None:
    """Map one BFF review object to GlassdoorReview. Returns None if required fields missing."""
    review_id = raw.get("id") or raw.get("reviewId") or raw.get("reviewIdKey")
    if review_id is None:
        return None
    review_id_str = str(review_id) if not isinstance(review_id, str) else review_id

    rating_val = raw.get("ratingOverall") or raw.get("overallRating") or raw.get("rating")
    try:
        rating = float(rating_val) if rating_val is not None else 3.0
    except (TypeError, ValueError):
        rating = 3.0
    rating = max(1.0, min(5.0, rating))

    title = (raw.get("summary") or raw.get("title") or "") or ""
    pros = (raw.get("pros") or "") or ""
    cons = (raw.get("cons") or "") or ""
    advice = raw.get("adviceToManagement") or raw.get("adviceToManagementKey")
    if advice is not None and not isinstance(advice, str):
        advice = None
    advice = (advice or "").strip() or None

    is_current = bool(raw.get("isCurrentJob") or raw.get("isCurrentEmployee") or False)
    job_title = _job_title_from_review(raw, root)

    dt = _review_date_from_api(
        raw.get("reviewDateTime") or raw.get("reviewDate") or raw.get("createdAt")
    )
    if dt is None:
        return None
    return GlassdoorReview(
        review_id=review_id_str,
        rating=rating,
        title=title,
        pros=pros,
        cons=cons,
        advice_to_management=advice,
        is_current_employee=is_current,
        job_title=job_title,
        review_date=dt,
    )


async def _fetch_reviews_async(
    company_name: str,
    limit: int,
    api_key: str,
) -> List[GlassdoorReview]:
    """Async: typeahead -> reviews URL -> HTML metadata -> BFF pages -> map to GlassdoorReview."""
    from scrapfly import ScrapeConfig, ScrapflyClient, ScrapflyScrapeError

    client = ScrapflyClient(key=api_key)
    base_config = {"asp": True, "country": "US", "render_js": True}

    # 1) Company lookup
    typeahead_url = (
        "https://www.glassdoor.com/api-web/employer/find.htm"
        f"?autocomplete=true&maxEmployersForAutocomplete=50&term={company_name!s}"
    )
    try:
        typeahead_result = await client.async_scrape(
            ScrapeConfig(url=typeahead_url, **base_config)
        )
    except Exception as e:
        logger.warning("glassdoor_typeahead_failed company=%s error=%s", company_name, e)
        return []
    if isinstance(typeahead_result, ScrapflyScrapeError):
        logger.warning(
            "glassdoor_typeahead_failed company=%s message=%s",
            company_name,
            getattr(typeahead_result, "message", str(typeahead_result)),
        )
        return []

    try:
        data = json.loads(typeahead_result.content)
    except json.JSONDecodeError as e:
        logger.warning("glassdoor_typeahead_parse_failed company=%s error=%s", company_name, e)
        return []
    if not isinstance(data, list) or len(data) == 0:
        logger.info("glassdoor_no_company_found company=%s", company_name)
        return []

    first = data[0]
    employer_name = first.get("label") or first.get("employerName") or company_name
    employer_id = first.get("id")
    if employer_id is None:
        employer_id = first.get("parentRelationshipVO", {}) or {}
        if isinstance(employer_id, dict):
            employer_id = employer_id.get("employerId")
    if employer_id is None:
        logger.warning("glassdoor_no_employer_id company=%s", company_name)
        return []
    employer_id_str = str(employer_id)

    # 2) Reviews HTML page for metadata
    reviews_url = _reviews_url(employer_name, employer_id_str)
    try:
        html_result = await client.async_scrape(
            ScrapeConfig(url=reviews_url, **base_config)
        )
    except Exception as e:
        logger.warning("glassdoor_html_failed url=%s error=%s", reviews_url, e)
        return []
    if isinstance(html_result, ScrapflyScrapeError):
        logger.warning(
            "glassdoor_html_failed url=%s message=%s",
            reviews_url,
            getattr(html_result, "message", str(html_result)),
        )
        return []

    content = getattr(html_result, "content", None) or ""
    metadata = _parse_reviews_metadata(content)
    if not metadata:
        logger.warning("glassdoor_metadata_missing url=%s", reviews_url)
        return []

    eid = metadata["employer_id"]
    dpid = metadata["dynamic_profile_id"]

    # 3) BFF page 1
    bff_url = "https://www.glassdoor.com/bff/employer-profile-mono/employer-reviews"
    config_page1 = ScrapeConfig(
        url=bff_url,
        method="POST",
        asp=True,
        country="US",
        headers={"content-type": "application/json"},
        body=_bff_body(eid, dpid, 1),
    )
    try:
        page1_result = await client.async_scrape(config_page1)
    except Exception as e:
        logger.warning("glassdoor_bff_failed company=%s error=%s", company_name, e)
        return []
    if isinstance(page1_result, ScrapflyScrapeError):
        logger.warning(
            "glassdoor_bff_failed company=%s message=%s",
            company_name,
            getattr(page1_result, "message", str(page1_result)),
        )
        return []

    try:
        page1_data = json.loads(page1_result.content)
    except json.JSONDecodeError as e:
        logger.warning("glassdoor_bff_parse_failed company=%s error=%s", company_name, e)
        return []

    reviews_payload = (page1_data.get("data") or {}).get("employerReviews") or {}
    all_raw = list(reviews_payload.get("reviews") or [])
    total_pages = int(reviews_payload.get("numberOfPages") or 1)
    total_pages = min(total_pages, MAX_SCRAPFLY_PAGES)
    if total_pages > 1:
        remaining = [
            ScrapeConfig(
                url=bff_url,
                method="POST",
                asp=True,
                country="US",
                headers={"content-type": "application/json"},
                body=_bff_body(eid, dpid, p),
            )
            for p in range(2, total_pages + 1)
        ]
        try:
            async for res in client.concurrent_scrape(remaining):
                if isinstance(res, ScrapflyScrapeError):
                    continue
                try:
                    pd = json.loads(res.content)
                    revs = ((pd.get("data") or {}).get("employerReviews") or {}).get("reviews") or []
                    all_raw.extend(revs)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("glassdoor_bff_remaining_pages_error error=%s", e)

    mapped: List[GlassdoorReview] = []
    for r in all_raw:
        if len(mapped) >= limit:
            break
        if not isinstance(r, dict):
            continue
        rev = _map_bff_review_to_model(r)
        if rev is not None:
            mapped.append(rev)
    logger.info(
        "glassdoor_fetch_ok company=%s count=%s raw=%s",
        company_name,
        len(mapped),
        len(all_raw),
    )
    return mapped


def fetch_reviews(
    company_name: str,
    ticker: str = "",
    limit: int = 100,
) -> List[GlassdoorReview]:
    """
    Fetch Glassdoor reviews for a company via ScrapFly (typeahead + BFF).
    Returns [] if ScrapFly key is missing, company_name is blank, or scraping fails.
    """
    company_name = (company_name or "").strip()
    if not company_name:
        logger.debug("glassdoor_fetch_skipped reason=no_company_name")
        return []
    settings = get_settings()
    api_key = (settings.scrapfly_api_key or "").strip()
    if not api_key:
        logger.info("glassdoor_fetch_skipped reason=no_scrapfly_key company=%s", company_name)
        return []
    limit = min(max(1, limit), MAX_SCRAPFLY_PAGES * BFF_PAGE_SIZE)
    try:
        return asyncio.run(_fetch_reviews_async(company_name, limit, api_key))
    except Exception as e:
        logger.warning("glassdoor_fetch_failed company=%s error=%s", company_name, e)
        return []
