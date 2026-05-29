"""SQLAlchemy async database layer."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from core.config import settings
from core.logger import logger


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    contact_email = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), index=True, default=settings.default_tenant_id)
    channel = Column(String(32), index=True)  # web | wechat | email
    customer_id = Column(String(128), index=True, nullable=True)
    customer_name = Column(String(128), nullable=True)
    status = Column(String(32), default="active", index=True)  # active|closed|takeover
    current_agent = Column(String(64), nullable=True)
    human_takeover = Column(Integer, default=0)  # 0|1
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    summary = Column(Text, nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role = Column(String(32))  # user | assistant | system | human-agent
    agent_name = Column(String(64), nullable=True)
    content = Column(Text)
    meta = Column(Text, nullable=True)  # JSON-encoded extras
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    session = relationship("Session", back_populates="messages")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), index=True)
    tenant_id = Column(String(64), index=True)
    title = Column(String(256))
    description = Column(Text)
    category = Column(String(64))  # complaint | tech | aftersales | consult
    priority = Column(String(16), default="normal")  # low | normal | high | urgent
    status = Column(String(32), default="open")  # open | in_progress | resolved | closed
    assignee = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), index=True)
    date = Column(String(16), index=True)
    total_sessions = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    resolved = Column(Integer, default=0)
    escalated = Column(Integer, default=0)
    avg_response_time = Column(Float, default=0.0)
    content = Column(Text)  # AI-generated narrative
    created_at = Column(DateTime, default=datetime.utcnow)


# ----------------------- Engine / Session -----------------------

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create all tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")

    # Seed default tenant if missing
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == settings.default_tenant_id)
        )
        if result.scalar_one_or_none() is None:
            session.add(Tenant(id=settings.default_tenant_id, name="Default Tenant"))
            await session.commit()
            logger.info(f"Seeded default tenant: {settings.default_tenant_id}")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception(f"DB session error: {exc}")
            raise
        finally:
            await session.close()
