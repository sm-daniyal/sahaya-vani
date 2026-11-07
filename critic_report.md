# EGM Critic Review Report (Step 7)

**Target:** `E:\sahayavaani\README.md` (`lines 1-173`)  
**Context baseline:** `D:\pattern-mirror\pattern-mirror-main\README.md`  
**Mode:** REVIEW

## Reviewer Status

| Reviewer | Lens Focus | Status |
|---|---|---|
| `egm-design` | System architecture, dataflow accuracy, pipeline & state diagrams | completed |
| `egm-structural` | Layout symmetry, section hierarchy, table structure against baseline | completed |
| `egm-style` | Technical copy clarity, formatting hygiene, URL/badge encoding, terminology | completed |

---

## Executive Severity Breakdown

* 🔴 **Blocker**: 2 findings
* 🟡 **Major**: 4 findings
* 🟢 **Nit**: 4 findings
* **Total Prioritized Findings**: 10

---

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Redundant Implementation Column in Voice Pipeline Table - Severity: Blocker
* **Reviewer Lens:** `egm-structural` / `egm-style`
* **Affected Scope:** Lines 60–71 (`## Technical design` -> `### Full-duplex voice processing pipeline`)
* **Discrepancy Description**: The voice processing pipeline table uses a 3-column layout: `| Stage | Implementation | What it does |`. In every single row, Column 1 has a markdown link to the file (e.g. `[Noise Gate](backend/bolna_layer/audio_utils.py)`), and Column 2 repeats the exact same file link in backticks (e.g. `[`audio_utils.py`](backend/bolna_layer/audio_utils.py)`).
* **Rationale & Recommendation**: Violates DRY documentation principles and breaks structural symmetry with Pattern Mirror (which strictly uses a 2-column layout: `| Stage | What it does |`, embedding the code link into the Stage name). Collapse Columns 1 and 2 into a single `Stage` column linking directly to the implementation file:
  ```markdown
  | Stage | What it does |
  |---|---|
  | [Noise Gate](backend/bolna_layer/audio_utils.py) | Frame-level amplitude envelope filter suppressing microphone hiss and low-energy background noise below 400 RMS. |
  ```

---

### 2. Missing Dedicated Architectural Subsections in Technical Design - Severity: Blocker
* **Reviewer Lens:** `egm-design` / `egm-structural`
* **Affected Scope:** Lines 54–141 (`## Technical design`)
* **Discrepancy Description**: The entire technical design is grouped under a single H3 (`### Full-duplex voice processing pipeline`), under which two distinct diagrams (streaming flowchart and LangGraph state machine) are bundled. Meanwhile, core architectural innovations highlighted in the problem statement and design principles—specifically the deterministic LangGraph safety guardrail engine, the zero-latency local fallback mechanism (Potato PC protection), and real-time WebSocket EMR push—lack dedicated narrative H3 subsections.
* **Rationale & Recommendation**: In Pattern Mirror, each subsystem receives its own distinct H3 subsection (`### Bias detection pipeline`, `### Dictionary growth`, `### Drift check`, `### Pattern surfacing`). Restructure `## Technical design` into four modular subsections:
  1. `### Full-duplex voice processing pipeline` (table + streaming flowchart)
  2. `### LangGraph clinical safety guardrails & state engine` (narrative + state diagram)
  3. `### Zero-latency resilient fallback engine (GPU disconnect protection)` (explaining the 0.001s socket pre-check and rule engine fallback)
  4. `### Real-time EMR WebSocket telemetry` (explaining state broadcast and UI synchronization)

---

### 3. Pipeline Flowchart Missing Slot-Filling Conversational Loop & SmallTalk Node - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 75–96 (`Diagram — End-to-end voice streaming pipeline`)
* **Discrepancy Description**: In `GRAPH_EXEC`, the flowchart shows a strictly linear path: `SF["slot_filling_node"] --> CONF["confirm_booking_node"]`. It omits the multi-turn conversational loop when slots are missing (`missing_slots -> prompt patient via LLM/TTS`), omits the `small_talk_node` (defined in `graph.py` lines 91 & 108), and misleadingly shows only `CONF` and `ESC` routing to `LLM`.
* **Rationale & Recommendation**: Update the Mermaid flowchart to accurately represent real LangGraph state transitions:
  - Add edge from `SF` back out to `LLM` / patient prompt when slots are incomplete (`slots missing -> prompt patient`).
  - Add `small_talk_node` routed from `G1` for greetings, farewells, and clinic operational inquiries.

---

