"""Signals: run external signal pipeline for a company, then view signals table."""
from uuid import UUID

import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_companies,
    get_signals,
    collect_signals,
    collect_signals_all,
    get_signal_collection_logs,
    get_signal_formulas,
    compute_signals,
    get_company_signal_summary,
)
from streamlit_ui.utils.config import get_api_url

st.set_page_config(page_title="Signals | PE Org-AI-R", page_icon="📡", layout="wide")
st.title("Signals")
st.caption("Run the external signal pipeline for a company, then view the signals table.")

api_url = get_api_url()
client = get_client()

# --- Run signals pipeline ---
st.subheader("Run signals pipeline")
companies_data = get_companies(client)
companies_items = companies_data.get("items") or []
company_options = [
    (f"{c.get('ticker', '')} — {c.get('name', '')}", str(c["id"]))
    for c in companies_items
    if c.get("id") and c.get("ticker")
]

run_scope = st.radio(
    "Run for",
    options=["One company", "All companies"],
    index=0,
    key="signals_run_scope",
    horizontal=True,
)
if not company_options and run_scope == "One company":
    st.caption("Add at least one company (Companies page) to run the pipeline.")
elif run_scope == "All companies" and not company_options:
    st.caption("Add at least one company (Companies page) to run the pipeline for all.")
else:
    with st.form("run_signals_pipeline"):
        company_labels = [x[0] for x in company_options]
        company_ids = [x[1] for x in company_options]
        if run_scope == "One company":
            sel_idx = st.selectbox(
                "Company",
                range(len(company_labels)),
                format_func=lambda i: company_labels[i],
                key="signals_company_select",
            )
        st.caption("Select which signal categories to collect:")
        cat_tech = st.checkbox("Technology hiring", value=True, key="sig_tech")
        cat_innovation = st.checkbox("Innovation activity", value=True, key="sig_innovation")
        cat_digital = st.checkbox("Digital presence", value=True, key="sig_digital")
        cat_leadership = st.checkbox("Leadership signals", value=True, key="sig_leadership")
        cat_glassdoor = st.checkbox("Glassdoor reviews", value=False, key="sig_glassdoor")
        cat_board = st.checkbox("Board composition", value=False, key="sig_board")
        run_clicked = st.form_submit_button("Run signals pipeline")

    if run_clicked:
        selected_categories = []
        if cat_tech:
            selected_categories.append("technology_hiring")
        if cat_innovation:
            selected_categories.append("innovation_activity")
        if cat_digital:
            selected_categories.append("digital_presence")
        if cat_leadership:
            selected_categories.append("leadership_signals")
        if cat_glassdoor:
            selected_categories.append("glassdoor_reviews")
        if cat_board:
            selected_categories.append("board_composition")
        if not selected_categories:
            st.error("Select at least one signal category.")
        else:
            try:
                if run_scope == "All companies":
                    resp = collect_signals_all(selected_categories, client=client)
                    task_id = resp.get("task_id", "")
                    st.session_state["signals_task_id"] = task_id
                    st.session_state["signals_last_company_id"] = None
                    st.session_state["signals_last_company_label"] = "All companies"
                    st.session_state["signals_last_categories"] = selected_categories
                    st.success(resp.get("message", "Signal collection started for all companies. See log below."))
                else:
                    company_id = company_ids[sel_idx]
                    company_label = company_labels[sel_idx]
                    resp = collect_signals(company_id, selected_categories, client=client)
                    task_id = resp.get("task_id", "")
                    st.session_state["signals_task_id"] = task_id
                    st.session_state["signals_last_company_id"] = company_id
                    st.session_state["signals_last_company_label"] = company_label
                    st.session_state["signals_last_categories"] = selected_categories
                    st.success("Signal collection started. See log below; then use the formula and Compute button.")
            except Exception as e:
                st.error(f"Failed to start collection: {e}")

    # --- Pipeline log: fetch on Refresh only (no auto-polling) ---
    signals_task_id = st.session_state.get("signals_task_id")
    if signals_task_id:
        st.markdown("**Pipeline log**")
        if st.button("Refresh log", key="signals_refresh_log"):
            st.rerun()
        try:
            data = get_signal_collection_logs(signals_task_id, client=client)
            logs = data.get("logs") or []
            finished = data.get("finished", False)
        except Exception:
            logs = ["(Could not fetch logs from server.)"]
            finished = False
        st.caption("Click Refresh log to update. No automatic polling.")
        log_text = "\n".join(logs) if logs else "(waiting for logs…)"
        st.text_area(
            "Signal pipeline log",
            value=log_text,
            height=200,
            disabled=True,
            label_visibility="collapsed",
            key="signals_pipeline_log_output",
        )
    if signals_task_id and st.session_state.get("signals_last_company_label") == "All companies":
        st.caption("Collection was run for all companies. Run for a single company above to compute scores and view signals for that company.")

