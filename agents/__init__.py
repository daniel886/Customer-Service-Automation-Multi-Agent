"""Agents package."""
from agents.aftersales_agent import AfterSalesAgent
from agents.base import AgentContext, AgentResult, BaseAgent
from agents.complaint_agent import ComplaintAgent
from agents.consultation_agent import ConsultationAgent
from agents.tech_support_agent import TechSupportAgent


def all_agents() -> dict[str, BaseAgent]:
    return {
        ConsultationAgent.name: ConsultationAgent(),
        ComplaintAgent.name: ComplaintAgent(),
        TechSupportAgent.name: TechSupportAgent(),
        AfterSalesAgent.name: AfterSalesAgent(),
    }


__all__ = [
    "AgentContext",
    "AgentResult",
    "BaseAgent",
    "ConsultationAgent",
    "ComplaintAgent",
    "TechSupportAgent",
    "AfterSalesAgent",
    "all_agents",
]
