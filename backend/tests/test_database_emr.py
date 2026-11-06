"""
Unit tests for SQLite EMR Database Operations.
Tests appointment booking, status updates, doctor handoffs, and serialization.
"""
import pytest
from sqlalchemy.future import select
from database import Appointment, HumanHandoff


class TestDatabaseEMR:
    @pytest.mark.asyncio
    async def test_create_appointment_basic(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(
                patient_name="Ramesh Kumar",
                department="Cardiology",
                date="2026-11-10",
                time="10:00",
                status="confirmed",
            )
            session.add(appt)
            await session.commit()
            await session.refresh(appt)

            assert appt.id is not None
            assert appt.patient_name == "Ramesh Kumar"
            assert appt.department == "Cardiology"
            assert appt.status == "confirmed"

    @pytest.mark.asyncio
    async def test_create_appointment_with_session_and_phone(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(
                patient_name="Daniyal",
                department="Orthopedics",
                phone="9876543210",
                session_id="sess-xyz-123",
                status="confirmed",
            )
            session.add(appt)
            await session.commit()
            await session.refresh(appt)

            assert appt.phone == "9876543210"
            assert appt.session_id == "sess-xyz-123"

    @pytest.mark.asyncio
    async def test_appointment_to_dict_format(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(
                patient_name="Ananya Sharma",
                department="Dermatology",
                date="2026-11-12",
                time="14:30",
            )
            session.add(appt)
            await session.commit()
            await session.refresh(appt)

            d = appt.to_dict()
            assert isinstance(d, dict)
            assert d["id"] == appt.id
            assert d["patient_name"] == "Ananya Sharma"
            assert d["created_at"] is not None

    @pytest.mark.asyncio
    async def test_query_appointment_by_id(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(patient_name="Deepak", department="ENT")
            session.add(appt)
            await session.commit()
            appt_id = appt.id

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            fetched = result.scalar_one_or_none()
            assert fetched is not None
            assert fetched.patient_name == "Deepak"

    @pytest.mark.asyncio
    async def test_update_appointment_status_confirmed(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(patient_name="Kiran", department="General", status="pending")
            session.add(appt)
            await session.commit()
            appt_id = appt.id

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            target = result.scalar_one()
            target.status = "confirmed"
            await session.commit()

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            assert result.scalar_one().status == "confirmed"

    @pytest.mark.asyncio
    async def test_cancel_appointment(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(patient_name="Lata", department="Gynecology", status="confirmed")
            session.add(appt)
            await session.commit()
            appt_id = appt.id

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            target = result.scalar_one()
            target.status = "cancelled"
            await session.commit()

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            assert result.scalar_one().status == "cancelled"

    @pytest.mark.asyncio
    async def test_flag_human_handoff_with_appointment(self, async_test_db):
        async with async_test_db() as session:
            appt = Appointment(patient_name="Vijay", department="Cardiology")
            session.add(appt)
            await session.commit()

            handoff = HumanHandoff(
                appointment_id=appt.id,
                session_id="sess-handoff-1",
                reason="Patient asked for dosage advice",
                transcript="Patient: how much paracetamol to take?",
            )
            session.add(handoff)
            await session.commit()
            await session.refresh(handoff)

            assert handoff.id is not None
            assert handoff.appointment_id == appt.id
            assert "dosage" in handoff.reason
            assert "paracetamol" in handoff.transcript

    @pytest.mark.asyncio
    async def test_flag_standalone_human_handoff(self, async_test_db):
        async with async_test_db() as session:
            handoff = HumanHandoff(
                appointment_id=None,
                session_id="sess-handoff-standalone",
                reason="Emergency chest pain inquiry",
            )
            session.add(handoff)
            await session.commit()
            await session.refresh(handoff)

            assert handoff.id is not None
            assert handoff.appointment_id is None

    @pytest.mark.asyncio
    async def test_handoff_to_dict_format(self, async_test_db):
        async with async_test_db() as session:
            handoff = HumanHandoff(
                session_id="sess-dict-test",
                reason="Medical diagnosis query",
            )
            session.add(handoff)
            await session.commit()
            await session.refresh(handoff)

            d = handoff.to_dict()
            assert d["id"] == handoff.id
            assert d["reason"] == "Medical diagnosis query"
            assert d["flagged_at"] is not None

    @pytest.mark.asyncio
    async def test_query_all_appointments_sorted(self, async_test_db):
        async with async_test_db() as session:
            session.add(Appointment(patient_name="P1", department="D1"))
            session.add(Appointment(patient_name="P2", department="D2"))
            session.add(Appointment(patient_name="P3", department="D3"))
            await session.commit()

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).order_by(Appointment.id.desc()))
            all_appts = result.scalars().all()
            assert len(all_appts) == 3
            assert all_appts[0].patient_name == "P3"
            assert all_appts[2].patient_name == "P1"

    @pytest.mark.asyncio
    async def test_appointment_transcript_persistence(self, async_test_db):
        transcript_text = "Agent: Namaskara\nPatient: Need cardiologist\nAgent: Confirmed"
        async with async_test_db() as session:
            appt = Appointment(
                patient_name="Sanjay",
                department="Cardiology",
                transcript=transcript_text,
            )
            session.add(appt)
            await session.commit()
            appt_id = appt.id

        async with async_test_db() as session:
            result = await session.execute(select(Appointment).where(Appointment.id == appt_id))
            assert result.scalar_one().transcript == transcript_text

    @pytest.mark.asyncio
    async def test_empty_database_returns_empty_list(self, async_test_db):
        async with async_test_db() as session:
            result = await session.execute(select(Appointment))
            assert result.scalars().all() == []
