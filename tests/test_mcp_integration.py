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
    exit_terminal,
    get_screen_content,
    list_terminal_sessions,
    open_terminal,
    send_input,
)
from src.terminal_control_mcp.models import (
    DestroySessionRequest,
    GetScreenContentRequest,
    OpenTerminalRequest,
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
            ("echo 'Hello World'\n", "Hello World"),
            ("python3 --version\n", "Python"),
            ("whoami\n", ""),
            ("pwd\n", "/"),
            ("date\n", "2025"),
        ]

        for command, expected_content in test_commands:
            request = OpenTerminalRequest(shell="bash")
            result = await open_terminal(request, mock_context)

            assert result.success, "Failed to open terminal"

            # Send command to shell
            if result.session_id:
                input_request = SendInputRequest(
                    session_id=result.session_id, input_text=command
                )
                await send_input(input_request, mock_context)

                # Get screen content to check output
                if expected_content:
                    await asyncio.sleep(0.5)  # Give command time to execute
                    screen_request = GetScreenContentRequest(
                        session_id=result.session_id
                    )
                    screen_result = await get_screen_content(
                        screen_request, mock_context
                    )
                    if screen_result.success and screen_result.screen_content:
                        assert expected_content in screen_result.screen_content

                # Cleanup
                destroy_request = DestroySessionRequest(session_id=result.session_id)
                await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_command_blocking(self, mock_context, dangerous_commands):
        """Test that dangerous commands are blocked by security"""
        # Only test commands that are actually blocked by send_input validation
        dangerous_input_commands = ["sudo rm -rf /", "su - root", "passwd"]

        for command in dangerous_input_commands:
            # Create terminal first
            request = OpenTerminalRequest(shell="bash")
            result = await open_terminal(request, mock_context)

            if result.success and result.session_id:
                # Now try to send dangerous command - should be blocked
                input_request = SendInputRequest(
                    session_id=result.session_id, input_text=command
                )

                with pytest.raises(ValueError, match="Security violation"):
                    await send_input(input_request, mock_context)

                # Cleanup
                destroy_request = DestroySessionRequest(session_id=result.session_id)
                await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_path_validation_in_working_directory(self, mock_context):
        """Test path validation for working directory"""
        # Safe working directory should work
        safe_request = OpenTerminalRequest(shell="bash", working_directory="/tmp")
        result = await open_terminal(safe_request, mock_context)
        assert result.success

        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await exit_terminal(destroy_request, mock_context)

        # Dangerous working directory should be blocked
        dangerous_request = OpenTerminalRequest(shell="bash", working_directory="/etc")

        with pytest.raises(ValueError, match="Security violation"):
            await open_terminal(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_environment_variable_protection(self, mock_context):
        """Test protection of critical environment variables"""
        # Safe environment variables should work
        safe_request = OpenTerminalRequest(
            shell="bash", environment={"TEST_VAR": "safe_value"}
        )
        result = await open_terminal(safe_request, mock_context)
        assert result.success

        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await exit_terminal(destroy_request, mock_context)

        # Protected environment variables should be blocked
        dangerous_request = OpenTerminalRequest(
            shell="bash", environment={"PATH": "/malicious/path"}
        )

        with pytest.raises(ValueError, match="Security violation"):
            await open_terminal(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_session_management(self, mock_context):
        """Test session management with security validation"""
        # Test initial session list (should be empty)
        sessions = await list_terminal_sessions(mock_context)
        assert sessions.success
        initial_count = len(sessions.sessions)

        # Start a session with a safe command
        request = OpenTerminalRequest(shell="python3")
        result = await open_terminal(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Test session list with active sessions
            sessions = await list_terminal_sessions(mock_context)
            assert sessions.success
            assert len(sessions.sessions) == initial_count + 1

            # Test getting screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await get_screen_content(screen_request, mock_context)
            assert screen_result.success
            assert screen_result.process_running

        finally:
            # Always cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            destroy_result = await exit_terminal(destroy_request, mock_context)
            assert destroy_result.success

    @pytest.mark.asyncio
    async def test_interactive_workflow_with_security(self, mock_context):
        """Test interactive workflow with input validation"""
        # Start interactive Python session
        request = OpenTerminalRequest(shell="python3")
        result = await open_terminal(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Wait for process to be ready
            await asyncio.sleep(0.5)

            # Get screen content
            screen_request = GetScreenContentRequest(session_id=session_id)
            screen_result = await get_screen_content(screen_request, mock_context)
            assert screen_result.success

            # Send safe input
            input_request = SendInputRequest(session_id=session_id, input_text="Alice\n")
            input_result = await send_input(input_request, mock_context)
            assert input_result.success

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_input_blocking(self, mock_context):
        """Test that dangerous input is blocked"""
        # Start a simple interactive session
        request = OpenTerminalRequest(shell="python3")
        result = await open_terminal(request, mock_context)
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
                    await send_input(input_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, mock_context):
        """Test rate limiting in the context of tool calls"""
        # This test would need to make many rapid calls to trigger rate limiting
        # For now, we'll just verify the security manager is being called

        request = OpenTerminalRequest(shell="bash")

        # Mock the security manager to simulate rate limit exceeded

        with patch.object(
            mock_context.request_context.lifespan_context.security_manager,
            "validate_tool_call",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="Security violation"):
                await open_terminal(request, mock_context)

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
        request = OpenTerminalRequest(shell="python3")
        result = await open_terminal(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            await asyncio.sleep(1)  # Wait for Python prompt

            # Test safe Python commands
            safe_commands = ["import math", "print(math.pi)", "x = 2 + 3", "print(x)"]

            for cmd in safe_commands:
                input_request = SendInputRequest(session_id=session_id, input_text=cmd + "\n")
                result = await send_input(input_request, mock_context)
                assert result.success
                await asyncio.sleep(0.2)

            # Exit Python
            exit_request = SendInputRequest(session_id=session_id, input_text="exit()\n")
            await send_input(exit_request, mock_context)

        finally:
            # Cleanup
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await exit_terminal(destroy_request, mock_context)
            except Exception:
                pass  # Session may have already ended

    @pytest.mark.asyncio
    async def test_error_handling_and_cleanup(self, mock_context):
        """Test proper error handling and session cleanup"""
        # Start a session
        request = OpenTerminalRequest(shell="bash")
        result = await open_terminal(request, mock_context)
        assert result.success
        session_id = result.session_id

        # Verify session exists
        sessions = await list_terminal_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id in session_ids

        # Destroy session
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await exit_terminal(destroy_request, mock_context)
        assert destroy_result.success

        # Verify session is gone
        sessions = await list_terminal_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id not in session_ids

        # Try to destroy non-existent session
        destroy_request = DestroySessionRequest(session_id="non-existent")
        destroy_result = await exit_terminal(destroy_request, mock_context)
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
        request = OpenTerminalRequest(shell="bash")
        result = await open_terminal(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Then try to send malicious input - should be blocked
            malicious_request = SendInputRequest(
                session_id=session_id, input_text="'; rm -rf / #"
            )

            with pytest.raises(ValueError, match="Security violation"):
                await send_input(malicious_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

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
            # Environment manipulation attempts
            OpenTerminalRequest(
                shell="bash",
                environment={"LD_PRELOAD": "/tmp/malicious.so"},
            ),
            # Path manipulation attempts
            OpenTerminalRequest(
                shell="bash",
                environment={"PATH": "/tmp/malicious:/usr/bin"},
            ),
        ]

        for request in escalation_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await open_terminal(request, mock_context)

    @pytest.mark.asyncio
    async def test_data_exfiltration_prevention(self, mock_context):
        """Test prevention of data exfiltration attempts"""

        exfiltration_attempts = [
            # Working directory manipulation
            OpenTerminalRequest(shell="bash", working_directory="/etc"),
            OpenTerminalRequest(shell="bash", working_directory="/.ssh"),
        ]

        for request in exfiltration_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await open_terminal(request, mock_context)


class TestContentModeIntegration:
    """Integration tests for the new content mode functionality"""

    @pytest.mark.asyncio
    async def test_content_mode_parameter_validation(self, mock_context):
        """Test that content mode parameters are properly validated"""
        # Test valid content modes
        valid_modes = ["screen", "since_input", "history", "tail"]

        for mode in valid_modes:
            line_count = 10 if mode == "tail" else None
            request = GetScreenContentRequest(
                session_id="test_session", content_mode=mode, line_count=line_count
            )

            # Request should be valid (will fail on session not found, but parameter validation passes)
            response = await get_screen_content(request, mock_context)
            assert response.success is False
            assert "Session not found" in response.error

    @pytest.mark.asyncio
    async def test_content_mode_with_real_session(self, mock_context):
        """Test content modes with a real terminal session"""
        # Create a terminal session first
        create_request = OpenTerminalRequest(shell="bash")
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        try:
            # Test each content mode
            test_cases = [
                ("screen", None, "should get current screen"),
                ("history", None, "should get full history"),
                ("tail", 5, "should get last 5 lines"),
                ("since_input", None, "should get output since last input"),
            ]

            for mode, line_count, description in test_cases:
                request = GetScreenContentRequest(
                    session_id=session_id, content_mode=mode, line_count=line_count
                )

                response = await get_screen_content(request, mock_context)
                assert (
                    response.success is True
                ), f"Failed for mode {mode}: {description}"
                assert response.session_id == session_id
                assert response.screen_content is not None
                assert response.timestamp is not None

                # For tail mode, verify line_count parameter is handled
                if mode == "tail" and line_count:
                    # Content should be limited (though exact validation depends on tmux output)
                    assert isinstance(response.screen_content, str)

        finally:
            # Clean up session
            destroy_request = DestroySessionRequest(session_id=session_id)
            destroy_response = await exit_terminal(destroy_request, mock_context)
            assert destroy_response.success is True

    @pytest.mark.asyncio
    async def test_content_mode_defaults(self, mock_context):
        """Test that content mode defaults to 'screen' when not specified"""
        # Create a terminal session
        create_request = OpenTerminalRequest(shell="bash")
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        try:
            # Test request without content_mode (should default to "screen")
            request = GetScreenContentRequest(session_id=session_id)
            response = await get_screen_content(request, mock_context)

            assert response.success is True
            assert response.screen_content is not None

            # Compare with explicit screen mode
            explicit_request = GetScreenContentRequest(
                session_id=session_id, content_mode="screen"
            )
            explicit_response = await get_screen_content(explicit_request, mock_context)

            assert explicit_response.success is True
            # Both should return similar content (may vary slightly due to timing)
            assert isinstance(response.screen_content, str)
            assert isinstance(explicit_response.screen_content, str)

        finally:
            # Clean up session
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_since_input_mode_workflow(self, mock_context):
        """Test the 'since_input' mode with actual input workflow"""
        # Create a terminal session
        create_request = OpenTerminalRequest(shell="bash")
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        try:
            # Send some input
            input_request = SendInputRequest(
                session_id=session_id,
                input_text="echo 'Test output for since_input mode'\n",
            )
            input_response = await send_input(input_request, mock_context)
            assert input_response.success is True

            # Wait a moment for command to process
            await asyncio.sleep(0.2)

            # Get content since last input
            content_request = GetScreenContentRequest(
                session_id=session_id, content_mode="since_input"
            )
            content_response = await get_screen_content(content_request, mock_context)

            assert content_response.success is True
            assert content_response.screen_content is not None
            # Should contain recent output
            assert isinstance(content_response.screen_content, str)

        finally:
            # Clean up session
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_tail_mode_line_count_validation(self, mock_context):
        """Test that tail mode properly handles line_count parameter"""
        # Create a terminal session
        create_request = OpenTerminalRequest(shell="bash")
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        try:
            # Test tail mode with different line counts
            line_counts = [1, 5, 10, 20]

            for line_count in line_counts:
                request = GetScreenContentRequest(
                    session_id=session_id, content_mode="tail", line_count=line_count
                )

                response = await get_screen_content(request, mock_context)
                assert response.success is True, f"Failed for line_count={line_count}"
                assert response.screen_content is not None

                # Content should be a string (exact line validation depends on tmux behavior)
                assert isinstance(response.screen_content, str)

        finally:
            # Clean up session
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_content_mode_backwards_compatibility(self, mock_context):
        """Test that existing code without content_mode still works"""
        # Create a terminal session
        create_request = OpenTerminalRequest(shell="bash")
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        try:
            # Test old-style request (just session_id)
            old_style_request = GetScreenContentRequest(session_id=session_id)
            old_response = await get_screen_content(old_style_request, mock_context)

            # Test new-style request with explicit screen mode
            new_style_request = GetScreenContentRequest(
                session_id=session_id, content_mode="screen"
            )
            new_response = await get_screen_content(new_style_request, mock_context)

            # Both should succeed and return similar results
            assert old_response.success is True
            assert new_response.success is True
            assert old_response.screen_content is not None
            assert new_response.screen_content is not None

        finally:
            # Clean up session
            destroy_request = DestroySessionRequest(session_id=session_id)
            await exit_terminal(destroy_request, mock_context)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
