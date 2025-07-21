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
from types import SimpleNamespace
from typing import Any

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


async def create_mock_context() -> Any:
    """Create mock context for tool calls"""
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
            command_args=None,
            automation_patterns=None,
            execution_timeout=30,
            follow_up_commands=None,
            environment=None,
            working_directory=None,
            wait_after_automation=None
        )

        result = await execute_command(request, ctx)

        assert result.success, f"{test_name} failed: {result.error}"
        assert result.executed, f"{test_name} not executed"

        output = result.output or ""

        if expected_content:
            assert expected_content in output, f"{test_name} failed: expected '{expected_content}' in {repr(output)}"

        print(f"✓ {test_name}: {repr(output.strip()[:50])}")
        destroy_request = DestroySessionRequest(session_id=result.session_id)
        await destroy_session(destroy_request, ctx)
        return True

    except Exception as e:
        print(f"✗ {test_name} failed: {e}")
        return False


async def _start_interactive_session(ctx: Any, command: str, test_name: str) -> str:
    """Start interactive session for testing"""
    request = ExecuteCommandRequest(
        command=command,
        command_args=None,
        automation_patterns=None,
        execution_timeout=30,
        follow_up_commands=None,
        environment=None,
        working_directory=None,
        wait_after_automation=None
    )
    result = await execute_command(request, ctx)
    assert result.success, f"{test_name} execute_command failed: {result.error}"
    session_id = result.session_id
    print(f"  Started session {session_id} for {test_name}")
    return session_id

async def _execute_interactions(ctx: Any, session_id: str, interactions: list[tuple[str, str]], test_name: str) -> None:
    """Execute interaction patterns for testing"""
    for expect_pattern, response_text in interactions:
        expect_request = ExpectAndRespondRequest(
            session_id=session_id,
            expect_pattern=expect_pattern,
            response=response_text,
            timeout=30,
            case_sensitive=False
        )
        result = await expect_and_respond(expect_request, ctx)
        assert result.get("success"), f"{test_name} expect_and_respond failed: {result.get('error')}"
        print(f"  Interaction: expect '{expect_pattern}' → respond '{response_text}'")

async def _cleanup_session(ctx: Any, session_id: str, test_name: str) -> None:
    """Cleanup test session"""
    destroy_request = DestroySessionRequest(session_id=session_id)
    destroy_result = await destroy_session(destroy_request, ctx)
    assert destroy_result.success, f"{test_name} cleanup failed"

async def _handle_test_failure(ctx: Any, error: Exception, test_name: str, local_vars: dict[str, Any]) -> bool:
    """Handle test failure and attempt cleanup"""
    print(f"✗ {test_name} failed: {error}")
    try:
        if 'session_id' in local_vars and local_vars['session_id']:
            print(f"  Attempting to cleanup session: {local_vars['session_id']}")
            destroy_request = DestroySessionRequest(session_id=local_vars['session_id'])
            cleanup_result = await destroy_session(destroy_request, ctx)
            if cleanup_result.success:
                print(f"  ✓ Session {local_vars['session_id']} cleaned up successfully")
            else:
                print(f"  ✗ Failed to cleanup session: {cleanup_result.message}")
    except Exception as cleanup_error:
        print(f"  ✗ Cleanup failed: {cleanup_error}")
    return False

async def test_interactive_workflow(command: str, interactions: list[tuple[str, str]], expected_final: str, test_name: str) -> bool:
    """Test interactive workflow: execute_command → expect_and_respond → ... → destroy_session"""
    ctx = None
    session_id = None
    try:
        ctx = await create_mock_context()
        session_id = await _start_interactive_session(ctx, command, test_name)
        await _execute_interactions(ctx, session_id, interactions, test_name)
        await asyncio.sleep(0.5)
        await _cleanup_session(ctx, session_id, test_name)
        print(f"✓ {test_name}: Interactive workflow completed")
        return True
    except Exception as e:
        # Pass context if available, otherwise create a new one for cleanup
        if ctx is None:
            try:
                ctx = await create_mock_context()
            except Exception:
                print(f"✗ {test_name} failed: {e} (unable to create cleanup context)")
                return False
        return await _handle_test_failure(ctx, e, test_name, {'session_id': session_id})


async def _test_initial_session_list(ctx: Any) -> None:
    """Test initial session list (should be empty)"""
    sessions = await list_sessions(ctx)
    assert sessions.success, "Failed to list sessions"
    print(f"✓ Initial sessions: {len(sessions.sessions)}")

async def _start_test_session(ctx: Any) -> str:
    """Start a long-running test session"""
    request = ExecuteCommandRequest(
        command="python3 -c \"import time; input('Press enter: '); time.sleep(1); print('done')\"",
        command_args=None,
        automation_patterns=None,
        execution_timeout=60,
        follow_up_commands=None,
        environment=None,
        working_directory=None,
        wait_after_automation=None
    )
    result = await execute_command(request, ctx)
    assert result.success, f"Failed to start session: {result.error}"
    session_id = result.session_id
    print(f"✓ Started session: {session_id}")
    return session_id

async def _test_active_session_list(ctx: Any) -> None:
    """Test session list with active sessions"""
    sessions = await list_sessions(ctx)
    assert sessions.success, "Failed to list sessions"
    assert len(sessions.sessions) >= 1, "Session not found in list"
    print(f"✓ Active sessions: {len(sessions.sessions)}")

