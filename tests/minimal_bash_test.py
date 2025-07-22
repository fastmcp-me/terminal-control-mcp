#!/usr/bin/env python3
import asyncio
import os
import sys

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.interactive_automation_mcp.main import (
    destroy_session,
    execute_command,
    expect_and_respond,
)
from src.interactive_automation_mcp.models import (
    DestroySessionRequest,
    ExecuteCommandRequest,
    ExpectAndRespondRequest,
)
from tests.test_execute_command import create_mock_context


async def main():
    """Minimal test case for the bash read command."""
    test_name = "Minimal Bash Test"
    print(f"--- Running {test_name} ---")
    ctx = None
    session_id = None

    command = 'bash -c "read -p \'Enter value: \' val; echo "You entered: $val""'

    try:
        ctx = await create_mock_context()

        # 1. Start the interactive session
        start_request = ExecuteCommandRequest(command=command)
        start_result = await execute_command(start_request, ctx)

        if not start_result.success or not start_result.session_id:
            print(
                f"✗ {test_name} failed: Could not start session. Error: {start_result.error}"
            )
            return

        session_id = start_result.session_id
        print(f"✓ Session started: {session_id}")
        print(f"  Initial output: {start_result.output}")

        # 2. Interact with the session
        interaction_request = ExpectAndRespondRequest(
            session_id=session_id,
            expect_pattern="Enter value:",
            response="test123",
            timeout=10,
        )
        interaction_result = await expect_and_respond(interaction_request, ctx)

        if not interaction_result.get("success"):
            print(
                f"✗ {test_name} failed: Interaction failed. Error: {interaction_result.get('error')}"
            )
            print(f"  Output before failure: {interaction_result.get('before')}")
            return

        print("✓ Interaction successful.")
        print(f"  Output after interaction: {interaction_result.get('output')}")

        print(f"--- {test_name} Passed ---")

    except Exception as e:
        print(f"✗ {test_name} failed with exception: {e}")
    finally:
        # 3. Cleanup the session
        if ctx and session_id:
            print(f"  Cleaning up session {session_id}...")
            await destroy_session(DestroySessionRequest(session_id=session_id), ctx)
            print("  Session cleaned up.")


if __name__ == "__main__":
    asyncio.run(main())