# --- Compute from existing data (no fetch) ---
st.subheader("Compute from existing data")
st.caption("Run compute on stored raw data only. No API fetch. Pick a company and categories that already have raw data in the DB.")
if company_options:
    company_labels_co = [x[0] for x in company_options]
    company_ids_co = [x[1] for x in company_options]
    with st.form("compute_from_existing"):
        co_sel_idx = st.selectbox(
            "Company",
            range(len(company_labels_co)),
            format_func=lambda i: company_labels_co[i],
            key="compute_only_company",
        )
        st.caption("Select which signal categories to compute (uses stored raw data):")
        co_tech = st.checkbox("Technology hiring", value=True, key="co_tech")
        co_innovation = st.checkbox("Innovation activity", value=True, key="co_innovation")
        co_digital = st.checkbox("Digital presence", value=True, key="co_digital")
        co_leadership = st.checkbox("Leadership signals", value=True, key="co_leadership")
        co_glassdoor = st.checkbox("Glassdoor reviews", value=False, key="co_glassdoor")
        co_board = st.checkbox("Board composition", value=False, key="co_board")
        co_clicked = st.form_submit_button("Compute from stored raw data")
    if co_clicked:
        co_categories = []
        if co_tech:
            co_categories.append("technology_hiring")
        if co_innovation:
            co_categories.append("innovation_activity")
        if co_digital:
            co_categories.append("digital_presence")
        if co_leadership:
            co_categories.append("leadership_signals")
        if co_glassdoor:
            co_categories.append("glassdoor_reviews")
        if co_board:
            co_categories.append("board_composition")
        if not co_categories:
            st.error("Select at least one signal category.")
        else:
            try:
                co_company_id = company_ids_co[co_sel_idx]
                co_company_label = company_labels_co[co_sel_idx]
                resp = compute_signals(co_company_id, co_categories, client=client)
                computed = resp.get("computed") or []
                msg = resp.get("message", "")
                if computed:
                    st.success(f"Computed: {', '.join(computed)}. {msg}")
                    st.session_state["signals_last_company_id"] = co_company_id
                    st.session_state["signals_last_company_label"] = co_company_label
                    st.session_state["signals_last_categories"] = co_categories
                else:
                    st.info(msg or "No raw data found for selected categories.")
                st.rerun()
            except Exception as e:
                st.error(f"Compute failed: {e}")
else:
    st.caption("Add at least one company (Companies page) to use compute from existing data.")

# --- Formula and Compute (when we have a company from collect) ---
last_company_id = st.session_state.get("signals_last_company_id")
last_company_label = st.session_state.get("signals_last_company_label")
last_categories = st.session_state.get("signals_last_categories") or ["technology_hiring"]

if last_company_id and last_company_label:
    st.subheader("Compute scores from collected data")
    st.caption(f"Raw data collected for **{last_company_label}**. Compute scores using the formula below.")
    try:
        formulas_resp = get_signal_formulas(client=client)
        formulas = formulas_resp.get("formulas") or {}
    except Exception:
        formulas = {}
    for cat in last_categories:
        label = cat.replace("_", " ").title()
        formula_text = formulas.get(cat, "(No formula description.)")
        with st.expander(f"Formula: {label}", expanded=(cat == "technology_hiring")):
            st.markdown(formula_text)
    if st.button("Compute scores", type="primary", key="signals_compute_btn"):
        try:
            resp = compute_signals(last_company_id, last_categories, client=client)
            computed = resp.get("computed") or []
            msg = resp.get("message", "")
            if computed:
                st.success(f"Computed: {', '.join(computed)}. {msg}")
            else:
                st.info(msg)
            st.rerun()
        except Exception as e:
            st.error(f"Compute failed: {e}")

