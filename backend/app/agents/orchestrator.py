import contextvars
import json
from langchain_classic.agents.openai_tools.base import create_openai_tools_agent
from langchain_classic.agents.agent import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.agents.skills.weather.tool import WeatherSkill
from app.agents.skills.base import SkillResult
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.llm.openai_client import OpenAIClient
from app.agents.mocks.mock_system import MOCK_SYSTEM_DB
from app.infrastructure.api.aaem_client import AAEMClient
from app.infrastructure.api.ppm_client import PPMClient


agent_shared_state = contextvars.ContextVar("agent_shared_state")


def get_chat_agent():
    llm = OpenAIClient(model="gpt-4o-mini", temperature=0.0, streaming=True).get_llm()
    vector_store_provider = PGVectorProvider()

    rag_skill = AgricultureRAGSkill(
        vector_store_provider=vector_store_provider,
        llm_provider=OpenAIClient(model="gpt-4o-mini", temperature=0.0),
    )
    weather_skill = WeatherSkill()

    @tool(rag_skill.name)
    def agriculture_tool(query: str) -> str:
        """
        AGRICULTURAL EXPERT HANDBOOK LOOKUP TOOL.
        !!! RED ALERT FOR 'query' PARAMETER !!!

        1. ABSOLUTELY NEVER pass raw numbers or sensor data into the query (DO NOT use words like: "pH 4.5", "N 120", "P 45", "moisture 40%"). Doing so will cause system errors.

        2. YOU MUST translate the data into PROFESSIONAL KEYWORDS before searching:

           - If pH < 5 -> Translate to "acidic soil", "alum soil", "soil improvement".

           - If N, P, K are low -> Translate to "nutrient deficiency", "basal fertilizer", "top dressing".

        3. CORRECT query example: "How to apply top dressing for tillering rice on acidic soil"

        4. INCORRECT query example: "How to fertilize rice pH 4.5 N 120"

        """
        result: SkillResult = rag_skill.run(query)

        # Lấy kho chứa của User hiện tại ra và bỏ kết quả vào
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass  # An toàn bỏ qua nếu test ngoài FastAPI

        return result.answer

    # Tool 2: Get IoT Data by Station
    @tool("Get_IoT_Sensor_Data")
    def iot_sensor_tool(station_id: str) -> str:
        """Get current sensor data (N, P, K, pH, etc.) for a specific station."""
        try:
            state = agent_shared_state.get()
            token = state.get("access_token")
            if not token:
                return "Error: No access token. Please log in again."
                
            aaem_client = AAEMClient()
            stations = aaem_client.fetch_all_user_stations(token)
            
            # Find corresponding station
            target_station = None
            for st in stations:
                if str(st.get("stationId")) == str(station_id):
                    target_station = st
                    break
                    
            if not target_station:
                return f"Error: Could not find station with ID {station_id}."
                
            # Filter DataStreamId
            multi_streams = target_station.get("multiDataStreamDTOs", [])
            stream_map = {}
            for stream in multi_streams:
                s_id = stream.get("multiDataStreamId")
                name = stream.get("multiDataStreamName", "Sensor")
                if s_id is not None:
                    stream_map[str(s_id)] = name
                    
            if not stream_map:
                return f"Station {station_id} currently has no sensor connections."
                
            # Get latest observations
            stream_ids = [int(k) for k in stream_map.keys()]
            observations = aaem_client.get_latest_observations(token, stream_ids)
            
            # Map ID -> Sensor Name -> Value
            result_dict = {}
            for obs in observations:
                s_id = str(obs.get("dataStreamId"))
                val = obs.get("result", "N/A")
                sensor_name = stream_map.get(s_id, f"Sensor {s_id}")
                result_dict[sensor_name] = val
                
            if not result_dict:
                return f"Station {station_id} has no observation data yet."
                
            return f"IoT Data for station {station_id}: {json.dumps(result_dict, ensure_ascii=False)}"
            
        except Exception as e:
            return f"System error while fetching IoT data: {str(e)}"

    # Tool 3: Get Global Growth Stage
    @tool("Get_Current_Growth_Stage")
    def current_stage_tool(status: str = "IN_PROGRESS") -> str:
        """Get current growth stage / active tasks for the entire farm (global, no station_id needed).
        The 'status' parameter defaults to 'IN_PROGRESS', but can be 'OPEN', 'IN_PROGRESS', 'DONE', or 'ALL' (or a combination separated by commas).
        """
        try:
            state = agent_shared_state.get()
            token = state.get("access_token")
            if not token:
                return "Error: No access token. Please log in again."
                
            ppm_client = PPMClient()
            
            # Parse comma-separated statuses
            status_list = [s.strip().upper() for s in status.split(",") if s.strip()]
            
            if "ALL" in status_list:
                status_list = ["OPEN", "IN_PROGRESS", "DONE"]
            
            if not status_list:
                status_list = ["IN_PROGRESS"]
                
            active_tasks = ppm_client.get_tasks_by_statuses(token, statuses=status_list)
            
            status_str = ", ".join(status_list)
            if not active_tasks:
                return f"There are currently no tasks with status ({status_str}) for your projects."
                
            result_list = []
            for t in active_tasks:
                task_name = t.get("name", "Unknown")
                proj_name = t.get("projectName", "Unnamed Project")
                start_date = t.get("startDateActual", t.get("startDate", ""))
                t_status = t.get("status", "Unknown")
                
                info = f"- Task: '{task_name}' (Project: '{proj_name}', Status: {t_status})"
                if start_date:
                    info += f", started from: {start_date}"
                result_list.append(info)
                
            return f"NOTE FOR AI: This data represents ALL tasks globally across all projects matching the requested statuses. Do NOT repeat it per station.\n\nTasks matching ({status_str}):\n" + "\n".join(result_list)
            
        except Exception as e:
            return f"System error while fetching growth stage data: {str(e)}"

    # Tool 4: Weather (Mock)
    @tool("Get_Weather_Information")
    def weather_tool(location: str) -> str:
        """Use this tool to get current weather information (temperature, rain, sun) for a specific location."""
        result: SkillResult = weather_skill.run(
            location
        )  # Truyền location vào làm query
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass
        return result.answer

    # Gộp tất cả tools lại
    tools = [agriculture_tool, iot_sensor_tool, current_stage_tool, weather_tool]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are FarmMate AI, an expert agricultural consultant.

                CURRENT USER INFORMATION:
                {user_context}

                PROCESSING FRAMEWORK (STRICTLY FOLLOW):
                
                Step 1 - CLASSIFY QUESTION & TOOL SELECTION:
                - If the user asks theory/general knowledge ("How to plant rice?", "What is Urea?"): STRICTLY call `Agriculture_Technical_Advice`. DO NOT call any other tool.
                - If the user asks for comprehensive advice ("What should I do today?", "Check my farm"): Call `Get_IoT_Sensor_Data`, `Get_Weather_Information`, `Get_Current_Growth_Stage`, AND `Agriculture_Technical_Advice`.
                - If the user asks for TARGETED metrics, you MUST ONLY call the specific tool requested and NOTHING ELSE:
                   + Ask for pH, moisture, sensor data -> ONLY call `Get_IoT_Sensor_Data`. (DO NOT call Weather or Growth Stage).
                   + Ask for weather, rain, forecast -> ONLY call `Get_Weather_Information`.
                   + Ask for tasks, jobs, growth stages -> ONLY call `Get_Current_Growth_Stage`.
                
                Step 2 - STATION HANDLING (If IoT or Weather is needed):
                - Growth stage (PPM) is GLOBAL. No station ID needed.
                - IoT and Weather are PER-STATION. If the user has MULTIPLE STATIONS and hasn't specified which one, STOP and politely ask: "Which station would you like to check?". If specified, extract 'station_id' and 'location'.
                   + IMPORTANT: When extracting 'location' for the Weather tool, remove prefixes like "Khí tượng" or "Lúa" and use only the city/province name (e.g., "Vĩnh Long").

                Step 3 - TRANSFORMATION & RAG QUERY (Only if comprehensive advice is requested):
                - Combine GROWTH STAGE and SOIL CONDITION to translate into PROFESSIONAL KEYWORDS.
                - You MUST call the `Agriculture_Technical_Advice` tool using those keywords. Do this EVEN IF the Weather or IoT tools failed or returned missing data.

                Step 4 - SYNTHESIZE & ADVISE:
                - Always answer the user in Vietnamese in a natural, helpful consultant tone.
                - ONLY base your advice on the data returned by the tools. If a tool doesn't return the requested data, explain the limitation naturally based on the context.
                   + Example: If the user asks for soil pH but the IoT tool only returns weather data, naturally explain that the station doesn't have a soil pH sensor.
                   + Example: If the `Agriculture_Technical_Advice` (RAG) tool was used but found no data, state clearly that your document system currently lacks this information. **CRITICAL: You MUST STOP there. Do NOT provide any general advice, guesses, or recommendations from your own knowledge.**
                - ABSOLUTELY DO NOT hallucinate or guess any agricultural techniques, fertilizer names, or dosages under any circumstances.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    ).partial(tool_name=rag_skill.name)

    agent = create_openai_tools_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True, return_intermediate_steps=True
    )

    return agent_executor
