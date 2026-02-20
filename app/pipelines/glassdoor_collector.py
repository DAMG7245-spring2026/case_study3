"""Glassdoor review collector: fetch raw reviews via RapidAPI (preferred) or ScrapFly (typeahead + BFF). No scoring."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, List, Tuple

import httpx

from app.config import get_settings
from app.models.glassdoor import GlassdoorReview

logger = logging.getLogger(__name__)

# RapidAPI Glassdoor (real-time-glassdoor-data): target 30–40 reviews per company
RAPIDAPI_GLASSDOOR_HOST = "real-time-glassdoor-data.p.rapidapi.com"
TARGET_RAPIDAPI_REVIEWS_MIN = 30
TARGET_RAPIDAPI_REVIEWS_MAX = 40
RAPIDAPI_PAGE_SIZE = 10  # typical default; we'll paginate until we hit target
RAPIDAPI_MAX_PAGES = 5  # cap to avoid runaway pagination and 429 rate limits

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


# --- RapidAPI (real-time-glassdoor-data) ---


def _rapidapi_headers(api_key: str) -> dict:
    return {
        "x-rapidapi-host": RAPIDAPI_GLASSDOOR_HOST,
        "x-rapidapi-key": api_key,
    }


def _extract_company_id_from_search_payload(payload: Any) -> str | None:
    """Extract company_id from company-search response payload (list or dict with results/companies/items)."""
    if payload is None:
        return None
    items: List[dict] = []
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        items = (
            list(payload.get("results") or [])
            or list(payload.get("companies") or [])
            or list(payload.get("items") or [])
        )
        items = [x for x in items if isinstance(x, dict)]
    if not items:
        return None
    first = items[0]
    cid = first.get("company_id") or first.get("id") or first.get("employerId")
    if cid is not None:
        return str(cid)
    return None


def _get_company_id_rapidapi(company_name: str, api_key: str) -> str | None:
    """Resolve Glassdoor company_id from company name via RapidAPI company-search. Tries query then q; flexible parsing."""
    url = f"https://{RAPIDAPI_GLASSDOOR_HOST}/company-search"
    headers = _rapidapi_headers(api_key)
    for param_name in ("query", "q"):
        params = {param_name: company_name}
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, headers=headers, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.debug("rapidapi_glassdoor_company_search param=%s company=%s error=%s", param_name, company_name, e)
            continue
        payload = data.get("data") if isinstance(data, dict) else data
        cid = _extract_company_id_from_search_payload(payload)
        if cid:
            return cid
    logger.warning(
        "rapidapi_glassdoor_no_company_id company=%s (tried query and q)",
        company_name,
    )
    return None


def _parse_rapidapi_review_date(v: Any) -> datetime | None:
    """Parse review date from RapidAPI (ISO string or ms timestamp)."""
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
            ts = int(v)
            return datetime.fromtimestamp(ts / 1000.0 if ts > 1e12 else ts)
        except (ValueError, OSError):
            pass
    return None


def _map_rapidapi_review_to_model(raw: dict) -> GlassdoorReview | None:
    """Map one RapidAPI company-reviews item to GlassdoorReview. Returns None if required fields missing."""
    review_id = raw.get("id") or raw.get("reviewId") or raw.get("review_id")
    if review_id is None:
        return None
    review_id_str = str(review_id)
    rating_val = raw.get("rating") or raw.get("overallRating") or raw.get("overall_rating") or raw.get("ratingOverall")
    try:
        rating = float(rating_val) if rating_val is not None else 3.0
    except (TypeError, ValueError):
        rating = 3.0
    rating = max(1.0, min(5.0, rating))
    title = (raw.get("summary") or raw.get("title") or raw.get("headline") or "") or ""
    pros = (raw.get("pros") or "") or ""
    cons = (raw.get("cons") or "") or ""
    advice = raw.get("adviceToManagement") or raw.get("advice_to_management")
    if advice is not None and not isinstance(advice, str):
        advice = None
    advice = (advice or "").strip() or None
    is_current = bool(raw.get("isCurrentEmployee") or raw.get("is_current_employee") or False)
    job_title = (raw.get("jobTitle") or raw.get("job_title") or "") or ""
    dt = _parse_rapidapi_review_date(
        raw.get("reviewDate") or raw.get("review_date") or raw.get("reviewDateTime") or raw.get("review_datetime") or raw.get("createdAt")
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


# --- Culture scoring (PDF Task 5.0c: Glassdoor → Culture dimension) ---

INNOVATION_POSITIVE = [
    "innovative", "cutting-edge", "forward-thinking",
    "encourages new ideas", "experimental", "creative freedom",
    "startup mentality", "move fast", "disruptive",
]
INNOVATION_NEGATIVE = [
    "bureaucratic", "slow to change", "resistant",
    "outdated", "stuck in old ways", "red tape",
    "politics", "siloed", "hierarchical",
]
DATA_DRIVEN_KEYWORDS = [
    "data-driven", "metrics", "evidence-based",
    "analytical", "kpis", "dashboards", "data culture",
    "measurement", "quantitative",
]
AI_AWARENESS_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "automation", "data science", "ml", "algorithms",
    "predictive", "neural network",
]
CHANGE_POSITIVE = [
    "agile", "adaptive", "fast-paced", "embraces change",
    "continuous improvement", "growth mindset",
]
CHANGE_NEGATIVE = [
    "rigid", "traditional", "slow", "risk-averse",
    "change resistant", "old school",
]

RECENCY_DAYS_FULL_WEIGHT = 730  # 2 years
CURRENT_EMPLOYEE_MULTIPLIER = 1.2


@dataclass
class CultureScoreResult:
    """Result of Glassdoor culture scoring with component breakdown and matched keywords."""

    overall: float
    confidence: float
    evidence_count: int
    component_scores: dict[str, float]  # innovation, data_driven, ai_awareness, change_readiness
    keywords_matched: dict[str, list[str]]  # per-category lists of keywords that appeared


def _count_keywords_in_text(text: str, keywords: List[str]) -> int:
    """Count how many of the keywords appear in text (case-insensitive)."""
    lower = text.lower()
    return sum(1 for kw in keywords if kw in lower)


def _keywords_matched_in_text(text: str, keywords: List[str]) -> List[str]:
    """Return the subset of keywords that appear in text (case-insensitive)."""
    lower = text.lower()
    return [kw for kw in keywords if kw in lower]


def compute_culture_score_from_reviews(
    company_id: str,
    ticker: str,
    reviews: List[GlassdoorReview],
) -> CultureScoreResult:
    """
    Score Glassdoor reviews for culture (PDF Task 5.0c).

    Uses keyword counts with recency and current-employee weights.
    Overall = 0.30 * innovation + 0.25 * data_driven + 0.25 * ai_awareness + 0.20 * change_readiness.
    All component scores clamped to [0, 100].

    Returns:
        CultureScoreResult with overall, confidence, evidence_count, component_scores, keywords_matched.
    """
    empty_components = {
        "innovation": 50.0,
        "data_driven": 0.0,
        "ai_awareness": 0.0,
        "change_readiness": 50.0,
    }
    empty_keywords = {
        "innovation_positive": [],
        "innovation_negative": [],
        "data_driven": [],
        "ai_awareness": [],
        "change_positive": [],
        "change_negative": [],
    }
    if not reviews:
        return CultureScoreResult(
            overall=50.0,
            confidence=0.0,
            evidence_count=0,
            component_scores=empty_components,
            keywords_matched=empty_keywords,
        )

    now = datetime.now(timezone.utc)
    total_weight = 0.0
    innovation_positive = 0.0
    innovation_negative = 0.0
    data_driven_mentions = 0.0
    ai_awareness_mentions = 0.0
    change_positive = 0.0
    change_negative = 0.0
    innovation_pos_matched: set[str] = set()
    innovation_neg_matched: set[str] = set()
    data_driven_matched: set[str] = set()
    ai_awareness_matched: set[str] = set()
    change_pos_matched: set[str] = set()
    change_neg_matched: set[str] = set()

    for review in reviews:
        text = f"{review.pros} {review.cons} {review.advice_to_management or ''}".lower()
        try:
            if review.review_date.tzinfo is not None:
                delta = now - review.review_date
            else:
                delta = now.replace(tzinfo=None) - review.review_date
            days_old = delta.days
        except Exception:
            days_old = 365
        recency_weight = 1.0 if days_old < RECENCY_DAYS_FULL_WEIGHT else 0.5
        employee_weight = CURRENT_EMPLOYEE_MULTIPLIER if review.is_current_employee else 1.0
        weight = recency_weight * employee_weight
        total_weight += weight

        innovation_positive += weight * _count_keywords_in_text(text, INNOVATION_POSITIVE)
        innovation_negative += weight * _count_keywords_in_text(text, INNOVATION_NEGATIVE)
        data_driven_mentions += weight * _count_keywords_in_text(text, DATA_DRIVEN_KEYWORDS)
        ai_awareness_mentions += weight * _count_keywords_in_text(text, AI_AWARENESS_KEYWORDS)
        change_positive += weight * _count_keywords_in_text(text, CHANGE_POSITIVE)
        change_negative += weight * _count_keywords_in_text(text, CHANGE_NEGATIVE)

        innovation_pos_matched.update(_keywords_matched_in_text(text, INNOVATION_POSITIVE))
        innovation_neg_matched.update(_keywords_matched_in_text(text, INNOVATION_NEGATIVE))
        data_driven_matched.update(_keywords_matched_in_text(text, DATA_DRIVEN_KEYWORDS))
        ai_awareness_matched.update(_keywords_matched_in_text(text, AI_AWARENESS_KEYWORDS))
        change_pos_matched.update(_keywords_matched_in_text(text, CHANGE_POSITIVE))
        change_neg_matched.update(_keywords_matched_in_text(text, CHANGE_NEGATIVE))

    if total_weight <= 0:
        return CultureScoreResult(
            overall=50.0,
            confidence=min(0.9, 0.3 + len(reviews) / 50.0),
            evidence_count=len(reviews),
            component_scores=empty_components,
            keywords_matched={
                "innovation_positive": sorted(innovation_pos_matched),
                "innovation_negative": sorted(innovation_neg_matched),
                "data_driven": sorted(data_driven_matched),
                "ai_awareness": sorted(ai_awareness_matched),
                "change_positive": sorted(change_pos_matched),
                "change_negative": sorted(change_neg_matched),
            },
        )

    # Component scores (0-100)
    innovation = (innovation_positive - innovation_negative) / total_weight * 50 + 50
    innovation = max(0.0, min(100.0, innovation))

    data_driven = (data_driven_mentions / total_weight) * 100
    data_driven = max(0.0, min(100.0, data_driven))

    ai_awareness = (ai_awareness_mentions / total_weight) * 100
    ai_awareness = max(0.0, min(100.0, ai_awareness))

    change_readiness = (change_positive - change_negative) / total_weight * 50 + 50
    change_readiness = max(0.0, min(100.0, change_readiness))

    overall = (
        0.30 * innovation
        + 0.25 * data_driven
        + 0.25 * ai_awareness
        + 0.20 * change_readiness
    )
    overall = max(0.0, min(100.0, overall))

    confidence = min(0.9, 0.3 + len(reviews) / 50.0)

    component_scores = {
        "innovation": round(innovation, 2),
        "data_driven": round(data_driven, 2),
        "ai_awareness": round(ai_awareness, 2),
        "change_readiness": round(change_readiness, 2),
    }
    keywords_matched = {
        "innovation_positive": sorted(innovation_pos_matched),
        "innovation_negative": sorted(innovation_neg_matched),
        "data_driven": sorted(data_driven_matched),
        "ai_awareness": sorted(ai_awareness_matched),
        "change_positive": sorted(change_pos_matched),
        "change_negative": sorted(change_neg_matched),
    }
    return CultureScoreResult(
        overall=round(overall, 2),
        confidence=round(confidence, 4),
        evidence_count=len(reviews),
        component_scores=component_scores,
        keywords_matched=keywords_matched,
    )


def _fetch_reviews_via_rapidapi(
    company_name: str,
    limit: int,
    api_key: str,
    glassdoor_company_id: str | None = None,
) -> List[GlassdoorReview]:
    """
    Fetch 30–40 (or up to limit) Glassdoor reviews using RapidAPI company-reviews.
    When glassdoor_company_id is provided, skip company-search; otherwise resolve via company-search.
    Returns [] if company not found or API errors.
    """
    company_name = (company_name or "").strip()
    if not api_key:
        return []
    company_id = (glassdoor_company_id or "").strip() or None
    if not company_id:
        company_id = _get_company_id_rapidapi(company_name, api_key)
    if not company_id:
        return []
    target = min(max(TARGET_RAPIDAPI_REVIEWS_MIN, limit), TARGET_RAPIDAPI_REVIEWS_MAX)
    collected: List[GlassdoorReview] = []
    page = 1
    url = f"https://{RAPIDAPI_GLASSDOOR_HOST}/company-reviews"
    headers = _rapidapi_headers(api_key)
    while len(collected) < target:
        if page > RAPIDAPI_MAX_PAGES:
            break
        params = {
            "company_id": company_id,
            "page": page,
            "sort": "POPULAR",
            "language": "en",
            "only_current_employees": "false",
            "extended_rating_data": "false",
            "domain": "www.glassdoor.com",
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(url, headers=headers, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("rapidapi_glassdoor_reviews_failed company=%s page=%s error=%s", company_name, page, e)
            break
        # Normalize: data may be { "data": { "reviews": [...] } } or { "data": [...] } or { "reviews": [...] }
        payload = data.get("data") if isinstance(data, dict) else data
        if payload is None:
            break
        if isinstance(payload, dict):
            raw_list = payload.get("reviews") or payload.get("items") or payload.get("results")
        else:
            raw_list = payload if isinstance(payload, list) else None
        if not isinstance(raw_list, list) or len(raw_list) == 0:
            if isinstance(payload, dict) and not payload.get("reviews") and page == 1:
                logger.warning("rapidapi_glassdoor_no_reviews_key company=%s payload_keys=%s", company_name, list(payload.keys()))
            break
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            if len(collected) >= target:
                break
            try:
                rev = _map_rapidapi_review_to_model(item)
                if rev is not None:
                    collected.append(rev)
            except Exception as e:
                logger.debug("rapidapi_glassdoor_skip_review item_id=%s error=%s", item.get("review_id") or item.get("id"), e)
        if len(raw_list) < RAPIDAPI_PAGE_SIZE:
            break
        page += 1
        time.sleep(0.3)  # gentle rate limit between pages
    logger.info(
        "rapidapi_glassdoor_fetch_ok company=%s count=%s",
        company_name,
        len(collected),
    )
    return collected


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
    glassdoor_company_id: str | None = None,
) -> List[GlassdoorReview]:
    """
    Fetch Glassdoor reviews for a company. Prefers RapidAPI (30–40 reviews) when key is set;
    when glassdoor_company_id is provided, uses it and skips company-search. Otherwise falls back to ScrapFly if no RapidAPI.
    Returns [] if no key, blank name, or failure.
    """
    company_name = (company_name or "").strip()
    if not company_name and not (glassdoor_company_id or "").strip():
        logger.debug("glassdoor_fetch_skipped reason=no_company_name_or_id")
        return []
    settings = get_settings()
    rapidapi_key = (settings.rapidapi_glassdoor_key or "").strip()
    if rapidapi_key:
        try:
            reviews = _fetch_reviews_via_rapidapi(
                company_name, limit, rapidapi_key, glassdoor_company_id=glassdoor_company_id
            )
            if reviews:
                return reviews
            logger.debug("glassdoor_rapidapi_returned_empty falling_back company=%s", company_name)
        except Exception as e:
            logger.warning("glassdoor_rapidapi_failed company=%s error=%s falling_back", company_name, e)
    scrapfly_key = (settings.scrapfly_api_key or "").strip()
    if not scrapfly_key:
        logger.info("glassdoor_fetch_skipped reason=no_api_key company=%s", company_name)
        return []
    limit = min(max(1, limit), MAX_SCRAPFLY_PAGES * BFF_PAGE_SIZE)
    try:
        return asyncio.run(_fetch_reviews_async(company_name, limit, scrapfly_key))
    except Exception as e:
        logger.warning("glassdoor_fetch_failed company=%s error=%s", company_name, e)
        return []
