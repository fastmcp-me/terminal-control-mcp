#!/usr/bin/env python3
"""
Test the simplified MCP server architecture:
- execute_command: Starts session, runs command
- get_screen_content: Gets current terminal output
- send_input: Sends input to session
- list_sessions: Shows active sessions
- destroy_session: Cleans up sessions
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.interactive_automation_mcp.main import (
    destroy_session,
    execute_command,
    get_screen_content,
    list_sessions,
    send_input,
)
from src.interactive_automation_mcp.models import (
    DestroySessionRequest,
    ExecuteCommandRequest,
    GetScreenContentRequest,
    SendInputRequest,
)
from src.interactive_automation_mcp.security import SecurityManager
from src.interactive_automation_mcp.session_manager import SessionManager


def setup_test_logging() -> str:
    """Set up logging to both console and file"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"test_simplified_{timestamp}.log")

    # Configure logging
    logger = logging.getLogger("interactive-automation-mcp")
    logger.setLevel(logging.INFO)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger (avoid duplicate handlers)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)

    return log_file


async def create_mock_context() -> Any:
    """Create mock context for tool calls"""
    # Initialize components like the main server does
    session_manager = SessionManager()
    security_manager = SecurityManager()

    app_ctx = SimpleNamespace(
        session_manager=session_manager, security_manager=security_manager
    )

    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app_ctx))


async def test_simple_command(
    command: str, expected_content: str, test_name: str
) -> bool:
    """Test simple non-interactive command execution"""
    try:
        ctx = await create_mock_context()

        request = ExecuteCommandRequest(
            command=command,
            execution_timeout=30,
        )

        result = await execute_command(request, ctx)

        assert result.success, f"{test_name} failed: {result.error}"

        output = result.output or ""

        if expected_content:
            assert (
                expected_content in output
            ), f"{test_name} failed: expected '{expected_content}' in {repr(output)}"

        print(f"✓ {test_name}: {repr(output.strip()[:50])}")
        destroy_request = DestroySessionRequest(session_id=result.session_id)
        await destroy_session(destroy_request, ctx)
        return True

    except Exception as e:
        print(f"✗ {test_name} failed: {e}")
        return False


async def test_interactive_workflow(
    command: str, interactions: list[tuple[str, str]], test_name: str
) -> bool:
    """Test interactive workflow: execute_command → get_screen_content → send_input → ... → destroy_session"""
    ctx = None
    session_id = None
    try:
        ctx = await create_mock_context()

        # 1. Start interactive command
        request = ExecuteCommandRequest(
            command=command,
            execution_timeout=60,
        )
        result = await execute_command(request, ctx)
        assert result.success, f"{test_name} execute_command failed: {result.error}"
        session_id = result.session_id
        print(f"  Started session {session_id} for {test_name}")

        # 2. Process each interaction
        for _expected_pattern, input_text in interactions:
            # Give time for output to appear
            await asyncio.sleep(0.5)

            # Get current screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await get_screen_content(screen_request, ctx)
            assert (
                screen_result.success
            ), f"Failed to get screen content: {screen_result.error}"

            screen_content = screen_result.screen_content or ""
            print(
                f"  Screen content: {repr(screen_content[-100:])}"
            )  # Show last 100 chars

            # Check if process is still running
            if not screen_result.process_running:
                print(f"  Process ended, final content: {repr(screen_content)}")
                break

            # Send input
            input_request = SendInputRequest(
                session_id=session_id, input_text=input_text
            )
            input_result = await send_input(input_request, ctx)
            assert input_result.success, f"Failed to send input: {input_result.error}"
            print(f"  Sent input: '{input_text}'")

        # Small delay before cleanup
        await asyncio.sleep(0.5)

        # Cleanup
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await destroy_session(destroy_request, ctx)
        assert destroy_result.success, f"{test_name} cleanup failed"

        print(f"✓ {test_name}: Interactive workflow completed")
        return True

    except Exception as e:
        print(f"✗ {test_name} failed: {e}")
        # Cleanup on error
        if ctx and session_id:
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await destroy_session(destroy_request, ctx)
                print(f"  ✓ Cleaned up session {session_id}")
            except Exception as cleanup_error:
                print(f"  ✗ Cleanup failed: {cleanup_error}")
        return False


async def test_session_management() -> bool:
    """Test session management tools"""
    print("=== Testing Session Management ===")
    ctx = None
    session_id = None
    try:
        ctx = await create_mock_context()

        # Test initial session list (should be empty)
        sessions = await list_sessions(ctx)
        assert sessions.success, "Failed to list sessions"
        print(f"✓ Initial sessions: {len(sessions.sessions)}")

        # Start a long-running session
        request = ExecuteCommandRequest(
            command="python3 -u -c \"import time; input('Press enter: '); time.sleep(1); print('done')\"",
            execution_timeout=60,
        )
        result = await execute_command(request, ctx)
        assert result.success, f"Failed to start session: {result.error}"
        session_id = result.session_id
        print(f"✓ Started session: {session_id}")

        # Test session list with active sessions
        sessions = await list_sessions(ctx)
        assert sessions.success, "Failed to list sessions"
        assert len(sessions.sessions) >= 1, "Session not found in list"
        print(f"✓ Active sessions: {len(sessions.sessions)}")

        # Test session destruction
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await destroy_session(destroy_request, ctx)
        assert destroy_result.success, "Failed to destroy session"
        print(f"✓ Destroyed session: {session_id}")

        return True

    except Exception as e:
        print(f"✗ Session management test failed: {e}")
        # Cleanup any remaining session
        if ctx and session_id:
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await destroy_session(destroy_request, ctx)
                print(f"  ✓ Cleaned up session {session_id}")
            except Exception as cleanup_error:
                print(f"  ✗ Cleanup failed: {cleanup_error}")
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
    """Test interactive workflows using the new turn-taking pattern"""
    print("=== Testing Interactive Workflows ===")

    workflows = [
        (
            "python3 -u -c \"name=input('Enter name: '); print(f'Hello {name}!')\"",
            [("Enter name:", "Alice")],
            "Python input workflow",
        ),
        (
            "python3 -u -c \"choice=input('Continue? (y/n): '); print('Yes!' if choice=='y' else 'No!')\"",
            [("Continue?", "y")],
            "Python choice workflow",
        ),
    ]

    success_count = 0
    for command, interactions, name in workflows:
        if await test_interactive_workflow(command, interactions, name):
            success_count += 1

    print(f"Interactive Workflows: {success_count}/{len(workflows)} passed")
    return success_count == len(workflows)


async def test_python_repl_workflow() -> bool:
    """Test Python REPL as a more complex interactive workflow"""
    print("=== Testing Python REPL Workflow ===")

    interactions = [
        (">>>", "import math"),
        (">>>", "print(math.pi)"),
        (">>>", "result = 2 + 3"),
        (">>>", "print(f'Result: {result}')"),
        (">>>", "exit()"),
    ]

    return await test_interactive_workflow(
        "python3 -u", interactions, "Python REPL workflow"
    )


async def main() -> bool:
    """Main function to run all tests"""

    # Set up logging to file
    log_file = setup_test_logging()

    print("Testing Simplified MCP Server Architecture")
    print("=" * 50)
    print(
        "Tools: execute_command, get_screen_content, send_input, list_sessions, destroy_session"
    )
    print(f"Logs will be written to: {log_file}")
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
    print(f"Full execution logs saved to: {log_file}")

    return all(results)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
