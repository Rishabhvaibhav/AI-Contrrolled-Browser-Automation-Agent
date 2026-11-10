# ShadowBrowser

An autonomous, AI-controlled browser framework designed to replicate real Google Chrome behavior. ShadowBrowser maintains persistent user sessions across multiple services (such as LinkedIn, Naukri, Indeed, and Google), provides humanized interaction modeling to evade bot heuristics, automates batch job applications from CSV datasets, discovers and validates PDF documents web-wide, and natively integrates with the Alpme Gateway API and Graphify knowledge graphs for token efficiency..

---

## Architectural Principles

Standard automation setups (plain Playwright, Selenium, or Puppeteer) are readily flagged and invalidated by enterprise anti-bot defenses (Cloudflare, PerimeterX, LinkedIn, Naukri) due to three primary vectors:

1. Transient Contexts: Spawning fresh, unauthenticated browser instances with zero cookie history, empty caches, and clean local storage.
2. Fingerprint Indicators: Exposing automated flags (`navigator.webdriver = true`), atypical plugin sets, and Chrome DevTools Protocol (CDP) artifacts.
3. Machine-like Input: Executing linear mouse jumps and instantaneous keystroke sequences.

ShadowBrowser mitigates these vectors through the following architecture:

- Persistent Real Chrome Profiles: Operates directly against host Google Chrome binaries using a permanent `user_data_dir`. Cookies, tokens, indexedDB, and cache are preserved on disk between sessions. Logging into LinkedIn or Naukri once persists across all subsequent automated runs.
- Human Interaction Modeling: Mouse trajectories follow randomized cubic Bezier curves with micro-jitter and acceleration profiles. Keystrokes include variable inter-key delays (45ms to 140ms) and natural punctuation pauses.
- Dual-Mode Web Understanding:
  - Element Indexing (inspired by browser-use): Scans interactive DOM nodes and injects lightweight visual badges for precise element selection.
  - Structural Snapshotting (inspired by obscura): Generates clean markdown representations and provides a standard Model Context Protocol (MCP) server for external agent integration.
- Graphify Codebase Context: Employs tree-sitter AST extraction via Graphify to generate compact structural graphs (`graphify-out/graph.json`), reducing token overhead by up to 9.1x when feeding code context to LLMs.
- Alpme Gateway Integration: Targets `https://alpme.com/v1` via standard Bearer authorization, with automated exponential backoff and jitter for resilient execution during high-load periods.

---


## Capabilities

### 1. Batch Job Application Engine
- Ingests CSV files containing job URLs and role metadata.
- Operates under authenticated LinkedIn, Naukri, or corporate ATS sessions.
- Automatically identifies "Easy Apply", "Quick Apply", and standard submission entry points.
- Traverses multi-step application dialogs, maps candidate attributes (e.g. name, email, contact, experience, current CTC, notice period), and attaches `resume.pdf`.
- Supports a Safe Review mode to stage entries for user inspection prior to final submission.
- Emits execution status reports to `applied_jobs_report.csv`.

### 2. Internet-Wide PDF Discovery
- Searches academic repositories, technical indexes, and search engines using specialized operators (`filetype:pdf`).
- Evaluates candidate links, handles intermediate landing pages, and downloads binary streams.
- Validates PDF structure and integrity via `pypdf` (verifying `%PDF-` magic bytes, page volume, and metadata).
- Stores verified documents into `downloads/`.

### 3. Session and Profile Management
- Allows headful browser launching for manual authentication, OTP verification, and CAPTCHA handling.
- Inspects saved session cookies to report authentication status across target platforms.

### 4. Graphify Knowledge Graph
- Extracts deterministic AST representations of project classes, methods, and dependencies.
- Serves subgraphs to coding agents without requiring raw file dumps.

---

## Directory Structure

```text
ShadowBrowser/
|-- .env                     # Alpme API keys and runtime parameters
|-- .env.example             # Configuration template
|-- main.py                  # Primary CLI entrypoint
|-- requirements.txt         # Project dependencies
|-- candidate_profile.json   # Candidate application schema (Rishabh Vaibhav)
|-- sample_jobs.csv          # Sample job postings dataset
|-- resume.pdf               # Candidate resume for file upload workflows
|-- core/
|   |-- config.py            # Environment and runtime configuration
|   |-- browser_engine.py    # Persistent Chrome driver and anti-detection hooks
|   |-- profile_manager.py   # Profile lifecycle and interactive authentication
|   |-- dom_indexer.py       # DOM tree analyzer and badge annotator
|   |-- human_emulator.py    # Bezier mouse curve and typing simulation
|   |-- llm_client.py        # Alpme gateway client with retry policies
|   `-- graph_context.py     # Graphify knowledge graph query interface
|-- agents/
|   |-- base_agent.py        # Core observe-plan-act loop
|   |-- general_agent.py     # Autonomous goal-driven web agent
|   |-- job_applier.py       # Batch CSV job submission engine
|   `-- pdf_hunter.py        # Web-wide PDF hunter and validator
|-- mcp_server/
|   `-- server.py            # Model Context Protocol stdio server
|-- ui/
|   `-- app.py               # Streamlit web dashboard
|-- graphify-out/            # Generated AST graph, report, and visualizations
|-- profiles/                # Persistent Chrome user data storage
`-- downloads/               # Output directory for verified documents
```

---

## Configuration

Set configuration variables in `.env`:

```ini
# Alpme Gateway Configuration
ALPME_BASE_URL=https://alpme.com/v1
ALPME_API_KEY=your_alpme_api_key_here
ALPME_MODEL=gemini-3.8-flash

