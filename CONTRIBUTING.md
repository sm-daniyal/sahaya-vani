# Contributing to SahayaVaani

Thank you for your interest in contributing to SahayaVaani, a sovereign bilingual clinical voice AI receptionist for Indian healthcare.

---

## 1. Development Principles

- **Zero Hallucination Tolerance**: Clinical triage and appointment routing must be deterministic. Never allow the LLM to make unsupervised prescription or diagnostic claims.
- **Vernacular First**: Spoken Kannada (`kn-IN`) and code-mixed Kanglish are primary citizen interfaces, not secondary translations.
- **Strict Isolated Testing**: All unit and workflow tests must run in 100% network isolation without requiring live external API tokens or GPU hardware.

---

## 2. Local Setup & Verification

1. **Clone & Virtual Environment**:
   ```bash
   git clone https://github.com/sm-daniyal/sahaya-vani.git
   cd sahaya-vani
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Run Test Suite**:
   Before submitting any pull request or commit, ensure all 102 tests pass:
   ```bash
   pytest -c backend/pytest.ini backend/tests -v
   ```

3. **Frontend Build Verification**:
   ```bash
   cd ../frontend
   npm install
   npm run build
   ```

---

## 3. Pull Request Guidelines

- Branch names should be descriptive (e.g. `feat/kannada-dialects`, `fix/vad-edge-cases`).
- Atomic commits following conventional commit syntax (`feat:`, `fix:`, `docs:`, `chore:`).
- Document all new environment configuration keys in `backend/.env.example`.

---

## 4. Code Style & Standards

- **Python**: Follow PEP 8 guidelines. Type annotations are required on all service and LangGraph node functions.
- **React / JavaScript**: Functional components with hooks. Styling follows the **IBM Carbon Design System for Healthcare** using `--cds-*` tokens.
- **Emoji Free Policy**: Maintain technical documentation integrity with zero emojis in code comments, commit messages, or user-facing UI components.

---

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
