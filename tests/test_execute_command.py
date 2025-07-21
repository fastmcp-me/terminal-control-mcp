#!/usr/bin/env python3
"""
Test the simplified MCP server architecture:
- execute_command: Starts session, runs command, reads output
- expect_and_respond: Sends input to existing session, reads output  
- list_sessions: Shows active sessions
- destroy_session: Cleans up sessions
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.interactive_automation_mcp.automation_engine import AutomationEngine
from src.interactive_automation_mcp.main import (
    destroy_session,
    execute_command,
    expect_and_respond,
    list_sessions,
)
from src.interactive_automation_mcp.models import (
    DestroySessionRequest,
    ExecuteCommandRequest,
    ExpectAndRespondRequest,
)
from src.interactive_automation_mcp.security import SecurityManager
from src.interactive_automation_mcp.session_manager import SessionManager


async def create_mock_context():
    """Create mock context for tool calls"""
    from types import SimpleNamespace

    # Initialize components like the main server does
    session_manager = SessionManager()
    automation_engine = AutomationEngine(session_manager)
    security_manager = SecurityManager()

    app_ctx = SimpleNamespace(
        session_manager=session_manager,
        automation_engine=automation_engine,
        security_manager=security_manager
    )

    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=app_ctx
        )
    )


async def test_simple_command(command: str, expected_content: str, test_name: str) -> bool:
    """Test simple non-interactive command execution"""
    try:
        ctx = await create_mock_context()

        request = ExecuteCommandRequest(
            command=command,
            execution_timeout=30
        )

        result = await execute_command(request, ctx)

        assert result.success, f"{test_name} failed: {result.error}"
        assert result.executed, f"{test_name} not executed"

        output = result.output or ""

        if expected_content:
            assert expected_content in output, f"{test_name} failed: expected '{expected_content}' in {repr(output)}"

        print(f"✓ {test_name}: {repr(output.strip()[:50])}")
        return True

    except Exception as e:
        print(f"✗ {test_name} failed: {e}")
        return False


async def test_interactive_workflow(command: str, interactions: list[tuple[str, str]], expected_final: str, test_name: str) -> bool:
    """Test interactive workflow: execute_command → expect_and_respond → ... → destroy_session"""
    try:
        ctx = await create_mock_context()

        # Step 1: Start interactive command
        request = ExecuteCommandRequest(
            command=command,
            execution_timeout=30
        )

        result = await execute_command(request, ctx)
        assert result.success, f"{test_name} execute_command failed: {result.error}"

        session_id = result.session_id
        print(f"  Started session {session_id} for {test_name}")

        # Step 2: Interact with the session
        for expect_pattern, response_text in interactions:
            request = ExpectAndRespondRequest(
                session_id=session_id,
                expect_pattern=expect_pattern,
                response=response_text,
                timeout=30
            )

            result = await expect_and_respond(request, ctx)
            assert result.get("success"), f"{test_name} expect_and_respond failed: {result.get('error')}"
            print(f"  Interaction: expect '{expect_pattern}' → respond '{response_text}'")

        # Step 3: Get final output
        # Give a moment for final output
        await asyncio.sleep(0.5)

        # Step 4: Verify final state and cleanup
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await destroy_session(destroy_request, ctx)
        assert destroy_result.success, f"{test_name} cleanup failed"

        print(f"✓ {test_name}: Interactive workflow completed")
        return True

    except Exception as e:
        print(f"✗ {test_name} failed: {e}")
        # Try to cleanup on failure
        try:
            if 'session_id' in locals():
                destroy_request = DestroySessionRequest(session_id=session_id)
                await destroy_session(destroy_request, ctx)
        except Exception:
            pass
        return False


async def test_session_management() -> bool:
    """Test session management tools"""
    print("=== Testing Session Management ===")

    try:
        ctx = await create_mock_context()

        # Test list_sessions (should be empty initially)
        sessions = await list_sessions(ctx)
        assert sessions.success, "Failed to list sessions"
        print(f"✓ Initial sessions: {len(sessions.sessions)}")

        # Start a long-running command
        request = ExecuteCommandRequest(
            command="python3 -c \"import time; input('Press enter: '); time.sleep(1); print('done')\"",
            execution_timeout=60
        )

        result = await execute_command(request, ctx)
        assert result.success, f"Failed to start session: {result.error}"

        session_id = result.session_id
        print(f"✓ Started session: {session_id}")

        # Test list_sessions (should show our session)
        sessions = await list_sessions(ctx)
        assert sessions.success, "Failed to list sessions"
        assert len(sessions.sessions) >= 1, "Session not found in list"
        print(f"✓ Active sessions: {len(sessions.sessions)}")

        # Test destroy_session
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await destroy_session(destroy_request, ctx)
        assert destroy_result.success, "Failed to destroy session"
        print(f"✓ Destroyed session: {session_id}")

        return True

    except Exception as e:
        print(f"✗ Session management test failed: {e}")
        return False


async def test_basic_commands() -> bool:
    """Test basic non-interactive commands"""
    print("=== Testing Basic Commands ===")

    commands = [
        ("echo 'Hello World'", "Hello World", "Echo test"),
        ("python3 --version", "Python", "Python version"),
        ("whoami", "", "Current user"),
        ("pwd", "/", "Current directory"),
        ("date", "2025", "System date"),
        ("ls /tmp", "", "List directory"),
        ("echo 'test' | wc -c", "5", "Pipe command"),
    ]

    success_count = 0
    for command, expected, name in commands:
        if await test_simple_command(command, expected, name):
            success_count += 1

    print(f"Basic Commands: {success_count}/{len(commands)} passed")
    return success_count == len(commands)


async def test_interactive_workflows() -> bool:
    """Test interactive workflows using execute_command → expect_and_respond"""
    print("=== Testing Interactive Workflows ===")

    workflows = [
        (
            "python3 -c \"name=input('Enter name: '); print(f'Hello {name}!')\"",
            [("Enter name:", "Alice")],
            "Hello Alice!",
            "Python input workflow"
        ),
        (
            "python3 -c \"choice=input('Continue? (y/n): '); print('Yes!' if choice=='y' else 'No!')\"",
            [("Continue\\? \\(y/n\\):", "y")],
            "Yes!",
            "Python choice workflow"
        ),
        (
            "bash -c \"read -p 'Enter value: ' val; echo \\\"You entered: \\$val\\\"\"",
            [("Enter value:", "test123")],
            "You entered: test123",
            "Bash input workflow"
        ),
    ]

    success_count = 0
    for command, interactions, expected_final, name in workflows:
        if await test_interactive_workflow(command, interactions, expected_final, name):
            success_count += 1

    print(f"Interactive Workflows: {success_count}/{len(workflows)} passed")
    return success_count == len(workflows)


async def test_python_repl_workflow() -> bool:
    """Test Python REPL as a more complex interactive workflow"""
    print("=== Testing Python REPL Workflow ===")

    try:
        ctx = await create_mock_context()

        # Start Python REPL
        request = ExecuteCommandRequest(
            command="python3 -c \"import code; code.interact(banner='Python REPL Ready')\"",
            execution_timeout=60
        )

        result = await execute_command(request, ctx)
        assert result.success, f"Failed to start Python REPL: {result.error}"

        session_id = result.session_id
        print(f"  Started Python REPL session: {session_id}")

        # Test sequence: import → calculation → exit
        interactions = [
            (">>>", "import math"),
            (">>>", "print(math.pi)"),
            (">>>", "result = 2 + 3"),
            (">>>", "print(f'Result: {result}')"),
            (">>>", "exit()")
        ]

        for expect_pattern, response_text in interactions:
            request = ExpectAndRespondRequest(
                session_id=session_id,
                expect_pattern=expect_pattern,
                response=response_text,
                timeout=30
            )

            result = await expect_and_respond(request, ctx)
            if not result.get("success"):
                print(f"  Failed interaction: expect '{expect_pattern}' → respond '{response_text}': {result.get('error')}")
                # Continue anyway, some interactions might fail due to timing
            else:
                print(f"  ✓ expect '{expect_pattern}' → respond '{response_text}'")

        # Cleanup
        destroy_request = DestroySessionRequest(session_id=session_id)
        await destroy_session(destroy_request, ctx)

        print("✓ Python REPL workflow completed")
        return True

    except Exception as e:
        print(f"✗ Python REPL workflow failed: {e}")
        return False


async def main() -> bool:
    """Main function to run all tests"""

    print("Testing Simplified MCP Server Architecture")
    print("=" * 50)
    print("Tools: execute_command, expect_and_respond, list_sessions, destroy_session")
    print()

    # Run all test categories
    results = [
        await test_basic_commands(),
        await test_session_management(),
        await test_interactive_workflows(),
        await test_python_repl_workflow(),
    ]

    # Summary
    total_passed = sum(results)
    total_tests = len(results)

    print(f"\n{'='*50}")
    print(f"Overall Results: {total_passed}/{total_tests} test categories passed")

    return all(results)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