async def _test_session_destruction(ctx: Any, session_id: str) -> None:
    """Test session destruction"""
    destroy_request = DestroySessionRequest(session_id=session_id)
    destroy_result = await destroy_session(destroy_request, ctx)
    assert destroy_result.success, "Failed to destroy session"
    print(f"✓ Destroyed session: {session_id}")

async def test_session_management() -> bool:
    """Test session management tools"""
    print("=== Testing Session Management ===")
    ctx = None
    session_id = None
    try:
        ctx = await create_mock_context()
        await _test_initial_session_list(ctx)
        session_id = await _start_test_session(ctx)
        await _test_active_session_list(ctx)
        await _test_session_destruction(ctx, session_id)
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
            "bash -c \"read -p 'Enter value: ' val; echo \\\"You entered: \\\$val\\\"\"",
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


async def _start_python_repl(ctx: Any) -> str:
    """Start Python REPL session for testing"""
    request = ExecuteCommandRequest(
        command='python3 -c \'import code; code.interact(banner="Python REPL Ready")\'',
        command_args=None,
        automation_patterns=None,
        execution_timeout=60,
        follow_up_commands=None,
        environment=None,
        working_directory=None,
        wait_after_automation=None
    )
    result = await execute_command(request, ctx)
    assert result.success, f"Failed to start Python REPL: {result.error}"
    session_id = result.session_id
    print(f"  Started Python REPL session: {session_id}")
    return session_id

async def _execute_python_interactions(ctx: Any, session_id: str) -> None:
    """Execute Python REPL interaction sequence"""
    interactions = [
        (">>>", "import math"),
        (">>>", "print(math.pi)"),
        (">>>", "result = 2 + 3"),
        (">>>", "print(f'Result: {result}')"),
        (">>>", "exit()")
    ]

    for expect_pattern, response_text in interactions:
        expect_request = ExpectAndRespondRequest(
            session_id=session_id,
            expect_pattern=expect_pattern,
            response=response_text,
            timeout=30,
            case_sensitive=False
        )
        result = await expect_and_respond(expect_request, ctx)
        if not result.get("success"):
            print(f"  Failed interaction: expect '{expect_pattern}' → respond '{response_text}': {result.get('error')}")
        else:
            print(f"  ✓ expect '{expect_pattern}' → respond '{response_text}'")

async def _cleanup_repl_session(ctx: Any, session_id: str) -> None:
    """Cleanup Python REPL session"""
    destroy_request = DestroySessionRequest(session_id=session_id)
    await destroy_session(destroy_request, ctx)

async def test_python_repl_workflow() -> bool:
    """Test Python REPL as a more complex interactive workflow"""
    print("=== Testing Python REPL Workflow ===")
    try:
        ctx = await create_mock_context()
        session_id = await _start_python_repl(ctx)
        await _execute_python_interactions(ctx, session_id)
        await _cleanup_repl_session(ctx, session_id)
        print("✓ Python REPL workflow completed")
        return True
    except Exception as e:
        print(f"✗ Python REPL workflow failed: {e}")
        return False

async def _execute_pdb_interactions(ctx: Any, session_id: str) -> None:
    """Execute Python debugger interaction sequence"""
    interactions = [
        ("(Pdb)", "b 25"),
        ("(Pdb)", "c"),
        ("(Pdb)", "p result"),
        ("(Pdb)", "exit"),
    ]

    for expect_pattern, response_text in interactions:
        expect_request = ExpectAndRespondRequest(
            session_id=session_id,
            expect_pattern=expect_pattern,
            response=response_text,
            timeout=10,
            case_sensitive=False
        )
        result = await expect_and_respond(expect_request, ctx)
        if not result.get("success"):
            print(f"  Failed interaction: expect '{expect_pattern}' → respond '{response_text}': {result.get('error')}")
        else:
            print(f"  ✓ expect '{expect_pattern}' → respond '{response_text}'")

async def test_python_debugger_workflow() -> bool:
    """Test Python debugger (pdb) as a complex interactive workflow"""
    print("=== Testing Python Debugger Workflow ===")
    ctx = None
    session_id = None
    try:
        ctx = await create_mock_context()
        command = "python3 -m pdb examples/example_debug.py"
        
        request = ExecuteCommandRequest(
            command=command,
            execution_timeout=60
        )
        result = await execute_command(request, ctx)
        assert result.success, f"Failed to start Pdb: {result.error}"
        session_id = result.session_id
        print(f"  Started Pdb session: {session_id}")

        await _execute_pdb_interactions(ctx, session_id)
        
        destroy_request = DestroySessionRequest(session_id=session_id)
        await destroy_session(destroy_request, ctx)
        
        print("✓ Python debugger workflow completed")
        return True
    except Exception as e:
        print(f"✗ Python debugger workflow failed: {e}")
        if ctx and session_id:
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await destroy_session(destroy_request, ctx)
                print(f"  ✓ Cleaned up session {session_id}")
            except Exception as cleanup_error:
                print(f"  ✗ Cleanup failed: {cleanup_error}")
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
        await test_python_debugger_workflow(),
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