#!/usr/bin/env python3
"""
Example Workflow: Mathematical Operations Pipeline

This script demonstrates combining multiple math tools to:
1. Add two numbers
2. Process the result
3. Calculate average of multiple numbers

Run with: python examples/math_workflow.py
"""

import sys
from pathlib import Path

# Add src to path to import vmcp_sdk
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk


def math_workflow():
    """Complete math workflow combining multiple calculation tools."""
    print("🔢 Mathematical Operations Workflow")
    print("=" * 60)

    # Access the 1xndemo vmcp
    demo = getattr(vmcp_sdk, "1xndemo")

    # Step 1: Add two numbers
    print("\n➕ Step 1: Adding two numbers...")
    try:
        result1 = demo.all_feature_add_numbers(a=15, b=27)
        print(f"   15 + 27 = ?")

        if isinstance(result1, dict):
            structured = result1.get("structuredContent", {})
            if structured:
                sum_result = structured.get("result")
                print(f"   Result: {sum_result}")
            else:
                content = result1.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Result: {text}")
        else:
            print(f"   Result: {result1}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Step 2: Use the add tool (alternative)
    print("\n➕ Step 2: Using alternative add tool...")
    try:
        result2 = demo.all_feature_add(a=10, b=20)
        print(f"   10 + 20 = ?")

        if isinstance(result2, dict):
            structured = result2.get("structuredContent", {})
            if structured:
                sum_result = structured.get("result")
                print(f"   Result: {sum_result}")
            else:
                content = result2.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Result: {text}")

    except Exception as e:
        print(f"   ⚠️  Warning: {e}")

    # Step 3: Calculate average (if available)
    print("\n📊 Step 3: Calculating average...")
    try:
        # The average tool needs comma-separated values
        numbers = "5,10,15,20,25"
        result3 = demo.average(values=numbers)
        print(f"   Average of {numbers} = ?")

        if isinstance(result3, dict):
            structured = result3.get("structuredContent", {})
            if structured:
                avg_result = structured.get("result")
                print(f"   Result: {avg_result}")
            else:
                content = result3.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Result: {text}")

    except Exception as e:
        print(f"   ⚠️  Warning: Could not calculate average: {e}")

    print("\n" + "=" * 60)
    print("✅ Math workflow completed!")


if __name__ == "__main__":
    math_workflow()

