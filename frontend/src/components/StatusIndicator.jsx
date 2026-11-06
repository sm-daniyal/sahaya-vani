import { IconUser, IconBrain, IconShield, IconFileText, IconCheck, IconCross } from './Icons.jsx'

/**
 * StatusIndicator
 * Visual stepper showing the current state machine node using clean SVGs.
 */
const STEPS = [
  { key: 'greeting',          label: 'Greeting',    Icon: IconUser },
  { key: 'intent_classifier', label: 'Classifying', Icon: IconBrain },
  { key: 'safety_check',      label: 'Safety Check',Icon: IconShield },
  { key: 'slot_filling',      label: 'Slot Filling', Icon: IconFileText },
  { key: 'confirm_booking',   label: 'Confirming',  Icon: IconCheck },
  { key: 'escalate_human',    label: 'Escalated',   Icon: IconCross },
]

export default function StatusIndicator({ currentNode }) {
  const activeIdx = STEPS.findIndex(s => s.key === currentNode)

  return (
    <div className="status-indicator card">
      <div className="card-title-row">
        <h2 className="card-title">Processing Pipeline</h2>
        {currentNode && <span className="active-node-tag">{currentNode}</span>}
      </div>
      <div className="stepper">
        {STEPS.map((step, idx) => {
          let cls = 'step-idle'
          if (idx < activeIdx)       cls = 'step-done'
          if (idx === activeIdx)     cls = 'step-active'
          if (step.key === 'escalate_human' && idx === activeIdx) cls = 'step-escalated'

          const StepIcon = step.Icon

          return (
            <div key={step.key} className={`step ${cls}`}>
              <div className="step-icon">
                <StepIcon className="w-4 h-4" />
              </div>
              <div className="step-label">{step.label}</div>
              {idx < STEPS.length - 1 && <div className="step-connector" />}
            </div>
          )
        })}
      </div>

      {!currentNode && (
        <p className="status-hint">Initiate a voice interaction to trace live state transitions.</p>
      )}
    </div>
  )
}
