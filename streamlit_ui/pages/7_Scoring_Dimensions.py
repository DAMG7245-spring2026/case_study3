"""Dimension Scoring: signal-to-dimension mapping table and rubric results."""
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

NEW_ROW_BG = "#e8f5e9"  # light green


def _build_mapping_matrix():
    """Build signal × dimension matrix from SIGNAL_TO_DIMENSION_MAP."""
    rows = []
    for source, label, is_new in SIGNAL_ROW_ORDER:
        mapping = SIGNAL_TO_DIMENSION_MAP.get(source)
        if not mapping:
            rows.append({"source_label": label + (" [NEW]" if is_new else ""), "is_new": is_new, "cells": []})
            continue
        cells = []
        for dim in DIMENSION_ORDER:
            if dim == mapping.primary_dimension:
                w = float(mapping.primary_weight)
                is_primary = True
            else:
                w = float(mapping.secondary_mappings.get(dim, 0))
                is_primary = False
            cells.append({"value": w if w > 0 else None, "is_primary": is_primary})
        display_label = label + (" [NEW]" if is_new else "")
        rows.append({"source_label": display_label, "is_new": is_new, "cells": cells})
    return rows


def _render_cs2_mapping_table():
    """Render the CS2 Source table: signals × dimensions with weights, bold primary, [NEW] highlight."""
    rows = _build_mapping_matrix()
    headers = ["CS2 Source"] + [DIMENSION_LABELS[d] for d in DIMENSION_ORDER]
    lines = [
        "<div style='overflow-x: auto; margin: 1rem 0;'>",
        "<table style='border-collapse: collapse; width: 100%; font-size: 0.9rem;'>",
        "<thead><tr style='border-bottom: 2px solid #333;'>",
    ]
    for h in headers:
        lines.append(f"<th style='text-align: left; padding: 8px 12px; font-weight: bold;'>{h}</th>")
    lines.append("</tr></thead><tbody>")
    for i, row in enumerate(rows):
        bg = f" background-color: {NEW_ROW_BG};" if row["is_new"] else ""
        lines.append(f"<tr style='border-bottom: 1px solid #ddd;{bg}'>")
        lines.append(f"<td style='padding: 8px 12px; font-weight: 500; border-right: 1px solid #ddd;'>{row['source_label']}</td>")
        for c in row["cells"]:
            if c["value"] is not None:
                val = f"{c['value']:.2f}"
                style = "font-weight: bold;" if c["is_primary"] else ""
                lines.append(f"<td style='padding: 8px 12px; {style}'>{val}</td>")
            else:
                lines.append("<td style='padding: 8px 12px; color: #999;'>—</td>")
        lines.append("</tr>")
    lines.append("</tbody></table></div>")
    st.markdown("".join(lines), unsafe_allow_html=True)


st.set_page_config(page_title="Dimension Scoring | PE Org-AI-R", page_icon="📐", layout="wide")
render_scoring_sidebar()

st.title("Dimension Scoring")
st.caption("Signal-to-dimension mapping and rubric results (score, confidence, contributing sources)")

# CS2-style signal × dimension mapping table (data from evidence_mapping_table)
st.subheader("CS2 Source")
_render_cs2_mapping_table()

# Rubric results from session state
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
        rows.append({
            "dimension": dim,
            "score": round(float(d.get("score", 0)), 2),
            "confidence": round(float(d.get("confidence", 0)), 2),
            "evidence_count": d.get("evidence_count", 0),
            "contributing_sources": contrib_str[:80] + ("..." if len(contrib_str) > 80 else ""),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Level / keywords matched: not exposed by backend (rubric run internally).")
