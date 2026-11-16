# SPEC2RTL — Complete Project Handoff Document

> **Purpose:** This document provides everything a new AI coding agent needs to continue frontend development on SPEC2RTL without re-reading the entire codebase. It covers frontend architecture, backend pipeline, API contracts, known gaps, and recommended next steps.
>
> **Generated:** 2026-11-10 | **Status:** Inspection only — no project files were modified.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Pipeline Architecture](#4-backend-pipeline-architecture)
5. [API Contracts](#5-api-contracts)
6. [Frontend–Backend Data Flow](#6-frontendfbackend-data-flow)
7. [Agent-by-Agent Frontend Coverage](#7-agent-by-agent-frontend-coverage)
8. [Design System](#8-design-system)
9. [State Management](#9-state-management)
10. [Known Gaps & Mismatches](#10-known-gaps--mismatches)
11. [Artifact Storage & File Naming](#11-artifact-storage--file-naming)
12. [Environment & Dev Setup](#12-environment--dev-setup)
13. [Test Suite Summary](#13-test-suite-summary)
14. [Recommended Next Steps for Frontend Development](#14-recommended-next-steps-for-frontend-development)

---

## 1. Project Overview

SPEC2RTL is a multi-agent AI pipeline that converts hardware specification documents (PDF or DOCX) into synthesisable Register-Transfer Level (RTL) Verilog code.

### Pipeline Stage Order (Backend)

```
1. Understanding Agent      → understanding.json
2. Decomposer Agent         → decomposition.json
3. Description Agent        → descriptions.json
4. Pseudocode Agent         → pseudocode.json  (+  pseudocode_validation.json)
5. RTL Generation Agent     → rtl_generation.json  (+  integrated_rtl.v, top_level_rtl.v)
6. RTL Verification Agent   → rtl_verification.json
7. Reflection Agent (cond.) → reflection.json  (only if RTL verification fails)
8. RTL Generation Agent (retry, up to 2 times)
9. RTL Verification Agent (retry)
```

> [!IMPORTANT]
> Description Verification **has been removed** from the main pipeline. `verify_description()` is never called in `src/pipeline.py`. The `VerificationView` on the frontend currently tries to display description verification data, which is a known mismatch — see §10.

---

## 2. Repository Structure

```
SPEC2RTL/
├── api/
│   ├── main.py                     # FastAPI app, CORS, router registration
│   ├── routes/
│   │   └── runs.py                 # All HTTP + SSE endpoints
│   ├── schemas/
│   │   └── runs.py                 # Pydantic API models
│   └── services/
│       └── runner.py               # RunManager, background thread, event bus
├── frontend/
│   ├── index.html                  # HTML entry; loads /src/main.jsx
│   ├── package.json                # React 18, react-router-dom 6, axios, lucide-react, tailwind
│   ├── tailwind.config.js          # Custom color palette + typography
│   ├── vite.config.js              # Port 5173; proxy /api → http://127.0.0.1:8000
│   ├── postcss.config.js
│   └── src/
│       ├── main.jsx                # ReactDOM.createRoot; BrowserRouter + RunProvider wrap App
│       ├── App.jsx                 # Routes: / → Dashboard, /results → Results, /history → History
│       ├── api.js                  # axios instance (baseURL: /api) + errorMessage()
│       ├── index.css               # Global CSS; custom @tailwind layers + .expand-panel animation
│       ├── context/
│       │   └── RunContext.jsx      # Global state: runs list, active run, outputs cache, SSE/poll
│       ├── pages/
│       │   ├── Dashboard.jsx       # Home: UploadPanel + RunSummary + AgentBoard
│       │   ├── Results.jsx         # Run selector dropdown + RunSummary + AgentBoard
│       │   └── History.jsx         # Paginated run list; download output files
│       ├── components/
│       │   ├── AgentBoard.jsx      # Accordion list of all 6 agents; expands to show output views
│       │   ├── UploadPanel.jsx     # Drag-and-drop / file picker; calls startRun()
│       │   ├── Sidebar.jsx         # Fixed nav sidebar: Dashboard / Pipeline Results / Run History
│       │   ├── RunSummary.jsx      # Progress bar + stats (components_described, verification_passed)
│       │   ├── StatusBadge.jsx     # Colour-coded pill for status strings
│       │   ├── CodeViewer.jsx      # Line-numbered pseudocode with syntax highlighting + copy/download
│       │   ├── JsonViewer.jsx      # Syntax-highlighted JSON viewer with copy + download link
│       │   └── SignalTable.jsx     # 4-column table: Name | Direction | Width | Description
│       ├── views/
│       │   ├── UnderstandingView.jsx   # Renders understanding.json
│       │   ├── DecompositionView.jsx   # Renders decomposition.json with interaction table
│       │   ├── DescriptionView.jsx     # Renders descriptions.json (accordion, SignalTable)
│       │   ├── VerificationView.jsx    # Renders verification.json (see §10 — mismatch)
│       │   ├── PseudocodeView.jsx      # Renders pseudocode.json + raw LLM artifact
│       │   └── RTLResultsView.jsx      # Renders rtl_generation.json (component explorer, RTL code)
│       └── lib/
│           ├── format.js           # AGENTS list, stageProgress(), asList(), asText(), formatTime()
│           └── highlight.js        # highlightJson() + highlightPseudocode() (syntax colouring)
├── src/
│   ├── pipeline.py                 # run_pipeline() — full 9-step execution
│   ├── schemas.py                  # All Pydantic models
│   ├── experimental_rtl_generation.py
│   ├── llm/
│   │   └── llm.py                  # Gemini LLM wrapper
│   └── agents/
│       ├── understanding.py
│       ├── decomposer.py
│       ├── description.py
│       ├── pseudocode.py
│       ├── validate_pseudocode.py
│       ├── rtl_generation.py
│       ├── verification.py         # verify_rtl() + (unused) verify_description()
│       └── reflection.py           # reflect_on_rtl()
├── outputs/
│   └── runs/
│       └── {run_id}/               # Per-run artifact directory
├── tests/                          # Pytest test suite (115 tests, all pass)
├── test_validate_pseudocode.py
├── test_converter_and_simulator.py
├── .env                            # GEMINI_API_KEY (never commit)
└── requirements.txt
```

---

## 3. Frontend Architecture

### Entry Point Chain

```
index.html
  → /src/main.jsx
      → <BrowserRouter>
          → <RunProvider>   (context/RunContext.jsx)
              → <App />     (App.jsx)
                  → <Sidebar />
                  → <Routes>
                        / → <Dashboard />
                        /results → <Results />
                        /history → <History />
                        * → redirect to /
```

### Routing (react-router-dom v6)

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | `Dashboard.jsx` | Main page: upload, live progress, agent cards |
| `/results` | `Results.jsx` | Inspect any run's agent outputs in detail |
| `/history` | `History.jsx` | Browse all runs, download artifact files |
| `*` | `<Navigate to="/" />` | Catch-all redirect |

### Pages

**`Dashboard.jsx`**
- Imports: `AgentBoard`, `RunSummary`, `UploadPanel`, `useRuns`
- Layout: `UploadPanel` → `RunSummary` (if `active` exists) → "Agents" heading with link to `/results` → `AgentBoard`
- Tagline: *"Run the six-stage hardware specification pipeline…"* (hardcoded as 6 stages)

**`Results.jsx`**
- Imports: `AgentBoard`, `RunSummary`, `useRuns`, `formatTime`
- Has a `<select>` dropdown populated from `runs` array — allows switching between all stored runs
- Shows `RunSummary` + `AgentBoard` for the selected run

**`History.jsx`**
- Lists all runs from `runs` state; each row shows filename, status badge, start time, file type/size
- "Open" button calls `setActiveId(runId)` + navigates to `/results`
- "Outputs" button fetches `GET /api/runs/{run_id}/outputs` and renders clickable download links

---

## 4. Backend Pipeline Architecture

### `src/pipeline.py` — `run_pipeline(source_path, run_dir)`

The pipeline emits **progress events** (dicts) that the runner converts to SSE frames. It runs in a background thread.

```python
AGENT_ORDER = [
    "understanding",
    "decomposer",
    "description",
    "pseudocode",
    "rtl_generation",
    "rtl_verification",
    "reflection",
]
```

### Pipeline Execution Flow

```
1.  read_spec()                              → specification.txt
2.  understand_spec()                        → understanding.json
3.  decompose_spec()                         → decomposition.json
4.  describe_components()                    → descriptions.json
5.  generate_pseudocode()                    → pseudocode.json, pseudocode_raw.txt
6.  validate_pseudocode() [deterministic]    → pseudocode_validation.json
7.  _execute_rtl_generation_stage()          → rtl_generation.json, integrated_rtl.v
8.  verify_rtl()                             → rtl_verification.json
9.  while not valid and attempts < 2:
       reflect_on_rtl()                      → reflection.json, reflection_attempt_N.json
       _execute_rtl_generation_stage()       → rtl_generation_attempt_N.json
       verify_rtl()                          → rtl_verification_attempt_N.json
```

### `api/services/runner.py` — `RunManager`

- **`RUNS_DIR`** = `outputs/runs/`
- **`AGENT_FILES`** maps agent IDs to JSON filenames:
  ```python
  {
    "understanding": "understanding.json",
    "decomposer":    "decomposition.json",
    "description":   "descriptions.json",
    "verification":  "rtl_verification.json",   # NOTE: points to rtl_verification.json
    "pseudocode":    "pseudocode.json",
    "rtl_generation":"rtl_generation.json",
    "rtl_verification": "rtl_verification.json",
    "reflection":    "reflection.json",
  }
  ```
- **`DOWNLOADABLE`** set controls which files appear in `GET /runs/{id}/outputs` and can be downloaded
- Each run has a `metadata.json` containing the full run state: status, `agents` dict, `summary`
- **SSE** via `queue.Queue` per subscriber; heartbeat every 15 s; closes on `completed`/`failed`
- Background thread: `threading.Thread(target=_run_pipeline_thread, ...)`

### `src/agents/reflection.py` — `reflect_on_rtl()`

```python
def reflect_on_rtl(source_chunks, generated_rtl, verification) -> RTLReflectionOutput
```

- Takes: original spec text chunks, full RTL string, `VerificationResult` object
- Returns: `RTLReflectionOutput(needs_revision, feedback, component_feedback, reasoning)`
- Fallback: if LLM call fails → synthesises feedback from `verification.issues`
- Saves: `reflection.json`, `reflection_attempt_N.json` (N = attempt index)

### `src/agents/verification.py` — `verify_rtl()`

```python
def verify_rtl(source_chunks, rtl_generation_output) -> VerificationResult
def verify_description(source_chunks, decomposition, descriptions) -> list[VerificationResult]
```

- `verify_rtl()` → used in pipeline → saves `rtl_verification.json`
- `verify_description()` → **NOT called** in `pipeline.py` → legacy, retained for tests

---

## 5. API Contracts

### Base URL

Frontend: `baseURL: "/api"` (axios) → proxied by Vite to `http://127.0.0.1:8000`  
Backend: FastAPI at port 8000; routes under `/api`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Returns `{"status": "ok"}` |
| `POST` | `/api/runs` | Upload PDF/DOCX; starts pipeline; returns `{run_id, status}` |
| `GET` | `/api/runs` | List all runs; returns `{runs: [...]}` |
| `GET` | `/api/runs/{run_id}` | Full run metadata including `agents` dict and `summary` |
| `GET` | `/api/runs/{run_id}/events` | SSE stream of progress events |
| `GET` | `/api/runs/{run_id}/outputs` | Returns `{files: [...], artifacts: [...]}` |
| `GET` | `/api/runs/{run_id}/outputs/{agent_name}` | JSON output for a specific agent |
| `GET` | `/api/runs/{run_id}/download/{filename}` | Download a raw artifact file |

### Key Response Schemas

**`GET /api/runs/{run_id}` → `RunMetadata`**
```json
{
  "run_id": "abc123",
  "filename": "spec.pdf",
  "file_size": 102400,
  "file_type": ".pdf",
  "started_at": "2026-11-10T10:00:00Z",
  "finished_at": "2026-11-10T10:10:00Z",
  "status": "completed",
  "error": null,
  "failed_stage": null,
  "source": "api",
  "ingestion": "completed",
  "agents": {
    "understanding": {
      "status": "completed",
      "started_at": "...",
      "finished_at": "...",
      "error": null,
      "message": null,
      "components": []
    },
    "decomposer": { ... },
    "description": { ... },
    "pseudocode": {
      "status": "completed",
      "components": [
        { "name": "ALU", "status": "completed" }
      ]
    },
    "rtl_generation": {
      "status": "completed",
      "component_generation_status": "completed",
      "interface_validation_status": "passed",
      "integration_status": "completed",
      "compilation_status": "completed",
      "components": [
        {
          "name": "ALU",
          "generation_status": "completed",
          "interface_validation_status": "passed"
        }
      ]
    },
    "rtl_verification": { "status": "completed" },
    "reflection": { "status": "skipped" }
  },
  "summary": {
    "components_described": 4,
    "verification_passed": null,
    "verification_failed": null,
    "pseudocode_generation_status": "COMPLETED",
    "rtl_generation_status": "completed",
    "rtl_verification_valid": true,
    "reflection_needed": false
  }
}
```

> [!NOTE]
> `summary.verification_passed` and `summary.verification_failed` are populated from description verification (which is removed from the pipeline). They will be `null` in all recent runs. The frontend's `RunSummary.jsx` renders these as `—` when null.

**SSE Event Payload**
```json
{
  "type": "progress",
  "metadata": { /* same shape as RunMetadata */ }
}
```
Heartbeat: `{"type": "heartbeat"}` — no `metadata` field.

### Upload Rules (enforced by both frontend and backend)
- Allowed formats: `.pdf`, `.docx`
- Max file size: 20 MB
- One pipeline runs at a time per session (frontend disables button while `running`)

---

## 6. Frontend–Backend Data Flow

```
User drops PDF
  → UploadPanel.submit()
      → startRun(file)         [RunContext]
          → POST /api/runs     (FormData with file)
              ← {run_id, status: "running"}
          → setActiveId(run_id)
          → refreshRuns()      → GET /api/runs

activeId change
  → useEffect in RunContext
      → GET /api/runs/{activeId}      ← RunMetadata
      → if status === "running":
          → watchRun(runId)
              → EventSource /api/runs/{id}/events
                  ← SSE: {type, metadata}
                      → rememberActive(metadata)   updates `active` state
              → on SSE error → startPolling(runId) [2 s interval GET]

Agent expanded in AgentBoard
  → loadOutput(agentId, runId)        [RunContext]
      → GET /api/runs/{runId}/outputs/{agentId}
          ← JSON content of the agent's output file
      → stored in outputs[agentId] cache (keyed by runId + stamp)

  Special case: agentId === "verification"
      → also loads "description" and "decomposer" outputs
         (needed to show component names in VerificationView)
```

---

## 7. Agent-by-Agent Frontend Coverage

### Agent 1 — Understanding Agent ✅ FULLY IMPLEMENTED

- **Frontend ID:** `"understanding"`
- **Backend file:** `understanding.json`
- **View:** `UnderstandingView.jsx`
- **Displays:**
  - `system_purpose` (text block)
  - `major_components` (chip grid)
  - `inputs` / `outputs` (bullet lists)
  - `functional_requirements` (ordered list)
  - `constraints` (bullet list)
  - `ambiguities` (amber warning cards)
- **Data shape expected:** a single object (not array)

### Agent 2 — Decomposer Agent ✅ FULLY IMPLEMENTED

- **Frontend ID:** `"decomposer"`
- **Backend file:** `decomposition.json`
- **View:** `DecompositionView.jsx`
- **Displays:**
  - Component count + searchable component cards (name, purpose, inputs chips, outputs chips)
  - Architecture interactions table (parses `"SourceComp signalName -> DestComp signalName"` format)
  - Implementation plan (numbered steps with title + description)
- **Data shape:** `{ components: [...], interactions: [...], implementation_plan: [...] }`

### Agent 3 — Description Agent ✅ FULLY IMPLEMENTED

- **Frontend ID:** `"description"`
- **Backend file:** `descriptions.json`
- **View:** `DescriptionView.jsx`
- **Displays:**
  - Searchable accordion; each component expands to show:
    - `inputs` via `SignalTable` (name, direction, width, description)
    - `outputs` via `SignalTable`
    - `state_elements` table (name, type, width, reset_value, description)
    - `behavior` bullets
    - `constraints` bullets
    - `spec_references` bullets
- **Data shape:** Array of description objects; each has `module_name`, `purpose`, `inputs`, `outputs`, `state_elements`, `behavior`, `constraints`, `spec_references`

### Agent 4 — Verification Agent ⚠️ PARTIALLY IMPLEMENTED / MISMATCH

- **Frontend ID:** `"verification"`
- **Backend file mapped by AGENT_FILES:** `rtl_verification.json`
- **View:** `VerificationView.jsx`
- **What the view expects:** an Array of `{ valid, issues, suggestions, reasoning }` per component (description verification format)
- **What the backend actually saves:** a single `VerificationResult` object for RTL verification: `{ valid, issues, suggestions, reasoning }` — NOT an array
- **Known issue:** `VerificationView` will render RTL verification as if it were per-component description verification. The counts (Passed/Failed/Unknown) will be misleading.
- **Deeper problem:** AgentBoard loads `description` + `decomposer` outputs alongside verification to populate component names — these component names are mismatched since the data is now RTL-level, not per-component description-level.
- **What the frontend AGENTS list says:** Agent 04, name "Verification Agent", description "Checks each description against the specification and decomposition." — this description is now inaccurate.

> [!WARNING]
> The "Verification Agent" card in AgentBoard shows description-verification UI for what is actually RTL verification output. This is the most critical frontend–backend mismatch.

### Agent 5 — Pseudocode Generation Agent ✅ FULLY IMPLEMENTED

- **Frontend ID:** `"pseudocode"`
- **Backend file:** `pseudocode.json`
- **View:** `PseudocodeView.jsx`
- **Displays:**
  - Summary card: `generation_status`, `validation_status`, component count
  - Per-component `<details>` accordion: inputs/outputs chips, `CodeViewer` with line-numbered pseudocode + syntax highlighting, validation issues, assumptions, unresolved requirements
  - Aggregate validation issues + unresolved requirements
  - Execution output (if present)
  - Raw LLM artifact preview (fetches `pseudocode_raw.txt` via `/api/runs/{runId}/outputs` index; checks `body.artifacts` for the filename)
- **Data shape:** `{ generation_status, validation_status, components: [{ component_name, module_name, pseudocode: [...lines], inputs, outputs, generation_status, validation_status, validation_issues, assumptions, unresolved_issues }], validation_issues, unresolved_issues, execution_output, execution_errors }`

### Agent 6 — RTL Generation Agent ✅ FULLY IMPLEMENTED (most complete view)

- **Frontend ID:** `"rtl_generation"`
- **Backend file:** `rtl_generation.json`
- **View:** `RTLResultsView.jsx`
- **Displays:**
  - Header: `experimental` flag, module name, language, `generation_status` badge
  - 5 stat tiles: component records, modules with RTL, interfaces passed, generation issues, unresolved issues
  - Stage pills: component generation, interface validation, integration, compilation, RTL agent status
  - `ComponentExplorer`: sidebar nav of all component modules; clicking one shows module name, component name, status badges, inputs/outputs chip lists, `generation_error`, copy-able RTL code block
  - Integrated top-level RTL section: full Verilog `rtl_code`, `component_instances` with port connections
  - Generation issues (error tone), unresolved issues (warning tone), assumptions
- **AgentBoard extra detail for rtl_generation:** Renders `component_generation_status`, `interface_validation_status`, `integration_status`, `compilation_status` as status pills directly in the card header (before expansion), plus per-component `generation_status`/`interface_validation_status` badges
- **Data shape:** `RTLGenerationOutput` — `module_name`, `language`, `rtl_code`, `component_modules: [{ component_name, module_name, rtl_code, inputs, outputs, generation_status, interface_validation_status, generation_error }]`, `component_instances`, `interactions`, `generation_status`, `component_generation_status`, `interface_validation_status`, `integration_status`, `compilation_status`, `generation_issues`, `assumptions`, `unresolved_issues`, `experimental`

### Agents NOT in Frontend — RTL Verification & Reflection ❌ NOT IMPLEMENTED

- **`rtl_verification`** (backend ID) → **not** in `AGENTS` array in `format.js`
- **`reflection`** (backend ID) → **not** in `AGENTS` array in `format.js`
- These agents run in the backend and produce `rtl_verification.json` and `reflection.json`
- The backend's `AGENT_ORDER` includes both: `["understanding", "decomposer", "description", "pseudocode", "rtl_generation", "rtl_verification", "reflection"]`
- Because they are not in `AGENTS`, they never appear as cards in `AgentBoard`, never appear in `stageProgress()` calculation, and their outputs cannot be browsed in the UI
- Their data is accessible via `GET /api/runs/{id}/outputs/rtl_verification` and `.../reflection` but nothing in the frontend calls these endpoints

### "Composer Agent" — NOT IMPLEMENTED in Frontend

- The user mentioned a "Composer Agent / Specification Composer" frontend stage
- After exhaustive search of all `.jsx` and `.js` files, **no such page, component, route, or view exists** in the frontend source
- The closest concept is `UploadPanel.jsx` which shows "Specification" as a heading and handles file upload
- This is a **planned feature that has not been implemented** at all

---

## 8. Design System

### Fonts (Google Fonts, loaded in `index.html`)

| Role | Font | Weights |
|------|------|---------|
| `font-sans` (body, UI) | Manrope | 400, 500, 600, 700 |
| `font-mono` (code, JSON) | IBM Plex Mono | 400, 500 |

### Tailwind Custom Colour Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `canvas` | `#F8F5FF` | Page background |
| `lavender` | `#C5A6F2` | Accents, gradients |
| `lilac` | `#DCCBFA` | Borders, hover states |
| `violet` | `#A879E5` | Section labels, running dots |
| `primary` | `#7540C5` | CTA buttons, active nav, accents |
| `indigo` | `#35145D` | Headings, body text |
| `muted` | `#4A3566` | Secondary text, labels |
| `lime` | `#C8F52F` | "Completed"/"Passed" status badges; glowing dot on sidebar logo |
| `soft` | `#E9DDFB` | Card borders, light backgrounds, chips |

### Semantic Colour Usage (not in Tailwind — inline classes)

| Purpose | Class pattern | Example |
|---------|--------------|---------|
| Error backgrounds | `bg-[#FFF6F6]` / `border-[#F3C0C0]` / `text-[#8F1D1D]` | Errors, failed states |
| Warning backgrounds | `bg-[#FFF8EA]` / `border-[#E7D7A1]` / `text-[#7A5B12]` | Warnings, unresolved |
| Success | `bg-[#C8F52F]` / `text-[#35145D]` | Completed/passed badges |

### Status Badge Colour Map (`StatusBadge.jsx`)

| Status | Style |
|--------|-------|
| `pending` | `bg-[#E9DDFB] text-[#4A3566]` |
| `running` | `bg-[#E9DDFB] text-[#7540C5]` + pulsing dot |
| `completed` | `bg-[#C8F52F] text-[#35145D]` |
| `failed` | `bg-[#FDECEC] text-[#B42318]` |
| `blocked` | `bg-[#FFF6E8] text-[#9A6700]` |
| `skipped` | `bg-[#FFF6E8] text-[#9A6700]` |
| `warnings` | `bg-[#FFF6E8] text-[#9A6700]` |
| `passed` | `bg-[#C8F52F] text-[#35145D]` |
| `not_run` | `bg-[#E9DDFB] text-[#4A3566]` |
| `not_attempted` | `bg-[#E9DDFB] text-[#4A3566]` |

### Custom Shadows (`tailwind.config.js`)

```css
card: "0 16px 40px rgba(117, 64, 197, 0.10), 0 0 28px rgba(197, 166, 242, 0.28)"
glow: "0 10px 28px rgba(117, 64, 197, 0.32)"
```

### Key CSS Patterns (`index.css`)

- Global background: radial gradient (lavender/violet blobs) over `#F8F5FF`
- `aside`: glassmorphism with `backdrop-filter: blur(16px)`, right edge shadow
- `article.rounded-3xl` / `section.rounded-3xl`: `bg-color: rgba(255,255,255,0.8)`, `backdrop-filter: blur(14px)`
- `.expand-panel`: CSS Grid row transition for smooth accordion open/close (280ms ease)
- Dashboard header: gradient card with lime glow orb (pseudo-element)

---

## 9. State Management

SPEC2RTL uses React Context only. No Redux, Zustand, or other external state library.

### `RunContext.jsx` — `RunProvider` / `useRuns()`

**State fields:**

| Field | Type | Description |
|-------|------|-------------|
| `runs` | `Array` | All runs from `GET /api/runs` |
| `active` | `Object\|null` | Full metadata of the currently-active run |
| `activeId` | `string\|null` | ID of active run; persisted in `sessionStorage["spec2rtl-active-run"]` |
| `outputs` | `Object` | Cache: `{[agentId]: {data, raw, stamp, runId}}` |
| `starting` | `boolean` | True while `POST /api/runs` is in-flight |
| `banner` | `string\|null` | Global error banner text |

**Key functions exposed via context:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `startRun` | `(file: File) → Promise<{run_id, status}>` | Upload + start pipeline |
| `loadOutput` | `(agentId, runId?) → Promise<{data, raw, stamp, runId}>` | Load + cache agent JSON |
| `setActiveId` | `(id: string) → void` | Switch active run |
| `refreshRuns` | `() → Promise<runs[]>` | Reload the run list |
| `setBanner` | `(msg: string\|null) → void` | Show/dismiss error banner |
| `running` | `boolean` (computed) | `starting || active?.status === "running"` |

**Live update strategy:**

1. `watchRun(runId)` opens an `EventSource` on `/api/runs/{id}/events`
2. Each SSE message updates `active` state via `rememberActive(payload.metadata)`
3. On SSE error → falls back to `startPolling(runId)` (2 s `setInterval`)
4. On `completed`/`failed` → `stopLiveUpdates()` + `refreshRuns()`

**Output caching:**

`loadOutput()` has a stamp-based cache: `${status}|${finished_at}|${message}`. It re-fetches only when the stamp changes or the agent is still running. The cache key includes `runId` so switching runs clears stale data.

---

## 10. Known Gaps & Mismatches

> [!IMPORTANT]
> These are the most important issues the next developer must address.

### Gap 1 — RTL Verification & Reflection Not Shown in UI ❌

**Problem:** `format.js` AGENTS array has 6 entries. Backend `AGENT_ORDER` has 7. The frontend never shows `rtl_verification` or `reflection` agent cards, never loads their outputs, and never counts them in `stageProgress()`.

**Files to change:**
- `frontend/src/lib/format.js` → add `rtl_verification` and `reflection` entries to `AGENTS`
- `frontend/src/components/AgentBoard.jsx` → add ICONS for both; add view cases in `FormattedOutput`
- Create `frontend/src/views/RTLVerificationView.jsx` — new view needed
- Create `frontend/src/views/ReflectionView.jsx` — new view needed

**Data shapes for new views:**

RTL Verification (`rtl_verification.json`):
```json
{ "valid": true, "issues": [], "suggestions": [], "reasoning": "..." }
```

Reflection (`reflection.json`):
```json
{
  "needs_revision": false,
  "feedback": "...",
  "component_feedback": {"ALU": "..."},
  "reasoning": "..."
}
```

---

### Gap 2 — "Verification" Card Shows Wrong Data ⚠️

**Problem:** `format.js` agent `"verification"` maps to `verification.json` (old description verification). The backend's `AGENT_FILES["verification"]` now maps to `rtl_verification.json`. `VerificationView.jsx` expects an array of per-component results but gets a single RTL verification object.

**Fix options (choose one):**
- **Option A:** Rename frontend agent `"verification"` → `"rtl_verification"` and update `VerificationView` to handle a single `VerificationResult` object
- **Option B:** Keep the card as-is but replace `VerificationView` with a new `RTLVerificationView` that renders a single result, and add a separate `"reflection"` card

**Files to change:** `format.js`, `AgentBoard.jsx`, `VerificationView.jsx`

---

### Gap 3 — `stageProgress()` Undercounts ⚠️

**Problem:** Progress bar goes to 100% after 6 agents, ignoring rtl_verification and reflection. A run still shows "100%" even if RTL verification has not started.

**Fix:** Add `rtl_verification` and `reflection` to `AGENTS` in `format.js`. Both agents have natural `status: "skipped"` when unused (reflection is skipped when RTL verification passes on first try), so they still count toward progress.

---

### Gap 4 — RunSummary Shows Old Description Verification Stats ⚠️

**Problem:** `RunSummary.jsx` renders `summary.verification_passed` and `summary.verification_failed`. These fields are set by description verification which is removed from the pipeline. They are always `null` in recent runs, so the UI shows `—` for both.

**Current:** `run.summary` has these fields from `api/schemas/runs.py`:
```python
class RunSummary(BaseModel):
    components_described: Optional[int]
    verification_passed: Optional[int]     # always null now
    verification_failed: Optional[int]     # always null now
    pseudocode_generation_status: Optional[str]
    rtl_generation_status: Optional[str]
    rtl_verification_valid: Optional[bool]  # actual RTL result
    reflection_needed: Optional[bool]
```

**Fix:** Update `RunSummary.jsx` to show RTL-relevant stats instead:
- Replace "Verification passed/failed" stat tiles with "RTL Valid" (from `summary.rtl_verification_valid`) + "Reflection needed" (from `summary.reflection_needed`)

---

### Gap 5 — Dashboard Tagline is Inaccurate ℹ️

**Problem:** `Dashboard.jsx` says *"Run the six-stage hardware specification pipeline"* (line 16). The backend now has 7–9 stages including RTL verification and conditional reflection.

**Fix:** Update the description string in `Dashboard.jsx` and `Sidebar.jsx` footer text.

---

### Gap 6 — Composer Agent / Specification Composer NOT IMPLEMENTED ❌

**Problem:** The user mentioned a "Composer Agent" frontend, but it does not exist anywhere in the frontend source code. `UploadPanel.jsx` provides basic file upload but no structured spec authoring UI.

**What's missing:** A page/component that allows users to:
- Write or edit hardware specifications in a structured text editor
- Preview or compose specification text before submitting to the pipeline
- Optionally save drafts

**Recommended implementation:**
- New page: `frontend/src/pages/Composer.jsx` or `SpecificationComposer.jsx`
- New route in `App.jsx`: `/composer`
- New nav link in `Sidebar.jsx`
- Backend may need a new endpoint for text-based spec submission (current `POST /api/runs` only accepts file upload)

---

### Gap 7 — No RTL Download Button in Results UI ℹ️

**RTLResultsView.jsx** shows the RTL code but has no direct download link for `integrated_rtl.v` or `top_level_rtl.v`. Users can find them via the History page "Outputs" button.

**Fix:** Add download `<a>` tags in `RTLResultsView.jsx` pointing to `/api/runs/{runId}/download/integrated_rtl.v` (need `runId` prop passed down).

---

### Gap 8 — `RTLGenerationView` in AgentBoard is Dead Code ℹ️

`AgentBoard.jsx` has a local `RTLGenerationView` component (lines 226–284) that is never called. The `FormattedOutput` function at line 222 routes `agentId === "rtl_generation"` to `<RTLResultsView>` (the view file), not the local component. The local `RTLGenerationView` can be safely deleted.

---

## 11. Artifact Storage & File Naming

All run artifacts are stored under `outputs/runs/{run_id}/`.

| Filename | Created by | Contents |
|----------|-----------|----------|
| `metadata.json` | runner.py | Run metadata, agent statuses, summary |
| `specification.txt` | pipeline.py | Extracted text from uploaded PDF/DOCX |
| `input_summary.json` | pipeline.py | File path, hash, page count |
| `understanding.json` | understanding agent | `UnderstandingOutput` Pydantic model |
| `decomposition.json` | decomposer agent | `DecompositionOutput` Pydantic model |
| `descriptions.json` | description agent | `List[ComponentDescription]` |
| `pseudocode.json` | pseudocode agent | `PseudocodeOutput` Pydantic model |
| `pseudocode_raw.txt` | pseudocode agent | Raw LLM response text |
| `pseudocode_validation.json` | validate_pseudocode | Validation results |
| `rtl_generation.json` | rtl_generation agent | `RTLGenerationOutput` Pydantic model |
| `integrated_rtl.v` | rtl_generation agent | Full Verilog for the top-level module |
| `top_level_rtl.v` | rtl_generation agent | Alias / alternative top-level file |
| `compilation.log` | rtl_generation agent | Verilog compilation output |
| `rtl_verification.json` | verification agent | `VerificationResult` Pydantic model |
| `reflection.json` | reflection agent | `RTLReflectionOutput` Pydantic model |
| `pipeline_summary.json` | pipeline.py | End-of-run summary statistics |
| `run_manifest.json` | runner.py | File listing + hash manifest |
| `reflection_attempt_N.json` | reflection agent | Per-retry reflection output |
| `rtl_verification_attempt_N.json` | verification agent | Per-retry RTL verification |
| `rtl_generation_attempt_N.json` | rtl_generation agent | Per-retry RTL generation |

Experimental RTL sub-runs are stored in `outputs/rtl_generation_runs/{run_id}/`.

---

## 12. Environment & Dev Setup

### Python Backend

```
Python 3.13 (via Anaconda venv)
venv location: .\venv\Scripts\python.exe

Install:
  pip install -r requirements.txt

Run backend:
  uvicorn api.main:app --reload --port 8000

Environment variables (.env):
  GEMINI_API_KEY=<your key>
```

### Frontend

```
Node.js (version unspecified; pnpm or npm)

Install:
  cd frontend
  npm install      (or pnpm install)

Run dev server:
  npm run dev      → http://localhost:5173

Build:
  npm run build

Preview build:
  npm run preview  → http://localhost:4173
```

### CORS Configuration (`api/main.py`)

The FastAPI app allows:
- `http://localhost:5173` (Vite dev)
- `http://127.0.0.1:5173`
- `http://localhost:4173` (Vite preview)
- `http://127.0.0.1:4173`

### Vite Proxy (`vite.config.js`)

All requests to `/api/*` on port 5173 are proxied to `http://127.0.0.1:8000`. This means the frontend never makes cross-origin requests in development.

---

## 13. Test Suite Summary

| File | Tests | Status |
|------|-------|--------|
| `tests/` (42 tests) | Unit tests for agents, schemas, pipeline | ✅ All pass |
| `test_validate_pseudocode.py` | Pseudocode grammar validation | ✅ All pass |
| `test_converter_and_simulator.py` | APU simulation tests | ✅ All pass |
| `tests/test_rtl_reflection_pipeline.py` | 9 reflection pipeline tests (added in this session) | ✅ All pass |
| **Total** | **~124 tests** | **✅ All pass** |

Run all tests:
```bash
.\venv\Scripts\python.exe -m pytest tests/ test_validate_pseudocode.py test_converter_and_simulator.py -v
```

---

## 14. Recommended Next Steps for Frontend Development

Listed in priority order based on impact and urgency.

### Priority 1 — Fix Verification Agent Card (1–2 hours)

The "Verification" card is currently showing RTL verification output via a view designed for description verification. This is confusing and misleading.

**Steps:**
1. In `frontend/src/lib/format.js`, change the `"verification"` agent entry:
   - Change `id` to `"rtl_verification"`
   - Change `name` to `"RTL Verification Agent"`
   - Change `description` to something like `"Checks generated RTL against the hardware specification."`
   - Change `file` to `"rtl_verification.json"`
2. In `AgentBoard.jsx`:
   - Add `rtl_verification` to `ICONS` map (use `ShieldCheck`)
   - Update `FormattedOutput` to handle `"rtl_verification"` → new `RTLVerificationView`
3. Create `frontend/src/views/RTLVerificationView.jsx`:
   - Renders a single `VerificationResult`: `valid`, `issues`, `suggestions`, `reasoning`
   - Use the same colour-coded layout as `VerificationView` but for a single result

---

### Priority 2 — Add RTL Verification & Reflection Cards (2–3 hours)

Add two new agent cards that actually reflect the backend pipeline:

**Agent 7 — RTL Verification Agent:**
- Already exists as `rtl_verification` above (Priority 1)

**Agent 8 — Reflection Agent:**
1. Add to `AGENTS` in `format.js`:
   ```js
   {
     id: "reflection",
     number: "07",
     name: "Reflection Agent",
     description: "Analyses RTL verification failures and generates targeted correction feedback.",
     file: "reflection.json",
   }
   ```
2. Add `reflection: Sparkles` (or `Lightbulb`) to `ICONS` in `AgentBoard.jsx`
3. Create `frontend/src/views/ReflectionView.jsx`:
   - Shows `needs_revision` (boolean → badge)
   - Shows `feedback` (text block)
   - Shows `component_feedback` (object → list of `{component: feedback}` pairs)
   - Shows `reasoning` (text block)
4. Add case to `FormattedOutput` in `AgentBoard.jsx`

---

### Priority 3 — Fix RunSummary Stats (30 minutes)

Replace the now-meaningless description verification counts with RTL-relevant stats:

```jsx
// RunSummary.jsx — replace this:
<Stat label="Verification passed" value={summary.verification_passed} accent />
<Stat label="Verification failed" value={summary.verification_failed} />

// With:
<Stat label="RTL Verified" value={summary.rtl_verification_valid === true ? "Yes" : summary.rtl_verification_valid === false ? "No" : "—"} accent={summary.rtl_verification_valid === true} />
<Stat label="Reflection needed" value={summary.reflection_needed === true ? "Yes" : summary.reflection_needed === false ? "No" : "—"} />
```

Or keep 3 stat tiles: Components described | RTL valid | Reflection used

---

### Priority 4 — RTL Download Links in RTLResultsView (30 minutes)

Pass `runId` down from `AgentBoard` through `FormattedOutput` to `RTLResultsView`:
```jsx
// In RTLResultsView.jsx, add a download button section:
{runId && (
  <div className="flex gap-2">
    <a href={`/api/runs/${runId}/download/integrated_rtl.v`}>Download integrated_rtl.v</a>
    <a href={`/api/runs/${runId}/download/top_level_rtl.v`}>Download top_level_rtl.v</a>
  </div>
)}
```

---

### Priority 5 — Specification Composer Page (4–8 hours)

A new page for writing/editing hardware specifications before submission:
- Route: `/composer`
- Nav link in `Sidebar.jsx`
- Textarea or rich text editor for spec authoring
- "Submit" button that posts text as a file or via a new API endpoint
- **Backend change needed:** Add `POST /api/runs/text` endpoint that accepts plain text body and writes it as `specification.txt` to start the pipeline

---

### Priority 6 — Update Stale Text (15 minutes)

- `Dashboard.jsx` line 16: `"Run the six-stage hardware specification pipeline…"` → `"Run the multi-stage hardware specification pipeline…"`
- `Sidebar.jsx` line 64: `"Six stages transform a specification into verified pseudocode and component RTL."` → `"Seven stages transform a specification into verified RTL, with automatic reflection on failure."`

---

### Nice-to-Have — Progress Bar Accuracy

Once Priorities 1 & 2 are done and `AGENTS` has 8 entries, `stageProgress()` will automatically become accurate. No changes needed to `stageProgress()` itself.

---

## Appendix A — Pydantic Schemas Quick Reference

Key schemas from `src/schemas.py` and `api/schemas/runs.py`:

```python
# Backend output schemas
class UnderstandingOutput(BaseModel):
    system_purpose: str
    major_components: list[str]
    inputs: list[str]
    outputs: list[str]
    functional_requirements: list[str]
    constraints: list[str]
    ambiguities: list[str]

class ComponentDescription(BaseModel):
    module_name: str
    purpose: str
    inputs: list[Signal]       # Signal: {name, direction, width, description}
    outputs: list[Signal]
    state_elements: list[StateElement]
    behavior: list[str]
    constraints: list[str]
    spec_references: list[str]

class VerificationResult(BaseModel):
    valid: bool
    issues: list[str]
    suggestions: list[str]
    reasoning: str

class RTLGenerationOutput(BaseModel):
    module_name: str
    language: str
    rtl_code: str
    component_modules: list[ComponentRTLModule]
    component_instances: list[ComponentInstance]
    interactions: list[str]
    generation_status: str
    component_generation_status: Optional[str]
    interface_validation_status: Optional[str]
    integration_status: Optional[str]
    compilation_status: Optional[str]
    generation_issues: list[str]
    assumptions: list[str]
    unresolved_issues: list[str]
    experimental: Optional[bool]
    rtl_agent_status: Optional[str]

class RTLReflectionOutput(BaseModel):
    needs_revision: bool
    feedback: str
    component_feedback: dict[str, str]
    reasoning: str

# API schemas (api/schemas/runs.py)
class RunSummary(BaseModel):
    components_described: Optional[int]
    verification_passed: Optional[int]     # legacy, always null
    verification_failed: Optional[int]     # legacy, always null
    pseudocode_generation_status: Optional[str]
    rtl_generation_status: Optional[str]
    rtl_verification_valid: Optional[bool]
    reflection_needed: Optional[bool]
```

---

## Appendix B — Format Utility Functions (`lib/format.js`)

```js
asList(value)       // Normalises any value to an array; filters null/undefined
asText(value, fb)   // Returns string; falls back to fb (default "Not provided")
formatBytes(size)   // "102.3 KB" / "1.4 MB" / "512 B"
formatTime(value)   // ISO 8601 → locale date+time string; "—" if null
stageProgress(run)  // 0–100 based on AGENTS completion; partial credit for running agents
```

---

*End of handoff document. All file paths are relative to `C:\Users\srira\OneDrive\Desktop\SPEC2RTL\`.*
