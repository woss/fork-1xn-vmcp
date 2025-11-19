#!/usr/bin/env python3
"""
Comprehensive Workflow Example

This script demonstrates a complete workflow combining multiple tools:
1. Get agent information
2. Get current time
3. Perform calculations
4. Get weather information

Run with: python examples/comprehensive_workflow.py
"""

import sys
from pathlib import Path

# Add src to path to import vmcp_sdk
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk


def comprehensive_workflow():
    """Complete workflow combining multiple tools."""
    print("🚀 Comprehensive vMCP Workflow")
    print("=" * 80)

    # Access the 1xndemo vmcp
    demo = getattr(vmcp_sdk, "1xndemo")

    results = {}

    # Step 1: Get agent information
    print("\n🤖 Step 1: Getting agent information...")
    try:
        agent_info = demo.get_agent_info()
        print("   ✓ Agent info retrieved")

        if isinstance(agent_info, dict):
            structured = agent_info.get("structuredContent", {})
            if structured:
                results["agent_info"] = structured
                print(f"   Agent: {structured.get('name', 'Unknown')}")
            else:
                content = agent_info.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Info: {text[:60]}...")
                    results["agent_info"] = text

    except Exception as e:
        print(f"   ⚠️  Warning: {e}")

    # Step 2: Get current time
    print("\n🕐 Step 2: Getting current time...")
    try:
        time_result = demo.all_feature_get_current_time(timezone_name="America/New_York")
        print("   ✓ Current time retrieved")

        if isinstance(time_result, dict):
            structured = time_result.get("structuredContent", {})
            if structured:
                current_time = structured.get("result")
                print(f"   Time: {current_time}")
                results["current_time"] = current_time

    except Exception as e:
        print(f"   ⚠️  Warning: {e}")

    # Step 3: Perform calculations
    print("\n🔢 Step 3: Performing calculations...")
    try:
        # Add numbers
        sum_result = demo.all_feature_add_numbers(a=25, b=17)
        if isinstance(sum_result, dict):
            structured = sum_result.get("structuredContent", {})
            if structured:
                total = structured.get("result")
                print(f"   25 + 17 = {total}")
                results["sum"] = total

        # Calculate average
        try:
            avg_result = demo.average(values="10,20,30,40,50")
            if isinstance(avg_result, dict):
                structured = avg_result.get("structuredContent", {})
                if structured:
                    avg = structured.get("result")
                    print(f"   Average of [10,20,30,40,50] = {avg}")
                    results["average"] = avg
        except Exception as e:
            print(f"   ⚠️  Average calculation skipped: {e}")

    except Exception as e:
        print(f"   ⚠️  Warning: {e}")

    # Step 4: Get weather for a city
    print("\n🌤️  Step 4: Getting weather information...")
    try:
        weather = demo.all_feature_get_weather(city="Tokyo")
        if isinstance(weather, dict):
            structured = weather.get("structuredContent", {})
            if structured:
                weather_text = structured.get("result")
                print(f"   Weather: {weather_text}")
                results["weather"] = weather_text
            else:
                content = weather.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Weather: {text}")
                    results["weather"] = text

    except Exception as e:
        print(f"   ⚠️  Warning: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 Workflow Summary")
    print("=" * 80)
    print(f"   Steps completed: {len(results)}")
    for key, value in results.items():
        if isinstance(value, str) and len(value) > 50:
            print(f"   {key}: {value[:50]}...")
        else:
            print(f"   {key}: {value}")

    print("\n✅ Comprehensive workflow completed!")


if __name__ == "__main__":
    comprehensive_workflow()

