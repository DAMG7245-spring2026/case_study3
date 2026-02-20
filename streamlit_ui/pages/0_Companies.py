"""Companies: list, add, and update companies."""
import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_companies,
    get_company,
    get_industries,
    create_company,
    update_company,
    delete_company,
)
from streamlit_ui.utils.config import get_api_url

st.set_page_config(page_title="Companies | PE Org-AI-R", page_icon="🏢", layout="wide")
st.title("Companies")
st.caption("List, add, and update companies. Data is stored in the database.")

api_url = get_api_url()
client = get_client()

try:
    raw = get_industries(client)
    industries = raw if isinstance(raw, list) else (raw.get("items") or raw.get("industries") or [])
    industries_by_id = {str(i.get("id", "")): i for i in industries if i.get("id")}
except Exception as e:
    st.error(f"Cannot reach API at {api_url}. Is the backend running? Error: {e}")
    st.stop()

industry_options = [(i.get("name", ""), i.get("id")) for i in industries if i.get("id") is not None]
industry_labels = [x[0] for x in industry_options]
industry_ids = [str(x[1]) for x in industry_options]

# --- List companies ---
st.subheader("All companies")
# Add company button (opens modal when st.dialog available)
col_btn, _ = st.columns([1, 5])
with col_btn:
    if st.button("Add company", type="primary", key="open_add_modal"):
        st.session_state["show_add_company_modal"] = True
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

try:
    data = get_companies(client, page=1, page_size=100)
    items = data.get("items") or []
    total = data.get("total", 0)
except Exception as e:
    st.error(f"Failed to load companies: {e}")
    items = []
    total = 0

# Delete confirmation as modal popup (st.dialog requires Streamlit 1.33+)
def _render_delete_dialog(pending):
    st.warning(f"Delete **{pending.get('name', '')}** ({pending.get('ticker', '')})? This cannot be undone.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm delete", type="primary", key="confirm_delete"):
            try:
                delete_company(pending["id"])
                st.session_state["company_to_delete"] = None
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")
    with col2:
        if st.button("Cancel", key="cancel_delete"):
            st.session_state["company_to_delete"] = None
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()


if "company_to_delete" in st.session_state and st.session_state["company_to_delete"]:
    pending = st.session_state["company_to_delete"]
    if hasattr(st, "dialog"):
        # Modal popup (Streamlit 1.33+): clear state when user closes dialog without confirming
        def _clear_pending():
            st.session_state["company_to_delete"] = None

        @st.dialog("Delete company", dismissible=True, on_dismiss=_clear_pending)
        def _confirm_delete_modal():
            _render_delete_dialog(pending)

        _confirm_delete_modal()
    else:
        # Fallback: inline confirmation for older Streamlit
        _render_delete_dialog(pending)
        st.stop()

if items:
    # Table header
    h1, h2, h3, h4 = st.columns([2, 3, 2, 2])
    with h1:
        st.markdown("**Ticker**")
    with h2:
        st.markdown("**Name**")
    with h3:
        st.markdown("**Industry**")
    with h4:
        st.markdown("**Actions**")
    # Table rows: 3 columns (Ticker, Name, Industry) + 4th column (Edit | Delete)
    for c in items:
        cid = c.get("id")
        if not cid:
            continue
        ind_id = c.get("industry_id")
        industry_name = industries_by_id.get(str(ind_id), {}).get("name", "") if ind_id else ""
        ticker = c.get("ticker") or ""
        name = c.get("name") or ""
        col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
        with col1:
            st.text(ticker)
        with col2:
            st.text(name)
        with col3:
            st.text(industry_name)
        with col4:
            sub1, sub2 = st.columns(2)
            with sub1:
                if st.button("Edit", key=f"edit_{cid}"):
                    st.session_state["company_to_edit_id"] = str(cid)
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
            with sub2:
                if st.button("Delete", key=f"delete_{cid}"):
                    st.session_state["company_to_delete"] = {"id": str(cid), "ticker": ticker, "name": name}
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
    st.caption(f"Total: {total} companies.")
else:
    st.caption("No companies yet. Click **Add company** to add one.")

