# Graph Report - Github Project  (2026-11-11)

## Corpus Check
- 16 files · ~12,890 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .csv 1)

## Summary
- 247 nodes · 558 edges · 10 communities (7 shown, 3 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- JobApplier
- main.py
- BaseBrowserAgent
- BrowserEngine
- LLMClient
- Usage
- manifest.json
- GraphContext

## God Nodes (most connected - your core abstractions)
1. `BrowserEngine` - 39 edges
2. `JobApplier` - 23 edges
3. `LLMClient` - 18 edges
4. `PDFHunter` - 17 edges
5. `BaseBrowserAgent` - 16 edges
6. `GraphContext` - 15 edges
7. `ProfileManager` - 15 edges
8. `main()` - 13 edges
9. `DOMIndexer` - 13 edges
10. `ShadowBrowserMCPServer` - 12 edges

## Surprising Connections (you probably didn't know these)
- `BaseBrowserAgent` --uses--> `BrowserEngine`  [INFERRED]
  agents/base_agent.py → core/browser_engine.py
- `BaseBrowserAgent` --uses--> `LLMClient`  [INFERRED]
  agents/base_agent.py → core/llm_client.py
- `ShadowBrowserMCPServer` --uses--> `DOMIndexer`  [INFERRED]
  mcp_server/server.py → core/dom_indexer.py
- `ShadowBrowserMCPServer` --uses--> `PDFHunter`  [INFERRED]
  mcp_server/server.py → agents/pdf_hunter.py
- `ShadowBrowserMCPServer` --uses--> `BrowserEngine`  [INFERRED]
  mcp_server/server.py → core/browser_engine.py

## Import Cycles
- None detected.

## Communities (10 total, 3 thin omitted)

### Community 0 - "JobApplier"
Cohesion: 0.08
Nodes (4): JobApplier, cmd_apply_csv(), _apply(), run_jobs()

### Community 1 - "main.py"
Cohesion: 0.11
Nodes (10): BaseBrowserAgent, DOMIndexer, HumanEmulator, ProfileManager, cmd_check_logins(), cmd_graph_benchmark(), cmd_login(), cmd_mcp() (+2 more)

### Community 3 - "BrowserEngine"
Cohesion: 0.08
Nodes (5): PDFHunter, BrowserEngine, cmd_find_pdf(), _find(), run_hunt()

### Community 5 - "LLMClient"
Cohesion: 0.13
Nodes (5): GeneralAgent, LLMClient, cmd_task(), _task(), run_general_agent()

### Community 6 - "Usage"
Cohesion: 0.10
Nodes (20): 1. Batch Job Application Engine, 1. Interactive Web Dashboard, 2. Internet-Wide PDF Discovery, 2. Profile Authentication (One-Time Setup), 3. Session and Profile Management, 3. Verify Active Logins, 4. Execute Job Applications from CSV, 4. Graphify Knowledge Graph (+12 more)

### Community 7 - "manifest.json"
Cohesion: 0.50
Nodes (3): manifest_version, name, version

### Community 8 - "GraphContext"
Cohesion: 0.15
Nodes (3): GraphContext, cmd_graph_query(), cmd_graphify()

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BrowserEngine` connect `BrowserEngine` to `JobApplier`, `main.py`, `BaseBrowserAgent`, `LLMClient`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `BrowserEngine` (e.g. with `BaseBrowserAgent` and `PDFHunter`) actually correct?**
  _`BrowserEngine` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `JobApplier` be split into smaller, more focused modules?**
  _Cohesion score 0.0753045404208195 - nodes in this community are weakly interconnected._
- **Why does `JobApplier` connect `JobApplier` to `main.py`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `PDFHunter` (e.g. with `BrowserEngine` and `ShadowBrowserMCPServer`) actually correct?**
  _`PDFHunter` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10839598997493734 - nodes in this community are weakly interconnected._
- **Why does `GraphContext` connect `GraphContext` to `main.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._