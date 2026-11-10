# ShadowBrowser

An autonomous, AI-controlled browser framework designed to replicate authentic Google Chrome behavior. ShadowBrowser maintains persistent user sessions across multiple services (such as LinkedIn, Naukri, Indeed, Upwork, and Google), provides humanized interaction modeling (Bézier curves, micro-jitter, typing cadence with typo simulation) to evade modern bot heuristics, automates batch job applications from CSV datasets, discovers and validates PDF documents web-wide, executes end-to-end freelance platform onboarding with autonomous 2FA/OTP resolution via Gmail, and natively integrates with the Alpme Gateway API and Graphify knowledge graphs for token efficiency.

---

## Architectural Principles

Standard automation setups (plain Playwright, Selenium, or Puppeteer) are readily flagged and invalidated by enterprise anti-bot defenses (Cloudflare, PerimeterX, LinkedIn, Naukri, Kasada) due to three primary vectors:

1. **Transient Contexts**: Spawning fresh, unauthenticated browser instances with zero cookie history, empty caches, and clean local storage.
2. **Fingerprint Indicators**: Exposing automated flags (`navigator.webdriver = true`), atypical plugin sets, and Chrome DevTools Protocol (CDP) artifacts.
3. **Machine-like Input**: Executing linear mouse jumps and instantaneous keystroke sequences.

ShadowBrowser mitigates these vectors through the following architecture:

- **Persistent Real Chrome Profiles**: Operates directly against host Google Chrome binaries using a permanent `user_data_dir`. Cookies, tokens, IndexedDB, and cache are preserved on disk between sessions. Logging into LinkedIn, Naukri, or Google once persists across all subsequent automated runs.
- **Human Interaction Modeling v2**:
  - *Dynamic Bézier Trajectories*: Mouse movements calculate cubic curves with randomized control points, micro-tremor, Gaussian overshoot, and variable velocity acceleration.
  - *Natural Typing Cadence*: Simulated keystrokes feature variable delay intervals (45ms to 140ms), burst typing, natural pauses on punctuation, and occasional realistic typo simulation with backspace corrections.
  - *Accelerated Smooth Scrolling*: Sine-eased scroll increments emulate real trackpad and mouse-wheel inertia.
  - *Idle Cursor Drift*: Simulates human micro-wandering while pages load or during LLM thinking cycles.
- **Dual-Mode Web Understanding**:
  - *Element Indexing (inspired by browser-use)*: Scans interactive DOM nodes and injects lightweight visual coordinate badges for precise zero-hallucination agent actions.
  - *Structural Snapshotting (inspired by obscura)*: Generates clean markdown representations and provides a standard Model Context Protocol (MCP) server for external agent integration.
- **Autonomous 2FA & OTP Extraction**: Resolves verification codes automatically via high-speed IMAP protocol (using Gmail App Passwords) or falls back to an in-browser Gmail tab within the authenticated persistent profile.
- **Graphify Codebase Context**: Employs tree-sitter AST extraction via Graphify to generate compact structural graphs (`graphify-out/graph.json`), reducing LLM token consumption by 9–12x compared to loading raw files.
- **Alpme Gateway Integration**: Native integration with `https://alpme.com/v1` via standard Bearer authorization, with automated exponential backoff and jitter for resilient execution during high-load periods.

---

## Capabilities

### 1. Batch Job Application Engine
- Ingests CSV files containing job URLs and role metadata.
- Operates under authenticated LinkedIn, Naukri, or corporate ATS sessions.
- Automatically identifies "Easy Apply", "Quick Apply", and standard submission entry points.
- Traverses multi-step application dialogs, maps candidate attributes (e.g. name, email, contact, experience, current CTC, notice period), and attaches `Resume.pdf`.
- Supports a **Safe Mode** to pre-fill forms and pause for user confirmation prior to final submission.
- Emits execution status reports to `applied_jobs_report.csv`.

### 2. Autonomous Freelance Platform Agent
- Automated multi-platform onboarding and profile setup across prioritized freelance networks (Upwork, Fiverr, Toptal, Freelancer, Contra, Wellfound, PeoplePerHour, Guru, etc.).
- Prioritized platform catalog (`freelance_platforms.json`) categorizing sites by domain (Tech & Development, AI/ML & Data Engineering, General).
- Automated proposal dispatch: searches matching freelance gigs, customizes proposal bios from `candidate_profile.json`, and applies with configured hourly rates ($35–$75/hr).
- Maintains a persistent status ledger (`freelance_signup_status.json`) tracking onboarding stages, verification status, and applied gig counts.

