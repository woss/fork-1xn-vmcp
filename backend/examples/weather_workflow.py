#!/usr/bin/env python3
"""
Example Workflow: Weather Information Pipeline

This script demonstrates combining multiple tools to:
1. Get location coordinates for a city
2. Get weather information for that location
3. Process and display the results

Run with: python examples/weather_workflow.py
"""

import sys
from pathlib import Path

# Add src to path to import vmcp_sdk
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk


def weather_workflow(city: str = "Sydney"):
    """
    Complete weather workflow combining location and weather tools.

    Args:
        city: City name to get weather for
    """
    print(f"🌤️  Weather Workflow for {city}")
    print("=" * 60)

    # Access the 1xndemo vmcp
    # Note: Since "1xndemo" starts with a number, we use getattr
    demo = getattr(vmcp_sdk, "1xndemo")

    # Step 1: Get location coordinates for the city
    print(f"\n📍 Step 1: Getting location for {city}...")
    try:
        location_result = demo.all_feature_get_location(city=city)
        print(f"   Result: {location_result}")

        # Extract coordinates from result
        if isinstance(location_result, dict):
            structured = location_result.get("structuredContent", {})
            if structured:
                lat = structured.get("latitude")
                lon = structured.get("longitude")
                print(f"   Coordinates: {lat}, {lon}")
            else:
                # Fallback: try to parse from content
                content = location_result.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Location data: {text}")
        else:
            print(f"   Location: {location_result}")

    except Exception as e:
        print(f"   ❌ Error getting location: {e}")
        return

    # Step 2: Get weather for the city
    print(f"\n🌡️  Step 2: Getting weather for {city}...")
    try:
        weather_result = demo.all_feature_get_weather(city=city)
        print(f"   Result: {weather_result}")

        # Extract weather info
        if isinstance(weather_result, dict):
            structured = weather_result.get("structuredContent", {})
            if structured:
                temp = structured.get("temperature")
                condition = structured.get("condition")
                print(f"   Temperature: {temp}°C")
                print(f"   Condition: {condition}")
            else:
                content = weather_result.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Weather: {text}")

    except Exception as e:
        print(f"   ❌ Error getting weather: {e}")
        return

    # Step 3: Generate a summary
    print(f"\n📝 Step 3: Generating summary...")
    try:
        # Use hello tool to create a greeting with the city name
        greeting = demo.all_feature_hello(name=f"{city} Weather")
        if isinstance(greeting, dict):
            content = greeting.get("content", [])
            if content and isinstance(content[0], dict):
                text = content[0].get("text", "")
                print(f"   {text}")

    except Exception as e:
        print(f"   ⚠️  Warning: Could not generate summary: {e}")

    print("\n" + "=" * 60)
    print("✅ Weather workflow completed!")


if __name__ == "__main__":
    # Get city from command line or use default
    city = sys.argv[1] if len(sys.argv) > 1 else "Sydney"
    weather_workflow(city)

