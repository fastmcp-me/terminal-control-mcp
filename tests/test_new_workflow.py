#!/usr/bin/env python3
"""
Test script for the new turn-taking workflow
"""
import asyncio
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from interactive_automation_mcp.main import AppContext, SecurityManager, SessionManager
from interactive_automation_mcp.models import (
    ExecuteCommandRequest,
)


async def test_new_workflow():
    """Test the new turn-taking workflow"""
    print("🚀 Testing new turn-taking workflow...")

    # Create app context
    session_manager = SessionManager()
    security_manager = SecurityManager()

    app_ctx = AppContext(
        session_manager=session_manager,
        security_manager=security_manager,
    )

    try:
        # 1. Execute a simple interactive command (Python REPL)
        print("\n1. Creating session with Python REPL...")
        request = ExecuteCommandRequest(
            command="python3 -u", execution_timeout=60  # Unbuffered Python
        )

        # Simulate security validation
        if not app_ctx.security_manager.validate_tool_call(
            "execute_command", request.model_dump()
        ):
            raise ValueError("Security violation")

        # Build command
        full_command = request.command
        if request.command_args:
            full_command += " " + " ".join(request.command_args)

        # Create session
        session_id = await app_ctx.session_manager.create_session(
            command=full_command,
            timeout=request.execution_timeout,
            environment=request.environment,
            working_directory=request.working_directory,
        )

        print(f"✅ Session created: {session_id}")

        # Give process time to start
        await asyncio.sleep(1.0)

        # 2. Get screen content
        print("\n2. Getting initial screen content...")
        session = await app_ctx.session_manager.get_session(session_id)
        if not session:
            raise RuntimeError("Session not found")

        screen_content = await session.get_output()
        process_running = session.is_process_alive()

        print(f"Process running: {process_running}")
        print(
            f"Screen content: {repr(screen_content[:100])}..."
            if screen_content
            else "No screen content"
        )

        # 3. Send input
        print("\n3. Sending input: print('Hello from new workflow!')")
        await session.send_input("print('Hello from new workflow!')")

        # Give time for output
        await asyncio.sleep(0.5)

        # 4. Get screen content again
        print("\n4. Getting updated screen content...")
        updated_content = await session.get_output()
        print(
            f"Updated content: {repr(updated_content[-200:])}..."
            if updated_content
            else "No content"
        )

        # 5. Send exit command
        print("\n5. Sending exit command...")
        await session.send_input("exit()")

        # Give time for process to exit
        await asyncio.sleep(0.5)

        # 6. Check final status
        print("\n6. Checking final status...")
        final_running = session.is_process_alive()
        print(f"Process still running: {final_running}")

        # 7. Clean up session
        print("\n7. Cleaning up session...")
        success = await app_ctx.session_manager.destroy_session(session_id)
        print(f"Session destroyed: {success}")

        print("\n✅ New workflow test completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up any remaining sessions
        sessions = await app_ctx.session_manager.list_sessions()
        for session_metadata in sessions:
            await app_ctx.session_manager.destroy_session(session_metadata.session_id)


if __name__ == "__main__":
    asyncio.run(test_new_workflow())