### 3. Automated 2FA & OTP Resolution
- **IMAP Reader (Primary)**: Direct SSL connection to `imap.gmail.com` to scan incoming emails for 4- to 8-digit verification codes, security PINs, and magic links within seconds.
- **Browser Fallback**: If IMAP credentials are not configured, opens an ephemeral tab to Gmail within the active persistent profile (leveraging pre-authenticated session cookies) to extract codes from the UI.

### 4. Internet-Wide PDF Discovery
- Searches academic repositories, technical indexes, and search engines using specialized operators (`filetype:pdf`).
- Evaluates candidate links, handles intermediate landing pages, and downloads binary streams.
- Validates PDF structure and integrity via `pypdf` (verifying `%PDF-` magic bytes, page volume, and metadata).
- Stores verified documents into `downloads/`.

### 5. Interactive Web Dashboard & Freelance Hub
- Streamlit-powered dashboard (`python main.py web`) with dark-mode metric cards and status badges.
- **Dedicated Tabs**:
  1. *Job Applier*: CSV uploads, real-time application logs, and candidate mapping.
  2. *PDF Hunter*: Document search, verification, and file download management.
  3. *Autonomous Agent*: Open-ended natural language browser control.
  4. *Profile & Session Manager*: Headful login triggers and cookie status inspection.
  5. *Freelance Hub*: Platform catalog inspection, one-click onboarding, and bio previews.
  6. *Graphify Code Intelligence*: Force-directed graph explorer and AST context extraction.
  7. *Settings*: Alpme gateway parameters, candidate JSON inspection, and directory audits.

### 6. Graphify Code Intelligence & Token Optimization
- Extracts deterministic AST representations of project classes, methods, and dependencies.
- Serves subgraphs to coding agents without requiring raw file dumps.

---

## Directory Structure

```text
ShadowBrowser/
|-- .env                     # Alpme API keys, Gmail credentials, and browser parameters
|-- .env.example             # Configuration template
|-- .gitignore               # Strict exclusion rules for .env, profiles/, and data/
|-- main.py                  # Primary CLI entrypoint with subcommands
|-- requirements.txt         # Project dependencies
|-- candidate_profile.json   # Candidate profile schema (Rishabh Vaibhav)
|-- sample_jobs.csv          # Sample job postings dataset
|-- Resume.pdf               # Candidate resume for automated file uploads
|-- core/
|   |-- config.py            # Environment, workspace paths, and runtime settings
|   |-- browser_engine.py    # Persistent Chrome driver and anti-detection hooks
|   |-- profile_manager.py   # Profile lifecycle and interactive authentication
|   |-- dom_indexer.py       # DOM tree analyzer and badge annotator
|   |-- human_emulator.py    # Bézier curves, micro-jitter, and typing cadence v2
|   |-- llm_client.py        # Alpme gateway client with retry policies
|   |-- freelance_profile.py # Dynamic freelance bio and rate builder
|   `-- graph_context.py     # Graphify knowledge graph query interface
|-- agents/
|   |-- base_agent.py        # Core observe-plan-act loop
|   |-- general_agent.py     # Autonomous goal-driven web agent
|   |-- job_applier.py       # Batch CSV job submission engine
|   |-- pdf_hunter.py        # Web-wide PDF hunter and validator
|   |-- freelance_agent.py   # Freelance platform onboarding and proposal dispatcher
|   `-- gmail_otp_reader.py  # IMAP and browser-based 2FA/OTP code extractor
|-- mcp_server/
|   `-- server.py            # Model Context Protocol stdio server
|-- ui/
|   `-- app.py               # Streamlit web dashboard with Freelance Hub
|-- graphify-out/            # Generated AST graph, report, and visualizations
|-- profiles/                # Persistent Chrome user data storage (git-ignored)
`-- downloads/               # Output directory for verified documents
```

---

## Configuration

Set configuration variables in `.env`:

```ini
# Alpme Gateway Configuration
ALPME_BASE_URL=https://alpme.com/v1
ALPME_API_KEY=your_alpme_api_key_here
ALPME_MODEL=gemini-2.5-flash

# Fallback LLM (Optional)
# OPENAI_API_KEY=
# OPENAI_BASE_URL=https://api.openai.com/v1

# Browser Settings
DEFAULT_PROFILE=default
HEADLESS=false
CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
SLOW_MO_MS=50
TIMEOUT_MS=30000

# Gmail 2FA / OTP Verification (Optional but Recommended)
GMAIL_ADDRESS=rishabhvaibhav7@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# Freelance Defaults
FREELANCE_HOURLY_RATE=50
```

---

## Usage

### 1. Interactive Web Dashboard
Launches the full Streamlit management interface:
```bash
python main.py web
```
The interface is available at `http://localhost:8501`.

