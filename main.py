import os
import sys
import argparse
import asyncio
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ShadowBrowser")

from core.config import (
    BASE_DIR,
    DEFAULT_PROFILE_NAME,
    HEADLESS_MODE,
    DEFAULT_MODEL,
    FREELANCE_PLATFORMS_JSON,
    FREELANCE_STATUS_JSON,
    RESUME_PATH,
)
from core.browser_engine import BrowserEngine
from core.profile_manager import ProfileManager
from core.llm_client import LLMClient
from core.graph_context import GraphContext
from agents.general_agent import GeneralAgent
from agents.job_applier import JobApplier, DEFAULT_CANDIDATE_PROFILE
from agents.pdf_hunter import PDFHunter


# ──────────────────────────────────────────────────────────────────────────────
#  Existing commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_web(args):
    """Launch the Streamlit Web Dashboard."""
    import subprocess
    app_path = BASE_DIR / "ui" / "app.py"
    logger.info(f"Starting ShadowBrowser Web Dashboard: {app_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])

def cmd_graphify(args):
    """Update the codebase knowledge graph with Graphify."""
    import subprocess
    logger.info("Executing Graphify AST extraction on codebase...")
    res = subprocess.run(["graphify", "update", "."], capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    gc = GraphContext()
    print(f"Graphify rebuild complete. Loaded {len(gc.nodes)} nodes and {len(gc.edges)} edges.")

def cmd_graph_query(args):
    """Query the Graphify knowledge graph for token-optimized context."""
    gc = GraphContext()
    context = gc.get_token_optimized_context(args.query, max_nodes=args.limit)
    print("\n" + "=" * 60)
    print("GRAPHIFY TOKEN-OPTIMIZED CONTEXT")
    print("=" * 60)
    print(context)
    print("=" * 60 + "\n")

def cmd_graph_benchmark(args):
    """Measure Graphify token savings."""
    import subprocess
    res = subprocess.run(["graphify", "benchmark"], capture_output=True, text=True)
    print(res.stdout)

def cmd_login(args):
    """Open real Chrome to log into a site and save the session."""
    pm = ProfileManager()
    asyncio.run(pm.open_manual_login(
        profile_name=args.profile,
        site_or_url=args.site,
        wait_seconds=args.wait,
    ))

def cmd_check_logins(args):
    """Check stored session cookies and login states."""
    pm = ProfileManager()
    results = asyncio.run(pm.inspect_profile_logins(args.profile))
    print("\n" + "=" * 55)
    print(f"PROFILE LOGIN REPORT: {results.get('profile')}")
    print("=" * 55)
    services = results.get("services", {})
    for k, v in services.items():
        status = "LOGGED IN  [Y]" if v.get("logged_in") else "NOT LOGGED IN [N]"
        print(f"  {v.get('name'):<14}: {status:<20} ({v.get('cookie_count')} cookies)")
    print(f"  Total Cookies: {results.get('total_cookies')}")
    print("=" * 55 + "\n")

def cmd_apply_csv(args):
    """Run batch job applications from a CSV file."""
    async def _apply():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()

        profile_data = dict(DEFAULT_CANDIDATE_PROFILE)
        profile_json = args.profile_json or "candidate_profile.json"
        if profile_json and os.path.exists(profile_json):
            with open(profile_json, "r") as f:
                profile_data.update(json.load(f))

        if args.resume:
            profile_data["resume_path"] = args.resume

        applier = JobApplier(
            engine=engine,
            candidate_profile=profile_data,
            safe_mode=args.safe,
            output_csv=args.output,
        )
        try:
            results = await applier.run_batch_from_csv(args.csv, max_jobs=args.limit)
            print(f"\nCompleted batch applications. Processed {len(results)} jobs.")
            print(f"Report saved to: {args.output}\n")
        finally:
            await engine.close()

    asyncio.run(_apply())

def cmd_find_pdf(args):
    """Search the internet and download PDF documents."""
    async def _find():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        hunter = PDFHunter(engine=engine)
        try:
            results = await hunter.search_and_download(
                query=args.query,
                max_results=args.limit,
                search_engine=args.search_engine,
            )
            print("\n" + "=" * 60)
            print(f"PDF HUNT RESULTS FOR: '{args.query}'")
            print("=" * 60)
            for idx, r in enumerate(results, 1):
                print(f"[{idx}] {r.get('filename')}")
                print(f"    Pages: {r.get('pages')} | Size: {r.get('file_size_kb')} KB")
                print(f"    Local Path: {r.get('local_path')}")
                print(f"    Source: {r.get('source_url')}")
            print("=" * 60 + "\n")
        finally:
            await engine.close()

    asyncio.run(_find())

def cmd_task(args):
    """Execute a general autonomous AI browser task."""
    async def _task():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        llm = LLMClient(model=args.model)
        agent = GeneralAgent(engine=engine, llm=llm, max_steps=args.steps)
        try:
            result = await agent.run(args.prompt)
            print("\n" + "=" * 55)
            print("TASK EXECUTION SUMMARY")
            print("=" * 55)
            print(f"Status: {result.get('status')}")
            print(f"Steps Taken: {result.get('steps')}")
            print(f"Summary: {result.get('summary')}")
            print(f"Final URL: {result.get('final_url')}")
            print("=" * 55 + "\n")
        finally:
            await engine.close()

    asyncio.run(_task())

def cmd_mcp(args):
    """Start the Obscura-compatible MCP stdio server."""
    from mcp_server.server import ShadowBrowserMCPServer
    server = ShadowBrowserMCPServer(profile_name=args.profile, headless=args.headless)
    asyncio.run(server.run_stdio())


# ──────────────────────────────────────────────────────────────────────────────
#  Freelance commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_freelance_signup(args):
    """Sign up on a specific freelance platform."""
    from agents.freelance_agent import FreelanceAgent, load_platforms, get_platform_key
    from core.freelance_profile import FreelanceProfile

    async def _signup():
        platforms = load_platforms()
        # Find the requested platform by name or domain key
        target = None
        for p in platforms:
            key = get_platform_key(p)
            if args.platform.lower() in (key, p.get("name", "").lower()):
                target = p
                break
        if not target:
            print(f"Platform not found: {args.platform}")
            print("Available platforms (priority 1):")
            for p in load_platforms(priority_filter=1):
                print(f"  {p['name']} ({get_platform_key(p)})")
            return

        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        agent = FreelanceAgent(
            engine=engine,
            profile=FreelanceProfile.from_json(),
            safe_mode=not args.no_safe,
            headless=args.headless,
        )
        try:
            result = await agent.signup_platform(target)
            print(f"\nResult: {result['status']}")
            if result.get("error"):
                print(f"Error: {result['error']}")
            print("\nLog:")
            for line in agent.get_log():
                print(f"  {line}")
        finally:
            await engine.close()

    asyncio.run(_signup())

def cmd_freelance_signup_all(args):
    """Sign up on all freelance platforms of a given priority level."""
    from agents.freelance_agent import FreelanceAgent, load_platforms
    from core.freelance_profile import FreelanceProfile

    async def _signup_all():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        agent = FreelanceAgent(
            engine=engine,
            profile=FreelanceProfile.from_json(),
            safe_mode=not args.no_safe,
        )
        try:
            results = await agent.signup_all(
                priority=args.priority,
                skip_existing=not args.redo,
            )
            print(f"\nCompleted signup attempts on {len(results)} platforms.")
            summary = agent.get_summary()
            print(f"  Signed up:   {summary['signed_up']}")
            print(f"  Errors:      {summary['errors']}")
            print(f"  Status file: {FREELANCE_STATUS_JSON}\n")
        finally:
            await engine.close()

    asyncio.run(_signup_all())

def cmd_freelance_apply(args):
    """Search for freelance projects and apply."""
    from agents.freelance_agent import FreelanceAgent, load_platforms
    from core.freelance_profile import FreelanceProfile

    async def _apply():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        agent = FreelanceAgent(
            engine=engine,
            profile=FreelanceProfile.from_json(),
            safe_mode=not args.no_safe,
        )
        platform_list = [p.strip() for p in args.platforms.split(",")] if args.platforms else None
        try:
            results = await agent.search_and_apply(
                query=args.query,
                platforms=platform_list,
                max_per_platform=args.limit,
            )
            print(f"\nFound {len(results)} projects matching '{args.query}'")
            for r in results:
                print(f"  [{r['platform']}] {r['title']}")
                if r.get("url"):
                    print(f"    URL: {r['url']}")
        finally:
            await engine.close()

    asyncio.run(_apply())

def cmd_freelance_status(args):
    """Show current signup and profile status across all platforms."""
    from agents.freelance_agent import load_status, load_platforms, get_platform_key

    status = load_status()
    if not status:
        print("No signup attempts recorded yet.")
        print(f"Run: python main.py freelance-signup-all --priority 1")
        return

    print("\n" + "=" * 65)
    print("FREELANCE PLATFORM STATUS")
    print("=" * 65)
    print(f"{'Platform':<25} {'Signed Up':<12} {'Profile':<12} {'Status'}")
    print("-" * 65)
    for key, data in sorted(status.items()):
        signed = "Yes" if data.get("signed_up") else "No"
        profile = "Complete" if data.get("profile_complete") else "Pending"
        st = data.get("status", "pending")
        print(f"  {key:<23} {signed:<12} {profile:<12} {st}")
    print("=" * 65 + "\n")

def cmd_freelance_profile(args):
    """Preview the freelance profile that will be submitted to platforms."""
    from core.freelance_profile import FreelanceProfile

    p = FreelanceProfile.from_json()
    print("\n" + "=" * 65)
    print("FREELANCE PROFILE PREVIEW")
    print("=" * 65)
    print(f"Name:         {p.full_name}")
    print(f"Email:        {p.email}")
    print(f"Phone:        {p.phone}")
    print(f"Headline:     {p.headline}")
    print(f"Hourly Rate:  {p.get_hourly_rate_string()}")
    print(f"Availability: {p.availability}")
    print(f"Experience:   {p.years_of_experience} years")
    print(f"Skills:       {p.get_skills_string()}")
    print(f"LinkedIn:     {p.linkedin_url}")
    print(f"GitHub:       {p.github_url}")
    print(f"Resume:       {p.resume_path} ({'exists' if p.resume_path.exists() else 'MISSING'})")
    print(f"\nBio (short):\n{p.get_bio(long=False)}")
    print("=" * 65 + "\n")

def cmd_freelance_platforms(args):
    """List available freelance platforms from the database."""
    from agents.freelance_agent import load_platforms, get_platform_key

    platforms = load_platforms(
        priority_filter=args.priority,
        category_filter=args.category,
    )
    print(f"\nTotal platforms: {len(platforms)}")
    if args.priority:
        print(f"Filter: priority={args.priority}")
    if args.category:
        print(f"Filter: category={args.category}")
    print("\n" + "=" * 70)
    print(f"{'#':<4} {'Name':<25} {'Priority':<10} {'Category':<18} {'URL'}")
    print("-" * 70)
    for i, p in enumerate(platforms, 1):
        print(f"  {i:<3} {p['name']:<25} {p.get('priority', 'N/A'):<10} {p.get('category',''):<18} {p.get('url','')}")
    print("=" * 70 + "\n")


# ──────────────────────────────────────────────────────────────────────────────
#  CLI entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ShadowBrowser: AI-Controlled Stealth Browser with Persistent Profiles"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # web
    subparsers.add_parser("web", help="Launch Streamlit Web UI Dashboard")

    # graphify
    subparsers.add_parser("graphify", help="Rebuild Graphify AST knowledge graph")

    # graph-query
    p_gquery = subparsers.add_parser("graph-query", help="Query Graphify knowledge graph")
    p_gquery.add_argument("query", help="Symbol, class, or keyword to query")
    p_gquery.add_argument("--limit", type=int, default=10, help="Max nodes to return")

    # graph-benchmark
    subparsers.add_parser("graph-benchmark", help="Measure token savings using Graphify")

    # login
    p_login = subparsers.add_parser("login", help="Open Chrome to log into site and save session")
    p_login.add_argument("--site", default="linkedin", help="Target site or URL")
    p_login.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_login.add_argument("--wait", type=int, default=None)

    # check-logins
    p_check = subparsers.add_parser("check-logins", help="Inspect profile login cookies")
    p_check.add_argument("--profile", default=DEFAULT_PROFILE_NAME)

    # apply-csv
    p_apply = subparsers.add_parser("apply-csv", help="Automate job applications from CSV")
    p_apply.add_argument("--csv", required=True, help="Path to jobs CSV")
    p_apply.add_argument("--resume", default=str(RESUME_PATH), help="Path to resume PDF")
    p_apply.add_argument("--profile-json", default="candidate_profile.json")
    p_apply.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_apply.add_argument("--safe", action="store_true")
    p_apply.add_argument("--limit", type=int, default=None)
    p_apply.add_argument("--output", default="applied_jobs_report.csv")
    p_apply.add_argument("--headless", action="store_true", default=HEADLESS_MODE)

    # find-pdf
    p_pdf = subparsers.add_parser("find-pdf", help="Search internet and download PDFs")
    p_pdf.add_argument("query")
    p_pdf.add_argument("--limit", type=int, default=3)
    p_pdf.add_argument("--search-engine", default="duckduckgo", choices=["duckduckgo", "google", "bing"])
    p_pdf.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_pdf.add_argument("--headless", action="store_true", default=True)

    # task
    p_task = subparsers.add_parser("task", help="Run autonomous natural language web task")
    p_task.add_argument("prompt")
    p_task.add_argument("--steps", type=int, default=15)
    p_task.add_argument("--model", default=DEFAULT_MODEL)
    p_task.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_task.add_argument("--headless", action="store_true", default=HEADLESS_MODE)

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Run MCP JSON-RPC Server")
    p_mcp.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_mcp.add_argument("--headless", action="store_true", default=True)

    # freelance-signup
    p_fs = subparsers.add_parser("freelance-signup", help="Sign up on a specific freelance platform")
    p_fs.add_argument("--platform", required=True, help="Platform name or domain (e.g. upwork, fiverr)")
    p_fs.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_fs.add_argument("--headless", action="store_true", default=False)
    p_fs.add_argument("--no-safe", action="store_true", help="Disable safe mode (auto-submit)")

    # freelance-signup-all
    p_fsa = subparsers.add_parser("freelance-signup-all", help="Sign up on all priority platforms")
    p_fsa.add_argument("--priority", type=int, default=1, help="Priority level (1=top platforms)")
    p_fsa.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_fsa.add_argument("--headless", action="store_true", default=False)
    p_fsa.add_argument("--no-safe", action="store_true")
    p_fsa.add_argument("--redo", action="store_true", help="Re-attempt already signed-up platforms")

    # freelance-apply
    p_fa = subparsers.add_parser("freelance-apply", help="Search and apply to freelance projects")
    p_fa.add_argument("--query", required=True, help="Job search query (e.g. 'Python ETL pipeline')")
    p_fa.add_argument("--platforms", default=None, help="Comma-separated platform keys (default: all priority-1)")
    p_fa.add_argument("--limit", type=int, default=5, help="Max jobs per platform")
    p_fa.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    p_fa.add_argument("--headless", action="store_true", default=False)
    p_fa.add_argument("--no-safe", action="store_true")

    # freelance-status
    subparsers.add_parser("freelance-status", help="Show signup status across all platforms")

    # freelance-profile
    subparsers.add_parser("freelance-profile", help="Preview freelance profile from resume data")

    # freelance-platforms
    p_fp = subparsers.add_parser("freelance-platforms", help="List platforms from the database")
    p_fp.add_argument("--priority", type=int, default=None, help="Filter by priority (1, 2, 3)")
    p_fp.add_argument("--category", default=None, help="Filter by category (e.g. tech_dev, ai_ml_data)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "web": cmd_web,
        "graphify": cmd_graphify,
        "graph-query": cmd_graph_query,
        "graph-benchmark": cmd_graph_benchmark,
        "login": cmd_login,
        "check-logins": cmd_check_logins,
        "apply-csv": cmd_apply_csv,
        "find-pdf": cmd_find_pdf,
        "task": cmd_task,
        "mcp": cmd_mcp,
        "freelance-signup": cmd_freelance_signup,
        "freelance-signup-all": cmd_freelance_signup_all,
        "freelance-apply": cmd_freelance_apply,
        "freelance-status": cmd_freelance_status,
        "freelance-profile": cmd_freelance_profile,
        "freelance-platforms": cmd_freelance_platforms,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
