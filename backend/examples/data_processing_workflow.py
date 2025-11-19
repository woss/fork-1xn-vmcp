#!/usr/bin/env python3
"""
Example Workflow: Data Processing Pipeline

This script demonstrates combining multiple tools to:
1. Get current time
2. Process data with logging

Run with: python examples/data_processing_workflow.py
"""

import sys
from pathlib import Path

# Add src to path to import vmcp_sdk
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk


def data_processing_workflow():
    """Complete data processing workflow."""
    print("📊 Data Processing Workflow")
    print("=" * 60)

    # Access the 1xndemo vmcp
    demo = getattr(vmcp_sdk, "1xndemo")

    # Step 1: Get current time
    print("\n🕐 Step 1: Getting current time...")
    try:
        time_result = demo.all_feature_get_current_time(timezone_name="UTC")
        print(f"   Requesting current time in UTC...")

        if isinstance(time_result, dict):
            structured = time_result.get("structuredContent", {})
            if structured:
                current_time = structured.get("result")
                print(f"   Current time: {current_time}")
            else:
                content = time_result.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Current time: {text}")

    except Exception as e:
        print(f"   ❌ Error getting time: {e}")
        return

    # Step 2: Process data with logging
    print("\n📝 Step 2: Processing data with logging...")
    try:
        # Process some sample data
        data_result = demo.all_feature_process_data(data="sample_data_123")
        print(f"   Processing data: 'sample_data_123'...")

        if isinstance(data_result, dict):
            structured = data_result.get("structuredContent", {})
            if structured:
                processed = structured.get("result")
                print(f"   Processed result: {processed}")
            else:
                content = data_result.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    print(f"   Processed: {text}")

    except Exception as e:
        print(f"   ⚠️  Warning: Could not process data: {e}")

    print("\n" + "=" * 60)
    print("✅ Data processing workflow completed!")


if __name__ == "__main__":
    data_processing_workflow()

