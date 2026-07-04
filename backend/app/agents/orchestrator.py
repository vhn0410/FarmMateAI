import contextvars
from langgraph.graph import StateGraph, START, END

from app.agents.workflow.state import AgentState
from app.agents.workflow.nodes import router_node, data_gatherer_node, rag_node, synthesizer_node

agent_shared_state = contextvars.ContextVar("agent_shared_state")


def route_after_classifier(state: AgentState):
    intent = state.get("intent")
    if intent == "FARMING_ADVICE":
        return "data_gatherer"
    elif intent == "DATA_CHECK":
        return "data_gatherer"
    elif intent == "GENERAL_KNOWLEDGE":
        return "rag"
    # Default fallback
    return "synthesizer"


def route_after_data(state: AgentState):
    intent = state.get("intent")
    if intent == "FARMING_ADVICE":
        return "rag"
    return "synthesizer"


def get_chat_agent():
    """
    Returns a compiled LangGraph application that serves as the conversational agent.
    This replaces the legacy LangChain AgentExecutor monolithic prompt architecture.
    """
    workflow = StateGraph(AgentState)
    
    # Add specialized nodes
    workflow.add_node("router", router_node)
    workflow.add_node("data_gatherer", data_gatherer_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("synthesizer", synthesizer_node)
    
    # Define the execution edges
    workflow.add_edge(START, "router")
    
    # Conditional routing after classification
    workflow.add_conditional_edges(
        "router",
        route_after_classifier,
        {
            "data_gatherer": "data_gatherer",
            "rag": "rag",
            "synthesizer": "synthesizer"
        }
    )
    
    # Conditional routing after gathering farm data
    workflow.add_conditional_edges(
        "data_gatherer",
        route_after_data,
        {
            "rag": "rag",
            "synthesizer": "synthesizer"
        }
    )
    
    # Flow directly to synthesis
    workflow.add_edge("rag", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    app = workflow.compile()
    return app
