"""Pydantic v2 schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    customer_id: Optional[str] = Field(default=None, description="External customer identifier")
    customer_name: Optional[str] = None
    channel: Literal["web", "wechat", "email"] = "web"
    message: str
    metadata: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    agent_name: str
    reply: str
    routed_to: List[str] = Field(default_factory=list)
    handoff_to_human: bool = False
    metadata: dict = Field(default_factory=dict)


class MessageOut(BaseModel):
    id: int
    role: str
    agent_name: Optional[str]
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionOut(BaseModel):
    id: str
    tenant_id: str
    channel: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    status: str
    current_agent: Optional[str]
    human_takeover: int
    created_at: datetime
    updated_at: datetime
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketCreate(BaseModel):
    session_id: str
    tenant_id: Optional[str] = None
    title: str
    description: str
    category: Literal["complaint", "tech", "aftersales", "consult"] = "consult"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class TicketOut(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    assignee: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TakeoverRequest(BaseModel):
    session_id: str
    operator: str = "admin"
    note: Optional[str] = None


class TakeoverReplyRequest(BaseModel):
    session_id: str
    operator: str = "admin"
    message: str


class StatsOut(BaseModel):
    total_sessions: int
    active_sessions: int
    closed_sessions: int
    takeover_sessions: int
    total_messages: int
    total_tickets: int
    open_tickets: int


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
