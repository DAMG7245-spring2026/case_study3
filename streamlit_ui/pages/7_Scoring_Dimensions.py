"""Dimension Scoring: combined editable signal × dimension weight matrix and rubric results."""

import streamlit as st

from app.models.enums import Dimension
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    SIGNAL_TO_DIMENSION_MAP,
    SignalSource,
)
from streamlit_ui.components.scoring_sidebar import (
    get_dimension_details,
    get_last_result,
    render_scoring_sidebar,
)

# Column order and short labels (CS2 style)
DIMENSION_ORDER = [
    Dimension.DATA_INFRASTRUCTURE,
    Dimension.AI_GOVERNANCE,
    Dimension.TECHNOLOGY_STACK,
    Dimension.TALENT_SKILLS,
    Dimension.LEADERSHIP_VISION,
    Dimension.USE_CASE_PORTFOLIO,
    Dimension.CULTURE_CHANGE,
]
DIMENSION_LABELS = {
    Dimension.DATA_INFRASTRUCTURE: "Data",
    Dimension.AI_GOVERNANCE: "Gov",
    Dimension.TECHNOLOGY_STACK: "Tech",
    Dimension.TALENT_SKILLS: "Talent",
    Dimension.LEADERSHIP_VISION: "Lead",
    Dimension.USE_CASE_PORTFOLIO: "Use",
    Dimension.CULTURE_CHANGE: "Culture",
}

# Row order and display labels; last two are [NEW]
SIGNAL_ROW_ORDER = [
    (SignalSource.TECHNOLOGY_HIRING, "technology_hiring", False),
    (SignalSource.INNOVATION_ACTIVITY, "innovation_activity", False),
    (SignalSource.DIGITAL_PRESENCE, "digital_presence", False),
    (SignalSource.LEADERSHIP_SIGNALS, "leadership_signals", False),
    (SignalSource.SEC_ITEM_1, "sec_item_1 (Business)", False),
    (SignalSource.SEC_ITEM_1A, "sec_item_1a (Risk)", False),
    (SignalSource.SEC_ITEM_7, "sec_item_7 (MD&A)", False),
    (SignalSource.GLASSDOOR_REVIEWS, "glassdoor_reviews", True),
    (SignalSource.BOARD_COMPOSITION, "board_composition", True),
]

DIM_COLS = [DIMENSION_LABELS[d] for d in DIMENSION_ORDER]


