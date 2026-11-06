import { useEffect, useRef } from 'react'
import { IconUser, IconBot } from './Icons.jsx'

/**
 * TranscriptPanel
 * Live conversation log with speech bubbles and speaker attribution.
 */
export default function TranscriptPanel({ lines }) {
  const bottomRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div className="transcript-panel card">
      <div className="card-title-row">
        <h2 className="card-title">Live Transcript</h2>
        <span className="transcript-count">{lines.length} turn{lines.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="transcript-scroll">
        {lines.length === 0 ? (
          <div className="transcript-empty">
            <p className="empty-title">Transcript will appear here in real time</p>
            <p className="empty-sub">Patient speech and voice responses stream live.</p>
          </div>
        ) : (
          lines.map((line, idx) => (
            <div
              key={idx}
              className={`transcript-bubble ${line.speaker === 'agent' ? 'bubble-agent' : 'bubble-patient'}`}
            >
              <div className="bubble-header">
                <span className="bubble-speaker">
                  {line.speaker === 'agent' ? (
                    <span className="speaker-tag agent-tag">
                      <IconBot className="w-3.5 h-3.5 inline mr-1" /> Assistant
                    </span>
                  ) : (
                    <span className="speaker-tag patient-tag">
                      <IconUser className="w-3.5 h-3.5 inline mr-1" /> Patient
                    </span>
                  )}
                </span>
                {line.confidence !== undefined && (
                  <span className="bubble-confidence" title="STT Confidence">
                    {Math.round(line.confidence * 100)}%
                  </span>
                )}
              </div>
              <p className="bubble-text">{line.text}</p>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
