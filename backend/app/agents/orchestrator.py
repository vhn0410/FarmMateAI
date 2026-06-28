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

           - If pH < 5 -> Translate to "đất phèn", "đất chua", "cải tạo đất".

           - If N, P, K are low -> Translate to "thiếu dinh dưỡng", "bón lót", "bón thúc".

        3. YOU MUST translate the query into VIETNAMESE before searching, because the database documents are in Vietnamese!

        4. CORRECT query example: "Cách bón phân thúc cho lúa đẻ nhánh trên đất phèn"

        5. INCORRECT query example: "How to fertilize rice pH 4.5 N 120"

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
        """Get current hardware sensor data (N, P, K, pH, temperature, humidity, etc.) for a specific station. Always call this when the user wants to check a station's data, even if the station is a weather station."""
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
    def current_stage_tool(status: str = "ALL", project_name: str = None) -> str:
        """Get current growth stage / active tasks for the farm.
        The 'status' parameter defaults to 'ALL', but can be 'OPEN', 'IN_PROGRESS', 'DONE', or 'ALL' (or a combination separated by commas).
        The 'project_name' parameter is optional. If the user asks for a specific project, provide its exact name here to filter the results natively.
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
                
            if project_name:
                active_tasks = [t for t in active_tasks if project_name.lower() in t.get("projectName", "").lower()]
                if not active_tasks:
                    return f"There are currently no tasks matching project '{project_name}' with status ({status_str})."

            # Loại bỏ các dự án mẫu (template) bằng cách kiểm tra:
            # Nếu TOÀN BỘ task trong một project đều KHÔNG CÓ startDate và startDateActual, thì đó là template
            project_has_dates = {}
            for t in active_tasks:
                pid = t.get("projectId")
                if t.get("startDateActual") or t.get("startDate"):
                    project_has_dates[pid] = True
            
            # Lọc các task thuộc về dự án thực tế
            active_tasks = [t for t in active_tasks if project_has_dates.get(t.get("projectId"))]
            
            # Sắp xếp các task theo Tên Dự Án trước, sau đó mới đến 'index' để hiển thị đúng thứ tự từng dự án
            active_tasks.sort(key=lambda t: (t.get("projectName", "").strip().lower(), t.get("index", 9999)))

            # Xác định Current Task và Next Task cho từng dự án
            project_stages = {}
            for t in active_tasks:
                proj = t.get("projectName", "Unnamed Project").replace('\n', ' ').strip()
                if proj not in project_stages:
                    project_stages[proj] = {"current": None, "next": None, "open_tasks": []}
                
                status_val = t.get("status", "UNKNOWN")
                task_name = t.get("name", "Unknown").replace('\n', ' ').strip()
                
                if status_val == "IN_PROGRESS":
                    project_stages[proj]["current"] = task_name
                elif status_val == "OPEN":
                    project_stages[proj]["open_tasks"].append(task_name)
                    
            summary_header = "**Giai đoạn sinh trưởng hiện tại (Current Growth Stage):**\n"
            for proj, data in project_stages.items():
                current = data["current"]
                if not current and data["open_tasks"]:
                    # Nếu không có task IN_PROGRESS, lấy task OPEN đầu tiên làm current
                    current = data["open_tasks"][0]
                    next_task = data["open_tasks"][1] if len(data["open_tasks"]) > 1 else "None"
                else:
                    next_task = data["open_tasks"][0] if data["open_tasks"] else "None"
                
                summary_header += f"- Dự án '{proj}': Đang thực hiện [{current or 'None'}]. Tiếp theo: [{next_task}].\n"
            
            summary_header += "\n**Chi tiết tất cả các Task:**\n"

            result_list = ["| Task Name | Project Name | Status | Start Date |", "|---|---|---|---|"]
            
            # Khởi tạo bộ đếm trạng thái để giúp LLM vẽ biểu đồ chính xác
            status_counts = {"OPEN": 0, "IN_PROGRESS": 0, "DONE": 0}
            
            for t in active_tasks:
                task_name = t.get("name", "Unknown").replace('\n', ' ').strip()
                proj_name = t.get("projectName", "Unnamed Project").replace('\n', ' ').strip()
                start_date = t.get("startDateActual", t.get("startDate", ""))
                status_val = t.get("status", "UNKNOWN")
                
                # Tăng biến đếm
                if status_val in status_counts:
                    status_counts[status_val] += 1
                else:
                    status_counts[status_val] = 1
                    
                if start_date:
                    try:
                        start_date = start_date.split('T')[0]
                    except:
                        pass
                else:
                    start_date = "None"
                    
                result_list.append(f"| {task_name} | {proj_name} | {status_val} | {start_date} |")

            final_output = summary_header + "\n".join(result_list)
            
            # Thêm phần thống kê chính xác để LLM không đếm sai
            summary = "\n\n**Thống kê số lượng Task (Sử dụng số liệu này để vẽ biểu đồ):**\n"
            for k, v in status_counts.items():
                if v > 0:
                    summary += f"- {k}: {v}\n"
                    
            return final_output + summary
            
        except Exception as e:
            return f"System error while fetching growth stage data: {str(e)}"

    # Tool 4: Weather (Mock)
    @tool("Get_Weather_Information")
    def weather_tool(location: str) -> str:
        """Use this tool to get general city-level meteorological forecasts (rain, forecast) for a location. Do NOT use this tool for checking a specific hardware station's data."""
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
                
                Step 1 - CLASSIFY QUESTION & TOOL SELECTION (CRITICAL):
                - If the user asks for ADVICE or FARMING INSTRUCTIONS (e.g., "What should I do today?", "How to fertilize?", "Tư vấn bón phân"): You MUST call `Get_Current_Growth_Stage` (to know the farm's current step), call `Get_IoT_Sensor_Data` and `Get_Weather_Information` for environmental context, and finally call `Agriculture_Technical_Advice` (RAG) to get the actual knowledge.
                   + CRITICAL: When calling `Get_Current_Growth_Stage`, if the user mentions a specific crop or project (like "lúa" or "cá"), you MUST pass it into the `project_name` parameter so it filters exactly that crop.
                - If the user ONLY asks to check data without asking for advice (e.g. "Kiểm tra dữ liệu Trạm..."): ONLY call `Get_IoT_Sensor_Data` (and optionally `Get_Weather_Information`). DO NOT call `Get_Current_Growth_Stage` or `Agriculture_Technical_Advice` unless explicitly asked.
                - If the user asks purely theoretical knowledge not tied to their farm: STRICTLY call `Agriculture_Technical_Advice` ONLY.
                
                Step 2 - STATION HANDLING (If IoT or Weather is needed):
                - Growth stage (PPM) is GLOBAL. No station ID needed.
                - IoT and Weather are PER-STATION. If the user has MULTIPLE STATIONS and hasn't specified which one, STOP and politely ask: "Which station would you like to check?". If specified, extract 'station_id' and 'location'.
                   + IMPORTANT: When extracting 'location' for the Weather tool, remove prefixes like "Khí tượng" or "Lúa" and use only the city/province name (e.g., "Vĩnh Long").
                   + CRITICAL: When you ask the user to choose a station, you MUST format each station as an ACTION LINK so the user can click it.
                   + IMPORTANT: If the user asked for ADVICE (e.g. "how to fertilize"), the action link MUST preserve that intent so you remember it in the next turn! Do NOT just use "Kiểm tra dữ liệu".
                   + Example (just checking): `[Trạm Khí tượng Vĩnh Long](#action:Kiểm_tra_dữ_liệu_Trạm_Khí_tượng_Vĩnh_Long)`
                   + Example (asking for fertilizer advice): `[Trạm Khí tượng Vĩnh Long](#action:Tư_vấn_bón_phân_dựa_trên_dữ_liệu_Trạm_Khí_tượng_Vĩnh_Long)`

                Step 3 - TRANSFORMATION & RAG QUERY (Only if ADVICE is requested):
                - Combine GROWTH STAGE (from PPM), WEATHER, and SOIL CONDITION (from IoT) to translate into PROFESSIONAL KEYWORDS for your RAG query.
                - You MUST call the `Agriculture_Technical_Advice` tool using those keywords to find the exact technique. Do this EVEN IF some tools failed or returned missing data.

                Step 4 - SYNTHESIZE & ADVISE:
                - Always answer the user in Vietnamese in a natural, helpful consultant tone.
                - ONLY base your advice on the data returned by the tools. If a tool doesn't return the requested data, explain the limitation naturally based on the context.
                   + Example: If the user asks for soil pH but the IoT tool only returns weather data, naturally explain that the station doesn't have a soil pH sensor.
                   + Example: If the `Agriculture_Technical_Advice` (RAG) tool was used but found no data, state clearly that your document system currently lacks this information. **CRITICAL: You MUST STOP there. Do NOT provide any general advice, guesses, or recommendations from your own knowledge.**
                - ABSOLUTELY DO NOT hallucinate or guess any agricultural techniques, fertilizer names, or dosages under any circumstances.
                - When listing out specific tasks or items (e.g. from PPM), DO NOT deduplicate or skip items even if they share the same name. List every single one exactly as returned by the tool.
                - **ACTION LINKS (QUICK REPLIES)**: Whenever you present a choice to the user (e.g. asking which station they want to check) or suggest a follow-up action, you MUST format it as a markdown link starting with `#action:`. 
                  + CRITICAL: The exact query in the link MUST NOT contain any spaces. Replace all spaces with underscores `_`.
                  + Syntax: `[Display Text](#action:Exact_Query_To_Send)`
                  + Example: `[Trạm Khí tượng Vĩnh Long (ID: 22)](#action:Kiểm_tra_dữ_liệu_Trạm_Khí_tượng_Vĩnh_Long_ID_22)`
                  + Example: `[Hướng dẫn bón phân](#action:Tư_vấn_cách_bón_phân_cho_lúa)`
                
                Step 5 - VISUALIZATION & FORMATTING (CRITICAL):
                - For mixed sensor data (like pH, Temperature, Moisture, NPK), you MUST use a Markdown Table. Do NOT use charts for these.
                - When displaying the list of PPM Tasks, YOU MUST render them EXACTLY as a Markdown Table with all columns preserved (Task Name, Project Name, Status, Start Date). Do NOT skip any tasks, including DONE tasks. Do NOT convert the table into a text list!
                - For PPM Task Summaries (e.g. counting how many tasks are OPEN, IN_PROGRESS, DONE), you MUST output a Pie Chart to visualize the distribution.
                - To render a chart, output a markdown code block exactly like this:
                ```chart
                {{
                  "type": "pie",
                  "data": [
                    {{"key": "OPEN", "data": 2}},
                    {{"key": "IN_PROGRESS", "data": 5}},
                    {{"key": "DONE", "data": 1}}
                  ]
                }}
                ```
                - Make sure the JSON is valid. Only include this block when summarizing PPM task statuses.
                """,
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
