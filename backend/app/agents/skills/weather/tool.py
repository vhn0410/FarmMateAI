import requests

from app.agents.skills.base import BaseSkill, SkillResult
from app.core.config import settings


class WeatherSkill(BaseSkill):
    name = "Get_Weather_Information"
    description = (
        "Use this tool to get current weather information (temperature, humidity, weather condition) "
        "for a specific province, city, or location."
    )

    def __init__(self):
        """Initialize the Weather Tool."""
        # Get API key from environment variables
        self.api_key = settings.openweathermap_api_key
        self.base_url = settings.openweathermap_base_url

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Execute weather data retrieval.
        The 'query' variable here is the location name passed by the LLM.
        """
        location = query.strip()
        agent_actions = [f"Started fetching weather data for location: '{location}'"]

        # Check if API Key is configured
        if not self.api_key:
            error_msg = "System is missing OPENWEATHERMAP_API_KEY configuration."
            agent_actions.append("Error: Missing API Key.")
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )

        try:
            # Parameters sent to OpenWeatherMap
            params = {
                "q": location,
                "appid": self.api_key,
                "units": "metric",  # Get temperature in Celsius
                "lang": "en",  # Return description in English
            }

            agent_actions.append("Sending HTTP GET request to OpenWeatherMap...")
            response = requests.get(self.base_url, params=params, timeout=10)

            # Process the response
            if response.status_code == 200:
                data = response.json()

                # Extract important parameters
                temp = data["main"]["temp"]
                humidity = data["main"]["humidity"]
                description = data["weather"][0]["description"]
                city_name = data["name"]

                # Create answer for LLM to read
                answer = (
                    f"Current weather data in {city_name}: "
                    f"Condition: {description}, temperature: {temp}°C, humidity: {humidity}%."
                )
                agent_actions.append(f"Success: {answer}")

                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={
                        "location_requested": location,
                        "location_found": city_name,
                        "temperature": temp,
                        "humidity": humidity,
                        "description": description,
                    },
                    agent_actions=agent_actions,
                )

            elif response.status_code == 404:
                # LLM provided a non-existent location
                answer = f"Could not find weather data station for location '{location}'."
                agent_actions.append(f"Error 404: Could not find location '{location}'.")
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

            else:
                answer = f"Error calling weather API. Status code: {response.status_code}."
                agent_actions.append(f"API Error: {response.text}")
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

        except Exception as e:
            error_msg = f"System error while looking up weather: {str(e)}"
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )
