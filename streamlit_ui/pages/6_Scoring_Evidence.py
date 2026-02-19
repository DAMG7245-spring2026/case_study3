"""Evidence Pipeline: CS2/CS3 signals and coverage summary."""
from uuid import UUID

import streamlit as st

from streamlit_ui.components.api_client import get_client, get_company_evidence
from streamlit_ui.components.scoring_sidebar import (
    get_selected_company_id,
    render_scoring_sidebar,
)

st.set_page_config(page_title="Evidence Pipeline | PE Org-AI-R", page_icon="📁", layout="wide")
render_scoring_sidebar()

st.title("Evidence Pipeline")
st.caption("CS2 signals (hiring, innovation, digital, leadership, SEC) and CS3 (Glassdoor, Board) with coverage")

company_id = get_selected_company_id()
if not company_id:
    st.info("Select a company in the sidebar.")
    st.stop()

client = get_client()
try:
    evidence = get_company_evidence(UUID(company_id), client=client)
except Exception as e:
    st.error(f"Failed to load evidence: {e}")
    client.close()
    st.stop()

# Group signals by category
signals = evidence.get("signals") or []
by_cat = {}
for s in signals:
    cat = s.get("category") or "other"
    by_cat.setdefault(cat, []).append(s)

# CS2 categories
cs2_cats = ["technology_hiring", "innovation_activity", "digital_presence", "leadership_signals"]
sec_cats = [c for c in by_cat if "sec" in c.lower() or c in ("sec_item_1", "sec_item_1a", "sec_item_7")]
# SEC from documents
docs = evidence.get("documents") or []
doc_count = evidence.get("document_count", 0)
chunk_count = evidence.get("chunk_count", 0)

st.subheader("CS2 signals")
for cat in cs2_cats:
    items = by_cat.get(cat, [])
    with st.expander(f"{cat.replace('_', ' ').title()} ({len(items)} signals)", expanded=len(items) <= 5):
        if not items:
            st.caption("No signals")
        else:
            rows = [{"source": s.get("source"), "score": s.get("normalized_score"), "confidence": s.get("confidence")} for s in items[:20]]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            if len(items) > 20:
                st.caption(f"... and {len(items) - 20} more")

st.caption("SEC: documents and chunks")
st.metric("Documents", doc_count)
st.metric("Chunks", chunk_count)
if docs:
    st.dataframe(
        [{"type": d.get("filing_type"), "status": d.get("status")} for d in docs[:15]],
        use_container_width=True,
        hide_index=True,
    )

st.subheader("CS3 sources")
for cat in ["glassdoor_reviews", "board_composition"]:
    items = by_cat.get(cat, [])
    label = "Glassdoor culture" if cat == "glassdoor_reviews" else "Board composition"
    with st.expander(f"{label} ({len(items)} signals)"):
        if not items:
            st.caption("No signals")
        else:
            for s in items[:10]:
                st.write(f"Score: {s.get('normalized_score')}, Confidence: {s.get('confidence')}")

# Coverage summary
st.subheader("Coverage summary")
st.caption("Signal categories present (full coverage report can be added via backend).")
cat_counts = {k: len(v) for k, v in by_cat.items()}
if cat_counts:
    st.dataframe(
        [{"category": k, "count": v} for k, v in sorted(cat_counts.items())],
        use_container_width=True,
        hide_index=True,
    )

client.close()