# --- Signals table ---
if last_company_id and last_company_label:
    st.subheader(f"Signals for {last_company_label}")
    if st.button("Refresh table", key="signals_refresh_table"):
        st.rerun()
    try:
        result = get_signals(
            client=client,
            page=1,
            page_size=100,
            company_id=UUID(last_company_id),
        )
    except Exception as e:
        st.error(f"Cannot load signals: {e}")
    else:
        items = result.get("items") or []
        total = result.get("total", 0)
        if not items:
            st.info("No signals yet for this company. Run the pipeline, then click Refresh table.")
        else:
            st.caption(f"Total: {total} signals.")
            st.dataframe(
                [
                    {
                        "id": str(s.get("id", ""))[:8],
                        "category": s.get("category", ""),
                        "source": s.get("source", ""),
                        "raw_value": (s.get("raw_value") or "")[:80],
                        "score": s.get("normalized_score"),
                        "confidence": s.get("confidence"),
                    }
                    for s in items
                ],
                use_container_width=True,
                hide_index=True,
            )

            # --- Signal computation by category ---
            st.subheader("Signal computation by category")
            st.caption("Expand a category to see how its score was calculated.")
            CATEGORY_ORDER = [
                "technology_hiring",
                "innovation_activity",
                "digital_presence",
                "leadership_signals",
                "glassdoor_reviews",
                "board_composition",
            ]
            CATEGORY_LABELS = {
                "technology_hiring": "Technology hiring (job)",
                "innovation_activity": "Innovation activity",
                "digital_presence": "Digital presence",
                "leadership_signals": "Leadership signals",
                "glassdoor_reviews": "Glassdoor reviews",
                "board_composition": "Board composition",
            }
            groups = {}
            for s in items:
                cat = s.get("category") or ""
                groups.setdefault(cat, []).append(s)
            try:
                formulas_resp = get_signal_formulas(client=client)
                formulas = formulas_resp.get("formulas") or {}
            except Exception:
                formulas = {}
            for cat in CATEGORY_ORDER:
                if cat not in groups or not groups[cat]:
                    continue
                label = CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
                rep = groups[cat][0]
                formula_text = formulas.get(cat, "(No formula description.)")
                with st.expander(label, expanded=False):
                    st.markdown("**Formula**")
                    st.markdown(formula_text)
                    st.markdown("**Computation for this company**")
                    st.write("Score:", rep.get("normalized_score"), "| Confidence:", rep.get("confidence"))
                    raw_val = rep.get("raw_value") or ""
                    if raw_val:
                        st.write("Raw value:", raw_val[:200] + ("..." if len(raw_val) > 200 else ""))
                    meta = rep.get("metadata")
                    if meta and isinstance(meta, dict):
                        st.markdown("**Metadata**")
                        st.json(meta)
                    elif meta:
                        st.markdown("**Metadata**")
                        st.write(meta)

# --- Final summary ---
if last_company_id and last_company_label:
    st.subheader("Final summary")
    try:
        summary = get_company_signal_summary(UUID(last_company_id), client=client)
    except Exception:
        summary = None
    if summary:
        h = float(summary.get("technology_hiring_score") or 0)
        i = float(summary.get("innovation_activity_score") or 0)
        d = float(summary.get("digital_presence_score") or 0)
        l_ = float(summary.get("leadership_signals_score") or 0)
        composite = (h + i + d + l_) / 4.0 if (h or i or d or l_) else 0.0
        count = int(summary.get("signal_count") or 0)
        st.metric("Composite score", f"{composite:.1f}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Technology hiring", f"{h:.1f}")
        col2.metric("Innovation activity", f"{i:.1f}")
        col3.metric("Digital presence", f"{d:.1f}")
        col4.metric("Leadership signals", f"{l_:.1f}")
        st.caption(f"Signal count: {count}")
    else:
        st.caption("No summary yet. Run pipeline and Compute to see scores.")

client.close()
