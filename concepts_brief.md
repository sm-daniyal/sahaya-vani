# IBM Carbon for Healthcare Frontend Redesign

* **Author:** sm-daniyal
* **Date:** 2026-11-07
* **Status:** Proposed Concept Brief (EGM Brainstorm)

## Overview

This specification details the frontend redesign of SahayaVaani from a generic prototype layout to an enterprise-grade clinical console aligned with the **IBM Carbon Design System for Healthcare**. The redesign introduces high-density clinical data structures, standardized IBM Plex typography, crisp architectural surfaces (eliminating soft generic radii), and high-contrast telemetry indicators tailored for hospital receptionists and triage nurses.

---

## Analysis & Architectural Lenses

### 1. Typography & Readability (UX & Ergonomics Lens)
* **Problem**: The current interface uses system Inter with soft proportional numerals, causing jitter in tabular data (timestamps, RMS meter percentages, appointment IDs).
* **Carbon Solution**:
  * **Primary Interface Font**: `IBM Plex Sans` (weights 400, 500, 600) for navigation, micro-headers, patient names, and conversational transcript bubbles.
  * **Telemetry & Tabular Font**: `IBM Plex Mono` (weights 400, 500) for appointment IDs (`#09`), timestamps (`14:30`), VAD latency windows (`550 ms`), and microphone RMS readouts (`45%`). Tabular numeric alignment prevents layout shifts during live speech.

### 2. Clinical Color Tokens & Hierarchy (SRE & Human Factors Lens)
* **Background Shell**: Carbon Gray 10 (`#f4f4f4`) with high-contrast White card tiles (`#ffffff`) bordered by sharp 1px Carbon Gray 20 (`#e0e0e0`).
* **Header Bar**: Dark Carbon Charcoal Shell (`#161616`) or Clean High-Contrast White with a 2px Carbon Blue 60 (`#0f62fe`) top activation stroke, projecting hospital operational authority.
* **Semantic Status Tags**:
  * **Confirmed / Active**: Carbon Green 60 (`#24a148`) on `#defbe6` tag background.
  * **Safety Escalation / Critical**: Carbon Red 60 (`#da1e28`) on `#ffebe8` tag background with bold border contrast.
  * **Pending / Triage**: Carbon Yellow 30 (`#f1c21b`) on `#fcf4d6`.
  * **Interactive Accent**: Carbon Blue 60 (`#0f62fe`) for primary call actions and active nodes.

### 3. High-Density Data Layout (YAGNI & Complexity Lens)
* **Table Architecture**: Replace loose pill cards with Carbon Data Table standards: 48px row heights, uppercase `0.75rem` micro-headers with `letter-spacing: 0.05em`, subtle horizontal dividers, and fixed-width alignment.
* **Audio Telemetry Box**: Replace cartoonish rounded microphone visuals with a technical Carbon Telemetry module: dark panel (`#262626`), real-time decibel/RMS meter in IBM Plex Mono, and linear equalizer indicators.
* **Pipeline Stepper**: Horizontal Carbon Progress Indicator featuring numbered step badges (`01` through `06`) connected by solid Carbon lines.

---

## Goals vs. Non-Goals

### In-Scope Goals
* Import and link official Google Fonts for `IBM Plex Sans` and `IBM Plex Mono` in `index.html`.
* Overhaul `frontend/src/styles/App.css` using IBM Carbon design tokens (colors, spacing, 2px/0px sharp corners, typography).
* Restructure `App.jsx`, `VoiceInterface.jsx`, `EMRTable.jsx`, `StatusIndicator.jsx`, and `TranscriptPanel.jsx` to apply Carbon component semantics.
* Retain 100% backward compatibility with backend WebSocket protocols (`/ws/call` and `/ws/emr`).
* Verify zero layout shifts, verify build passes (`npm run build`), and maintain zero-emoji standard.

### Out-of-Scope Non-Goals
* Adding heavy third-party React component libraries (e.g. `@carbon/react`) that bloat bundle size; we implement the Carbon design system natively via CSS to maintain ultra-fast Vite builds.
* Altering backend LangGraph state machines or SQLite database models.

---

## Key Decisions & Staging for Implementation

1. **Native CSS Implementation**: Utilize CSS custom properties (`--cds-*`) directly in `App.css` rather than pulling in external NPM packages, keeping the frontend fast, lightweight, and dependency-free.
2. **Visual Hierarchy Split**:
   * Left Column (38% width): Voice Telemetry Terminal, Audio Level Monitor, and Live Conversation Feed.
   * Right Column (62% width): Clinical Pipeline Stepper and Live EMR Data Table.
3. **Emergency Escalation Contrast**: Safety escalations must visibly override table rows with a prominent Carbon Red indicator for immediate physician triage visibility.