# Browser Engine Parameters
DEFAULT_PROFILE=default
HEADLESS=false
CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
SLOW_MO_MS=50
TIMEOUT_MS=30000
```

---

## Usage

### 1. Interactive Web Dashboard
Launches the Streamlit management interface:
```bash
python main.py web
```
The interface is available at `http://localhost:8501`.

### 2. Profile Authentication (One-Time Setup)
Opens a visible Google Chrome window to log in to target platforms. Cookies and authentication tokens are saved permanently to the profile directory.
```bash
# Log in to LinkedIn
python main.py login --site linkedin

# Log in to Naukri
python main.py login --site naukri

# Log in to a custom authentication endpoint
python main.py login --site https://accounts.google.com
```

### 3. Verify Active Logins
Inspects stored cookies and confirms whether authenticated sessions exist:
```bash
python main.py check-logins
```

### 4. Execute Job Applications from CSV
Processes a target CSV file and applies to each job posting:
```bash
# Safe mode: fills form and pauses before final submission
python main.py apply-csv --csv sample_jobs.csv --resume resume.pdf --safe

# Direct submission with job limit
python main.py apply-csv --csv sample_jobs.csv --resume resume.pdf --limit 5
```

### 5. Internet PDF Discovery
Finds, downloads, and validates documents matching a query:
```bash
python main.py find-pdf "Attention is all you need paper" --limit 2
```

### 6. General Autonomous Browsing Task
Dispatches an open-ended natural language goal:
```bash
python main.py task "Navigate to news.ycombinator.com and extract the title and link of the top story"
```

### 7. Graphify Code Intelligence & Token Optimization
Rebuilds the AST knowledge graph and queries subgraphs to minimize LLM token overhead:
```bash
# Re-extract codebase AST
python main.py graphify

# Query structural dependencies for a specific module
python main.py graph-query "JobApplier"

# Run token savings benchmark
python main.py graph-benchmark
```

### 8. Run Model Context Protocol (MCP) Server
Runs an Obscura-compatible stdio server for integration into Cursor, Claude Code, or Antigravity:
```bash
python main.py mcp
```

---

## Candidate Profile Reference

Automated applications reference `candidate_profile.json`. Example structure:

```json
{
  "first_name": "Rishabh",
  "last_name": "Vaibhav",
  "full_name": "Rishabh Vaibhav",
  "email": "rishabh.vaibhav.dev@gmail.com",
  "phone": "+91 9876543210",
  "city": "Bengaluru",
  "country": "India",
  "current_company": "Cloud Systems & AI Labs",
  "current_title": "Senior AI & Full Stack Engineer",
  "years_of_experience": "5",
  "notice_period_days": "30",
  "current_ctc": "24,00,000 INR",
  "expected_ctc": "35,00,000 INR",
  "linkedin_url": "https://www.linkedin.com/in/rishabh-vaibhav",
  "naukri_profile_url": "https://www.naukri.com/mnjuser/profile",
  "github_url": "https://github.com/rishabh-vaibhav",
  "resume_path": "resume.pdf",
  "work_authorization": "Yes",
  "sponsorship_required": "No"
}
```

---

## Technical Specifications

| Component | Technical Implementation |
| :--- | :--- |
| Driver Layer | Playwright with persistent Chromium/Chrome context pointing to local Chrome binary |
| Profile Persistence | Real Chrome `user_data_dir` preserving cookies, LevelDB storage, cache, and service workers |
| Automation Masking | `--disable-blink-features=AutomationControlled`, prototype patching of `navigator.webdriver`, realistic runtime object mocking |
| Cursor Simulation | Dynamic cubic Bezier calculation with randomized control points and sub-pixel micro-jitter |
| Input Simulation | Randomized keystroke intervals with heuristic pauses for punctuation characters |
| DOM Indexing | In-page JavaScript extraction labeling interactive nodes with visual coordinate badges |
| Code Intelligence | Graphify AST parsing across Python sources with 9.1x measured token reduction |
| Gateway Client | OpenAI-compatible SDK configured for `https://alpme.com/v1` with exponential backoff retry |