# --- Add company modal ---
if st.session_state.get("show_add_company_modal") and hasattr(st, "dialog"):

    def _clear_add_modal():
        st.session_state["show_add_company_modal"] = False

    @st.dialog("Add company", dismissible=True, on_dismiss=_clear_add_modal)
    def _add_company_modal():
        with st.form("add_company_modal_form"):
            name = st.text_input("Name", placeholder="Acme Inc.")
            ticker = st.text_input("Ticker", placeholder="ACM")
            if not industry_options:
                st.warning("No industries in DB. Seed the industries table first.")
                industry_id = None
            else:
                sel_idx = st.selectbox("Industry", range(len(industry_labels)), format_func=lambda i: industry_labels[i])
                industry_id = industry_ids[sel_idx]
            domain = st.text_input("Domain (optional)", placeholder="acme.com")
            careers_url = st.text_input("Careers URL (optional)", placeholder="https://careers.acme.com")
            news_url = st.text_input("News URL (optional)", placeholder="https://acme.com/news")
            leadership_url = st.text_input("Leadership URL (optional)", placeholder="https://acme.com/leadership")
            glassdoor_company_id = st.text_input(
                "Glassdoor company ID (optional)",
                placeholder="e.g. 9079 from ...-Reviews-E9079.htm",
                help="Glassdoor employer ID for review collection when RapidAPI search fails.",
            )
            col1, col2, _ = st.columns(3)
            with col1:
                submitted = st.form_submit_button("Add company")
            with col2:
                cancel = st.form_submit_button("Cancel")
            if cancel:
                _clear_add_modal()
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            if submitted:
                ticker_norm = (ticker or "").strip().upper()
                if not name or not ticker_norm:
                    st.error("Name and Ticker are required.")
                elif not industry_id:
                    st.error("Please select an industry.")
                else:
                    try:
                        create_company(
                            name=name,
                            ticker=ticker_norm,
                            industry_id=industry_id,
                            domain=domain or None,
                            careers_url=careers_url or None,
                            news_url=news_url or None,
                            leadership_url=leadership_url or None,
                            glassdoor_company_id=glassdoor_company_id.strip() or None,
                        )
                        st.success(f"Company {ticker_norm} added.")
                        _clear_add_modal()
                        if hasattr(st, "rerun"):
                            st.rerun()
                        else:
                            st.experimental_rerun()
                    except Exception as e:
                        err = str(e)
                        if "409" in err or "already exists" in err.lower():
                            st.error("A company with this ticker already exists.")
                        else:
                            st.error(f"Failed to add company: {e}")

    _add_company_modal()

# --- Edit company modal ---
edit_id = st.session_state.get("company_to_edit_id")
if edit_id and hasattr(st, "dialog"):
    try:
        company = get_company(edit_id, client)
    except Exception:
        company = None
    if company:

        def _clear_edit_modal():
            if "company_to_edit_id" in st.session_state:
                del st.session_state["company_to_edit_id"]

        @st.dialog("Edit company", dismissible=True, on_dismiss=_clear_edit_modal)
        def _edit_company_modal():
            with st.form("edit_company_modal_form"):
                st.caption(f"Editing: {company.get('ticker')} — {company.get('name')}")
                upd_name = st.text_input("Name", value=company.get("name") or "")
                st.text_input("Ticker (read-only)", value=company.get("ticker") or "", disabled=True, key="edit_ticker_ro")
                cur_ind_id = str(company.get("industry_id") or "")
                if industry_options:
                    ind_sel = next((i for i, iid in enumerate(industry_ids) if str(iid) == cur_ind_id), 0)
                    n = len(industry_labels)
                    upd_industry_idx = st.selectbox("Industry", range(n), index=min(ind_sel, n - 1), format_func=lambda i: industry_labels[i], key="upd_industry_modal")
                    upd_industry_id = industry_ids[upd_industry_idx]
                else:
                    st.caption("No industries in DB; industry cannot be changed.")
                    upd_industry_id = None
                upd_domain = st.text_input("Domain", value=company.get("domain") or "", key="upd_domain_modal")
                upd_careers_url = st.text_input("Careers URL", value=company.get("careers_url") or "", key="upd_careers_modal")
                upd_news_url = st.text_input("News URL", value=company.get("news_url") or "", key="upd_news_modal")
                upd_leadership_url = st.text_input("Leadership URL", value=company.get("leadership_url") or "", key="upd_leadership_modal")
                upd_glassdoor_company_id = st.text_input(
                    "Glassdoor company ID",
                    value=company.get("glassdoor_company_id") or "",
                    placeholder="e.g. 9079 from ...-Reviews-E9079.htm",
                    key="upd_glassdoor_modal",
                    help="Glassdoor employer ID for review collection when RapidAPI search fails.",
                )
                col1, col2, _ = st.columns(3)
                with col1:
                    save_clicked = st.form_submit_button("Save changes")
                with col2:
                    cancel_clicked = st.form_submit_button("Cancel")
                if cancel_clicked:
                    _clear_edit_modal()
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                if save_clicked:
                    try:
                        update_company(
                            edit_id,
                            name=upd_name or None,
                            industry_id=upd_industry_id,
                            domain=upd_domain or None,
                            careers_url=upd_careers_url or None,
                            news_url=upd_news_url or None,
                            leadership_url=upd_leadership_url or None,
                            glassdoor_company_id=upd_glassdoor_company_id.strip() or None,
                        )
                        st.success("Company updated.")
                        _clear_edit_modal()
                        if hasattr(st, "rerun"):
                            st.rerun()
                        else:
                            st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to update: {e}")

        _edit_company_modal()
    else:
        if "company_to_edit_id" in st.session_state:
            del st.session_state["company_to_edit_id"]

client.close()
