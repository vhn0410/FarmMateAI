import json

from app.agents.skills.base import BaseSkill, SkillResult
from app.infrastructure.api.aaem_client import AAEMClient


class IoTManagementSkill(BaseSkill):
    name = "Get_IoT_Sensor_Data"
    description = (
        "Get current hardware sensor data (N, P, K, pH, temperature, humidity, etc.) for a specific station. "
        "Always call this when the user wants to check a station's data, even if the station is a weather station."
    )

    def __init__(self):
        """Initialize the IoT Management Tool."""
        pass

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Execute IoT data retrieval.
        We expect 'token' and 'station_id' in kwargs. 'query' is unused.
        """
        token = kwargs.get("token")
        station_id = kwargs.get("station_id")
        
        agent_actions = [f"Started fetching IoT sensor data for station ID: {station_id}..."]

        if not token:
            error_msg = "Error: No access token. Please log in again."
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )

        try:
            aaem_client = AAEMClient()
            stations = aaem_client.fetch_all_user_stations(token)

            # Find corresponding station
            target_station = None
            for st in stations:
                if str(st.get("stationId")) == str(station_id):
                    target_station = st
                    break

            if not target_station:
                error_msg = f"Error: Could not find station with ID {station_id}."
                agent_actions.append(error_msg)
                return SkillResult(
                    answer=error_msg,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

            # Filter DataStreamId
            multi_streams = target_station.get("multiDataStreamDTOs", [])
            stream_map = {}
            for stream in multi_streams:
                s_id = stream.get("multiDataStreamId")
                name = stream.get("multiDataStreamName", "Sensor")
                if s_id is not None:
                    stream_map[str(s_id)] = name

            if not stream_map:
                answer = f"Station {station_id} currently has no sensor connections."
                agent_actions.append(answer)
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

            # Get latest observations
            agent_actions.append(f"Found {len(stream_map)} sensor streams. Fetching latest observations...")
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
                answer = f"Station {station_id} has no observation data yet."
                agent_actions.append(answer)
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

            answer = f"IoT Data for station {station_id}: {json.dumps(result_dict, ensure_ascii=False)}"
            agent_actions.append("Success: Retrieved IoT observations.")

            return SkillResult(
                answer=answer,
                skill_name=self.name,
                metadata={"station_id": station_id, "data": result_dict},
                agent_actions=agent_actions,
            )

        except Exception as e:
            error_msg = f"System error while fetching IoT data: {str(e)}"
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )
