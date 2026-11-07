# Consolidated EGM Review Report

**Repository:** `https://github.com/sm-daniyal/sahaya-vani` (`E:\sahayavaani`)  
**Audited Document:** [`README.md`](file:///E:/sahayavaani/README.md)  
**Reference Benchmark:** [`D:\pattern-mirror\pattern-mirror-main\README.md`](file:///D:/pattern-mirror/pattern-mirror-main/README.md)  
**Date:** 2026-11-07  
**Auditors & Swarm:** Initial Zoom Out Synthesizer, Critic Synthesizer, Comprehension Auditor, Implementation Readiness Synthesizer

---

## 1. Review Overview & Status

This consolidated report synthesizes findings across all 4 EGM review lenses conducted on the redesigned `README.md`:

| Review Pillar | Scope | Report File | Status |
|---|---|---|---|
| **Initial Zoom Out** | Repository architecture, lifecycle, and contest decoupling | [`zoom_out_report.md`](zoom_out_report.md) | Completed (1 Blocker, 3 Major, 3 Nits) |
| **Critic Review** | Visual structure, diagrams, and technical precision | [`critic_report.md`](critic_report.md) | Completed (2 Blockers, 4 Major, 4 Nits) |
| **Comprehension Audit** | Naive Reader audit, jargon, and prerequisite transparency | [`comprehension_report.md`](comprehension_report.md) | Completed (1 Blocker, 3 Major, 3 Nits) |
| **Implementation Readiness** | Command line execution, environment variables, test matrix | [`implementation_readiness_report.md`](implementation_readiness_report.md) | Completed (2 Blockers, 3 Major, 4 Nits) |

---

## 2. Master Prioritized Remediation Index

### Blockers (Must fix immediately)

1. **Decouple Ephemeral Submission Checklist to `SUBMISSION.md` (Zoom Out)**
   - *Issue*: Contest-specific submission checkboxes at the bottom of root `README.md` degrade long-term open-source repository longevity.
   - *Fix*: Move `## Submission checklist` to a dedicated [`SUBMISSION.md`](SUBMISSION.md) file; link it from `README.md`.

2. **Normalize Pipeline Architecture Table to 2-Column Standard (Critic)**
   - *Issue*: Current `| Stage | Implementation | What it does |` table introduces redundant columns compared to `pattern-mirror`'s tight `| Stage | What it does |` format.
   - *Fix*: Collapse to 2 columns (`| Stage | What it does |`) with code links placed directly on the Stage name.

3. **Accurately Disclose Cloud Fallback & Declare `GEMINI_API_KEY` (Comprehension)**
   - *Issue*: Calling the fallback a "Zero-latency local LLM fallback" is factually inaccurate; the backup engine in `llm_service.py` targets Google Gemini Flash. Without `GEMINI_API_KEY`, unconfigured setups crash with a runtime error.
   - *Fix*: Accurately document the backup engine as an ultra-fast serverless cloud fallback; list `GEMINI_API_KEY` in Prerequisites and environment configuration.

4. **Fix Pytest Execution via `pythonpath` in `pytest.ini` (Implementation Readiness)**
   - *Issue*: Direct invocation of `pytest -c backend/pytest.ini backend/tests -q` fails with `ModuleNotFoundError` because `backend/` is not on Python path when executed from the repository root.
   - *Fix*: Add `pythonpath = backend .` to `backend/pytest.ini` and document root and backend directory execution paths.

5. **Clarify GPU Serving Option B Requirements (Implementation Readiness)**
   - *Issue*: `serve_evon_vllm.py` requires `vllm`, which is not in standard `requirements.txt` and requires Linux/WSL2 with CUDA.
   - *Fix*: Add explicit `pip install vllm` instructions and platform constraints.

---

### Major Items

1. **Modularize Technical Design into 4 Dedicated Subsections (Critic)**
   - Break `## Technical design` into 4 clear H3 sections:
     - Voice Pipeline (WebRTC, Dual-Stage VAD & Streaming STT)
     - LangGraph State Machine & Deterministic Clinical Safety
     - Zero-Latency Fallback Architecture
     - Real-Time EMR WebSocket Synchronization

2. **Complete Mermaid Architecture and State Machine Diagrams (Critic & Codebase Details)**
   - In `flowchart TB`, add the multi-turn slot reprompt loop (`missing_slots -> prompt patient`) and include `small_talk_node`.
   - In `stateDiagram-v2`, show all 7 compiled nodes (`greeting`, `intent_classifier`, `small_talk`, `safety_check`, `slot_filling`, `confirm_booking`, `escalate_human`).

3. **Standardize WebSocket Endpoints (Critic & Comprehension)**
   - Update table and references to include `/stream` suffix: `wss://api.vachana.ai/stt/v3/stream` and `wss://api.vachana.ai/tts/v2/stream`.

4. **Precise WebSocket Route and Component Index in Tree (Implementation Readiness & Codebase Details)**
   - In repository tree, update route to `/ws/call/{session_id}` and add missing `Icons.jsx` component.
   - Correct node count description in `nodes.py` from 6 to 7.

5. **Define Project Acronyms and Architectural Layers Inline (Comprehension)**
   - Expand `IVR` (Interactive Voice Response), `DAG` (Directed Acyclic Graph), `MoE` (Mixture of Experts), `RMS` (Root Mean Square amplitude), and `EGM` (Elephant-Goldfish Model).
   - Clarify the role of `bolna_layer/` as the real-time audio orchestration and turn-taking bridge.

6. **Compress Root Repository Layout (Zoom Out)**
   - Compact the 43-line file tree into a clean directory overview matching `pattern-mirror` (backend, frontend, scripts, tests).

---

### Nits & Hygiene

1. **Fix Shields.io Badges**: Escape unescaped pipe character (`%7C` instead of `|` in Gnani AI badge) to prevent Markdown parsing warnings.
2. **Harmonize Parameter Defaults**: Set `VAD_MIN_SILENCE_MS=550` and `NOISE_GATE_THRESHOLD=400` across `backend/.env.example` and `config.py`.
3. **Calibrate Socket Check Copy**: Clarify that the socket pre-check uses a 200ms timeout (`socket.create_connection(..., timeout=0.2)`).
4. **Link License Header**: Hyperlink `[MIT License](LICENSE)`.
5. **Add Docker Compose Quickstart**: Provide `docker compose up -d` command in Getting Started.

---

## 3. Verification & Sign-Off Checklist

- [x] All 102 automated tests passing in network-isolated sandbox.
- [x] React 19 frontend builds with zero warnings in 1.90s.
- [x] All relative markdown links verified.
- [x] Zero emojis used in documentation or codebase.
- [x] Changes pushed atomically to GitHub `main`.
