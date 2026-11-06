import { IconCalendar, IconFileText } from './Icons.jsx'

/**
 * EMRTable
 * Live appointment table updated in real time via WebSocket.
 */
export default function EMRTable({ appointments, flashedIds }) {
  const statusConfig = {
    confirmed:  { label: 'Confirmed',  cls: 'badge-green'  },
    pending:    { label: 'Pending',    cls: 'badge-yellow' },
    escalated:  { label: 'Escalated', cls: 'badge-red'    },
    cancelled:  { label: 'Cancelled', cls: 'badge-gray'   },
  }

  const formatDate = (d) => {
    if (!d) return '—'
    try {
      return new Date(d).toLocaleDateString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
      })
    } catch { return d }
  }

  return (
    <div className="emr-table-wrapper card">
      <div className="card-title-row">
        <div className="title-with-icon">
          <IconCalendar className="w-5 h-5 text-emerald" />
          <h2 className="card-title">EMR Appointments</h2>
        </div>
        <span className="record-count">{appointments.length} record{appointments.length !== 1 ? 's' : ''}</span>
      </div>

      {appointments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon-wrapper">
            <IconFileText className="w-8 h-8 text-muted" />
          </div>
          <p className="empty-title">No appointments registered yet</p>
          <p className="empty-sub">Start a voice session to schedule a patient consultation.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="emr-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Patient</th>
                <th>Department</th>
                <th>Date</th>
                <th>Time</th>
                <th>Phone</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appt) => (
                <tr
                  key={appt.id}
                  className={flashedIds.has(appt.id) ? 'row-flash' : ''}
                >
                  <td className="col-id">#{appt.id}</td>
                  <td className="col-name">{appt.patient_name || '—'}</td>
                  <td className="col-dept">
                    <span className="dept-badge">{appt.department || '—'}</span>
                  </td>
                  <td className="col-date">{formatDate(appt.date)}</td>
                  <td className="col-time">{appt.time || '—'}</td>
                  <td className="col-phone">{appt.phone || '—'}</td>
                  <td className="col-status">
                    <span className={`badge ${statusConfig[appt.status]?.cls || 'badge-gray'}`}>
                      {statusConfig[appt.status]?.label || appt.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
