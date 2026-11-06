"""
SahayaVaani — Seed SQLite EMR with sample data
Run: python scripts/seed_db.py  (from the backend/ directory)
"""
import asyncio
import sys
import os

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Allow running from project root or scripts/ dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import init_db, create_appointment, flag_for_handoff


SAMPLE_APPOINTMENTS = [
    {
        "patient_name": "Ramesh Kumar",
        "phone":        "9845012345",
        "department":   "Cardiology",
        "date":         "2026-11-10",
        "time":         "10:30",
        "status":       "confirmed",
        "transcript":   "Nange cardiology appointment beeku next week somavaara beligge.",
        "session_id":   "seed-001",
    },
    {
        "patient_name": "Priya Nair",
        "phone":        "9900123456",
        "department":   "Orthopedics",
        "date":         "2026-11-12",
        "time":         "14:00",
        "status":       "confirmed",
        "transcript":   "Orthopedics appointment budhawaara mdhyaahna beeku.",
        "session_id":   "seed-002",
    },
    {
        "patient_name": "Suresh Gowda",
        "phone":        "8123456789",
        "department":   "General Medicine",
        "date":         "2026-11-08",
        "time":         "09:00",
        "status":       "escalated",
        "transcript":   "Nange chest pain aagutte, enu medicine tagonali?",
        "session_id":   "seed-003",
    },
]


async def main():
    print("Initialising database...")
    await init_db()

    print("Seeding appointments...")
    for data in SAMPLE_APPOINTMENTS:
        appt = await create_appointment(**data)
        print(f"  ✓ Created appointment #{appt.id}: {appt.patient_name} → {appt.department}")

        if data["status"] == "escalated":
            handoff = await flag_for_handoff(
                session_id=data["session_id"],
                appointment_id=appt.id,
                reason="Patient asked for medical advice during call",
                transcript=data["transcript"],
            )
            print(f"    ⚠ Flagged for human handoff #{handoff.id}")

    print("\n✅ Database seeded successfully!")
    print(f"   Total appointments: {len(SAMPLE_APPOINTMENTS)}")


if __name__ == "__main__":
    asyncio.run(main())
