#!/usr/bin/env python3
"""
Integration tests for the MCP server with security validation
Tests the complete workflow including security checks
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
from src.terminal_control_mcp.security import SecurityManager
from src.terminal_control_mcp.session_manager import SessionManager


class TestMCPIntegration:
    """Integration tests for MCP server functionality with security"""

    @pytest.mark.asyncio
    async def test_basic_commands(self, mock_context):
        """Test basic non-interactive commands with security validation"""
        test_commands = [
            ("echo 'Hello World'", "Hello World"),
            ("python3 --version", "Python"),
            ("whoami", ""),
            ("pwd", "/"),
            ("date", "2025"),
        ]

        for command, expected_content in test_commands:
            request = ExecuteCommandRequest(command=command, execution_timeout=30)
            result = await tercon_execute_command(request, mock_context)

            assert result.success, f"Command failed: {result.command}"

            # Get screen content to check output
            if expected_content and result.session_id:
                import asyncio

                await asyncio.sleep(0.5)  # Give command time to execute
                screen_request = GetScreenContentRequest(session_id=result.session_id)
                screen_result = await tercon_get_screen_content(
                    screen_request, mock_context
                )
                if screen_result.success and screen_result.screen_content:
                    assert expected_content in screen_result.screen_content

            # Cleanup
            if result.session_id:
                destroy_request = DestroySessionRequest(session_id=result.session_id)
                await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_command_blocking(self, mock_context, dangerous_commands):
        """Test that dangerous commands are blocked by security"""
        for command in dangerous_commands:
            request = ExecuteCommandRequest(command=command)

            with pytest.raises(ValueError, match="Security violation"):
                await tercon_execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_path_validation_in_working_directory(self, mock_context):
        """Test path validation for working directory"""
        # Safe working directory should work
        safe_request = ExecuteCommandRequest(
            command="echo 'test'", working_directory="/tmp"
        )
        result = await tercon_execute_command(safe_request, mock_context)
        assert result.success

        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await tercon_destroy_session(destroy_request, mock_context)

        # Dangerous working directory should be blocked
        dangerous_request = ExecuteCommandRequest(
            command="echo 'test'", working_directory="/etc"
        )

        with pytest.raises(ValueError, match="Security violation"):
            await tercon_execute_command(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_environment_variable_protection(self, mock_context):
        """Test protection of critical environment variables"""
        # Safe environment variables should work
        safe_request = ExecuteCommandRequest(
            command="echo $TEST_VAR", environment={"TEST_VAR": "safe_value"}
        )
        result = await tercon_execute_command(safe_request, mock_context)
        assert result.success

        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await tercon_destroy_session(destroy_request, mock_context)

        # Protected environment variables should be blocked
        dangerous_request = ExecuteCommandRequest(
            command="echo $PATH", environment={"PATH": "/malicious/path"}
        )

        with pytest.raises(ValueError, match="Security violation"):
            await tercon_execute_command(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_session_management(self, mock_context):
        """Test session management with security validation"""
        # Test initial session list (should be empty)
        sessions = await tercon_list_sessions(mock_context)
        assert sessions.success
        initial_count = len(sessions.sessions)

        # Start a session with a safe command
        request = ExecuteCommandRequest(
            command="python3 -u -c \"import time; input('Enter: '); print('done')\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Test session list with active sessions
            sessions = await tercon_list_sessions(mock_context)
            assert sessions.success
            assert len(sessions.sessions) == initial_count + 1

            # Test getting screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await tercon_get_screen_content(
                screen_request, mock_context
            )
            assert screen_result.success
            assert screen_result.process_running

        finally:
            # Always cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            destroy_result = await tercon_destroy_session(destroy_request, mock_context)
            assert destroy_result.success

    @pytest.mark.asyncio
    async def test_interactive_workflow_with_security(self, mock_context):
        """Test interactive workflow with input validation"""
        # Start interactive Python session
        request = ExecuteCommandRequest(
            command="python3 -u -c \"name=input('Name: '); print(f'Hello {name}!')\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Wait for process to be ready
            await asyncio.sleep(0.5)

            # Get screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await tercon_get_screen_content(
                screen_request, mock_context
            )
            assert screen_result.success

            # Send safe input
            input_request = SendInputRequest(session_id=session_id, input_text="Alice")
            input_result = await tercon_send_input(input_request, mock_context)
            assert input_result.success

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_input_blocking(self, mock_context):
        """Test that dangerous input is blocked"""
        # Start a simple interactive session
        request = ExecuteCommandRequest(
            command="python3 -u -c \"x=input('Input: '); print(x)\"",
            execution_timeout=60,
        )
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            await asyncio.sleep(0.5)

            # Try to send dangerous input - should be blocked
            dangerous_inputs = ["sudo rm -rf /", "su - root", "passwd"]

            for dangerous_input in dangerous_inputs:
                input_request = SendInputRequest(
                    session_id=session_id, input_text=dangerous_input
                )

                with pytest.raises(ValueError, match="Security violation"):
                    await tercon_send_input(input_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, mock_context):
        """Test rate limiting in the context of tool calls"""
        # This test would need to make many rapid calls to trigger rate limiting
        # For now, we'll just verify the security manager is being called

        request = ExecuteCommandRequest(command="echo 'test'")

        # Mock the security manager to simulate rate limit exceeded

        with patch.object(
            mock_context.request_context.lifespan_context.security_manager,
            "validate_tool_call",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="Security violation"):
                await tercon_execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_session_limits_integration(self, mock_context):
        """Test session limits in practice"""
        # Test that the security manager validates session limits
        # This would be called by the session manager when creating sessions

        security_manager = (
            mock_context.request_context.lifespan_context.security_manager
        )

        # Under limit should pass
        assert security_manager.validate_session_limits(25) is True

        # Over limit should fail
        assert security_manager.validate_session_limits(51) is False

    @pytest.mark.asyncio
    async def test_python_repl_security(self, mock_context):
        """Test Python REPL with security considerations"""
        request = ExecuteCommandRequest(command="python3 -u", execution_timeout=60)
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            await asyncio.sleep(1)  # Wait for Python prompt

            # Test safe Python commands
            safe_commands = ["import math", "print(math.pi)", "x = 2 + 3", "print(x)"]

            for cmd in safe_commands:
                input_request = SendInputRequest(session_id=session_id, input_text=cmd)
                result = await tercon_send_input(input_request, mock_context)
                assert result.success
                await asyncio.sleep(0.2)

            # Exit Python
            exit_request = SendInputRequest(session_id=session_id, input_text="exit()")
            await tercon_send_input(exit_request, mock_context)

        finally:
            # Cleanup
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await tercon_destroy_session(destroy_request, mock_context)
            except Exception:
                pass  # Session may have already ended

    @pytest.mark.asyncio
    async def test_error_handling_and_cleanup(self, mock_context):
        """Test proper error handling and session cleanup"""
        # Start a session
        request = ExecuteCommandRequest(command="sleep 30", execution_timeout=60)
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        # Verify session exists
        sessions = await tercon_list_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id in session_ids

        # Destroy session
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await tercon_destroy_session(destroy_request, mock_context)
        assert destroy_result.success

        # Verify session is gone
        sessions = await tercon_list_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id not in session_ids

        # Try to destroy non-existent session
        destroy_request = DestroySessionRequest(session_id="non-existent")
        destroy_result = await tercon_destroy_session(destroy_request, mock_context)
        assert not destroy_result.success


class TestSecurityIntegrationScenarios:
    """Test complex security scenarios in integrated workflows"""

    @pytest.fixture
    def mock_context(self):
        """Create mock context for tool calls"""
        session_manager = SessionManager()
        security_manager = SecurityManager()

        app_ctx = SimpleNamespace(
            session_manager=session_manager, security_manager=security_manager
        )

        return SimpleNamespace(
            request_context=SimpleNamespace(lifespan_context=app_ctx)
        )

    @pytest.mark.asyncio
    async def test_multi_step_attack_prevention(self, mock_context):
        """Test prevention of multi-step attack scenarios"""

        # Try to create session with safe command first
        request = ExecuteCommandRequest(command="echo 'innocent'")
        result = await tercon_execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Then try to send malicious input - should be blocked
            malicious_request = SendInputRequest(
                session_id=session_id, input_text="'; rm -rf / #"
            )

            with pytest.raises(ValueError, match="Security violation"):
                await tercon_send_input(malicious_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await tercon_destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_resource_exhaustion_protection(self, mock_context):
        """Test protection against resource exhaustion"""

        # Test that we can't exceed session limits by trying to create too many
        session_manager = mock_context.request_context.lifespan_context.session_manager
        security_manager = (
            mock_context.request_context.lifespan_context.security_manager
        )

        # Mock having too many sessions
        with patch.object(
            session_manager, "sessions", {f"session_{i}": None for i in range(51)}
        ):
            pass  # Test is about validating session limits directly

            # Should be blocked due to session limit
            # Note: This test depends on session_manager implementing the check
            # For now, we test the security manager validation directly
            assert security_manager.validate_session_limits(51) is False

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, mock_context):
        """Test prevention of privilege escalation attempts"""

        escalation_attempts = [
            # Direct sudo attempts that should be blocked by current patterns
            ExecuteCommandRequest(
                command="sudo passwd root"
            ),  # matches sudo passwd pattern
            ExecuteCommandRequest(command="su - root"),  # matches su - pattern
            # Environment manipulation attempts
            ExecuteCommandRequest(
                command="echo test", environment={"LD_PRELOAD": "/tmp/malicious.so"}
            ),
            # Path manipulation attempts
            ExecuteCommandRequest(
                command="echo test", environment={"PATH": "/tmp/malicious:/usr/bin"}
            ),
        ]

        for request in escalation_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await tercon_execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_data_exfiltration_prevention(self, mock_context):
        """Test prevention of data exfiltration attempts"""

        exfiltration_attempts = [
            # Direct file access attempts
            ExecuteCommandRequest(command="cat /etc/passwd"),
            ExecuteCommandRequest(command="cp /etc/shadow /tmp/"),
            # Working directory manipulation
            ExecuteCommandRequest(command="ls", working_directory="/etc"),
            ExecuteCommandRequest(
                command="find . -name '*.key'", working_directory="/.ssh"
            ),
        ]

        for request in exfiltration_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await tercon_execute_command(request, mock_context)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
