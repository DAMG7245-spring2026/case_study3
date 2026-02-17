#!/usr/bin/env python
"""
One-time seed: insert the 10 target companies into Snowflake from the data
that was previously in app.models.evidence.TARGET_COMPANIES.

Run once after adding URL columns to companies:
  poetry run python scripts/seed_target_companies.py

Idempotent: skips tickers that already exist.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.snowflake import get_snowflake_service

# Industry name -> ID (from app/database/schema.sql seed)
INDUSTRY_IDS = {
    "Manufacturing": "550e8400-e29b-41d4-a716-446655440001",
    "Healthcare Services": "550e8400-e29b-41d4-a716-446655440002",
    "Business Services": "550e8400-e29b-41d4-a716-446655440003",
    "Retail": "550e8400-e29b-41d4-a716-446655440004",
    "Financial Services": "550e8400-e29b-41d4-a716-446655440005",
}

COMPANIES = [
    {"ticker": "CAT", "name": "Caterpillar Inc.", "industry": "Manufacturing",
     "domain": "caterpillar.com",
     "careers_url": "https://careers.caterpillar.com/en/jobs/?search=&country=United+States+of+America#results",
     "leadership_url": "https://www.caterpillar.com/en/company/governance/officers.html",
     "news_url": "https://www.caterpillar.com/en/news.html"},
    {"ticker": "DE", "name": "Deere & Company", "industry": "Manufacturing",
     "domain": "deere.com",
     "careers_url": "https://careers.deere.com/careers?location=united%20states",
     "leadership_url": "https://about.deere.com/en-us/explore-john-deere/leadership",
     "news_url": "https://www.deere.com/en/news/"},
    {"ticker": "UNH", "name": "UnitedHealth Group", "industry": "Healthcare Services",
     "domain": "unitedhealthgroup.com",
     "careers_url": "https://careers.unitedhealthgroup.com/job-search-results/",
     "leadership_url": None,
     "news_url": "https://www.unitedhealthgroup.com/newsroom/news.html"},
    {"ticker": "HCA", "name": "HCA Healthcare", "industry": "Healthcare Services",
     "domain": "hcahealthcare.com",
     "careers_url": "https://careers.hcahealthcare.com/search/jobs?q=AI&location=&ns_radius=40.2336&ns_from_search=1",
     "leadership_url": "https://careers.hcahealthcare.com/pages/executive",
     "news_url": "https://investor.hcahealthcare.com/news/default.aspx"},
    {"ticker": "ADP", "name": "Automatic Data Processing", "industry": "Business Services",
     "domain": "adp.com",
     "careers_url": "https://jobs.adp.com/en/jobs/?search=&mylocation=United+States&origin=global&lat=38.7945952&lng=-106.5348379&origin=global",
     "leadership_url": "https://www.adp.com/about-adp/leadership.aspx",
     "news_url": "https://mediacenter.adp.com/"},
    {"ticker": "PAYX", "name": "Paychex Inc.", "industry": "Business Services",
     "domain": "paychex.com",
     "careers_url": "https://careers.paychex.com/careers/jobs?stretchUnit=MILES&stretch=10&location=United%20States&woe=12&regionCode=US&sortBy=relevance&page=1",
     "leadership_url": None,
     "news_url": "https://www.paychex.com/newsroom"},
    {"ticker": "WMT", "name": "Walmart Inc.", "industry": "Retail",
     "domain": "walmart.com",
     "careers_url": "https://careers.walmart.com/us/en/results?searchQuery=united+states",
     "leadership_url": "https://corporate.walmart.com/about/leadership",
     "news_url": "https://corporate.walmart.com/content/corporate/en_us/news.tag=corporate:innovation.html"},
    {"ticker": "TGT", "name": "Target Corporation", "industry": "Retail",
     "domain": "target.com",
     "careers_url": "https://corporate.target.com/careers/job-search?currentPage=1&country=United%20States",
     "leadership_url": "https://corporate.target.com/about/leadership-team",
     "news_url": "https://corporate.target.com/press/releases"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "industry": "Financial Services",
     "domain": "jpmorganchase.com",
     "careers_url": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?keyword=ai&location=United+States&locationId=300000000289738&locationLevel=country&mode=location",
     "leadership_url": "https://www.jpmorganchase.com/about/leadership",
     "news_url": "https://www.jpmorganchase.com/about/technology/news"},
    {"ticker": "GS", "name": "Goldman Sachs", "industry": "Financial Services",
     "domain": "goldmansachs.com",
     "careers_url": "https://higher.gs.com/results?LOCATION=Albany|New%20York|Atlanta|Boston|Chicago|Dallas|Houston|Irving|Richardson|Detroit|Draper|Salt%20Lake%20City|Jersey%20City|Menlo%20Park|Newport%20Beach|San%20Francisco|Miami|West%20Palm%20Beach|Philadelphia|Pittsburgh|Seattle|Washington|Wilmington&page=1&sort=RELEVANCE",
     "leadership_url": "https://www.goldmansachs.com/our-firm/our-people-and-leadership/leadership",
     "news_url": "https://www.goldmansachs.com/insights/technology"},
]


def main():
    db = get_snowflake_service()
    now = datetime.now(timezone.utc)
    inserted = 0
    skipped = 0
    for c in COMPANIES:
        ticker = c["ticker"].upper()
        industry_id = INDUSTRY_IDS.get(c["industry"])
        if not industry_id:
            print(f"Skip {ticker}: unknown industry {c['industry']}")
            skipped += 1
            continue
        existing = db.execute_one(
            "SELECT id FROM companies WHERE ticker = %s AND is_deleted = FALSE",
            (ticker,)
        )
        if existing:
            print(f"Skip {ticker}: already exists")
            skipped += 1
            continue
        company_id = str(uuid4())
        db.execute_write(
            """
            INSERT INTO companies (id, name, ticker, industry_id, position_factor,
                domain, careers_url, news_url, leadership_url, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                company_id, c["name"], ticker, industry_id, 0.0,
                c.get("domain"), c.get("careers_url"), c.get("news_url"), c.get("leadership_url"),
                now, now
            )
        )
        print(f"Inserted {ticker}: {c['name']}")
        inserted += 1
    print(f"\nDone: {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
