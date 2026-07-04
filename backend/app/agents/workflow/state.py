from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """The state of the multi-agent LangGraph workflow."""
    
    # Input
    input: str
    chat_history: List[BaseMessage]
    user_context: str
    
    # Routing Intent
    intent: Optional[str]
    current_station_id: Optional[str]
    current_location: Optional[str]
    current_project: Optional[str]
    
    # Collected Data
    iot_data: Optional[str]
    iot_anomalies: Optional[str]
    ppm_data: Optional[str]
    weather_data: Optional[str]
    rag_data: Optional[str]
    
    # Execution Flags
    needs_station_selection: bool
    
    # Shared Result for UI Metadata
    skill_result: Optional[Any]
    
    # Output
    output: str
