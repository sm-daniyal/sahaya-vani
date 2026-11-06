# 🏥 SahayaVaani — Kannada/Kanglish Hospital Voice Agent

> **Phase 1 MVP** · Bangalore General Hospital Front-Desk Voice AI
> Powered by **Gnani Prisma STT** · **Evon LLM** · **Timbre TTS** · **LangGraph** · **FastAPI** · **React 19**

---

## Architecture

```
                        ┌─────────────────────────────────────────────────────┐
   Patient Phone/Web    │              SahayaVaani Backend (FastAPI)           │
   ─────────────────►   │                                                       │
   PCM 16kHz frames     │  ┌──────────────────────────────────────────────┐    │
                        │  │          Bolna Orchestration Layer             │    │
                        │  │  Noise Gate → VAD → Low-conf fallback         │    │
                        │  └───────────────────────┬──────────────────────┘    │
                        │                          │                            │
                        │            ┌─────────────▼──────────────┐            │
                        │            │   Gnani Prisma v2.5 STT     │◄── WSS ───►│ api.vachana.ai
                        │            │   wss://api.vachana.ai/stt  │            │
                        │            └─────────────┬──────────────┘            │
                        │                          │  transcript                │
                        │            ┌─────────────▼──────────────┐            │
                        │            │     LangGraph State Machine  │            │
                        │            │                             │            │
                        │            │  greeting → intent_classify  │            │
                        │            │     → safety_check          │            │
                        │            │     → slot_filling          │            │
                        │            │     → confirm_booking       │            │
                        │            │     → escalate_human        │            │
                        │            └──────────┬──────────────────┘            │
                        │                       │  response text               │
                        │            ┌──────────▼──────────────────┐            │
                        │            │  Gnani Evon v3.3 (vLLM)     │◄── HTTP ──►│ localhost:8000
                        │            │  Intent / Slots / Confirm   │            │
                        │            └──────────┬──────────────────┘            │
                        │                       │                              │
                        │            ┌──────────▼──────────────────┐            │
                        │            │  Gnani Timbre v2.5 TTS       │◄── WSS ───►│ api.vachana.ai
                        │            │  wss://api.vachana.ai/tts   │            │
                        │            └──────────┬──────────────────┘            │
                        │                       │  PCM audio                   │
   ◄─────────────────   │       Browser plays back agent voice                  │
   TTS audio + events   │                       │                              │
                        │            ┌──────────▼──────────────────┐            │
                        │            │   SQLite EMR (emr.db)        │            │
                        │            │   appointments + handoffs    │            │
                        │            └──────────┬──────────────────┘            │
                        │                       │  WS broadcast                │
   React Dashboard ◄────│───────── /ws/emr ─────┘                              │
                        └─────────────────────────────────────────────────────┘
```

## Project Structure

```
sahayavaani/
├── backend/
│   ├── main.py                   FastAPI app + all WebSocket endpoints
│   ├── config.py                 Pydantic settings (env-driven)
│   ├── database.py               SQLAlchemy async EMR models + CRUD
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── langgraph_agent/
│   │   ├── graph.py              StateGraph definition + conditional edges
│   │   ├── nodes.py              All 6 node functions
│   │   ├── state.py              AgentState TypedDict
│   │   └── prompts.py            All Kanglish prompt templates
│   ├── services/
│   │   ├── stt_service.py        Gnani Prisma v2.5 WebSocket client
│   │   ├── tts_service.py        Gnani Timbre v2.5 WebSocket client
│   │   ├── llm_service.py        vLLM/Evon OpenAI-compat client
│   │   └── vad_service.py        WebRTC VAD + amplitude fallback
│   └── bolna_layer/
│       ├── orchestrator.py       Main session loop (Bolna hybrid)
│       └── audio_utils.py        PCM utilities
├── frontend/
│   ├── index.html
│   ├── package.json              React 19 + Vite
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx               Two-column layout
│       ├── components/
│       │   ├── VoiceInterface.jsx   Mic capture, PCM streaming, TTS playback
│       │   ├── EMRTable.jsx         Live appointment table
│       │   ├── TranscriptPanel.jsx  Live conversation bubbles
│       │   └── StatusIndicator.jsx  LangGraph node stepper
│       └── styles/App.css
├── scripts/
│   ├── seed_db.py               Seed sample appointments
│   └── test_audio.py            CLI WAV test client
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend |
| Node.js | 20+ | Frontend (Vite/React) |
| pnpm or npm | latest | Frontend package manager |
| CUDA GPU | optional | vLLM acceleration |
| Gnani API Key | required | STT + TTS access |

---

## 1. Environment Setup

### Backend
```bash
cd backend
cp .env.example .env
# Edit .env — add your GNANI_API_KEY
```

Create a virtualenv and install dependencies:
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

> **Note on webrtcvad**: On Windows, you may need Visual Studio Build Tools:
> ```
> pip install webrtcvad-wheels   # pre-built wheel alternative
> ```

---

## 2. Start vLLM with Gnani Evon v3.3

```bash
# Option A: Docker (recommended)
docker run --gpus all -p 8000:8000 vllm/vllm-openai \
  --model gnani/evon-v3.3 \
  --served-model-name gnani/evon-v3.3

