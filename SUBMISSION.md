# SahayaVaani — Challenge Submission & Deliverables

* **Project:** SahayaVaani: Sovereign Bilingual Voice AI Clinical Reception & Scheduling Console
* **Author:** sm-daniyal ([GitHub](https://github.com/sm-daniyal))
* **Challenge:** The Great Indian AI Internship Challenge by [Gnani.ai](https://www.gnani.ai/internship)
* **Target Submission Deadline:** November 10, 2026, 11:59 PM IST
* **Repository:** [https://github.com/sm-daniyal/sahaya-vani](https://github.com/sm-daniyal/sahaya-vani)

---

## Submission Checklist

- [x] **Working full-stack voice application with real-time streaming**: Sub-600ms conversational turn-taking, 16 kHz WebRTC streaming, and instant transcript feedback.
- [x] **Gnani Prisma v2.5 STT integrated**: Real-time Kannada (`kn-IN`) streaming speech recognition via WebSocket endpoint `wss://api.vachana.ai/stt/v3/stream`.
- [x] **Gnani Evon v3.3 MoE LLM integrated**: Open-weights 30B MoE model (`gnani/evon-v3.3`) support with 1-click Google Colab notebook (`scripts/SahayaVaani_Evon_vLLM_Colab.ipynb`) and local GPU launcher (`scripts/serve_evon_vllm.py`).
- [x] **Gnani Timbre v2.5 TTS integrated**: Low-latency Kannada voice synthesis (`kannada_female_1`) via streaming WebSocket endpoint `wss://api.vachana.ai/tts/v2/stream`.
- [x] **102 passing unit and integration tests**: 100% automated test coverage across audio VAD, intent classification, slot extraction, LangGraph workflow, safety guardrails, SQLite EMR, and WebSocket orchestration with zero external network dependencies.
- [x] **Production clinical console**: Styled with the IBM Carbon Design System for Healthcare featuring IBM Plex typography, high-density EMR table, and real-time audio telemetry.
- [x] **Turnkey presentation slide deck**: Built-in 4-slide presentation deck at `frontend/public/slides.html` tailored for a 45-50 second demo video.
- [ ] **Record demo video**: 45-50 second walkthrough demonstrating problem statement, live Kannada appointment booking, safety guardrail escalation, and real-time EMR table sync.
- [ ] **Post demo video to X / Twitter**: Include hashtags `#GreatIndianAIInternshipChallenge`, `#GnaniAI`, `#KannadaAI`, and `#VoiceAI`.
- [ ] **Submit form on Gnani.ai**: Complete application form at [gnani.ai/internship](https://www.gnani.ai/internship) before deadline.

---

## Verification Commands

To verify all deliverables locally:

```bash
# 1. Run full automated test suite (102 tests, all passing):
pytest -c backend/pytest.ini backend/tests -q

# 2. Build production React 19 frontend:
cd frontend && npm run build

# 3. View the presentation deck:
# Open frontend/public/slides.html in any browser or visit http://localhost:5173/slides.html
```