### 4. Challenge Awards Alignment Section Disrupts Architectural Narrative Flow - Severity: Major
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Lines 143–157 (`## Challenge awards alignment`)
* **Discrepancy Description**: In Pattern Mirror, `## Technical design` transitions immediately into `## Tech stack`, providing an uninterrupted engineering reading path. SahayaVaani inserts `## Challenge awards alignment` directly between `Technical design` and `Tech stack`.
* **Rationale & Recommendation**: Move `## Challenge awards alignment` immediately following `## Tech stack` (as a bridge to Getting Started) or reposition it right after `## Product overview`. Keeping `## Technical design` and `## Tech stack` contiguous preserves technical architecture cohesion.

---

### 5. Unescaped Pipe Character in Shields.io Gnani AI Badge URL - Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Line 9
* **Discrepancy Description**: Line 9 uses literal pipe characters `|` in the query string:
  `![Gnani AI](https://img.shields.io/badge/Gnani%20AI-Prisma%20|%20Evon%20|%20Timbre-0f62fe)`
* **Rationale & Recommendation**: Literal pipe characters `|` inside markdown image links break rendering on strict markdown renderers and badge proxies. Replace literal pipes with `%7C` or double dashes `--`:
  `![Gnani AI](https://img.shields.io/badge/Gnani%20AI-Prisma_%7C_Evon_%7C_Timbre-0f62fe)`

---

### 6. WebSocket Endpoint URI Inconsistency Across Documentation - Severity: Major
* **Reviewer Lens:** `egm-design` / `egm-style`
* **Affected Scope:** Lines 64, 69, 79, 93, 164, 165
* **Discrepancy Description**:
  - Line 64 & Line 79 cite: `wss://api.vachana.ai/stt/v3`
  - Line 164 & `backend/config.py` cite: `wss://api.vachana.ai/stt/v3/stream`
  - Line 69 & Line 93 cite: `wss://api.vachana.ai/tts/v2`
  - Line 165 & `backend/config.py` cite: `wss://api.vachana.ai/tts/v2/stream`
* **Rationale & Recommendation**: The `/stream` path suffix is inconsistently dropped in table descriptions and diagram labels. Standardize all references to the exact streaming endpoint paths (`wss://api.vachana.ai/stt/v3/stream` and `wss://api.vachana.ai/tts/v2/stream`).

---

### 7. Missing Product Overview Footer Navigation Callout - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Line 51 (following line 50)
* **Discrepancy Description**: Pattern Mirror concludes `Product overview` with an actionable blockquote callout:
  `> Every view is shown in the [portfolio deck](docs/pattern-mirror-deck.pdf); or [run it locally](#getting-started) to explore the app live.`
  SahayaVaani ends abruptly at line 50 (`**Not** a chatbot · **not** a generic voice wrapper · **not** an English-only touch-tone IVR.`) without a transition to the demo deck or local setup.
* **Rationale & Recommendation**: Add the symmetric blockquote callout at line 51:
  `> Every interaction is demonstrated in the [walkthrough deck](frontend/public/slides.html); or [run it locally](#getting-started) to explore the clinical console live.`

---

### 8. Excessive Frequency of Horizontal Dividers (`---`) - Severity: Nit
* **Reviewer Lens:** `egm-structural` / `egm-style`
* **Affected Scope:** Lines 16, 26, 52, 141, 156, 172
* **Discrepancy Description**: Pattern Mirror uses `---` only twice in the entire document: once to bound the hero header, and once before the closing footer. SahayaVaani inserts `---` after every single H2 section, causing excessive visual fragmentation.
* **Rationale & Recommendation**: Remove horizontal dividers between `The problem` and `Product overview`, and between `Product overview` and `Technical design`, creating a cleaner, unified typography rhythm.

---

### 9. Tech Stack Table Header & Layer Alignment Symmetry - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 158–171
* **Discrepancy Description**: Table header uses `| Layer | Technology Choices |` instead of Pattern Mirror's concise `| Layer | Choices |`. Additionally, `WebSocket broadcast channels` is listed under `Data & Persistence` rather than under communication/transport.
* **Rationale & Recommendation**: Rename header to `| Layer | Choices |` and move WebSocket broadcast into `Backend` or an explicit `Protocols / Streaming` layer.

---

### 10. Presentation Deck Link Clarification - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Line 12
* **Discrepancy Description**: Line 12 links directly to `frontend/public/slides.html`. Clicking a raw HTML file on GitHub displays unrendered markup rather than slides.
* **Rationale & Recommendation**: Add brief contextual guidance: `[full walkthrough deck](frontend/public/slides.html) (served locally at http://localhost:5173/slides.html)`.
