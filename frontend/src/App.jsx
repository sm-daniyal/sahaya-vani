import { useState, useEffect, useRef, useCallback } from 'react'
import VoiceInterface from './components/VoiceInterface.jsx'
import EMRTable from './components/EMRTable.jsx'
import TranscriptPanel from './components/TranscriptPanel.jsx'
import StatusIndicator from './components/StatusIndicator.jsx'
import { IconCross, IconCalendar, IconShield, IconBot } from './components/Icons.jsx'

const BACKEND_WS = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8080'

export default function App() {
  const [appointments, setAppointments] = useState([])
  const [transcriptLines, setTranscriptLines] = useState([])
  const [currentNode, setCurrentNode] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [isCallActive, setIsCallActive] = useState(false)
  const [flashedIds, setFlashedIds] = useState(new Set())

  const emrWsRef = useRef(null)

  // ── Load initial appointments ────────────────────────────────────────────────
  const loadAppointments = useCallback(async () => {
    try {
      const res = await fetch('/api/appointments')
      const data = await res.json()
      setAppointments(data)
    } catch (err) {
      console.error('Failed to load appointments:', err)
    }
  }, [])

  // ── EMR live feed WebSocket ──────────────────────────────────────────────────
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(`${BACKEND_WS}/ws/emr`)
      emrWsRef.current = ws

      ws.onopen = () => {
        ws._pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, 20_000)
      }

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'initial_load') {
            setAppointments(msg.appointments)
          } else if (msg.type === 'appointment_created' || msg.type === 'appointment_updated') {
            loadAppointments().then(() => {
              setFlashedIds((prev) => new Set([...prev, msg.appointment_id]))
              setTimeout(() => {
                setFlashedIds((prev) => {
                  const next = new Set(prev)
                  next.delete(msg.appointment_id)
                  return next
                })
              }, 2500)
            })
          }
        } catch (e) {
          /* ignore parse errors */
        }
      }

      ws.onclose = () => {
        clearInterval(ws._pingInterval)
        setTimeout(connect, 3000)
      }

      ws.onerror = (err) => console.error('[EMR WS] Error:', err)
    }

    connect()
    return () => {
      if (emrWsRef.current) {
        clearInterval(emrWsRef.current._pingInterval)
        emrWsRef.current.close()
      }
    }
  }, [loadAppointments])

  // ── Handlers from VoiceInterface ─────────────────────────────────────────────
  const handleTranscript = useCallback((entry) => {
    setTranscriptLines((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].speaker === 'patient' && entry.speaker === 'patient') {
        const next = [...prev]
        next[next.length - 1] = entry
        return next
      }
      return [...prev, entry]
    })
  }, [])

  const handleStateChange = useCallback((node) => {
    setCurrentNode(node)
  }, [])

  const handleSessionStart = useCallback((sid) => {
    setSessionId(sid)
    setIsCallActive(true)
    setTranscriptLines([])
  }, [])

  const handleSessionEnd = useCallback(() => {
    setIsCallActive(false)
    loadAppointments()
  }, [loadAppointments])

  const escalatedCount = appointments.filter((a) => a.status === 'escalated').length
  const confirmedCount = appointments.filter((a) => a.status === 'confirmed').length

  return (
    <div className="app-root">
      {/* ── Official Hospital Header ───────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo-box">
            <IconCross className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="brand-top-tag">Bangalore General Hospital</div>
            <h1 className="brand-title">Clinical Reception & Voice AI Console</h1>
          </div>
        </div>

        <div className="header-meta-group">
          <div className="meta-pill gnani-pill">
            <span className="meta-dot dot-gnani" />
            <span className="meta-text">Gnani AI: Prisma v2.5 · Evon v3.3 · Timbre v2.5</span>
          </div>

          <div className="meta-pill">
            <span className="meta-dot dot-live" />
            <span className="meta-text">Bilingual: Kannada · Kanglish</span>
          </div>

          <div className="meta-pill">
            <span className="meta-text">Telephony: 16 kHz WebRTC VAD</span>
          </div>

          {sessionId && (
            <div className="meta-pill session-pill">
              <span className="meta-text">Session: <code>{sessionId.slice(0, 8)}</code></span>
            </div>
          )}
        </div>
      </header>

      {/* ── KPI Operational Metrics Row ────────────────────────────────────── */}
      <section className="stats-bar">
        <div className="stat-card">
          <div className="stat-icon-wrapper bg-mint">
            <IconCalendar className="w-5 h-5 text-emerald" />
          </div>
          <div>
            <div className="stat-value">{appointments.length}</div>
            <div className="stat-label">Total Appointments ({confirmedCount} Confirmed)</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper bg-amber">
            <IconShield className="w-5 h-5 text-amber" />
          </div>
          <div>
            <div className="stat-value">{escalatedCount}</div>
            <div className="stat-label">Safety Escalations (Physician Handoffs)</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper bg-blue">
            <IconBot className="w-5 h-5 text-blue" />
          </div>
          <div>
            <div className="stat-value">550 ms</div>
            <div className="stat-label">VAD Turn-Taking Response Window</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper bg-mint">
            <span className="online-pulse-dot" />
          </div>
          <div>
            <div className="stat-value">Operational</div>
            <div className="stat-label">LangGraph MemorySaver State Machine</div>
          </div>
        </div>
      </section>

      {/* ── Main Desktop 2-Column Grid ─────────────────────────────────────── */}
      <main className="app-main desktop-grid">
        {/* Left Column: Voice Terminal & Live Transcript */}
        <section className="terminal-column">
          <VoiceInterface
            backendWs={BACKEND_WS}
            onTranscript={handleTranscript}
            onStateChange={handleStateChange}
            onSessionStart={handleSessionStart}
            onSessionEnd={handleSessionEnd}
            transcriptLines={transcriptLines}
          />
          <TranscriptPanel lines={transcriptLines} />
        </section>

        {/* Right Column: AI Pipeline Stepper & Live Clinical EMR Table */}
        <section className="emr-column">
          <StatusIndicator currentNode={currentNode} />
          <EMRTable appointments={appointments} flashedIds={flashedIds} />
        </section>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="app-footer">
        SahayaVaani · Bangalore General Hospital Outpatient Department · Real-time Voice Reception System
      </footer>
    </div>
  )
}
