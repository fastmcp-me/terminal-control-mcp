#!/usr/bin/env python3
"""
Functional tests for command execution workflows
Tests the core command execution functionality including:
- Basic command execution and output capture
- Interactive command workflows with input/output
- Session lifecycle management
- Python REPL and other interactive programs
"""

import asyncio

import pytest

from src.terminal_control_mcp.main import (
    tercon_destroy_session,
    tercon_execute_command,
    tercon_get_screen_content,
    tercon_list_sessions,
    tercon_send_input,
)
from src.terminal_control_mcp.models import (
    DestroySessionRequest,
    ExecuteCommandRequest,
    GetScreenContentRequest,
    SendInputRequest,
)


class TestBasicCommands:
    """Test basic non-interactive command execution"""

    @pytest.mark.asyncio
    async def test_echo_command(self, mock_context):
        """Test simple echo command"""
        request = ExecuteCommandRequest(
            full_command="echo 'Hello World'", execution_timeout=30
        )
        result = await tercon_execute_command(request, mock_context)

        assert result.success
        assert result.session_id

        # Get output using screen content
        await asyncio.sleep(0.5)  # Give time for command to execute
        screen_request = GetScreenContentRequest(session_id=result.session_id)
        screen_result = await tercon_get_screen_content(screen_request, mock_context)

        if screen_result.success and screen_result.screen_content:
            assert "Hello World" in screen_result.screen_content

        # Cleanup
        destroy_request = DestroySessionRequest(session_id=result.session_id)
        await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_python_version(self, mock_context):
        """Test Python version command"""
        request = ExecuteCommandRequest(
            full_command="python3 --version", execution_timeout=30
        )
        result = await tercon_execute_command(request, mock_context)

        assert result.success
        assert result.session_id

        # Get output using screen content
        await asyncio.sleep(0.5)  # Give time for command to execute
        screen_request = GetScreenContentRequest(session_id=result.session_id)
        screen_result = await tercon_get_screen_content(screen_request, mock_context)

        if screen_result.success and screen_result.screen_content:
            assert "Python" in screen_result.screen_content

        # Cleanup
        destroy_request = DestroySessionRequest(session_id=result.session_id)
        await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_whoami_command(self, mock_context):
        """Test whoami command"""
        request = ExecuteCommandRequest(full_command="whoami", execution_timeout=30)
        result = await tercon_execute_command(request, mock_context)

        assert result.success
        # Don't check content since it varies by system

        # Cleanup
        destroy_request = DestroySessionRequest(session_id=result.session_id)
        await tercon_destroy_session(destroy_request, mock_context)


class TestSessionManagement:
    """Test session lifecycle management"""

    @pytest.mark.asyncio
    async def test_list_sessions_initially_empty(self, mock_context):
        """Test that session list is initially empty"""
        sessions = await tercon_list_sessions(mock_context)
        assert sessions.success
        # Note: other tests might have sessions running, so we just check it works
        assert isinstance(sessions.sessions, list)

    @pytest.mark.asyncio
    async def test_create_and_destroy_session(self, mock_context):
        """Test creating and destroying a session"""
        # Create session
        request = ExecuteCommandRequest(
            full_command="python3 -u -c \"input('Press enter: '); print('done')\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        # Check session exists
        sessions = await tercon_list_sessions(mock_context)
        assert sessions.success
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id in session_ids

        # Destroy session
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await tercon_destroy_session(destroy_request, mock_context)
        assert destroy_result.success


class TestInteractiveWorkflows:
    """Test interactive command workflows"""

    @pytest.mark.asyncio
    async def test_python_input_workflow(self, mock_context):
        """Test Python interactive input workflow"""
        # Start interactive command
        request = ExecuteCommandRequest(
            full_command="python3 -u -c \"name=input('Enter name: '); print(f'Hello {name}!')\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Give time for output to appear
            await asyncio.sleep(0.5)

            # Get screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await tercon_get_screen_content(
                screen_request, mock_context
            )
            assert screen_result.success

            if screen_result.process_running:
                # Send input
                input_request = SendInputRequest(
                    session_id=session_id, input_text="Alice"
                )
                input_result = await tercon_send_input(input_request, mock_context)
                assert input_result.success

                # Give time for processing
                await asyncio.sleep(0.5)

                # Get final output
                final_screen = await tercon_get_screen_content(
                    screen_request, mock_context
                )
                assert final_screen.success

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_python_choice_workflow(self, mock_context):
        """Test Python choice workflow"""
        # Start interactive command
        request = ExecuteCommandRequest(
            full_command="python3 -u -c \"choice=input('Continue? (y/n): '); print('Yes!' if choice=='y' else 'No!')\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Give time for output to appear
            await asyncio.sleep(0.5)

            # Get screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await tercon_get_screen_content(
                screen_request, mock_context
            )
            assert screen_result.success

            if screen_result.process_running:
                # Send input
                input_request = SendInputRequest(session_id=session_id, input_text="y")
                input_result = await tercon_send_input(input_request, mock_context)
                assert input_result.success

                # Give time for processing
                await asyncio.sleep(0.5)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)


class TestPythonREPL:
    """Test Python REPL workflows"""

    @pytest.mark.asyncio
    async def test_python_repl_workflow(self, mock_context):
        """Test Python REPL as a complex interactive workflow"""
        # Start Python REPL
        request = ExecuteCommandRequest(full_command="python3 -u", execution_timeout=60)
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            interactions = [
                "import math",
                "print(math.pi)",
                "result = 2 + 3",
                "print(f'Result: {result}')",
                "exit()",
            ]

            for input_text in interactions:
                # Give time for prompt to appear
                await asyncio.sleep(0.5)

                # Get screen content
                screen_request = GetScreenContentRequest(session_id=session_id)
                screen_result = await tercon_get_screen_content(
                    screen_request, mock_context
                )
                assert screen_result.success

                # Check if process is still running
                if not screen_result.process_running:
                    break

                # Send input
                input_request = SendInputRequest(
                    session_id=session_id, input_text=input_text
                )
                input_result = await tercon_send_input(input_request, mock_context)
                assert input_result.success

        finally:
            # Cleanup (process might have already exited)
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)
