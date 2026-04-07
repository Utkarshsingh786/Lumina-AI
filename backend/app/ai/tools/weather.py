"""
Weather tool — fetches current weather using wttr.in (free, no API key).

wttr.in is a publicly available weather service that returns JSON data.
Falls back gracefully if the service is unavailable.

wttr.in JSON format v2: https://wttr.in/:help
"""

from typing import Any

import httpx

from app.ai.tools.base import BaseTool, ToolResult
from app.core.logging import get_logger

logger = get_logger(__name__)

WTTR_URL = "https://wttr.in/{location}?format=j1"
REQUEST_TIMEOUT = 8.0  # seconds


def _parse_wttr_response(data: dict, location: str) -> str:
    """Extract human-readable weather summary from wttr.in JSON response."""
    try:
        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]

        area_name = (
            area.get("areaName", [{}])[0].get("value", location)
        )
        country = area.get("country", [{}])[0].get("value", "")
        display_location = f"{area_name}, {country}".strip(", ")

        temp_c = current.get("temp_C", "?")
        temp_f = current.get("temp_F", "?")
        feels_c = current.get("FeelsLikeC", "?")
        feels_f = current.get("FeelsLikeF", "?")
        humidity = current.get("humidity", "?")
        wind_kmph = current.get("windspeedKmph", "?")
        wind_miles = current.get("windspeedMiles", "?")
        description = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        visibility = current.get("visibility", "?")

        return (
            f"Weather in {display_location}:\n"
            f"  Condition: {description}\n"
            f"  Temperature: {temp_c}°C / {temp_f}°F (feels like {feels_c}°C / {feels_f}°F)\n"
            f"  Humidity: {humidity}%\n"
            f"  Wind: {wind_kmph} km/h / {wind_miles} mph\n"
            f"  Visibility: {visibility} km"
        )
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("weather.parse_error", error=str(e))
        return f"Weather data received for {location} but could not be fully parsed."


class WeatherTool(BaseTool):
    name = "get_weather"
    description = (
        "Get the current weather for any city or location. "
        "Returns temperature (Celsius and Fahrenheit), conditions, humidity, and wind speed."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": (
                    "The city or location to get weather for. "
                    "Examples: 'London', 'New York', 'Tokyo', 'Paris, France'"
                ),
            }
        },
        "required": ["location"],
    }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        location = args.get("location", "").strip()
        if not location:
            return ToolResult(
                tool_name=self.name,
                content="Error: no location provided",
                is_error=True,
            )

        logger.info("weather.fetch", location=location)

        url = WTTR_URL.format(location=location.replace(" ", "+"))
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            return ToolResult(
                tool_name=self.name,
                content=f"Weather service timed out for '{location}'. Please try again.",
                is_error=True,
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                tool_name=self.name,
                content=f"Weather service returned {e.response.status_code} for '{location}'.",
                is_error=True,
            )
        except Exception as e:
            logger.error("weather.unexpected_error", location=location, error=str(e))
            return ToolResult(
                tool_name=self.name,
                content=f"Could not fetch weather for '{location}': {e}",
                is_error=True,
            )

        summary = _parse_wttr_response(data, location)
        return ToolResult(
            tool_name=self.name,
            content=summary,
            metadata={"location": location},
        )
