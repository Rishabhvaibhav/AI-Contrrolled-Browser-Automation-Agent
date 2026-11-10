import sys
import json
import logging
import asyncio
from typing import Dict, Any, Optional

from core.browser_engine import BrowserEngine
from core.dom_indexer import DOMIndexer
from core.profile_manager import ProfileManager
from agents.job_applier import JobApplier
from agents.pdf_hunter import PDFHunter

logger = logging.getLogger("ShadowBrowser.MCP")

class ShadowBrowserMCPServer:
    """
    Obscura-compatible Model Context Protocol (MCP) and JSON-RPC Server
    allowing external AI agents (Claude, Cursor, Antigravity) to drive ShadowBrowser.
    """

    def __init__(self, profile_name: str = "default", headless: bool = True):
        self.profile_name = profile_name
        self.headless = headless
        self.engine: Optional[BrowserEngine] = None

    async def initialize(self):
        """Initializes the underlying persistent browser engine."""
        if not self.engine:
            self.engine = BrowserEngine(profile_name=self.profile_name, headless=self.headless)
            await self.engine.launch()

    async def dispatch_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Routes MCP tool calls to appropriate browser methods."""
        await self.initialize()

        if tool_name == "browser_navigate":
            url = arguments.get("url", "")
            success = await self.engine.navigate(url)
            state = await DOMIndexer.get_interactive_state(self.engine.page)
            await DOMIndexer.remove_badges(self.engine.page)
            return {
                "success": success,
                "current_url": self.engine.page.url,
                "title": state.get("title", ""),
                "interactive_count": len(state.get("interactiveElements", [])),
            }

        elif tool_name == "browser_snapshot":
            state = await DOMIndexer.get_interactive_state(self.engine.page)
            formatted = DOMIndexer.format_elements_for_llm(state.get("interactiveElements", []))
            markdown = await DOMIndexer.get_page_markdown(self.engine.page)
            await DOMIndexer.remove_badges(self.engine.page)
            return {
                "url": self.engine.page.url,
                "title": state.get("title", ""),
                "interactive_elements": formatted,
                "page_text": markdown[:2500],
            }

        elif tool_name == "browser_click":
            idx = int(arguments.get("element_id", arguments.get("index", 1)))
            await DOMIndexer.get_interactive_state(self.engine.page)
            loc = await DOMIndexer.get_element_by_index(self.engine.page, idx)
            await DOMIndexer.remove_badges(self.engine.page)

            if loc:
                await loc.click()
                await asyncio.sleep(1.0)
                return {"success": True, "message": f"Clicked element [{idx}]"}
            return {"success": False, "error": f"Element [{idx}] not found"}

        elif tool_name == "browser_type":
            idx = int(arguments.get("element_id", arguments.get("index", 1)))
            text = str(arguments.get("text", ""))
            press_enter = arguments.get("press_enter", False)

            await DOMIndexer.get_interactive_state(self.engine.page)
            loc = await DOMIndexer.get_element_by_index(self.engine.page, idx)
            await DOMIndexer.remove_badges(self.engine.page)

            if loc:
                await loc.fill(text)
                if press_enter:
                    await self.engine.page.keyboard.press("Enter")
                await asyncio.sleep(0.5)
                return {"success": True, "message": f"Typed text into element [{idx}]"}
            return {"success": False, "error": f"Element [{idx}] not found"}

        elif tool_name == "browser_find_pdf":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 2))
            hunter = PDFHunter(self.engine)
            results = await hunter.search_and_download(query, max_results=limit)
            return {"success": True, "found_count": len(results), "downloads": results}

        elif tool_name == "browser_login_status":
            pm = ProfileManager()
            status = await pm.inspect_profile_logins(self.profile_name)
            return {"success": True, "profile": self.profile_name, "logins": status.get("services", {})}

        elif tool_name == "browser_close":
            if self.engine:
                await self.engine.close()
                self.engine = None
            return {"success": True, "message": "Browser closed and profile saved."}

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    async def run_stdio(self):
        """Runs standard MCP stdio loop for external client connections."""
        logger.info("ShadowBrowser MCP Server listening on stdio...")
        loop = asyncio.get_event_loop()

        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            try:
                req = json.loads(line)
                req_id = req.get("id")
                method = req.get("method")
                params = req.get("params", {})

                if method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [
                                {"name": "browser_navigate", "description": "Navigate to URL"},
                                {"name": "browser_snapshot", "description": "Extract interactive DOM elements and text"},
                                {"name": "browser_click", "description": "Click element by indexed badge ID"},
                                {"name": "browser_type", "description": "Type text into element by ID"},
                                {"name": "browser_find_pdf", "description": "Search internet and download PDF"},
                                {"name": "browser_login_status", "description": "Check LinkedIn/Naukri/Google login status"},
                                {"name": "browser_close", "description": "Save profile and close browser"},
                            ]
                        }
                    }
                elif method == "tools/call":
                    tool_name = params.get("name")
                    args = params.get("arguments", {})
                    tool_res = await self.dispatch_tool(tool_name, args)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(tool_res)}]}
                    }
                else:
                    response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}}
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
