"""LangGraph multi-agent supervisor workflow.

Graph layout:

    +-----------+
    | supervisor| <-- decides which specialist handles the turn
    +-----+-----+
          |
          v
   one of: consultation / complaint / tech_support / aftersales
          |
          v
    +-----------+
    |  finalize | --> persist + emit reply
    +-----------+
"""
from __future__ import annotations

from typing import Annotated, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import all_agents
from agents.base import AgentContext, AgentResult
from core.logger import logger
from workflows.router import route_intent


class WorkflowState(TypedDict, total=False):
    session_id: str
    tenant_id: str
    user_message: str
    history: List[dict]
    metadata: dict
    chosen_agent: str
    result: Optional[AgentResult]
    routed_chain: List[str]
    handoff_count: int


_AGENTS = all_agents()
_MAX_HANDOFFS = 2


async def supervisor_node(state: WorkflowState) -> WorkflowState:
    chosen = state.get("chosen_agent")
    if not chosen:
        chosen = route_intent(state["user_message"])
    state["chosen_agent"] = chosen
    chain = state.get("routed_chain") or []
    if not chain or chain[-1] != chosen:
        chain.append(chosen)
    state["routed_chain"] = chain
    logger.info(f"[supervisor] route -> {chosen}")
    return state


async def _run_specialist(state: WorkflowState, agent_name: str) -> WorkflowState:
    agent = _AGENTS[agent_name]
    ctx = AgentContext(
        session_id=state["session_id"],
        tenant_id=state["tenant_id"],
        user_message=state["user_message"],
        history=state.get("history") or [],
        metadata=state.get("metadata") or {},
    )
    result = await agent.a_run(ctx)
    state["result"] = result

    # Hand-off support: re-enter supervisor with a new chosen agent
    if (
        result.handoff_to
        and result.handoff_to in _AGENTS
        and state.get("handoff_count", 0) < _MAX_HANDOFFS
        and result.handoff_to != agent_name
    ):
        logger.info(f"[{agent_name}] hand-off to {result.handoff_to}")
        state["chosen_agent"] = result.handoff_to
        state["handoff_count"] = state.get("handoff_count", 0) + 1
    else:
        state["chosen_agent"] = "__final__"
    return state


async def consultation_node(state: WorkflowState) -> WorkflowState:
    return await _run_specialist(state, "consultation")


async def complaint_node(state: WorkflowState) -> WorkflowState:
    return await _run_specialist(state, "complaint")


async def tech_support_node(state: WorkflowState) -> WorkflowState:
    return await _run_specialist(state, "tech_support")


async def aftersales_node(state: WorkflowState) -> WorkflowState:
    return await _run_specialist(state, "aftersales")


async def finalize_node(state: WorkflowState) -> WorkflowState:
    if not state.get("result"):
        # Should not happen, but provide a safe default.
        state["result"] = AgentResult(
            agent_name="system",
            reply="正在为您接入客服，请稍候。",
            suggest_human_takeover=True,
        )
    return state


def _route_supervisor(state: WorkflowState) -> str:
    chosen = state.get("chosen_agent")
    if chosen in {"consultation", "complaint", "tech_support", "aftersales"}:
        return chosen
    return "finalize"


def _route_after_specialist(state: WorkflowState) -> str:
    if state.get("chosen_agent") == "__final__":
        return "finalize"
    return "supervisor"


def build_graph():
    g = StateGraph(WorkflowState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("consultation", consultation_node)
    g.add_node("complaint", complaint_node)
    g.add_node("tech_support", tech_support_node)
    g.add_node("aftersales", aftersales_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_supervisor,
        {
            "consultation": "consultation",
            "complaint": "complaint",
            "tech_support": "tech_support",
            "aftersales": "aftersales",
            "finalize": "finalize",
        },
    )
    for n in ("consultation", "complaint", "tech_support", "aftersales"):
        g.add_conditional_edges(
            n,
            _route_after_specialist,
            {"supervisor": "supervisor", "finalize": "finalize"},
        )
    g.add_edge("finalize", END)

    return g.compile()


# Singleton compiled graph (cheap, but reuses state schema)
_graph = build_graph()


async def run_workflow(
    session_id: str,
    tenant_id: str,
    user_message: str,
    history: Optional[list[dict]] = None,
    metadata: Optional[dict] = None,
) -> AgentResult:
    """Execute the supervisor graph for one user turn."""
    state: WorkflowState = {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "user_message": user_message,
        "history": history or [],
        "metadata": metadata or {},
        "routed_chain": [],
        "handoff_count": 0,
    }
    result_state = await _graph.ainvoke(state)
    result: AgentResult = result_state.get("result")  # type: ignore[assignment]
    # Annotate the final result with the routing chain.
    if result is not None:
        chain = result_state.get("routed_chain") or []
        result.actions.append({"type": "route_chain", "chain": chain})
    return result
