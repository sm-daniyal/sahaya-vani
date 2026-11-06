"""
SahayaVaani — SQLite EMR Database Layer
Uses SQLAlchemy async (aiosqlite driver).
"""
import asyncio
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float,
    ForeignKey, func, event
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.future import select

from config import settings


# ── ORM Base ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Appointment(Base):
    """Mock EMR appointment record."""
    __tablename__ = "appointments"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    patient_name  = Column(String(120), nullable=False)
    phone         = Column(String(20), nullable=True)
    department    = Column(String(80), nullable=False, default="General")
    date          = Column(String(20), nullable=True)   # ISO date string
    time          = Column(String(20), nullable=True)   # HH:MM
    status        = Column(String(20), nullable=False, default="pending")
    # status values: pending | confirmed | escalated | cancelled
    transcript    = Column(Text, nullable=True)
    session_id    = Column(String(64), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    handoffs = relationship("HumanHandoff", back_populates="appointment", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "patient_name": self.patient_name,
            "phone":        self.phone,
            "department":   self.department,
            "date":         self.date,
            "time":         self.time,
            "status":       self.status,
            "transcript":   self.transcript,
            "session_id":   self.session_id,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "updated_at":   self.updated_at.isoformat() if self.updated_at else None,
        }


class HumanHandoff(Base):
    """Records where the agent escalated to a human doctor."""
    __tablename__ = "human_handoffs"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    session_id     = Column(String(64), nullable=True)
    reason         = Column(Text, nullable=True)
    transcript     = Column(Text, nullable=True)
    flagged_at     = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="handoffs")

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "appointment_id": self.appointment_id,
            "session_id":     self.session_id,
            "reason":         self.reason,
            "transcript":     self.transcript,
            "flagged_at":     self.flagged_at.isoformat() if self.flagged_at else None,
        }


# ── Engine & Session Factory ───────────────────────────────────────────────────

engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables (called on FastAPI startup)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── CRUD helpers ───────────────────────────────────────────────────────────────

async def create_appointment(
    *,
    patient_name: str,
    phone: Optional[str] = None,
    department: str = "General",
    date: Optional[str] = None,
    time: Optional[str] = None,
    status: str = "confirmed",
    transcript: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Appointment:
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            patient_name=patient_name,
            phone=phone,
            department=department,
            date=date,
            time=time,
            status=status,
            transcript=transcript,
            session_id=session_id,
        )
        session.add(appt)
        await session.commit()
        await session.refresh(appt)
        return appt


async def update_appointment(
    appointment_id: int,
    **kwargs,
) -> Optional[Appointment]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appt = result.scalar_one_or_none()
        if appt is None:
            return None
        for key, value in kwargs.items():
            if hasattr(appt, key):
                setattr(appt, key, value)
        appt.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(appt)
        return appt


async def get_appointments(limit: int = 100) -> List[Appointment]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment).order_by(Appointment.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def get_appointment(appointment_id: int) -> Optional[Appointment]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        return result.scalar_one_or_none()


async def flag_for_handoff(
    *,
    session_id: str,
    appointment_id: Optional[int] = None,
    reason: str = "Patient asked for medical advice",
    transcript: Optional[str] = None,
) -> HumanHandoff:
    async with AsyncSessionLocal() as session:
        handoff = HumanHandoff(
            appointment_id=appointment_id,
            session_id=session_id,
            reason=reason,
            transcript=transcript,
        )
        session.add(handoff)
        await session.commit()
        await session.refresh(handoff)
        return handoff


async def get_handoffs(limit: int = 50) -> List[HumanHandoff]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(HumanHandoff).order_by(HumanHandoff.flagged_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