### 2. Profile Authentication (One-Time Setup)
Opens a visible Google Chrome window to log in to target platforms. Cookies and authentication tokens are saved permanently to the profile directory:
```bash
# Log in to LinkedIn
python main.py login --site linkedin

# Log in to Naukri
python main.py login --site naukri

# Log in to Google / Gmail
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
python main.py apply-csv --csv sample_jobs.csv --resume Resume.pdf --safe

# Direct submission with job limit
python main.py apply-csv --csv sample_jobs.csv --resume Resume.pdf --limit 5
```

### 5. Freelance Platform Automation
Manage freelance platform signups, inspect profiles, and apply for gigs:
```bash
# Preview dynamic freelance profile generated from candidate data
python main.py freelance-profile

# View platform database categorized by priority
python main.py freelance-platforms --priority 1

# Check current signup and verification status across platforms
python main.py freelance-status

# Sign up on a specific platform (e.g. Upwork)
python main.py freelance-signup --platform upwork

# Onboard onto all Priority 1 freelance platforms
python main.py freelance-signup-all --priority 1

# Search and apply to freelance gigs/projects
python main.py freelance-apply --query "Python ETL pipeline" --limit 5
```

### 6. Internet PDF Discovery
Finds, downloads, and validates documents matching a query:
```bash
python main.py find-pdf "Attention is all you need paper" --limit 2
```

### 7. General Autonomous Browsing Task
Dispatches an open-ended natural language goal:
```bash
python main.py task "Navigate to news.ycombinator.com and extract the title and link of the top story"
```

### 8. Graphify Code Intelligence & Token Optimization
Rebuilds the AST knowledge graph and queries subgraphs to minimize LLM token overhead:
```bash
# Re-extract codebase AST
python main.py graphify

# Query structural dependencies for a specific module
python main.py graph-query "JobApplier"

# Run token savings benchmark
python main.py graph-benchmark
```

### 9. Run Model Context Protocol (MCP) Server
Runs a stdio server for external agent environments (Cursor, Claude Code, Antigravity):
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
  "email": "rishabhvaibhav7@gmail.com",
  "phone": "+91 7061864929",
  "city": "Bengaluru",
  "country": "India",
  "current_company": "Zocket Technologies",
  "current_title": "Senior Data & AI Engineer",
  "years_of_experience": "4",
  "notice_period_days": "0",
  "current_ctc": "18,00,000 INR",
  "expected_ctc": "28,00,000 INR",
  "linkedin_url": "https://www.linkedin.com/in/rishabh-vaibhav",
  "naukri_profile_url": "https://www.naukri.com/mnjuser/profile",
  "github_url": "https://github.com/rishabhvaibhav",
  "portfolio_url": "https://rishabhvaibhav.dev",
  "resume_path": "Resume.pdf",
  "work_authorization": "Yes",
  "sponsorship_required": "No",
  "summary": "Data Engineer and Gen AI Developer with 4 years of experience building production-grade ETL pipelines, RAG/LLM workflows, and multi-agent automation systems.",
  "headline": "Senior AI & Data Engineer | RAG Pipelines | LLM Integration | Python | Playwright | FastAPI",
  "skills": [
    "Python", "PySpark", "SQL", "FastAPI", "LangChain", "LangGraph",
    "Azure", "AWS", "GCP", "ETL Pipelines", "RAG", "LLM Integration", "Playwright"
  ],
  "hourly_rate_usd": 50,
  "hourly_rate_range_usd": [35, 75],
  "hourly_rate_inr": 4150,
  "preferred_work_type": ["remote", "contract", "freelance"],
  "availability": "Immediate",
  "notable_clients": ["Google", "AuditBoard", "Bank of America", "Airbus"]
}
```

---

## Technical Specifications

| Component | Technical Implementation |
| :--- | :--- |
| **Driver Layer** | Playwright with persistent Chromium/Chrome context pointing to local Chrome binary |
| **Profile Persistence** | Real Chrome `user_data_dir` preserving cookies, LevelDB storage, cache, and service workers |
| **Anti-Bot Stealth** | `--disable-blink-features=AutomationControlled`, prototype patching of `navigator.webdriver`, realistic runtime object mocking |
| **Human Emulation v2** | Dynamic cubic Bézier paths, Gaussian overshoot, micro-tremor, keystroke intervals with typo burst correction, accelerated smooth scrolling, and idle cursor wander |
| **Freelance Automation** | Autonomous platform onboarding, bio and proposal customization, status tracking ledger, and rate conversion |
| **2FA / OTP Extraction** | High-speed direct IMAP mail reader with regex pattern matching; fallback to persistent browser tab inside Google session |
| **DOM Indexing** | In-page JavaScript extraction labeling interactive nodes with visual coordinate badges |
| **Code Intelligence** | Graphify AST parsing across Python sources with 9–12x measured token reduction |
| **Gateway Client** | OpenAI-compatible SDK configured for `https://alpme.com/v1` with exponential backoff retry |
