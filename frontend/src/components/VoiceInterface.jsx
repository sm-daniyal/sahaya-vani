import { useState, useRef, useCallback, useEffect } from 'react'
import {
  IconCross,
  IconCalendar,
  IconFileText,
  IconMic,
  IconClose,
  IconPause,
  IconRefresh,
  IconShield,
} from './Icons.jsx'

const SAMPLE_RATE = 16000
const FRAME_BYTES = 1024 // 512 int16 samples per frame

export default function VoiceInterface({
  backendWs,
  onTranscript,
  onStateChange,
  onSessionStart,
  onSessionEnd,
  transcriptLines = [],
}) {
  const [status, setStatus] = useState('idle') // idle | connecting | active | error
  const [micAllowed, setMicAllowed] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)
  const [volume, setVolume] = useState(0) // 0-100
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false)

  const wsRef = useRef(null)
  const audioCtxRef = useRef(null)
  const sourceRef = useRef(null)
  const processorRef = useRef(null)
  const streamRef = useRef(null)
  const nextPlayTimeRef = useRef(0)
  const activeSourcesRef = useRef([])
  const isAgentSpeakingRef = useRef(false)
  const sessionIdRef = useRef(null)

  // ── Single AudioContext instance getter ─────────────────────────────────────
  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      audioCtxRef.current = new AudioCtx({ sampleRate: SAMPLE_RATE })
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume()
    }
    return audioCtxRef.current
  }, [])

  // ── Audio playback queue ───────────────────────────────────────────────────
  const schedulePlayback = useCallback(
    (arrayBuffer) => {
      if (!arrayBuffer || arrayBuffer.byteLength === 0) return
      const ctx = getAudioContext()
      if (!ctx) return

      let offset = 0
      if (arrayBuffer.byteLength >= 44) {
        const view = new DataView(arrayBuffer)
        if (
          view.getUint8(0) === 0x52 && // 'R'
          view.getUint8(1) === 0x49 && // 'I'
          view.getUint8(2) === 0x46 && // 'F'
          view.getUint8(3) === 0x46 // 'F'
        ) {
          offset = 44
        }
      }

      const pcmBytes = arrayBuffer.byteLength - offset
      const sampleCount = Math.floor(pcmBytes / 2)
      if (sampleCount <= 0) return

      isAgentSpeakingRef.current = true
      setIsAgentSpeaking(true)

      const int16 = new Int16Array(arrayBuffer, offset, sampleCount)
      const float32 = new Float32Array(sampleCount)
      for (let i = 0; i < sampleCount; i++) {
        float32[i] = int16[i] / 32768.0
      }

      const audioBuffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE)
      audioBuffer.copyToChannel(float32, 0)

      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)

      const currentTime = ctx.currentTime
      const startTime = Math.max(currentTime, nextPlayTimeRef.current)
      source.start(startTime)
      nextPlayTimeRef.current = startTime + audioBuffer.duration

      activeSourcesRef.current.push(source)
      source.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source)
        if (activeSourcesRef.current.length === 0) {
          isAgentSpeakingRef.current = false
          setIsAgentSpeaking(false)
          nextPlayTimeRef.current = ctx.currentTime
        }
      }
    },
    [getAudioContext]
  )

  // ── Start Call ─────────────────────────────────────────────────────────────
  const startCall = useCallback(async () => {
    setStatus('connecting')
    setErrorMsg(null)

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
        },
      })
      setMicAllowed(true)
      streamRef.current = stream
    } catch (err) {
      setMicAllowed(false)
      setStatus('error')
      setErrorMsg('Microphone access denied. Please grant microphone permissions and retry.')
      return
    }

    const ctx = getAudioContext()
    if (ctx.state === 'suspended') {
      await ctx.resume()
    }
    nextPlayTimeRef.current = ctx.currentTime

    const sessionId = crypto.randomUUID()
    sessionIdRef.current = sessionId
    const ws = new WebSocket(`${backendWs}/ws/call/${sessionId}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('active')
      onSessionStart?.(sessionId)
      startCapture(ctx, stream, ws)
    }

    ws.onmessage = (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        schedulePlayback(evt.data)
      } else {
        try {
          const msg = JSON.parse(evt.data)
          handleServerEvent(msg)
        } catch (e) {
          /* ignore */
        }
      }
    }

    ws.onclose = () => {
      setStatus('idle')
      stopCapture(false)
      onSessionEnd?.()
    }

    ws.onerror = () => {
      setStatus('error')
      setErrorMsg('WebSocket connection failed. Verify the backend server is running.')
    }
  }, [backendWs, getAudioContext, onSessionStart, onSessionEnd, schedulePlayback])

  // ── Stop Call ──────────────────────────────────────────────────────────────
  const stopCall = useCallback(() => {
    wsRef.current?.close()
    stopCapture(true)
    setStatus('idle')
  }, [])

  // ── Audio capture ──────────────────────────────────────────────────────────
  const startCapture = useCallback((ctx, stream, ws) => {
    const source = ctx.createMediaStreamSource(stream)
    sourceRef.current = source

    const bufferSize = FRAME_BYTES
    const processor = ctx.createScriptProcessor(bufferSize, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (evt) => {
      if (ws.readyState !== WebSocket.OPEN) return

      if (isAgentSpeakingRef.current) {
        setVolume(0)
        return
      }

      const rawFloat32 = evt.inputBuffer.getChannelData(0)

      let float32 = rawFloat32
      const actualRate = ctx.sampleRate
      if (actualRate !== SAMPLE_RATE) {
        const ratio = actualRate / SAMPLE_RATE
        const resampledLength = Math.floor(rawFloat32.length / ratio)
        const resampled = new Float32Array(resampledLength)
        for (let i = 0; i < resampledLength; i++) {
          const start = Math.floor(i * ratio)
          const end = Math.floor((i + 1) * ratio)
          let sum = 0
          for (let j = start; j < end; j++) sum += rawFloat32[j]
          const span = Math.max(1, end - start)
          resampled[i] = sum / span
        }
        float32 = resampled
      }

      const rms = Math.sqrt(float32.reduce((s, v) => s + v * v, 0) / float32.length)
      setVolume(Math.min(100, Math.round(rms * 400)))

      const int16 = new Int16Array(float32.length)
      for (let i = 0; i < float32.length; i++) {
        const clamped = Math.max(-1, Math.min(1, float32[i]))
        int16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767
      }

      ws.send(int16.buffer)
    }

    source.connect(processor)
    processor.connect(ctx.destination)
  }, [])

  const stopCapture = useCallback((abortPlayback = false) => {
    processorRef.current?.disconnect()
    processorRef.current = null
    sourceRef.current?.disconnect()
    sourceRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null

    if (abortPlayback) {
      activeSourcesRef.current.forEach((s) => {
        try {
          s.stop()
        } catch (e) {}
      })
      activeSourcesRef.current = []
      nextPlayTimeRef.current = 0
      isAgentSpeakingRef.current = false
      setIsAgentSpeaking(false)
    }
    setVolume(0)
  }, [])

  // ── Handle JSON events from server ─────────────────────────────────────────
  const handleServerEvent = useCallback(
    (msg) => {
      switch (msg.type) {
        case 'transcript':
          if (msg.text) {
            onTranscript?.({
              speaker: 'patient',
              text: msg.text,
              confidence: msg.confidence,
              is_final: msg.is_final,
            })
          }
          break
        case 'agent_response':
          isAgentSpeakingRef.current = true
          setIsAgentSpeaking(true)
          if (msg.text) {
            onTranscript?.({ speaker: 'agent', text: msg.text })
          }
          break
        case 'listening':
          if (msg.status === 'start') {
            const ctx = audioCtxRef.current
            const remainingSec = ctx ? Math.max(0, nextPlayTimeRef.current - ctx.currentTime) : 0
            if (remainingSec <= 0.2 || activeSourcesRef.current.length === 0) {
              isAgentSpeakingRef.current = false
              setIsAgentSpeaking(false)
            }
          }
          break
        case 'tts_done': {
          const ctx = audioCtxRef.current
          const remainingMs = ctx ? Math.max(0, (nextPlayTimeRef.current - ctx.currentTime) * 1000) + 150 : 150
          if (activeSourcesRef.current.length === 0 || remainingMs <= 150) {
            isAgentSpeakingRef.current = false
            setIsAgentSpeaking(false)
          } else {
            // Safety timeout guarantees microphone is unblocked as soon as audio stream finishes
            setTimeout(() => {
              if (activeSourcesRef.current.length === 0 || (ctx && ctx.currentTime >= nextPlayTimeRef.current - 0.1)) {
                isAgentSpeakingRef.current = false
                setIsAgentSpeaking(false)
              }
            }, remainingMs)
          }
          break
        }
        case 'state_change':
          onStateChange?.(msg.node)
          break
        case 'session_end':
          onSessionEnd?.()
          break
        default:
          break
      }
    },
    [onTranscript, onStateChange, onSessionEnd]
  )

  useEffect(() => () => stopCall(), [stopCall])

  const latestTurns = transcriptLines.slice(-4)

  return (
    <div className="terminal-card card">
      {/* ── Terminal Header ─────────────────────────────────────────────────── */}
      <div className="terminal-header">
        <div>
          <h2 className="terminal-title">Hospital Voice Terminal</h2>
          <p className="terminal-subtitle">Real-time bilingual voice interface for patient triage & scheduling</p>
        </div>

        <div className="terminal-status-badge-container">
          <span className={`status-badge-pill status-${status}`}>
            <span className={`status-dot ${status === 'active' ? (isAgentSpeaking ? 'dot-agent' : 'dot-listening') : ''}`} />
            {status === 'idle' && 'Terminal Ready'}
            {status === 'connecting' && 'Connecting Audio...'}
            {status === 'active' && (isAgentSpeaking ? 'Agent Speaking' : 'Listening (Live Mic)')}
            {status === 'error' && 'Error'}
          </span>
        </div>
      </div>

      {/* ── Visualizer & Audio Arena ──────────────────────────────────────── */}
      <div className={`terminal-visualizer-box ${status === 'active' ? 'box-active' : ''}`}>
        <div className={`terminal-glow ${status === 'active' ? (isAgentSpeaking ? 'glow-agent' : 'glow-patient') : ''}`} />

        <div className="terminal-pillars">
          <div
            className="terminal-pillar pillar-side"
            style={{
              transform: `scaleY(${status === 'active' ? 1 + (volume / 100) * 0.9 : 0.6})`,
            }}
          />
          <div
            className="terminal-pillar pillar-center"
            style={{
              transform: `scaleY(${status === 'active' ? 1 + (volume / 100) * 1.4 : 0.8})`,
            }}
          />
          <div
            className="terminal-pillar pillar-side"
            style={{
              transform: `scaleY(${status === 'active' ? 1 + (volume / 100) * 0.8 : 0.6})`,
            }}
          />
        </div>

        <div className="terminal-visualizer-caption">
          {status === 'idle' && 'Click Start Session to open the voice reception channel'}
          {status === 'connecting' && 'Establishing WebSocket & audio pipeline...'}
          {status === 'active' &&
            (isAgentSpeaking
              ? 'SahayaVaani synthesized voice streaming...'
              : volume > 10
              ? 'Hearing speech · Voice Activity Detected'
              : 'Listening · Speak naturally in Kannada or English')}
        </div>
      </div>

      {/* ── Audio Level Meter ────────────────────────────────────────────── */}
      <div className="audio-meter-row">
        <span className="meter-label">Microphone RMS</span>
        <div className="audio-meter-track">
          <div
            className="audio-meter-bar"
            style={{
              width: `${volume}%`,
              background: volume > 70 ? 'var(--red)' : volume > 35 ? 'var(--amber)' : 'var(--emerald-500)',
            }}
          />
        </div>
        <span className="meter-val">{volume}%</span>
      </div>

      {/* ── Primary Action Controls ──────────────────────────────────────── */}
      <div className="terminal-controls-row">
        {status === 'idle' && (
          <button className="terminal-btn btn-start-call" onClick={startCall}>
            <IconMic className="w-4 h-4 text-white inline mr-2" />
            Start Voice Session
          </button>
        )}

        {status === 'connecting' && (
          <button className="terminal-btn btn-connecting" disabled>
            Connecting to Audio Gateway...
          </button>
        )}

        {status === 'active' && (
          <button className="terminal-btn btn-end-call" onClick={stopCall}>
            <IconClose className="w-4 h-4 text-white inline mr-2" />
            Disconnect Session
          </button>
        )}

        {status === 'error' && (
          <button className="terminal-btn btn-start-call" onClick={startCall}>
            <IconRefresh className="w-4 h-4 text-white inline mr-2" />
            Retry Voice Connection
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="terminal-error-alert">
          <span>{errorMsg}</span>
          <button className="alert-retry-btn" onClick={startCall}>Retry</button>
        </div>
      )}

      {micAllowed === false && (
        <div className="terminal-warn-alert">
          Microphone access is blocked by the browser. Please allow microphone access in site permissions and refresh.
        </div>
      )}

      {/* ── Quick Department Triage Shortcuts ────────────────────────────── */}
      <div className="triage-shortcuts-section">
        <div className="shortcuts-title">Supported Clinical Routing</div>
        <div className="shortcuts-grid">
          <div className="shortcut-chip" onClick={status === 'idle' ? startCall : undefined}>
            <IconCross className="w-3.5 h-3.5 text-emerald" />
            <span>Emergency Triage</span>
          </div>
          <div className="shortcut-chip" onClick={status === 'idle' ? startCall : undefined}>
            <IconCalendar className="w-3.5 h-3.5 text-emerald" />
            <span>Cardiology OPD</span>
          </div>
          <div className="shortcut-chip" onClick={status === 'idle' ? startCall : undefined}>
            <IconCalendar className="w-3.5 h-3.5 text-emerald" />
            <span>Radiology (CT / MRI)</span>
          </div>
          <div className="shortcut-chip" onClick={status === 'idle' ? startCall : undefined}>
            <IconFileText className="w-3.5 h-3.5 text-emerald" />
            <span>General Medicine</span>
          </div>
        </div>
      </div>

      {/* ── Live Active Speech Dialogue ──────────────────────────────────── */}
      {status === 'active' && (
        <div className="live-stream-box">
          <div className="live-stream-header">
            <span className="live-stream-title">Active Speech Stream</span>
            <span className="live-pill">Live</span>
          </div>
          <div className="live-stream-content">
            {latestTurns.length === 0 ? (
              <p className="stream-placeholder">Listening for incoming speech in Kannada or English...</p>
            ) : (
              latestTurns.map((turn, i) => (
                <div
                  key={i}
                  className={`stream-row ${turn.speaker === 'agent' ? 'row-agent' : 'row-patient'}`}
                >
                  <span className="stream-speaker">
                    {turn.speaker === 'agent' ? 'SahayaVaani: ' : 'Patient: '}
                  </span>
                  <span className="stream-text">{turn.text}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