# Option B: pip
pip install vllm
vllm serve gnani/evon-v3.3 --port 8000

# Option C: CPU-only (slow, for testing)
vllm serve gnani/evon-v3.3 --port 8000 --device cpu
```

Verify: `curl http://localhost:8000/v1/models`

> **Without GPU**: The pipeline still works with any OpenAI-compatible API.
> Point `VLLM_BASE_URL` at OpenAI, Groq, or Ollama for testing.

---

## 3. Seed the Database

```bash
cd backend
python ../scripts/seed_db.py
```

Creates `emr.db` with 3 sample appointments.

---

## 4. Start the Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Visit: http://localhost:8080 → `{"status": "ok", "app": "SahayaVaani"}`

---

## 5. Start the Frontend

```bash
cd frontend
npm install          # or: pnpm install
npm run dev          # or: pnpm dev
```

Visit: **http://localhost:5173**

---

## 6. Run a Demo Call

### Option A: Browser microphone
1. Open http://localhost:5173
2. Click **🎙️ Start Call**
3. Speak in Kannada/Kanglish:
   - *"Nange cardiology appointment beeku next Monday beligge"*
4. Watch the transcript, state stepper, and EMR table update live.

### Option B: WAV file (no microphone needed)
```bash
# From project root
python scripts/test_audio.py path/to/sample_kannada.wav
```

---

## 7. Docker Compose (all-in-one)

```bash
# Requires NVIDIA GPU + Container Toolkit
cp backend/.env.example backend/.env
# Add GNANI_API_KEY to backend/.env

docker-compose up --build
```

Services:
- `vllm-evon`             → http://localhost:8000
- `sahayavaani-backend`   → http://localhost:8080

---

## LangGraph State Machine

```
[START]
  │
  ▼
greeting          ← Plays Kanglish welcome (pre-canned TTS)
  │
  ▼
intent_classifier ← Evon LLM classifies: book | reschedule | medical | other
  │
  ├── needs_repeat? → (loop back, ask patient to repeat)
  │
  ▼
safety_check      ← Hard guardrail: medical question? → escalate
  │
  ├── medical_question → escalate_human → [END]
  │
  ▼
slot_filling      ← Evon extracts: name, department, date, time
  │
  ├── missing slots? → (loop, ask for each missing field)
  │
  ▼
confirm_booking   ← Write to SQLite, broadcast /ws/emr event
  │
  ▼
[END]
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/appointments` | List all EMR appointments |
| `GET` | `/api/appointments/{id}` | Get one appointment |
| `GET` | `/api/handoffs` | List human escalation flags |
| `POST` | `/api/test-call` | Test with WAV file path |
| `WS` | `/ws/call/{session_id}` | Main voice call stream |
| `WS` | `/ws/emr` | Live EMR update feed |

### WebSocket Events (Server → Client)

```json
{ "type": "session_start",  "session_id": "uuid" }
{ "type": "listening",      "status": "start|end" }
{ "type": "transcript",     "text": "...", "confidence": 0.9, "is_final": true }
{ "type": "state_change",   "node": "slot_filling", "intent": "book_appointment" }
{ "type": "agent_response", "text": "Dhanyavadagalu..." }
{ "type": "tts_done",       "text": "..." }
{ "type": "session_end",    "appointment_id": 42, "outcome": "confirm_booking" }
```

---

## Safety Guardrail

The `safety_check` node implements a **two-layer guard**:

