"""SAR Narrative Copilot — thin Streamlit UI (Week 3).

Run (API must already be up on :8000):
  streamlit run ui/app.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on path when launched via `streamlit run ui/app.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.api_client import ApiError, SarApiClient

DEFAULT_API = os.getenv("SAR_API_BASE_URL", "http://127.0.0.1:8000")

# Lifecycle order for the stepper (terminal states are alternatives).
_LIFECYCLE = ["open", "drafted", "under_review", "approved"]
_TERMINAL = {"approved", "rejected"}


def get_client() -> SarApiClient:
    return SarApiClient(base_url=st.session_state.get("api_base", DEFAULT_API))


def init_state() -> None:
    defaults = {
        "api_base": DEFAULT_API,
        "token": None,
        "user": None,
        "selected_case_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def logout() -> None:
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.selected_case_id = None


def inject_styles() -> None:
    """Light compliance-console styling — avoid stock purple Streamlit chrome."""
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; max-width: 1200px; }
        .sar-stepper {
            display: flex; gap: 0.35rem; flex-wrap: wrap;
            margin: 0.4rem 0 1rem 0;
        }
        .sar-step {
            padding: 0.28rem 0.7rem; border-radius: 999px;
            font-size: 0.78rem; font-weight: 600;
            border: 1px solid #cbd5e1; color: #64748b; background: #f8fafc;
        }
        .sar-step.done { background: #ecfdf5; border-color: #6ee7b7; color: #047857; }
        .sar-step.current { background: #0f766e; border-color: #0f766e; color: #fff; }
        .sar-step.rejected { background: #fef2f2; border-color: #fca5a5; color: #b91c1c; }
        .sar-meta {
            display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.8rem;
        }
        .sar-chip {
            background: #f1f5f9; border: 1px solid #e2e8f0; color: #334155;
            padding: 0.2rem 0.55rem; border-radius: 6px; font-size: 0.8rem;
        }
        .sar-chip strong { color: #0f172a; }
        .sar-cite {
            border-left: 3px solid #0f766e; padding: 0.35rem 0.6rem;
            margin: 0.35rem 0; background: #f8fafc; font-size: 0.88rem;
        }
        .sar-audit-item {
            border-bottom: 1px solid #e2e8f0; padding: 0.55rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_lifecycle_stepper(status: str) -> None:
    """Visual lifecycle: open → drafted → under_review → approved | rejected."""
    parts: list[str] = ['<div class="sar-stepper">']
    if status == "rejected":
        # Show path up to under_review as done, then rejected as current terminal.
        for step in ["open", "drafted", "under_review"]:
            parts.append(f'<span class="sar-step done">{step}</span>')
        parts.append('<span class="sar-step rejected">rejected</span>')
    else:
        try:
            current_idx = _LIFECYCLE.index(status) if status in _LIFECYCLE else 0
        except ValueError:
            current_idx = 0
        for i, step in enumerate(_LIFECYCLE):
            cls = "sar-step"
            if i < current_idx:
                cls += " done"
            elif i == current_idx:
                cls += " current"
            parts.append(f'<span class="{cls}">{step}</span>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_case_header(case: dict) -> None:
    st.title(case["title"])
    st.markdown(
        f"""
        <div class="sar-meta">
          <span class="sar-chip"><strong>Alert</strong> {case['external_alert_id']}</span>
          <span class="sar-chip"><strong>Status</strong> {case['status']}</span>
          <span class="sar-chip"><strong>Typology</strong> {case['typology']}</span>
          <span class="sar-chip"><strong>Risk</strong> {case.get('risk_score') if case.get('risk_score') is not None else '—'}</span>
          <span class="sar-chip"><strong>Jurisdiction</strong> {case.get('jurisdiction', 'FinCEN')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_lifecycle_stepper(case["status"])


def render_audit_timeline(audit: list[dict], *, limit: int | None = None) -> None:
    if not audit:
        st.info("No audit events yet.")
        return
    events = list(reversed(audit))
    if limit is not None:
        events = events[:limit]
    for event in events:
        st.markdown(
            f"""
            <div class="sar-audit-item">
              <strong>{event['event_type']}</strong>
              <span style="color:#64748b;font-size:0.85rem">
                · {event['created_at']} · role=`{event.get('actor_role') or '—'}`
              </span>
              <div style="margin-top:0.2rem">{event['summary']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Detail"):
            try:
                st.json(json.loads(event.get("detail_json") or "{}"))
            except json.JSONDecodeError:
                st.code(event.get("detail_json") or "{}")


def render_login() -> None:
    st.title("SAR Narrative Copilot")
    st.caption("Analyst-in-the-loop · FinCEN-style 5 Ws + How · grounded RAG + audit trail")

    with st.form("login_form"):
        api_base = st.text_input("API base URL", value=st.session_state.api_base)
        email = st.text_input("Email", value="analyst@example.com")
        password = st.text_input("Password", type="password", value="AnalystPass123!")
        submitted = st.form_submit_button("Sign in", type="primary")

    if not submitted:
        st.info(
            "Seeded users: `analyst@example.com` / `reviewer@example.com` / `admin@example.com`. "
            "API must be running on the base URL above."
        )
        return

    st.session_state.api_base = api_base.rstrip("/")
    client = get_client()
    try:
        token = client.login(email.strip(), password)
        user = client.me(token)
    except ApiError as exc:
        st.error(f"Login failed — {exc.detail}")
        return
    except Exception as exc:  # connection refused, etc.
        st.error(f"Cannot reach API at {st.session_state.api_base}: {exc}")
        return

    st.session_state.token = token
    st.session_state.user = user
    st.rerun()


def render_sidebar() -> None:
    user = st.session_state.user
    st.sidebar.markdown(f"**{user['full_name']}**")
    st.sidebar.caption(f"{user['email']} · `{user['role']}`")
    if st.sidebar.button("Sign out"):
        logout()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Cases")
    client = get_client()
    try:
        cases = client.list_cases(st.session_state.token)
    except ApiError as exc:
        st.sidebar.error(exc.detail)
        return

    if not cases:
        st.sidebar.warning("No cases yet. Seed the DB or create one via API.")
        return

    labels = {
        c["id"]: f"#{c['id']} · {c['external_alert_id']} · {c['status']}"
        for c in cases
    }
    ids = list(labels.keys())
    current = st.session_state.selected_case_id
    index = ids.index(current) if current in ids else 0
    choice = st.sidebar.radio(
        "Select case",
        options=ids,
        index=index,
        format_func=lambda i: labels[i],
    )
    st.session_state.selected_case_id = choice


def _role() -> str:
    return (st.session_state.user or {}).get("role", "")


def render_case_workspace() -> None:
    case_id = st.session_state.selected_case_id
    if not case_id:
        st.info("Select a case from the sidebar.")
        return

    client = get_client()
    token = st.session_state.token
    try:
        case = client.get_case(token, case_id)
        drafts = client.list_drafts(token, case_id)
        audit = client.case_audit(token, case_id)
    except ApiError as exc:
        st.error(exc.detail)
        return

    render_case_header(case)

    tab_overview, tab_draft, tab_audit = st.tabs(
        ["Overview", "Narrative draft", "Audit trail"]
    )

    with tab_overview:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Customer (KYC)")
            st.markdown(
                f"""
                - **ID:** `{case['customer_id']}`
                - **Name:** {case['customer_name']}
                - **Occupation:** {case['customer_occupation']}
                - **Country:** {case['customer_country']}
                - **Expected activity:** {case['customer_expected_activity']}
                """
            )
        with col2:
            st.subheader("Alert reason")
            st.write(case["alert_reason"])

        st.subheader("Transactions (evidence)")
        st.caption("These txn refs are the allow-list the model may cite.")
        st.dataframe(case.get("transactions") or [], use_container_width=True)

        st.subheader("Recent audit")
        render_audit_timeline(audit, limit=5)
        if len(audit) > 5:
            st.caption("Showing latest 5 — full trail is on the Audit trail tab.")

    with tab_draft:
        render_draft_tab(client, token, case, drafts)

    with tab_audit:
        st.subheader("Full audit trail")
        render_audit_timeline(audit)


def render_evidence_panel(case: dict, latest: dict | None) -> None:
    """Left column: what the model was allowed to use + what it retrieved."""
    st.markdown("##### Evidence allow-list")
    txns = case.get("transactions") or []
    if not txns:
        st.warning("No transactions on this case.")
    else:
        for t in txns:
            st.markdown(
                f"- `{t.get('txn_ref')}` · {t.get('txn_type')} · "
                f"**{t.get('amount')}** {t.get('currency', 'USD')} · {t.get('location')}"
            )

    st.markdown("##### Retrieval citations")
    if not latest:
        st.caption("Generate a draft to see RAG citations.")
        return
    try:
        citations = json.loads(latest.get("retrieval_citations_json") or "[]")
    except json.JSONDecodeError:
        citations = []
    try:
        txn_refs = json.loads(latest.get("evidence_txn_refs_json") or "[]")
    except json.JSONDecodeError:
        txn_refs = []

    st.caption(f"Cited txn refs: {', '.join(txn_refs) or '(none yet)'}")
    if not citations:
        st.caption("No citations stored on this draft.")
        return
    for cite in citations:
        dist = cite.get("distance")
        dist_s = f"{dist:.3f}" if isinstance(dist, (int, float)) else dist
        st.markdown(
            f"""
            <div class="sar-cite">
              <strong>{cite.get('doc_id')}</strong> — {cite.get('title')}<br/>
              <span style="color:#64748b">distance={dist_s}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_draft_tab(client: SarApiClient, token: str, case: dict, drafts: list) -> None:
    role = _role()
    can_analyst = role in {"analyst", "admin"}
    can_reviewer = role in {"reviewer", "admin"}
    status = case["status"]
    latest = drafts[-1] if drafts else None

    # Analyst actions
    if can_analyst and status in {"open", "drafted"}:
        a1, a2, _ = st.columns([1, 1, 2])
        with a1:
            if st.button("Generate draft (RAG + Groq)", type="primary"):
                with st.spinner("Retrieving policy + calling Groq..."):
                    try:
                        client.generate_draft(token, case["id"])
                        st.success("Draft generated.")
                        st.rerun()
                    except ApiError as exc:
                        st.error(f"{exc.status_code}: {exc.detail}")
        with a2:
            if st.button("Submit for review"):
                try:
                    client.submit_case(token, case["id"])
                    st.success("Submitted.")
                    st.rerun()
                except ApiError as exc:
                    st.error(exc.detail)

    if can_reviewer and status in {"under_review", "drafted"}:
        st.markdown("#### Reviewer decision")
        decision_comment = st.text_area(
            "Decision comment (required)",
            key=f"decision_comment_{case['id']}",
            placeholder="Explain why you are approving or rejecting this narrative…",
            height=100,
        )
        comment_ok = bool(decision_comment.strip())
        if not comment_ok:
            st.caption("Enter a non-empty comment to enable Approve / Reject.")

        rev_cols = st.columns(2)
        with rev_cols[0]:
            if st.button("Approve", type="primary", disabled=not comment_ok):
                try:
                    client.approve_case(
                        token, case["id"], comment=decision_comment.strip()
                    )
                    st.success("Approved.")
                    st.rerun()
                except ApiError as exc:
                    st.error(exc.detail)
        with rev_cols[1]:
            if st.button("Reject", disabled=not comment_ok):
                try:
                    client.reject_case(
                        token, case["id"], comment=decision_comment.strip()
                    )
                    st.warning("Rejected.")
                    st.rerun()
                except ApiError as exc:
                    st.error(exc.detail)

    left, right = st.columns([1, 1.25], gap="large")
    with left:
        render_evidence_panel(case, latest)

    with right:
        if not latest:
            st.info("No draft yet. Analysts can click **Generate draft**.")
            return

        st.markdown(
            f"##### Draft v{latest['version']} · model=`{latest.get('model_name')}`"
        )

        if can_analyst and status in {"open", "drafted"}:
            with st.form("edit_draft"):
                who = st.text_area("Who", value=latest.get("who") or "", height=70)
                what = st.text_area("What", value=latest.get("what") or "", height=70)
                when = st.text_area("When", value=latest.get("when") or "", height=55)
                where = st.text_area("Where", value=latest.get("where") or "", height=55)
                why = st.text_area("Why", value=latest.get("why") or "", height=70)
                how = st.text_area("How", value=latest.get("how") or "", height=70)
                full = st.text_area(
                    "Full narrative",
                    value=latest.get("full_narrative") or "",
                    height=140,
                )
                if st.form_submit_button("Save edits"):
                    try:
                        client.update_draft(
                            token,
                            case["id"],
                            {
                                "who": who,
                                "what": what,
                                "when": when,
                                "where": where,
                                "why": why,
                                "how": how,
                                "full_narrative": full,
                            },
                        )
                        st.success("Draft updated.")
                        st.rerun()
                    except ApiError as exc:
                        st.error(exc.detail)
        else:
            for label, key in [
                ("Who", "who"),
                ("What", "what"),
                ("When", "when"),
                ("Where", "where"),
                ("Why", "why"),
                ("How", "how"),
                ("Full narrative", "full_narrative"),
            ]:
                st.markdown(f"**{label}**")
                st.write(latest.get(key) or "—")


def main() -> None:
    st.set_page_config(
        page_title="SAR Narrative Copilot",
        layout="wide",
    )
    inject_styles()
    init_state()

    if not st.session_state.token:
        render_login()
        return

    render_sidebar()
    render_case_workspace()


if __name__ == "__main__":
    main()
