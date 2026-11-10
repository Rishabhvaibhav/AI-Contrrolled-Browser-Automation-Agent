import os
import sys
import json
import asyncio
import base64
from pathlib import Path
import streamlit as st
import pandas as pd

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.config import (
    PROFILES_DIR,
    DOWNLOADS_DIR,
    SCREENSHOTS_DIR,
    ALPME_BASE_URL,
    ALPME_API_KEY,
    DEFAULT_MODEL,
    HEADLESS_MODE,
)
from core.browser_engine import BrowserEngine
from core.profile_manager import ProfileManager, TARGET_SERVICES
from core.llm_client import LLMClient
from core.graph_context import GraphContext
from agents.job_applier import JobApplier, DEFAULT_CANDIDATE_PROFILE
from agents.pdf_hunter import PDFHunter
from agents.general_agent import GeneralAgent

# Page configuration
st.set_page_config(
    page_title="ShadowBrowser | AI-Controlled Stealth Browser",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-ok { background-color: #065f46; color: #34d399; }
    .badge-err { background-color: #7f1d1d; color: #f87171; }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("### 🌐 ShadowBrowser Engine")
st.sidebar.caption("Real Chrome Profile Mimic + Alpme AI Gateway")

pm = ProfileManager()
profiles = pm.list_profiles()
selected_profile = st.sidebar.selectbox("Active Profile", profiles, index=0)

headless_option = st.sidebar.toggle("Headless Mode (Background)", value=HEADLESS_MODE)
model_choice = st.sidebar.text_input("Alpme Model", value=DEFAULT_MODEL)

st.sidebar.divider()
st.sidebar.markdown("#### 🔑 Gateway Connection")
has_key = bool(ALPME_API_KEY)
if has_key:
    st.sidebar.markdown("<span class='status-badge badge-ok'>ALPME_API_KEY Active</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='status-badge badge-err'>API Key Missing in .env</span>", unsafe_allow_html=True)

st.sidebar.caption(f"Endpoint: `{ALPME_BASE_URL}`")

# Title Header
st.markdown("<div class='main-title'>ShadowBrowser: Autonomous AI Web Agent</div>", unsafe_allow_html=True)
st.markdown("Persistent Real Chrome Profile • Anti-Detection Stealth • Batch Job Applications • Internet-Wide PDF Hunter")

tabs = st.tabs(["Job Applier", "PDF Hunter", "Autonomous Agent", "Profile & Session Manager", "Graphify Code Intelligence", "Settings"])

# =====================================================================
# TAB 1: CSV Job Applier
# =====================================================================
with tabs[0]:
    st.subheader("Automate Job Applications from CSV")
    st.caption("Loops over job postings, checks existing logins (LinkedIn, Naukri, Indeed), attaches resume PDF, and auto-fills multi-step forms.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 1. Upload Job Postings CSV")
        csv_file = st.file_uploader("Select CSV with job URLs", type=["csv"], key="job_csv_uploader")
        
        sample_path = BASE_DIR / "sample_jobs.csv"
        if not csv_file and sample_path.exists():
            st.info("💡 You can also test with the built-in `sample_jobs.csv`")
            use_sample = st.checkbox("Use sample_jobs.csv", value=True)
        else:
            use_sample = False

        st.markdown("#### 2. Candidate Resume & Preferences")
        resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="resume_uploader")
        resume_target_path = str(BASE_DIR / "resume.pdf")

        if resume_file:
            with open(resume_target_path, "wb") as f:
                f.write(resume_file.getbuffer())
            st.success("Resume uploaded and staged as `resume.pdf`")

        safe_mode = st.checkbox("Safe Mode (Pause before final submit for review)", value=True)
        max_jobs = st.number_input("Max jobs to process", min_value=1, max_value=100, value=5)

    with col2:
        st.markdown("#### 3. Candidate Profile Details")
        cand_name = st.text_input("Full Name", value=DEFAULT_CANDIDATE_PROFILE["full_name"])
        cand_email = st.text_input("Email", value=DEFAULT_CANDIDATE_PROFILE["email"])
        cand_phone = st.text_input("Phone Number", value=DEFAULT_CANDIDATE_PROFILE["phone"])
        cand_exp = st.text_input("Years of Experience", value=DEFAULT_CANDIDATE_PROFILE["years_of_experience"])
        cand_notice = st.text_input("Notice Period (Days)", value=DEFAULT_CANDIDATE_PROFILE["notice_period_days"])
        cand_ctc = st.text_input("Expected CTC", value=DEFAULT_CANDIDATE_PROFILE["expected_ctc"])
        cand_linkedin = st.text_input("LinkedIn Profile URL", value=DEFAULT_CANDIDATE_PROFILE["linkedin_url"])

    start_apply_btn = st.button("🚀 Start Applying to Jobs", type="primary")

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
                "first_name": cand_name.split()[0] if cand_name else "Alex",
                "last_name": cand_name.split()[-1] if len(cand_name.split()) > 1 else "",
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
                applier = JobApplier(
                    engine=engine,
                    candidate_profile=profile_data,
                    safe_mode=safe_mode,
                )
                try:
                    records = applier.read_jobs_csv(active_csv_path)[:max_jobs]
                    total = len(records)
                    all_results = []
                    for i, r in enumerate(records):
                        status_placeholder.info(f"Processing job {i+1}/{total}: {r.get('target_url')}")
                        res = await applier.apply_single_job(r)
                        all_results.append(res)
                        progress_bar.progress((i + 1) / total)
                        results_table_placeholder.dataframe(pd.DataFrame(all_results))
                    return all_results
                finally:
                    await engine.close()

            with st.spinner("Processing job applications with real persistent Chrome..."):
                final_res = asyncio.run(run_jobs())
                st.success(f"Processed {len(final_res)} jobs! Report saved to applied_jobs_report.csv")


# =====================================================================
# TAB 2: PDF Hunter
# =====================================================================
with tabs[1]:
    st.subheader("Find & Download PDFs from the Entire Internet")
    st.caption("Discovers academic papers, books, financial reports, or documentation, verifies PDF magic bytes, and parses page counts.")

    pdf_col1, pdf_col2 = st.columns([3, 1])
    with pdf_col1:
        pdf_query = st.text_input("Enter Document Title, Topic, or Query", value="Attention is all you need paper")
    with pdf_col2:
        search_engine_choice = st.selectbox("Search Engine", ["duckduckgo", "google", "bing"])
        max_pdf_limit = st.number_input("Max PDFs", min_value=1, max_value=10, value=3)

    hunt_pdf_btn = st.button("🔍 Hunt PDF Across Internet", type="primary")

    if hunt_pdf_btn and pdf_query:
        async def run_hunt():
            engine = BrowserEngine(profile_name=selected_profile, headless=headless_option)
            await engine.launch()
            hunter = PDFHunter(engine=engine)
            try:
                results = await hunter.search_and_download(
                    query=pdf_query,
                    max_results=max_pdf_limit,
                    search_engine=search_engine_choice,
                )
                return results
            finally:
                await engine.close()

        with st.spinner(f"Searching web for '{pdf_query}' and acquiring PDFs..."):
            found_pdfs = asyncio.run(run_hunt())
            if found_pdfs:
                st.success(f"Acquired and validated {len(found_pdfs)} PDF documents!")
                for doc in found_pdfs:
                    with st.expander(f"📄 {doc.get('filename')} ({doc.get('pages', 0)} pages, {doc.get('file_size_kb', 0)} KB)"):
                        st.write(f"**Source URL:** [{doc.get('source_url')}]({doc.get('source_url')})")
                        st.write(f"**Local Path:** `{doc.get('local_path')}`")
                        st.write(f"**Preview Text:** {doc.get('preview_text')}")
                        if os.path.exists(doc.get("local_path", "")):
                            with open(doc["local_path"], "rb") as f:
                                st.download_button(
                                    label=f"⬇️ Download {doc['filename']}",
                                    data=f.read(),
                                    file_name=doc["filename"],
                                    mime="application/pdf",
                                )
            else:
                st.warning("No direct downloadable PDFs could be retrieved for this query. Try refining your keywords.")


# =====================================================================
# TAB 3: Autonomous AI Agent
# =====================================================================
with tabs[2]:
    st.subheader("Autonomous AI Browser Control")
    st.caption("Give any natural language task. The agent observes the page DOM, decides actions, and executes with humanized mouse/keyboard emulation.")

    agent_task = st.text_area(
        "Enter Natural Language Instruction",
        value="Go to https://news.ycombinator.com, find the top story, and extract its title and link.",
        height=90,
    )
    max_agent_steps = st.slider("Max Execution Steps", min_value=3, max_value=30, value=10)
    run_agent_btn = st.button("⚡ Run Autonomous Agent", type="primary")

    if run_agent_btn and agent_task:
        log_container = st.empty()
        screenshot_container = st.empty()

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

        with st.spinner("AI Agent is driving the browser..."):
            res, history = asyncio.run(run_general_agent())
            st.success(f"Agent Finished: {res.get('status')}")
            st.markdown(f"**Summary:** {res.get('summary')}")

            if history:
                st.markdown("#### Execution Steps & Observations")
                for step in history:
                    with st.expander(f"Step {step['step']}: {step.get('result')}"):
                        st.write(f"**Thought:** {step.get('thought')}")
                        st.write(f"**Action:** `{step.get('action')}`")
                        st.write(f"**URL:** {step.get('url')}")
                        if step.get("screenshot") and os.path.exists(step["screenshot"]):
                            st.image(step["screenshot"], caption=f"Step {step['step']}")


# =====================================================================
# TAB 4: Profile & Login Manager
# =====================================================================
with tabs[3]:
    st.subheader("Chrome Profile & Login Session Manager")
    st.markdown("""
    When you log in once (LinkedIn, Naukri, Indeed, Google, GitHub), **all cookies, localStorage, and session tokens are permanently saved** inside your profile folder.
    Subsequent AI automated tasks will run already logged in!
    """)

    col_prof1, col_prof2 = st.columns([1, 1])

    with col_prof1:
        st.markdown("#### Saved Login Status")
        check_login_btn = st.button("🔄 Check Active Logins in Profile")
        if check_login_btn:
            with st.spinner("Inspecting profile cookies..."):
                login_info = asyncio.run(pm.inspect_profile_logins(selected_profile))
                services = login_info.get("services", {})
                for k, v in services.items():
                    is_in = v.get("logged_in", False)
                    badge_class = "badge-ok" if is_in else "badge-err"
                    status_text = "Logged In ✅" if is_in else "Not Logged In ❌"
                    st.markdown(
                        f"**{v['name']}**: <span class='status-badge {badge_class}'>{status_text}</span> ({v.get('cookie_count', 0)} cookies)",
                        unsafe_allow_html=True,
                    )
                st.info(f"Total Cookies Stored: {login_info.get('total_cookies', 0)}")

        st.divider()
        new_prof_name = st.text_input("Create New Profile", placeholder="e.g. work_profile")
        if st.button("➕ Create Profile"):
            if new_prof_name:
                pm.create_profile(new_prof_name)
                st.success(f"Created profile '{new_prof_name}'! Refresh page to select it.")

    with col_prof2:
        st.markdown("#### Interactive Manual Login")
        st.markdown("Launch a real visible Chrome window to log into any website and solve 2FA/OTPs. When you finish, the session is saved permanently.")
        
        target_site = st.selectbox(
            "Select Site to Log In",
            options=list(TARGET_SERVICES.keys()) + ["Custom URL"],
            format_func=lambda x: TARGET_SERVICES[x]["name"] if x in TARGET_SERVICES else "Custom URL",
        )
        custom_url = ""
        if target_site == "Custom URL":
            custom_url = st.text_input("Enter URL", value="https://www.google.com")

        wait_sec = st.number_input("Session open duration (seconds)", min_value=15, max_value=600, value=60)
        
        if st.button("🌐 Launch Chrome for Manual Login", type="primary"):
            site_param = custom_url if target_site == "Custom URL" else target_site
            with st.spinner(f"Chrome opened! Log into your account. Window will close in {wait_sec}s..."):
                asyncio.run(pm.open_manual_login(
                    profile_name=selected_profile,
                    site_or_url=site_param,
                    wait_seconds=wait_sec,
                ))
            st.success("Session saved! Profile updated.")


# =====================================================================
# TAB 5: Graphify Code Intelligence
# =====================================================================
with tabs[4]:
    st.subheader("Graphify Knowledge Graph & Token Optimization")
    st.caption("Deterministic AST parsing via tree-sitter. Reduces prompt token consumption by 9.1x by feeding structured subgraphs instead of full code files.")

    g_col1, g_col2 = st.columns([1, 1])
    gc = GraphContext()

    with g_col1:
        st.markdown("#### Query Code Knowledge Graph")
        graph_query = st.text_input("Enter class, function, or keyword", value="JobApplier")
        node_limit = st.slider("Max nodes to extract", min_value=2, max_value=20, value=8)
        
        if st.button("Extract Subgraph Context"):
            ctx_text = gc.get_token_optimized_context(graph_query, max_nodes=node_limit)
            st.code(ctx_text, language="markdown")

        if st.button("Rebuild Knowledge Graph"):
            with st.spinner("Re-extracting code AST with tree-sitter..."):
                import subprocess
                res = subprocess.run(["graphify", "update", "."], capture_output=True, text=True)
                st.success("Rebuilt code graph successfully!")
                st.text(res.stdout)

    with g_col2:
        st.markdown("#### Token Reduction Metrics")
        st.markdown("""
        - **Corpus Size:** ~14,733 tokens (naive full file read)
        - **Average Query Cost:** ~1,626 tokens (Graphify subgraphs)
        - **Token Reduction:** **9.1x fewer tokens per query**
        """)
        
        graph_html_path = BASE_DIR / "graphify-out" / "graph.html"
        if graph_html_path.exists():
            st.info("Interactive force-directed graph is available at `graphify-out/graph.html`")
            if st.button("Open Graph Report Summary"):
                st.markdown(gc.get_graph_report_summary())

# =====================================================================
# TAB 6: Settings
# =====================================================================
with tabs[5]:
    st.subheader("Settings & Alpme Gateway Configuration")
    st.text_input("Alpme Gateway Base URL", value=ALPME_BASE_URL, disabled=True)
    st.text_input("Active API Key", value=ALPME_API_KEY[:8] + "..." if ALPME_API_KEY else "Not Set", disabled=True)
    
    st.markdown("#### Available Models on Alpme Gateway")
    if st.button("📋 Query Available Gateway Models"):
        llm = LLMClient()
        models = llm.list_available_models()
        st.write(f"Total models available: {len(models)}")
        st.json(models)
