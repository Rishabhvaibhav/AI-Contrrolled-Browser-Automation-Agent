import os
import sys
import argparse
import asyncio
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
)
from core.browser_engine import BrowserEngine
from core.profile_manager import ProfileManager
from core.llm_client import LLMClient
from core.graph_context import GraphContext
from agents.general_agent import GeneralAgent
from agents.job_applier import JobApplier, DEFAULT_CANDIDATE_PROFILE
from agents.pdf_hunter import PDFHunter

def cmd_web(args):
    """Launches the Streamlit Web Dashboard."""
    import subprocess
    app_path = BASE_DIR / "ui" / "app.py"
    logger.info(f"Starting ShadowBrowser Web Dashboard: {app_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])

def cmd_graphify(args):
    """Updates the codebase knowledge graph with Graphify to optimize LLM tokens."""
    import subprocess
    logger.info("Executing Graphify AST extraction on codebase...")
    res = subprocess.run(["graphify", "update", "."], capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    gc = GraphContext()
    print(f"Graphify rebuild complete! Loaded {len(gc.nodes)} nodes and {len(gc.edges)} edges.")

def cmd_graph_query(args):
    """Queries the Graphify knowledge graph for token-optimized context."""
    gc = GraphContext()
    context = gc.get_token_optimized_context(args.query, max_nodes=args.limit)
    print("\n" + "=" * 60)
    print("GRAPHIFY TOKEN-OPTIMIZED CONTEXT")
    print("=" * 60)
    print(context)
    print("=" * 60 + "\n")

def cmd_graph_benchmark(args):
    """Runs Graphify benchmark showing token reduction percentage."""
    import subprocess
    res = subprocess.run(["graphify", "benchmark"], capture_output=True, text=True)
    print(res.stdout)

def cmd_login(args):
    """Opens visible real Chrome to manually log into a site and save profile."""
    pm = ProfileManager()
    asyncio.run(pm.open_manual_login(
        profile_name=args.profile,
        site_or_url=args.site,
        wait_seconds=args.wait,
    ))

def cmd_check_logins(args):
    """Checks stored session cookies and login states."""
    pm = ProfileManager()
    results = asyncio.run(pm.inspect_profile_logins(args.profile))
    print("\n" + "=" * 55)
    print(f"🔍 PROFILE LOGIN REPORT: {results.get('profile')}")
    print("=" * 55)
    services = results.get("services", {})
    for k, v in services.items():
        status = "LOGGED IN  [✓]" if v.get("logged_in") else "NOT LOGGED IN [✗]"
        print(f"• {v.get('name'):<12}: {status:<18} ({v.get('cookie_count')} cookies)")
    print(f"Total Cookies: {results.get('total_cookies')}")
    print("=" * 55 + "\n")

def cmd_apply_csv(args):
    """Runs batch job applications from a CSV file."""
    async def _apply():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        
        # Load candidate profile
        profile_data = dict(DEFAULT_CANDIDATE_PROFILE)
        if args.profile_json and os.path.exists(args.profile_json):
            import json
            with open(args.profile_json, "r") as f:
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
            print(f"\n✅ Completed batch applications. Processed {len(results)} jobs.")
            print(f"📊 Detailed report saved to: {args.output}\n")
        finally:
            await engine.close()

    asyncio.run(_apply())

def cmd_find_pdf(args):
    """Searches internet and acquires PDF documents."""
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
            print(f"📄 PDF HUNT RESULTS FOR: '{args.query}'")
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
    """Executes general autonomous AI browser task."""
    async def _task():
        engine = BrowserEngine(profile_name=args.profile, headless=args.headless)
        await engine.launch()
        llm = LLMClient(model=args.model)
        agent = GeneralAgent(engine=engine, llm=llm, max_steps=args.steps)
        try:
            result = await agent.run(args.prompt)
            print("\n" + "=" * 55)
            print("🤖 TASK EXECUTION SUMMARY")
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
    """Starts Obscura-compatible MCP stdio server."""
    from mcp_server.server import ShadowBrowserMCPServer
    server = ShadowBrowserMCPServer(profile_name=args.profile, headless=args.headless)
    asyncio.run(server.run_stdio())

def main():
    parser = argparse.ArgumentParser(
        description="ShadowBrowser: AI-Controlled Stealth Browser with Persistent Profiles"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: web
    subparsers.add_parser("web", help="Launch Streamlit Web UI Dashboard")

    # Command: graphify
    subparsers.add_parser("graphify", help="Rebuild Graphify AST knowledge graph for LLM token reduction")

    # Command: graph-query
    p_gquery = subparsers.add_parser("graph-query", help="Query Graphify knowledge graph without full source loading")
    p_gquery.add_argument("query", help="Symbol, class, or keyword to query")
    p_gquery.add_argument("--limit", type=int, default=10, help="Max nodes to return")

    # Command: graph-benchmark
    subparsers.add_parser("graph-benchmark", help="Measure token savings using Graphify knowledge graph")

    # Command: login
    p_login = subparsers.add_parser("login", help="Open real Chrome to log into site and save session")
    p_login.add_argument("--site", default="linkedin", help="Target site (linkedin, naukri, indeed, google, github) or URL")
    p_login.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Profile folder name")
    p_login.add_argument("--wait", type=int, default=None, help="Optional wait duration in seconds before closing")

    # Command: check-logins
    p_check = subparsers.add_parser("check-logins", help="Inspect profile login cookies")
    p_check.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Profile folder name")

    # Command: apply-csv
    p_apply = subparsers.add_parser("apply-csv", help="Automate job applications from a CSV file")
    p_apply.add_argument("--csv", required=True, help="Path to jobs CSV")
    p_apply.add_argument("--resume", default="resume.pdf", help="Path to candidate resume PDF")
    p_apply.add_argument("--profile-json", default="candidate_profile.json", help="Path to candidate profile JSON")
    p_apply.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Browser profile name")
    p_apply.add_argument("--safe", action="store_true", help="Safe mode: pause before final submit")
    p_apply.add_argument("--limit", type=int, default=None, help="Max jobs to process")
    p_apply.add_argument("--output", default="applied_jobs_report.csv", help="Output results CSV")
    p_apply.add_argument("--headless", action="store_true", default=HEADLESS_MODE, help="Run headless")

    # Command: find-pdf
    p_pdf = subparsers.add_parser("find-pdf", help="Search the internet and download target PDF")
    p_pdf.add_argument("query", help="Document title or search query")
    p_pdf.add_argument("--limit", type=int, default=3, help="Max PDFs to download")
    p_pdf.add_argument("--search-engine", default="duckduckgo", choices=["duckduckgo", "google", "bing"])
    p_pdf.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Browser profile name")
    p_pdf.add_argument("--headless", action="store_true", default=True, help="Run headless")

    # Command: task
    p_task = subparsers.add_parser("task", help="Run autonomous natural language web task")
    p_task.add_argument("prompt", help="Natural language objective")
    p_task.add_argument("--steps", type=int, default=15, help="Max execution steps")
    p_task.add_argument("--model", default=DEFAULT_MODEL, help="Alpme model name")
    p_task.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Browser profile name")
    p_task.add_argument("--headless", action="store_true", default=HEADLESS_MODE, help="Run headless")

    # Command: mcp
    p_mcp = subparsers.add_parser("mcp", help="Run Obscura-compatible MCP JSON-RPC Server")
    p_mcp.add_argument("--profile", default=DEFAULT_PROFILE_NAME, help="Browser profile name")
    p_mcp.add_argument("--headless", action="store_true", default=True, help="Run headless")

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
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
