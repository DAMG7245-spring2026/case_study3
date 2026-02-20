"""
Org-AI-R pipeline DAG: trigger documents collect-all, signals collect-all,
signals compute per company, and score-by-ticker per company via the PE Org-AI-R API.
API base URL: http://api:8000 (Docker network).
"""
from datetime import datetime
import time

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

API_BASE = "http://api:8000"
REQUEST_TIMEOUT = 300


def _api_post(path: str, json: dict) -> None:
    r = requests.post(f"{API_BASE}{path}", json=json, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()


def _api_get(path: str) -> list:
    r = requests.get(f"{API_BASE}{path}", timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("items", data) if isinstance(data, dict) else data


def trigger_documents_collect_all(**context):
    _api_post(
        "/api/v1/documents/collect-all",
        {"filing_types": ["10-K", "10-Q", "8-K", "DEF-14A"], "years_back": 3},
    )


def trigger_signals_collect_all(**context):
    _api_post(
        "/api/v1/signals/collect-all",
        {
            "categories": [
                "technology_hiring",
                "innovation_activity",
                "digital_presence",
                "leadership_signals",
                "glassdoor_reviews",
                "board_composition",
            ]
        },
    )


def wait_after_collection(**context):
    """Give background collect-all tasks time to run (collect-all returns immediately)."""
    time.sleep(120)


def signals_compute_all(**context):
    items = _api_get("/api/v1/companies?page=1&page_size=100")
    if not items:
        return
    for co in items:
        cid = co.get("id")
        if not cid:
            continue
        try:
            _api_post("/api/v1/signals/compute", {"company_id": cid, "categories": []})
        except requests.RequestException as e:
            # Log and continue with next company
            print(f"Compute failed for company {cid}: {e}")


def scores_by_ticker_all(**context):
    items = _api_get("/api/v1/companies?page=1&page_size=100")
    if not items:
        return
    for co in items:
        ticker = (co.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            _api_post("/api/v1/scores/score-by-ticker", {"ticker": ticker})
        except requests.RequestException as e:
            print(f"Score-by-ticker failed for {ticker}: {e}")


with DAG(
    dag_id="org_air_pipeline_dag",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["org-air", "pe-platform"],
) as dag:
    t_documents = PythonOperator(
        task_id="documents_collect_all",
        python_callable=trigger_documents_collect_all,
    )
    t_signals_collect = PythonOperator(
        task_id="signals_collect_all",
        python_callable=trigger_signals_collect_all,
    )
    t_wait = PythonOperator(
        task_id="wait_after_collection",
        python_callable=wait_after_collection,
    )
    t_compute = PythonOperator(
        task_id="signals_compute_all",
        python_callable=signals_compute_all,
    )
    t_scores = PythonOperator(
        task_id="scores_by_ticker_all",
        python_callable=scores_by_ticker_all,
    )

    t_documents >> t_signals_collect >> t_wait >> t_compute >> t_scores