1. **Rule-based**: If `intent == "medical_question"` → escalate immediately.
2. **LLM-based**: Even if intent is `other`, Evon re-reads the transcript for
   hidden medical content (e.g., "mere ko dawai chahiye"). Any `YES` → escalate.

On escalation:
- TTS: *"Naanu medical advice kodalaare. Doctor jotege maataadbeku."*
- DB: `HumanHandoff` row created for the session.
- Dashboard: Row appears in `/api/handoffs`.

---

## Configuration Reference

All settings are in `backend/config.py` and can be overridden via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GNANI_API_KEY` | *(required)* | Your Gnani API key |
| `STT_WS_URL` | `wss://api.vachana.ai/stt/v3/stream` | Prisma v2.5 endpoint |
| `TTS_WS_URL` | `wss://api.vachana.ai/tts/v2/stream` | Timbre v2.5 endpoint |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | vLLM endpoint |
| `EVON_MODEL_NAME` | `gnani/evon-v3.3` | Model identifier |
| `VAD_MIN_SILENCE_MS` | `400` | End-of-utterance silence threshold |
| `STT_CONFIDENCE_THRESHOLD` | `0.60` | Below this → ask to repeat |
| `NOISE_GATE_THRESHOLD` | `500` | Amplitude floor for noise gate |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `webrtcvad` install fails on Windows | `pip install webrtcvad-wheels` |
| vLLM OOM on GPU | Add `--max-model-len 2048` or use CPU mode |
| STT returns empty transcript | Check `GNANI_API_KEY` in `.env` |
| Frontend shows no appointments | Seed the DB: `python scripts/seed_db.py` |
| Microphone not captured | Allow browser mic permission; use HTTPS in production |

---

## 🧪 Automated Testing & CI/CD

SahayaVaani includes a comprehensive **102-test automated test suite** running via `pytest` and `pytest-asyncio` covering every layer of the voice agent stack with 100% test isolation (no external network or token dependencies required).

### Test Suite Structure

| Test Module | Coverage Area | Tests |
|-------------|---------------|-------|
| [`test_audio_vad.py`](file:///E:/sahayavaani/backend/tests/test_audio_vad.py) | Audio chunking, noise gating, peak normalization, VAD silence boundaries | 16 |
| [`test_intent_classifier.py`](file:///E:/sahayavaani/backend/tests/test_intent_classifier.py) | Kannada script/Kanglish greetings, booking intents, low-confidence repeat | 18 |
| [`test_slot_filling.py`](file:///E:/sahayavaani/backend/tests/test_slot_filling.py) | Department/symptom extraction, relative dates, time, phone, multi-turn accumulation | 18 |
| [`test_safety_guardrails.py`](file:///E:/sahayavaani/backend/tests/test_safety_guardrails.py) | Symptom allowance vs. medication advice blocking, doctor escalation handoff | 14 |
| [`test_database_emr.py`](file:///E:/sahayavaani/backend/tests/test_database_emr.py) | SQLite EMR appointment lifecycle, handoff tracking, serialization, status updates | 12 |
| [`test_langgraph_workflow.py`](file:///E:/sahayavaani/backend/tests/test_langgraph_workflow.py) | End-to-end multi-turn conversation DAG, state checkpointer, session continuity | 12 |
| [`test_orchestrator.py`](file:///E:/sahayavaani/backend/tests/test_orchestrator.py) | WebSocket protocol events, VAD buffer trigger, transcript streaming, error recovery | 12 |
| **Total** | **Comprehensive Full-Stack Coverage** | **102 Tests (100% Green)** |

### Running the Test Suite Locally

```bash
# Run all 102 tests
pytest -c backend/pytest.ini backend/tests -v

# Run with execution summary
pytest -c backend/pytest.ini backend/tests -q
# Output: 102 passed in ~1.6s
```

### GitHub Actions CI Workflow

The repository includes a ready-to-run GitHub Actions workflow (`.github/workflows/ci.yml`) that automatically executes:
1. **Matrix Test Suite (Python 3.11 & 3.12)**: Installs dependencies and runs all 102 pytest cases with JUnit XML reporting.
2. **Frontend Build & Validation**: Tests React 19 + Vite bundle compilation (`npm run build`).
3. **CI Status Badges**: Emits standard GitHub status checks on pull requests and commits.

---

## License

MIT © 2026 SahayaVaani Project
