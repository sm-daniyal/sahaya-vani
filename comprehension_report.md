# Comprehension Audit Report: `E:\sahayavaani\README.md`

**Target File**: [`README.md`](file:///E:/sahayavaani/README.md)  
**Feature Range**: Lines 1–173  
**Detailed Range**: Lines 174–346  
**Auditor Persona**: Naive Reader (Comprehension Goldfish — zero institutional context)

---

### What this proposes
SahayaVaani proposes an automated, sovereign clinical voice receptionist designed for outpatient hospital desks in Karnataka to streamline patient intake in Kannada and code-mixed Kanglish. The system captures patient speech over 16 kHz WebRTC audio, applies noise gating and voice activity detection, performs speech-to-text with Gnani Prisma, and processes dialogue through a deterministic LangGraph state machine with strict clinical triage guardrails. It generates conversational responses using an open-weights 30B MoE LLM (Gnani Evon v3.3 via vLLM) or a fallback engine, synthesizes voice output via Gnani Timbre TTS, and streams live appointment confirmations and emergency triage escalations directly to an IBM Carbon-styled receptionist dashboard over WebSockets.

### How the existing system works, per this document
According to the document, current outpatient reception desks suffer from heavy morning congestion because staff spend 4 to 6 minutes manually recording repetitive scheduling details per patient. Existing automated IVRs fail because they rely on rigid English touch-tone menus that do not understand colloquial Kannada or code-mixed speech, while standard cloud bots hallucinate medical prescriptions and collapse under hospital waiting room noise. The document presents SahayaVaani as an existing, functional full-stack solution featuring a FastAPI backend, an asynchronous SQLite EMR database, a React 19 clinical console, and 102 passing automated tests running in complete network isolation.

---

### Findings

#### Finding 1: Unstated Cloud LLM Dependency and Misleading "Local Fallback" Claim
1. **Severity**: Blocker
2. **Affected Scope**: Lines 48, 68, 166, 176–180 (Prerequisites), 187–193 (Configure environment), 242–244 (Developer Note on Potato PCs)
3. **Discrepancy Description & Rationale**:
   - The document repeatedly advertises a "Zero-latency local LLM fallback" (line 48) and assures developers on low-spec machines ("Potato PCs") that if port 8000 is inactive, the system "automatically detects that port 8000 is inactive in 0.001 seconds and routes through the backup engine, ensuring you never experience lag or connection timeouts" (lines 242–244).
   - However, the underlying implementation (`backend/services/llm_service.py` and `backend/.env.example`) reveals that the backup engine is Google Gemini Flash, an external cloud API that strictly requires a `GEMINI_API_KEY`. It is neither local nor offline.
   - Crucially, neither `GEMINI_API_KEY` nor any Google API account requirement is mentioned in the Prerequisites (lines 176–179 list only Python, Node.js, and Gnani API Key) or in Step 2: Configure environment (line 191 instructs only to "Edit .env and enter your GNANI_API_KEY").
   - If a naive reader without an NVIDIA GPU or Colab instance follows the Getting Started guide on a standard PC, the backend will crash at runtime with `RuntimeError: No LLM provider available. Ensure either VLLM_BASE_URL (for Evon) or GEMINI_API_KEY is configured.` upon processing the first patient query. The document must explicitly declare `GEMINI_API_KEY` as a fallback prerequisite or accurately describe the backup engine as an external cloud fallback.

---

#### Finding 2: Undefined Architectural Component "Bolna"
1. **Severity**: Major
2. **Affected Scope**: Lines 60–62 (table), Line 167 ("Agent Orchestration"), Line 278 ("Repository layout")
3. **Discrepancy Description & Rationale**:
   - The document introduces "Bolna" across multiple sections: `backend/bolna_layer/audio_utils.py` (lines 60, 62), "Bolna hybrid streaming turn-taker" (line 167), and `backend/bolna_layer/` in the repository tree (line 278).
   - "Bolna" is never defined, explained, or linked to external documentation. To a new team member, it is completely ambiguous whether Bolna is an external open-source framework, an installed third-party library, a proprietary Gnani technology, or an internal architectural abstraction layer.

---

#### Finding 3: Undefined Internal Acronym "EGM"
1. **Severity**: Major
2. **Affected Scope**: Lines 308, 321
3. **Discrepancy Description & Rationale**:
   - Line 308 and Line 321 reference `concepts_brief.md` as "EGM frontend redesign specification" and "EGM specification for the IBM Carbon for Healthcare frontend transformation".
   - The acronym "EGM" is unexpanded, undefined, and unlinked. A fresh reader has no way of knowing what EGM represents or why it governs the frontend specification.

---

#### Finding 4: Ambiguous Execution Working Directory for Test Suite
1. **Severity**: Major
2. **Affected Scope**: Lines 189, 215, 263–265 ("Running the test suite")
3. **Discrepancy Description & Rationale**:
   - In "Getting started", Step 3 directs the reader to `cd backend` (line 189), and Step 4 directs the reader to `cd frontend` in a second shell (line 215).
   - Later, under "Running the test suite", the command given is:
     ```bash
     pytest -c backend/pytest.ini backend/tests -q
     ```
   - This command succeeds only when run from the root repository directory (`sahaya-vani/`). If the reader executes it inside `backend/` (where Step 3 left them), pytest attempts to find `backend/backend/pytest.ini` and fails. The documentation must state the required working directory (e.g. `cd /path/to/sahaya-vani` or `pytest -c pytest.ini tests -q` when inside `backend/`).

---

#### Finding 5: Unexpanded Acronyms (IVR, DAG, MoE, RMS)
1. **Severity**: Nit
2. **Affected Scope**: Lines 22, 50 (`IVR`); Lines 65, 80, 82, 258 (`DAG`); Lines 68, 91, 166, 227, 332 (`MoE`); Lines 62, 63, 168, 298 (`RMS`)
3. **Discrepancy Description & Rationale**:
   - Multiple domain acronyms are introduced without inline expansion or glossary entries:
     - `IVR` (Interactive Voice Response) on lines 22 and 50.
     - `DAG` (Directed Acyclic Graph) on lines 65, 80, 82, and 258.
     - `MoE` (Mixture of Experts) on lines 68, 91, 166, 227, and 332.
     - `RMS` (Root Mean Square) on lines 62, 63, 168, and 298. Specifically, the audio threshold "below 400 RMS" does not specify the scale (raw 16-bit integer amplitude vs dBFS or normalized float), which creates ambiguity for audio engineers.

---

#### Finding 6: Parameter Value Discrepancy Between README and `.env.example`
1. **Severity**: Nit
2. **Affected Scope**: Lines 36, 62, 63, 78
3. **Discrepancy Description & Rationale**:
   - The README specifies a "dynamic 550ms silence window" (line 36) / "550ms silence boundary detection" (lines 63, 78) and a "Noise Gate below 400 RMS" (line 62).
   - In contrast, the provided `backend/.env.example` sets `VAD_MIN_SILENCE_MS=400` and `NOISE_GATE_THRESHOLD=500`. While `backend/config.py` defaults to 550ms and 400, any user who copies `.env.example` to `.env` as instructed in Step 2 will override the defaults with 400ms and 500 RMS, resulting in behavior divergent from the README claims.

---

#### Finding 7: Missing Link / Procedure for Gnani API Key Acquisition
1. **Severity**: Nit
2. **Affected Scope**: Lines 179, 191
3. **Discrepancy Description & Rationale**:
   - Step 2 requires setting `GNANI_API_KEY` for Prisma STT and Timbre TTS, but does not provide a link or instructions on where external evaluators or users should register or obtain this credential. Adding a reference link (e.g. Gnani developer portal or challenge coordinator contact) would make the guide fully self-contained.
