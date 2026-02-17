"""Logs: run collection script and view live output; backend logs."""
import subprocess
import sys
from pathlib import Path

import streamlit as st

from streamlit_ui.components.api_client import get_client, get_company_options, get_backend_logs

# Repo root (case_study3)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

st.set_page_config(page_title="Logs | PE Org-AI-R", page_icon="📋", layout="wide")
st.title("Logs")
st.caption("Run evidence collection and view live output")

client = get_client()
ticker_options, ticker_labels = get_company_options(client)
log_tickers = [t for t in ticker_options if t]

with st.form("run_collection"):
    st.subheader("Run collection")
    selected_tickers = st.multiselect(
        "Companies (select none = all)",
        options=log_tickers,
        format_func=lambda x: ticker_labels.get(x, x),
        help="Select one or more companies. Leave empty to run for all.",
    )
    documents_only = st.checkbox("Documents only", value=False)
    signals_only = st.checkbox("Signals only", value=False)
    years_back = st.slider("Years back", 1, 10, 3)
    run_clicked = st.form_submit_button("Run collection")

if run_clicked:
    companies_arg = ",".join(selected_tickers) if selected_tickers else "all"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "collect_evidence.py"),
        "--companies",
        companies_arg,
        "--years-back",
        str(years_back),
    ]
    if documents_only:
        cmd.append("--documents-only")
    if signals_only:
        cmd.append("--signals-only")

    log_lines: list[str] = []
    log_placeholder = st.empty()
    with log_placeholder.container():
        with st.status("Running collection...", expanded=False):
            process = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            while True:
                line = process.stdout.readline()
                if line:
                    log_lines.append(line.rstrip())
                    st.text("\n".join(log_lines[-200:]))
                if process.poll() is not None:
                    rest = process.stdout.read()
                    if rest:
                        for l in rest.splitlines():
                            log_lines.append(l)
                            st.text("\n".join(log_lines[-200:]))
                    break

    exit_code = process.returncode
    if exit_code == 0:
        st.success("Collection finished successfully.")
    else:
        st.warning(f"Process exited with code {exit_code}.")

    with st.expander("View output (scrollable)", expanded=False):
        log_text = "\n".join(log_lines)
        st.text_area(
            "Log output",
            value=log_text,
            height=400,
            disabled=True,
            label_visibility="collapsed",
            key="logs_output",
        )

# Backend logs: fetch when Refresh is clicked (no auto-polling)
st.divider()
st.subheader("Backend logs")
st.caption("Recent application logs from the FastAPI server. Click Refresh to update.")
if st.button("Refresh backend logs", key="logs_refresh_backend"):
    st.rerun()
try:
    data = get_backend_logs(client=client)
    lines = data.get("lines") or []
except Exception:
    lines = ["(Could not fetch backend logs. Is the API running?)"]
log_text = "\n".join(lines) if lines else "(no log lines yet)"
st.text_area(
    "Backend log output",
    value=log_text,
    height=320,
    disabled=True,
    label_visibility="collapsed",
    key="backend_log_output",
)

client.close()