def _render_editable_matrix():
    """Combined signal × dimension matrix with editable weights and reliability.

    Mapping relationships are fixed — only weight values and per-signal reliability
    can be edited. Unmapped cells (blank) are ignored on save.
    """
    import pandas as pd
    from app.pipelines.evidence_mapper.evidence_mapping_table import (
        build_signal_to_dimension_map,
        compute_weights_hash,
    )

    try:
        from app.services.snowflake import get_snowflake_service

        db = get_snowflake_service()
        db_rows = db.get_signal_dimension_weights()
    except Exception as exc:
        st.error(f"Could not connect to Snowflake: {exc}")
        return

    if not db_rows:
        st.info("No weights found in DB. Run schema.sql seed to populate defaults.")
        return

    # Staleness badge
    current_map = build_signal_to_dimension_map(db_rows)
    current_hash = compute_weights_hash(current_map)
    try:
        stale_ids = db.get_stale_dimension_score_companies(current_hash)
    except Exception:
        stale_ids = []

    if stale_ids:
        st.warning(
            f"**{len(stale_ids)} company/companies** have dimension scores computed with "
            "previous weights and may be stale."
        )
    else:
        st.success("All dimension scores are up-to-date with the current weights.")

    # Build lookup: (signal_source_str, dimension_str) -> row dict
    lookup = {(r["signal_source"], r["dimension"]): r for r in db_rows}

    # Build wide pivot DataFrame
    matrix_rows = []
    signal_index = []  # signal_source str per row, parallel to matrix_rows
    for source, label, is_new in SIGNAL_ROW_ORDER:
        display = label + (" [NEW]" if is_new else "")
        row: dict = {"Signal": display}
        for dim, dim_col in zip(DIMENSION_ORDER, DIM_COLS):
            key = (source.value, dim.value)
            if key in lookup:
                row[dim_col] = float(lookup[key]["weight"])
            else:
                row[dim_col] = None
        matrix_rows.append(row)
        signal_index.append(source.value)

    df = pd.DataFrame(matrix_rows)

    st.caption(
        "Edit **weight** values directly in the matrix. "
        "Blank cells have no mapping and are ignored on save. "
        "Click **Save weights** to persist changes."
    )

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        disabled=["Signal"],
        column_config={
            "Signal": st.column_config.TextColumn("Signal", width="medium"),
            **{
                col: st.column_config.NumberColumn(
                    col, min_value=0.0, max_value=1.0, format="%.4f"
                )
                for col in DIM_COLS
            },
        },
        key="editable_matrix",
    )

    if st.button("Save weights", type="primary"):
        # ── Validate: each row's mapped weights must sum to 1.0 ──────────
        sum_errors = []
        for i, sig_str in enumerate(signal_index):
            edited_row = edited_df.iloc[i]
            row_sum = sum(
                float(edited_row[dim_col])
                for dim, dim_col in zip(DIMENSION_ORDER, DIM_COLS)
                if (sig_str, dim.value) in lookup and edited_row[dim_col] is not None
            )
            if abs(row_sum - 1.0) > 1e-4:
                signal_label = edited_row["Signal"]
                sum_errors.append(
                    f"**{signal_label}**: weights sum to {row_sum:.4f} (must be 1.0000)"
                )
        if sum_errors:
            st.error(
                "Cannot save — the following rows do not sum to 1.0:\n\n"
                + "\n\n".join(f"- {e}" for e in sum_errors)
            )
            return

        changed = 0
        errors = []
        for i, sig_str in enumerate(signal_index):
            edited_row = edited_df.iloc[i]
            for dim, dim_col in zip(DIMENSION_ORDER, DIM_COLS):
                key = (sig_str, dim.value)
                if key not in lookup:
                    continue  # mapping is fixed — never create new connections
                orig = lookup[key]
                new_w = edited_row[dim_col]
                if new_w is None:
                    continue
                if abs(float(new_w) - float(orig["weight"])) > 1e-9:
                    try:
                        db.upsert_signal_dimension_weight(
                            signal_source=sig_str,
                            dimension=dim.value,
                            weight=float(new_w),
                            is_primary=bool(orig["is_primary"]),
                            reliability=float(orig["reliability"]),
                            updated_by="streamlit_ui",
                        )
                        changed += 1
                    except Exception as exc:
                        errors.append(f"{sig_str}/{dim.value}: {exc}")

        if errors:
            st.error("Errors saving some rows:\n" + "\n".join(errors))
        elif changed == 0:
            st.info("No changes detected.")
        else:
            st.success(f"Saved {changed} row(s).")
            st.warning(
                "Dimension scores computed with previous weights may be stale. "
                "Re-run the scoring pipeline for each company to refresh."
            )
            st.rerun()

    # Recompute stale companies
    if stale_ids:
        st.markdown("---")
        st.subheader(f"Recompute stale scores ({len(stale_ids)} companies)")
        if st.button("Recompute all stale", type="secondary"):
            import requests
            from streamlit_ui.utils.config import get_api_url

            api_base = get_api_url()
            successes, failures = [], []
            for cid in stale_ids:
                try:
                    resp = requests.post(
                        f"{api_base}/api/v1/scores/companies/{cid}/compute-dimension-scores",
                        timeout=60,
                    )
                    if resp.ok:
                        successes.append(cid)
                    else:
                        failures.append(f"{cid}: HTTP {resp.status_code}")
                except Exception as exc:
                    failures.append(f"{cid}: {exc}")

            if successes:
                st.success(f"Recomputed {len(successes)} company/companies successfully.")
            if failures:
                st.error("Failed for:\n" + "\n".join(failures))
            if not failures:
                st.rerun()


st.set_page_config(
    page_title="Dimension Scoring | PE Org-AI-R", page_icon="📐", layout="wide"
)
render_scoring_sidebar()

st.title("Dimension Scoring")
st.caption(
    "Signal-to-dimension mapping and rubric results (score, confidence, contributing sources)"
)

st.subheader("Signal × Dimension Weight Matrix")
_render_editable_matrix()

st.markdown("---")
st.subheader("Dimension results")
details = get_dimension_details()
if not details:
    result = get_last_result()
    if result:
        st.info("Run Pipeline again to load dimension details, or they are not yet stored.")
    else:
        st.info("Select a company and click **Run Pipeline** to see dimension scores.")
else:
    rows = []
    for d in details:
        dim = d.get("dimension", "")
        if isinstance(dim, dict):
            dim = dim.get("value", dim.get("name", str(dim)))
        contrib = d.get("contributing_sources") or []
        contrib_str = ", ".join(contrib) if isinstance(contrib, list) else str(contrib)
        rows.append(
            {
                "dimension": dim,
                "score": round(float(d.get("score", 0)), 2),
                "confidence": round(float(d.get("confidence", 0)), 2),
                "evidence_count": d.get("evidence_count", 0),
                "contributing_sources": contrib_str[:80]
                + ("..." if len(contrib_str) > 80 else ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Level / keywords matched: not exposed by backend (rubric run internally).")
