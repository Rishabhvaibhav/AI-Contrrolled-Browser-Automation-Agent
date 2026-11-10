"""
ui/app.py — ShadowBrowser Streamlit Dashboard
Enhanced with Freelance Hub tab, improved dark-mode cards, and real candidate data.
"""
import os
import sys
import json
import asyncio
import base64
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.config import (
    DATA_DIR,
    PROFILES_DIR,
    DOWNLOADS_DIR,
    SCREENSHOTS_DIR,
    ALPME_BASE_URL,
    ALPME_API_KEY,
    DEFAULT_MODEL,
    HEADLESS_MODE,
    FREELANCE_PLATFORMS_JSON,
    FREELANCE_STATUS_JSON,
    RESUME_PATH,
    GMAIL_ADDRESS,
)
from core.browser_engine import BrowserEngine
from core.profile_manager import ProfileManager, TARGET_SERVICES
from core.llm_client import LLMClient
from core.graph_context import GraphContext
from core.freelance_profile import FreelanceProfile
from agents.job_applier import JobApplier, DEFAULT_CANDIDATE_PROFILE
from agents.pdf_hunter import PDFHunter
from agents.general_agent import GeneralAgent
from agents.freelance_agent import FreelanceAgent, load_platforms, load_status, get_platform_key

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShadowBrowser | AI Browser Agent",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Base dark card */
    .sb-card {
        background: #1e2130;
        border: 1px solid #2d3148;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    /* Metric card */
    .metric-card {
        background: #161927;
        border: 1px solid #2d3148;
        border-radius: 8px;
        padding: 14px 18px;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #60a5fa;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 4px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.03em;
    }
    .badge-green  { background: #052e16; color: #4ade80; border: 1px solid #166534; }
    .badge-red    { background: #450a0a; color: #f87171; border: 1px solid #991b1b; }
    .badge-yellow { background: #422006; color: #fbbf24; border: 1px solid #92400e; }
    .badge-blue   { background: #0c1a2e; color: #60a5fa; border: 1px solid #1d4ed8; }
    .badge-gray   { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    /* Section headers */
    .section-header {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #64748b;
        margin: 16px 0 8px;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 4px;
    }
    /* Platform row */
    .platform-row {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid #1e293b;
        gap: 10px;
    }
    .platform-name { font-weight: 600; color: #e2e8f0; min-width: 160px; }
    .platform-cat  { color: #64748b; font-size: 0.82rem; min-width: 120px; }
    /* Main title */
    .main-title {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3b82f6, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .main-subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 1rem; }
    /* Log output */
    .log-output {
        font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
        font-size: 0.8rem;
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 10px 14px;
        color: #94a3b8;
        max-height: 300px;
        overflow-y: auto;
    }
    /* Button overrides */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("### ShadowBrowser")
st.sidebar.caption("Stealth AI Browser  |  Persistent Chrome Profile")
st.sidebar.divider()

pm = ProfileManager()
profiles = pm.list_profiles()
selected_profile = st.sidebar.selectbox("Active Chrome Profile", profiles, index=0)
headless_option = st.sidebar.toggle("Headless (Background Mode)", value=HEADLESS_MODE)
model_choice = st.sidebar.text_input("Alpme Model", value=DEFAULT_MODEL)

st.sidebar.divider()
st.sidebar.markdown("**Gateway Status**")
if ALPME_API_KEY:
    st.sidebar.markdown("<span class='badge badge-green'>ALPME API Key Active</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='badge badge-red'>API Key Missing</span>", unsafe_allow_html=True)
st.sidebar.caption(f"`{ALPME_BASE_URL}`")

st.sidebar.divider()
# Resume status
resume_exists = RESUME_PATH.exists()
st.sidebar.markdown("**Resume**")
if resume_exists:
    st.sidebar.markdown(f"<span class='badge badge-green'>{RESUME_PATH.name}</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='badge badge-red'>Resume.pdf not found</span>", unsafe_allow_html=True)

# ── Page Header ───────────────────────────────────────────────────────────────
st.markdown("<div class='main-title'>ShadowBrowser: Autonomous AI Web Agent</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='main-subtitle'>Persistent Real Chrome Profile &nbsp;•&nbsp; Anti-Detection Stealth &nbsp;•&nbsp; "
    "Freelance Platform Automation &nbsp;•&nbsp; Batch Job Applications &nbsp;•&nbsp; Internet-Wide PDF Hunter</div>",
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "Freelance Hub",
    "Job Applier",
    "PDF Hunter",
    "Autonomous Agent",
    "Profile & Sessions",
    "Code Intelligence",
    "Settings",
])


# =============================================================================
# TAB 0: FREELANCE HUB
# =============================================================================
with tabs[0]:
    st.subheader("Freelance Platform Automation")
    st.caption(
        "Sign up on platforms automatically, build your profile from your resume, "
        "and find & apply to freelance projects — all with undetectable human emulation."
    )

    # Load data
    fp = FreelanceProfile.from_json()
    all_platforms = load_platforms()
    p1_platforms = [p for p in all_platforms if p.get("priority") == 1]
    signup_status = load_status()

    # Top metrics
    total_attempted = len(signup_status)
    signed_up_count = sum(1 for v in signup_status.values() if v.get("signed_up"))
    profiles_done = sum(1 for v in signup_status.values() if v.get("profile_complete"))
    errors_count = sum(1 for v in signup_status.values() if v.get("status") == "error")

    m1, m2, m3, m4, m5 = st.columns(5)
    for col, val, label in [
        (m1, len(all_platforms), "Total Platforms"),
        (m2, len(p1_platforms), "Priority 1"),
        (m3, signed_up_count, "Signed Up"),
        (m4, profiles_done, "Profiles Built"),
        (m5, errors_count, "Errors"),
    ]:
        col.markdown(
            f"<div class='metric-card'><div class='metric-value'>{val}</div>"
            f"<div class='metric-label'>{label}</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    hub_col1, hub_col2 = st.columns([1, 1])

    # ── Left: Freelance Profile Preview ──────────────────────────────────────
    with hub_col1:
        st.markdown("<div class='section-header'>Your Freelance Profile</div>", unsafe_allow_html=True)
        st.markdown(f"""
<div class='sb-card'>
  <b style='font-size:1.1rem;color:#e2e8f0;'>{fp.full_name}</b><br>
  <span style='color:#94a3b8;font-size:0.85rem;'>{fp.headline}</span><br><br>
  <span style='color:#60a5fa;font-weight:600;'>{fp.get_hourly_rate_string()}</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <span style='color:#4ade80;'>{fp.availability} &bull; {fp.years_of_experience}+ yrs</span><br><br>
  <span style='color:#94a3b8;font-size:0.82rem;'>{fp.get_bio(long=False)}</span>
</div>
""", unsafe_allow_html=True)

        with st.expander("Full Bio (what gets submitted to platforms)"):
            st.text(fp.get_bio(long=True))

        st.markdown("<div class='section-header'>Skills</div>", unsafe_allow_html=True)
        skill_html = " ".join(
            f"<span class='badge badge-blue' style='margin:2px;'>{s}</span>"
            for s in fp.skills
        )
        st.markdown(skill_html, unsafe_allow_html=True)

        st.markdown("<div class='section-header'>Certifications</div>", unsafe_allow_html=True)
        for cert in fp.certifications:
            st.markdown(f"<span class='badge badge-yellow'>{cert}</span>", unsafe_allow_html=True)

        st.markdown("<div class='section-header'>Notable Clients</div>", unsafe_allow_html=True)
        st.markdown(", ".join(fp.notable_clients))

    # ── Right: Platform Signup Queue ─────────────────────────────────────────
    with hub_col2:
        st.markdown("<div class='section-header'>Priority 1 Platform Status</div>", unsafe_allow_html=True)

        for p in p1_platforms:
            key = get_platform_key(p)
            st_data = signup_status.get(key, {})
            signed = st_data.get("signed_up", False)
            prof_done = st_data.get("profile_complete", False)
            status_val = st_data.get("status", "pending")

            if signed and prof_done:
                badge = "<span class='badge badge-green'>Ready</span>"
            elif signed:
                badge = "<span class='badge badge-yellow'>Signed Up</span>"
            elif status_val == "error":
                badge = "<span class='badge badge-red'>Error</span>"
            elif status_val == "in_progress":
                badge = "<span class='badge badge-blue'>In Progress</span>"
            else:
                badge = "<span class='badge badge-gray'>Pending</span>"

            st.markdown(
                f"<div class='platform-row'>"
                f"<span class='platform-name'>{p['name']}</span>"
                f"<span class='platform-cat'>{p.get('category','')}</span>"
                f"{badge}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Signup Automation ─────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Signup Automation</div>", unsafe_allow_html=True)
    sa_col1, sa_col2, sa_col3 = st.columns([2, 1, 1])

    with sa_col1:
        platform_names = [p["name"] for p in p1_platforms]
        selected_platform = st.selectbox("Select Platform to Sign Up", platform_names)

    with sa_col2:
        safe_signup = st.toggle("Safe Mode (Pause before submit)", value=True, key="safe_signup")

    with sa_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        signup_btn = st.button("Start Signup", type="primary", use_container_width=True)

    signup_all_col1, signup_all_col2 = st.columns([2, 1])
    with signup_all_col1:
        priority_sel = st.select_slider("Signup Priority Level", options=[1, 2, 3], value=1)
    with signup_all_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        signup_all_btn = st.button("Sign Up All Priority Platforms", use_container_width=True)

    if signup_btn:
        target_p = next((p for p in p1_platforms if p["name"] == selected_platform), None)
        if target_p:
            log_placeholder = st.empty()

            async def _do_signup():
                engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
                await engine.launch()
                agent = FreelanceAgent(engine=engine, profile=fp, safe_mode=safe_signup)
                try:
                    result = await agent.signup_platform(target_p)
                    return result, agent.get_log()
                finally:
                    await engine.close()

            with st.spinner(f"Running signup on {selected_platform}..."):
                result, logs = asyncio.run(_do_signup())

            if result.get("status") == "success":
                st.success(f"Signup completed: {selected_platform}")
            else:
                st.error(f"Signup result: {result.get('status')} — {result.get('error', '')}")

            log_html = "<br>".join(logs)
            st.markdown(f"<div class='log-output'>{log_html}</div>", unsafe_allow_html=True)

    if signup_all_btn:
        async def _do_signup_all():
            engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
            await engine.launch()
            agent = FreelanceAgent(engine=engine, profile=fp, safe_mode=safe_signup)
            try:
                results = await agent.signup_all(priority=priority_sel)
                return results, agent.get_log(), agent.get_summary()
            finally:
                await engine.close()

        with st.spinner(f"Signing up on all priority-{priority_sel} platforms..."):
            results, logs, summary = asyncio.run(_do_signup_all())

        st.success(
            f"Done: {summary['signed_up']} signed up, {summary['errors']} errors "
            f"out of {summary['total_attempted']} attempted."
        )
        log_html = "<br>".join(logs)
        st.markdown(f"<div class='log-output'>{log_html}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Job Hunt ──────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Find & Apply to Freelance Projects</div>", unsafe_allow_html=True)

    jh_col1, jh_col2 = st.columns([3, 1])
    with jh_col1:
        job_query = st.text_input(
            "Project Search Query",
            value="Python ETL pipeline data engineer",
            help="Describe the type of project you're looking for",
        )
    with jh_col2:
        max_per_plat = st.number_input("Max per platform", min_value=1, max_value=20, value=5)

    platform_options = {p["name"]: get_platform_key(p) for p in p1_platforms}
    selected_platforms_names = st.multiselect(
        "Target Platforms",
        options=list(platform_options.keys()),
        default=list(platform_options.keys())[:5],
    )
    safe_apply = st.toggle("Safe Mode for Applications", value=True, key="safe_apply")
    hunt_btn = st.button("Find & Apply to Projects", type="primary")

    if hunt_btn and job_query:
        selected_keys = [platform_options[n] for n in selected_platforms_names]

        async def _hunt():
            engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
            await engine.launch()
            agent = FreelanceAgent(engine=engine, profile=fp, safe_mode=safe_apply)
            try:
                return await agent.search_and_apply(
                    query=job_query,
                    platforms=selected_keys if selected_keys else None,
                    max_per_platform=max_per_plat,
                )
            finally:
                await engine.close()

        with st.spinner(f"Searching '{job_query}' across {len(selected_platforms_names)} platforms..."):
            found_jobs = asyncio.run(_hunt())

        if found_jobs:
            st.success(f"Found {len(found_jobs)} projects")
            df = pd.DataFrame(found_jobs)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No projects found — try broadening your query or add more platforms.")

    st.markdown("---")

    # ── Platform Explorer ─────────────────────────────────────────────────────
    with st.expander("Browse All 168 Platforms"):
        cat_options = ["All"] + sorted(list({p.get("category", "") for p in all_platforms}))
        pri_options = ["All", 1, 2, 3]
        fc1, fc2 = st.columns(2)
        with fc1:
            cat_filter = st.selectbox("Category", cat_options, key="plat_cat")
        with fc2:
            pri_filter = st.selectbox("Priority", pri_options, key="plat_pri")

        filtered = all_platforms
        if cat_filter != "All":
            filtered = [p for p in filtered if p.get("category") == cat_filter]
        if pri_filter != "All":
            filtered = [p for p in filtered if p.get("priority") == pri_filter]

        df_platforms = pd.DataFrame([
            {
                "Name": p["name"],
                "Priority": p.get("priority", ""),
                "Category": p.get("category", ""),
                "URL": p.get("url", ""),
                "Signed Up": "Yes" if signup_status.get(get_platform_key(p), {}).get("signed_up") else "No",
            }
            for p in filtered
        ])
        st.dataframe(df_platforms, use_container_width=True, hide_index=True)


# =============================================================================
# TAB 1: CSV JOB APPLIER
# =============================================================================
with tabs[1]:
    st.subheader("Automate Job Applications from CSV")
    st.caption(
        "Loops over job postings, checks existing logins (LinkedIn, Naukri, Indeed), "
        "attaches resume PDF, and auto-fills multi-step forms."
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("<div class='section-header'>Job Postings CSV</div>", unsafe_allow_html=True)
        csv_file = st.file_uploader("Select CSV with job URLs", type=["csv"], key="job_csv_uploader")

        sample_path = BASE_DIR / "sample_jobs.csv"
        use_sample = False
        if not csv_file and sample_path.exists():
            st.info("Test with the built-in sample_jobs.csv")
            use_sample = st.checkbox("Use sample_jobs.csv", value=True)

        st.markdown("<div class='section-header'>Resume</div>", unsafe_allow_html=True)
        resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="resume_uploader")
        resume_target_path = str(BASE_DIR / "Resume.pdf")

        if resume_file:
            with open(resume_target_path, "wb") as f:
                f.write(resume_file.getbuffer())
            st.success("Resume uploaded: Resume.pdf")
        elif RESUME_PATH.exists():
            st.markdown(
                f"<span class='badge badge-green'>Using: {RESUME_PATH.name}</span>",
                unsafe_allow_html=True,
            )

        safe_mode = st.checkbox("Safe Mode (Pause before final submit)", value=True)
        max_jobs = st.number_input("Max jobs to process", min_value=1, max_value=100, value=5)
        include_freelance = st.checkbox("Include Freelance Platforms", value=False)

    with col2:
        st.markdown("<div class='section-header'>Candidate Profile</div>", unsafe_allow_html=True)
        cand_name = st.text_input("Full Name", value=DEFAULT_CANDIDATE_PROFILE["full_name"])
        cand_email = st.text_input("Email", value=DEFAULT_CANDIDATE_PROFILE["email"])
        cand_phone = st.text_input("Phone", value=DEFAULT_CANDIDATE_PROFILE["phone"])
        cand_exp = st.text_input("Years of Experience", value=DEFAULT_CANDIDATE_PROFILE["years_of_experience"])
        cand_notice = st.text_input("Notice Period (Days)", value=DEFAULT_CANDIDATE_PROFILE["notice_period_days"])
        cand_ctc = st.text_input("Expected CTC", value=DEFAULT_CANDIDATE_PROFILE["expected_ctc"])
        cand_linkedin = st.text_input("LinkedIn URL", value=DEFAULT_CANDIDATE_PROFILE["linkedin_url"])

    start_apply_btn = st.button("Start Applying to Jobs", type="primary")

    if start_apply_btn:
        active_csv_path = None
        if csv_file:
            active_csv_path = str(BASE_DIR / "uploaded_jobs.csv")
            with open(active_csv_path, "wb") as f:
                f.write(csv_file.getbuffer())
        elif use_sample and sample_path.exists():
            active_csv_path = str(sample_path)
        else:
            st.error("Please upload a CSV file or check 'Use sample_jobs.csv'.")

        if active_csv_path:
            profile_data = dict(DEFAULT_CANDIDATE_PROFILE)
            profile_data.update({
                "full_name": cand_name,
                "first_name": cand_name.split()[0] if cand_name else "Rishabh",
                "last_name": cand_name.split()[-1] if len(cand_name.split()) > 1 else "Vaibhav",
                "email": cand_email,
                "phone": cand_phone,
                "years_of_experience": cand_exp,
                "notice_period_days": cand_notice,
                "expected_ctc": cand_ctc,
                "linkedin_url": cand_linkedin,
                "resume_path": resume_target_path if os.path.exists(resume_target_path) else "",
            })

            progress_bar = st.progress(0.0)
            status_placeholder = st.empty()
            results_table_placeholder = st.empty()

            async def run_jobs():
                engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
                await engine.launch()
                applier = JobApplier(engine=engine, candidate_profile=profile_data, safe_mode=safe_mode)
                try:
                    records = applier.read_jobs_csv(active_csv_path)[:max_jobs]
                    total = len(records)
                    all_results = []
                    for i, r in enumerate(records):
                        status_placeholder.info(f"Processing {i+1}/{total}: {r.get('target_url')}")
                        res = await applier.apply_single_job(r)
                        all_results.append(res)
                        progress_bar.progress((i + 1) / total)
                        results_table_placeholder.dataframe(pd.DataFrame(all_results))
                    return all_results
                finally:
                    await engine.close()

            with st.spinner("Processing job applications with persistent Chrome..."):
                final_res = asyncio.run(run_jobs())
                st.success(f"Processed {len(final_res)} jobs. Report saved to applied_jobs_report.csv")


# =============================================================================
# TAB 2: PDF HUNTER
# =============================================================================
with tabs[2]:
    st.subheader("Find & Download PDFs from the Entire Internet")
    st.caption(
        "Discovers academic papers, books, financial reports, or documentation. "
        "Verifies PDF magic bytes and parses page counts."
    )

    pdf_col1, pdf_col2 = st.columns([3, 1])
    with pdf_col1:
        pdf_query = st.text_input("Document Title, Topic, or Query", value="Attention is all you need paper")
    with pdf_col2:
        search_engine_choice = st.selectbox("Search Engine", ["duckduckgo", "google", "bing"])
        max_pdf_limit = st.number_input("Max PDFs", min_value=1, max_value=10, value=3)

    hunt_pdf_btn = st.button("Hunt PDF Across Internet", type="primary")

    if hunt_pdf_btn and pdf_query:
        async def run_hunt():
            engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
            await engine.launch()
            hunter = PDFHunter(engine=engine)
            try:
                return await hunter.search_and_download(
                    query=pdf_query,
                    max_results=max_pdf_limit,
                    search_engine=search_engine_choice,
                )
            finally:
                await engine.close()

        with st.spinner(f"Searching web for '{pdf_query}'..."):
            found_pdfs = asyncio.run(run_hunt())
            if found_pdfs:
                st.success(f"Acquired {len(found_pdfs)} PDF documents")
                for doc in found_pdfs:
                    with st.expander(f"{doc.get('filename')} ({doc.get('pages', 0)} pages, {doc.get('file_size_kb', 0)} KB)"):
                        st.write(f"**Source:** [{doc.get('source_url')}]({doc.get('source_url')})")
                        st.write(f"**Local Path:** `{doc.get('local_path')}`")
                        st.write(f"**Preview:** {doc.get('preview_text')}")
                        if os.path.exists(doc.get("local_path", "")):
                            with open(doc["local_path"], "rb") as f:
                                st.download_button(
                                    label=f"Download {doc['filename']}",
                                    data=f.read(),
                                    file_name=doc["filename"],
                                    mime="application/pdf",
                                )
            else:
                st.warning("No PDFs found. Try refining your keywords.")


# =============================================================================
# TAB 3: AUTONOMOUS AGENT
# =============================================================================
with tabs[3]:
    st.subheader("Autonomous AI Browser Control")
    st.caption(
        "Give any natural language task. The agent observes the DOM, decides actions, "
        "and executes with humanized mouse and keyboard emulation."
    )

    agent_task = st.text_area(
        "Natural Language Instruction",
        value="Go to https://news.ycombinator.com, find the top story, and extract its title and link.",
        height=90,
    )
    max_agent_steps = st.slider("Max Execution Steps", min_value=3, max_value=30, value=10)
    run_agent_btn = st.button("Run Autonomous Agent", type="primary")

    if run_agent_btn and agent_task:
        async def run_general_agent():
            engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
            await engine.launch()
            llm = LLMClient(model=model_choice)
            agent = GeneralAgent(engine=engine, llm=llm, max_steps=max_agent_steps)
            try:
                res = await agent.run(agent_task)
                return res, agent.history
            finally:
                await engine.close()

        with st.spinner("AI Agent driving the browser..."):
            res, history = asyncio.run(run_general_agent())
            st.success(f"Agent finished: {res.get('status')}")
            st.markdown(f"**Summary:** {res.get('summary')}")

        if history:
            st.markdown("#### Execution Steps")
            for step in history:
                with st.expander(f"Step {step['step']}: {step.get('result')}"):
                    st.write(f"**Thought:** {step.get('thought')}")
                    st.write(f"**Action:** `{step.get('action')}`")
                    st.write(f"**URL:** {step.get('url')}")
                    if step.get("screenshot") and os.path.exists(step["screenshot"]):
                        st.image(step["screenshot"], caption=f"Step {step['step']}")


# =============================================================================
# TAB 4: PROFILE & SESSION MANAGER
# =============================================================================
with tabs[4]:
    st.subheader("Chrome Profile & Login Session Manager")
    st.markdown(
        "Log in once and all cookies, localStorage, and session tokens are saved permanently. "
        "Subsequent automated tasks run already authenticated."
    )

    col_prof1, col_prof2 = st.columns([1, 1])

    with col_prof1:
        st.markdown("<div class='section-header'>Login Status</div>", unsafe_allow_html=True)
        check_login_btn = st.button("Refresh Login Status")
        if check_login_btn:
            with st.spinner("Inspecting profile cookies..."):
                login_info = asyncio.run(pm.inspect_profile_logins(selected_profile))
            services = login_info.get("services", {})
            for k, v in services.items():
                is_in = v.get("logged_in", False)
                badge_cls = "badge-green" if is_in else "badge-red"
                label = "Logged In" if is_in else "Not Logged In"
                st.markdown(
                    f"**{v['name']}**: <span class='badge {badge_cls}'>{label}</span> "
                    f"({v.get('cookie_count', 0)} cookies)",
                    unsafe_allow_html=True,
                )
            st.info(f"Total Cookies Stored: {login_info.get('total_cookies', 0)}")

        st.divider()
        st.markdown("<div class='section-header'>Create New Profile</div>", unsafe_allow_html=True)
        new_prof_name = st.text_input("Profile Name", placeholder="e.g. work_profile")
        if st.button("Create Profile"):
            if new_prof_name:
                pm.create_profile(new_prof_name)
                st.success(f"Profile '{new_prof_name}' created. Refresh to select it.")

    with col_prof2:
        st.markdown("<div class='section-header'>Manual Login Window</div>", unsafe_allow_html=True)
        st.markdown(
            "Open a real Chrome window to log into any site and solve 2FA / OTPs. "
            "Session is saved permanently after you close the window."
        )
        target_site = st.selectbox(
            "Site",
            options=list(TARGET_SERVICES.keys()) + ["Custom URL"],
            format_func=lambda x: TARGET_SERVICES[x]["name"] if x in TARGET_SERVICES else "Custom URL",
        )
        custom_url = ""
        if target_site == "Custom URL":
            custom_url = st.text_input("Enter URL", value="https://www.google.com")

        wait_sec = st.number_input("Session open duration (seconds)", min_value=15, max_value=600, value=60)

        if st.button("Launch Chrome for Manual Login", type="primary"):
            site_param = custom_url if target_site == "Custom URL" else target_site
            with st.spinner(f"Chrome open! Log in now. Closes in {wait_sec}s..."):
                asyncio.run(pm.open_manual_login(
                    profile_name=selected_profile,
                    site_or_url=site_param,
                    wait_seconds=wait_sec,
                ))
            st.success("Session saved to profile.")


# =============================================================================
# TAB 5: CODE INTELLIGENCE (GRAPHIFY)
# =============================================================================
with tabs[5]:
    st.subheader("Graphify Knowledge Graph & Token Optimization")
    st.caption(
        "Deterministic AST parsing via tree-sitter. Reduces prompt token consumption by 9–12x "
        "by feeding structured subgraphs instead of full source files."
    )

    g_col1, g_col2 = st.columns([1, 1])
    gc = GraphContext()

    with g_col1:
        st.markdown("<div class='section-header'>Query Code Graph</div>", unsafe_allow_html=True)
        graph_query = st.text_input("Class, function, or keyword", value="FreelanceAgent")
        node_limit = st.slider("Max nodes", min_value=2, max_value=20, value=8)

        if st.button("Extract Subgraph Context"):
            ctx_text = gc.get_token_optimized_context(graph_query, max_nodes=node_limit)
            st.code(ctx_text, language="markdown")

        if st.button("Rebuild Knowledge Graph"):
            with st.spinner("Re-extracting AST with tree-sitter..."):
                import subprocess
                res = subprocess.run(["graphify", "update", "."], capture_output=True, text=True)
                st.success("Knowledge graph rebuilt.")
                if res.stdout:
                    st.text(res.stdout[:500])

    with g_col2:
        st.markdown("<div class='section-header'>Token Reduction Metrics</div>", unsafe_allow_html=True)

        mc1, mc2, mc3 = st.columns(3)
        for col, val, label in [
            (mc1, "~15K", "Corpus Tokens"),
            (mc2, "~1.6K", "Avg Query Cost"),
            (mc3, "9–12x", "Token Reduction"),
        ]:
            col.markdown(
                f"<div class='metric-card'><div class='metric-value' style='font-size:1.5rem;'>{val}</div>"
                f"<div class='metric-label'>{label}</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        graph_html_path = BASE_DIR / "graphify-out" / "graph.html"
        if graph_html_path.exists():
            st.info("Interactive graph available at `graphify-out/graph.html`")
            if st.button("Show Graph Report Summary"):
                st.markdown(gc.get_graph_report_summary())


# =============================================================================
# TAB 6: SETTINGS
# =============================================================================
with tabs[6]:
    st.subheader("Settings & Gateway Configuration")

    s_col1, s_col2 = st.columns(2)

    with s_col1:
        st.markdown("<div class='section-header'>Alpme Gateway</div>", unsafe_allow_html=True)
        st.text_input("Base URL", value=ALPME_BASE_URL, disabled=True)
        st.text_input(
            "API Key",
            value=ALPME_API_KEY[:8] + "..." if ALPME_API_KEY else "Not Set",
            disabled=True,
        )

        st.markdown("<div class='section-header'>Available Models</div>", unsafe_allow_html=True)
        if st.button("Query Gateway Models"):
            llm = LLMClient()
            models = llm.list_available_models()
            st.write(f"Models available: {len(models)}")
            st.json(models[:10])

    with s_col2:
        st.markdown("<div class='section-header'>Candidate Profile</div>", unsafe_allow_html=True)
        try:
            profile_json_path = BASE_DIR / "candidate_profile.json"
            if profile_json_path.exists():
                with open(profile_json_path) as pf:
                    profile_data = json.load(pf)
                st.json(profile_data)
        except Exception as e:
            st.error(f"Could not load candidate_profile.json: {e}")

        st.markdown("<div class='section-header'>Gmail OTP Reader</div>", unsafe_allow_html=True)
        gmail_configured = bool(os.getenv("GMAIL_APP_PASSWORD", ""))
        if gmail_configured:
            st.markdown("<span class='badge badge-green'>IMAP Configured</span>", unsafe_allow_html=True)
            st.caption("OTP emails will be read via Gmail IMAP (fast, no browser needed).")
        else:
            st.markdown("<span class='badge badge-yellow'>Browser Fallback</span>", unsafe_allow_html=True)
            st.caption(
                "Set GMAIL_APP_PASSWORD in .env for fast IMAP reading. "
                "Without it, the agent opens Gmail in a browser tab (slower)."
            )
        st.text_input("Gmail Address", value=GMAIL_ADDRESS, disabled=True)

    st.markdown("---")
    st.markdown("<div class='section-header'>Directory Paths</div>", unsafe_allow_html=True)
    path_data = {
        "Project Root": str(BASE_DIR),
        "Chrome Profiles": str(PROFILES_DIR),
        "Downloads": str(DOWNLOADS_DIR),
        "Screenshots": str(SCREENSHOTS_DIR),
        "Resume": str(RESUME_PATH),
        "Platform DB": str(FREELANCE_PLATFORMS_JSON),
        "Signup Status": str(FREELANCE_STATUS_JSON),
    }
    for label, path in path_data.items():
        exists = Path(path).exists()
        badge = "<span class='badge badge-green'>exists</span>" if exists else "<span class='badge badge-red'>missing</span>"
        st.markdown(f"**{label}**: `{path}` {badge}", unsafe_allow_html=True)
