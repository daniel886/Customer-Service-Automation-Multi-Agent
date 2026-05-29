"""Iteration 8: multi-tenant data isolation at the DB layer."""
import os
import uuid

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_tenant.db")
os.environ.setdefault("TEST_MODE", "1")


@pytest.mark.asyncio
async def test_session_tenant_filtering():
    from sqlalchemy import select
    from models.database import (
        AsyncSessionFactory,
        Message,
        Session,
        Tenant,
        init_db,
    )

    await init_db()

    sid_a = f"S-A-{uuid.uuid4().hex[:8]}"
    sid_b = f"S-B-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionFactory() as db:
        # Ensure tenants
        for tid, name in (("tenant_a", "Tenant A"), ("tenant_b", "Tenant B")):
            existing = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
            if not existing:
                db.add(Tenant(id=tid, name=name))
        db.add(Session(id=sid_a, tenant_id="tenant_a", channel="web"))
        db.add(Session(id=sid_b, tenant_id="tenant_b", channel="web"))
        await db.commit()

        db.add(Message(session_id=sid_a, role="user", content="A 的消息"))
        db.add(Message(session_id=sid_b, role="user", content="B 的消息"))
        await db.commit()

        a_sessions = (
            await db.execute(select(Session).where(Session.tenant_id == "tenant_a"))
        ).scalars().all()
        b_sessions = (
            await db.execute(select(Session).where(Session.tenant_id == "tenant_b"))
        ).scalars().all()

        assert sid_a in [s.id for s in a_sessions]
        assert sid_b not in [s.id for s in a_sessions]
        assert sid_b in [s.id for s in b_sessions]
        assert sid_a not in [s.id for s in b_sessions]


@pytest.mark.asyncio
async def test_ticket_tenant_filtering():
    from sqlalchemy import select
    from models.database import AsyncSessionFactory, Ticket, init_db

    await init_db()

    tid_a = f"T-A-{uuid.uuid4().hex[:8]}"
    tid_b = f"T-B-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionFactory() as db:
        db.add(Ticket(id=tid_a, session_id="x", tenant_id="tenant_a",
                      title="A", description="d", category="complaint"))
        db.add(Ticket(id=tid_b, session_id="y", tenant_id="tenant_b",
                      title="B", description="d", category="complaint"))
        await db.commit()

        a_tickets = (
            await db.execute(select(Ticket).where(Ticket.tenant_id == "tenant_a"))
        ).scalars().all()
        assert tid_a in [t.id for t in a_tickets]
        assert tid_b not in [t.id for t in a_tickets]
