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
            result = await execute_command(request, mock_context)
            
            assert result.success, f"Command failed: {result.command}"
            
            if expected_content:
                output = result.output or ""
                assert expected_content in output
            
            # Cleanup
            if result.session_id:
                destroy_request = DestroySessionRequest(session_id=result.session_id)
                await destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_command_blocking(self, mock_context, dangerous_commands):
        """Test that dangerous commands are blocked by security"""
        for command in dangerous_commands:
            request = ExecuteCommandRequest(command=command)
            
            with pytest.raises(ValueError, match="Security violation"):
                await execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_path_validation_in_working_directory(self, mock_context):
        """Test path validation for working directory"""
        # Safe working directory should work
        safe_request = ExecuteCommandRequest(
            command="echo 'test'",
            working_directory="/tmp"
        )
        result = await execute_command(safe_request, mock_context)
        assert result.success
        
        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await destroy_session(destroy_request, mock_context)

        # Dangerous working directory should be blocked
        dangerous_request = ExecuteCommandRequest(
            command="echo 'test'",
            working_directory="/etc"
        )
        
        with pytest.raises(ValueError, match="Security violation"):
            await execute_command(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_environment_variable_protection(self, mock_context):
        """Test protection of critical environment variables"""
        # Safe environment variables should work
        safe_request = ExecuteCommandRequest(
            command="echo $TEST_VAR",
            environment={"TEST_VAR": "safe_value"}
        )
        result = await execute_command(safe_request, mock_context)
        assert result.success
        
        # Cleanup
        if result.session_id:
            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await destroy_session(destroy_request, mock_context)

        # Protected environment variables should be blocked
        dangerous_request = ExecuteCommandRequest(
            command="echo $PATH",
            environment={"PATH": "/malicious/path"}
        )
        
        with pytest.raises(ValueError, match="Security violation"):
            await execute_command(dangerous_request, mock_context)

    @pytest.mark.asyncio
    async def test_session_management(self, mock_context):
        """Test session management with security validation"""
        # Test initial session list (should be empty)
        sessions = await list_sessions(mock_context)
        assert sessions.success
        initial_count = len(sessions.sessions)

        # Start a session with a safe command
        request = ExecuteCommandRequest(
            command="python3 -u -c \"import time; input('Enter: '); print('done')\"",
            execution_timeout=60,
        )
        result = await execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Test session list with active sessions
            sessions = await list_sessions(mock_context)
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
            destroy_result = await destroy_session(destroy_request, mock_context)
            assert destroy_result.success

    @pytest.mark.asyncio
    async def test_interactive_workflow_with_security(self, mock_context):
        """Test interactive workflow with input validation"""
        # Start interactive Python session
        request = ExecuteCommandRequest(
            command="python3 -u -c \"name=input('Name: '); print(f'Hello {name}!')\"",
            execution_timeout=60
        )
        result = await execute_command(request, mock_context)
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
            input_request = SendInputRequest(
                session_id=session_id, 
                input_text="Alice"
            )
            input_result = await send_input(input_request, mock_context)
            assert input_result.success

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_dangerous_input_blocking(self, mock_context):
        """Test that dangerous input is blocked"""
        # Start a simple interactive session
        request = ExecuteCommandRequest(
            command="python3 -u -c \"x=input('Input: '); print(x)\"",
            execution_timeout=60
        )
        result = await execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            await asyncio.sleep(0.5)

            # Try to send dangerous input - should be blocked
            dangerous_inputs = [
                "sudo rm -rf /",
                "su - root", 
                "passwd"
            ]

            for dangerous_input in dangerous_inputs:
                input_request = SendInputRequest(
                    session_id=session_id,
                    input_text=dangerous_input
                )
                
                with pytest.raises(ValueError, match="Security violation"):
                    await send_input(input_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, mock_context):
        """Test rate limiting in the context of tool calls"""
        # This test would need to make many rapid calls to trigger rate limiting
        # For now, we'll just verify the security manager is being called
        
        request = ExecuteCommandRequest(command="echo 'test'")
        
        # Mock the security manager to simulate rate limit exceeded
        original_validate = mock_context.request_context.lifespan_context.security_manager.validate_tool_call
        
        with patch.object(
            mock_context.request_context.lifespan_context.security_manager,
            'validate_tool_call',
            return_value=False
        ):
            with pytest.raises(ValueError, match="Security violation"):
                await execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_session_limits_integration(self, mock_context):
        """Test session limits in practice"""
        # Test that the security manager validates session limits
        # This would be called by the session manager when creating sessions
        
        security_manager = mock_context.request_context.lifespan_context.security_manager
        
        # Under limit should pass
        assert security_manager.validate_session_limits(25) is True
        
        # Over limit should fail
        assert security_manager.validate_session_limits(51) is False

    @pytest.mark.asyncio
    async def test_python_repl_security(self, mock_context):
        """Test Python REPL with security considerations"""
        request = ExecuteCommandRequest(command="python3 -u", execution_timeout=60)
        result = await execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            await asyncio.sleep(1)  # Wait for Python prompt

            # Test safe Python commands
            safe_commands = [
                "import math",
                "print(math.pi)",
                "x = 2 + 3",
                "print(x)"
            ]

            for cmd in safe_commands:
                input_request = SendInputRequest(session_id=session_id, input_text=cmd)
                result = await send_input(input_request, mock_context)
                assert result.success
                await asyncio.sleep(0.2)

            # Exit Python
            exit_request = SendInputRequest(session_id=session_id, input_text="exit()")
            await send_input(exit_request, mock_context)

        finally:
            # Cleanup
            try:
                destroy_request = DestroySessionRequest(session_id=session_id)
                await destroy_session(destroy_request, mock_context)
            except:
                pass  # Session may have already ended

    @pytest.mark.asyncio
    async def test_error_handling_and_cleanup(self, mock_context):
        """Test proper error handling and session cleanup"""
        # Start a session
        request = ExecuteCommandRequest(command="sleep 30", execution_timeout=60)
        result = await execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        # Verify session exists
        sessions = await list_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id in session_ids

        # Destroy session
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_result = await destroy_session(destroy_request, mock_context)
        assert destroy_result.success

        # Verify session is gone
        sessions = await list_sessions(mock_context)
        session_ids = [s.session_id for s in sessions.sessions]
        assert session_id not in session_ids

        # Try to destroy non-existent session
        destroy_request = DestroySessionRequest(session_id="non-existent")
        destroy_result = await destroy_session(destroy_request, mock_context)
        assert not destroy_result.success


class TestSecurityIntegrationScenarios:
    """Test complex security scenarios in integrated workflows"""

    @pytest.fixture
    async def mock_context(self):
        """Create mock context for tool calls"""
        session_manager = SessionManager()
        security_manager = SecurityManager()

        app_ctx = SimpleNamespace(
            session_manager=session_manager, 
            security_manager=security_manager
        )

        return SimpleNamespace(
            request_context=SimpleNamespace(lifespan_context=app_ctx)
        )

    @pytest.mark.asyncio
    async def test_multi_step_attack_prevention(self, mock_context):
        """Test prevention of multi-step attack scenarios"""
        
        # Try to create session with safe command first
        request = ExecuteCommandRequest(command="echo 'innocent'")
        result = await execute_command(request, mock_context)
        assert result.success
        session_id = result.session_id

        try:
            # Then try to send malicious input - should be blocked
            malicious_request = SendInputRequest(
                session_id=session_id,
                input_text="'; rm -rf / #"
            )
            
            with pytest.raises(ValueError, match="Security violation"):
                await send_input(malicious_request, mock_context)

        finally:
            # Cleanup
            destroy_request = DestroySessionRequest(session_id=session_id)
            await destroy_session(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_resource_exhaustion_protection(self, mock_context):
        """Test protection against resource exhaustion"""
        
        # Test that we can't exceed session limits by trying to create too many
        session_manager = mock_context.request_context.lifespan_context.session_manager
        security_manager = mock_context.request_context.lifespan_context.security_manager
        
        # Mock having too many sessions
        with patch.object(session_manager, 'session_count', return_value=51):
            request = ExecuteCommandRequest(command="echo 'test'")
            
            # Should be blocked due to session limit
            # Note: This test depends on session_manager implementing the check
            # For now, we test the security manager validation directly
            assert security_manager.validate_session_limits(51) is False

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, mock_context):
        """Test prevention of privilege escalation attempts"""
        
        escalation_attempts = [
            # Direct sudo attempts
            ExecuteCommandRequest(command="sudo -s"),
            ExecuteCommandRequest(command="sudo su -"),
            
            # Environment manipulation attempts
            ExecuteCommandRequest(
                command="echo test",
                environment={"LD_PRELOAD": "/tmp/malicious.so"}
            ),
            
            # Path manipulation attempts  
            ExecuteCommandRequest(
                command="echo test",
                environment={"PATH": "/tmp/malicious:/usr/bin"}
            )
        ]
        
        for request in escalation_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await execute_command(request, mock_context)

    @pytest.mark.asyncio
    async def test_data_exfiltration_prevention(self, mock_context):
        """Test prevention of data exfiltration attempts"""
        
        exfiltration_attempts = [
            # Direct file access attempts
            ExecuteCommandRequest(command="cat /etc/passwd"),
            ExecuteCommandRequest(command="cp /etc/shadow /tmp/"),
            
            # Working directory manipulation
            ExecuteCommandRequest(
                command="ls",
                working_directory="/etc"
            ),
            ExecuteCommandRequest(
                command="find . -name '*.key'",
                working_directory="/.ssh"
            )
        ]
        
        for request in exfiltration_attempts:
            with pytest.raises(ValueError, match="Security violation"):
                await execute_command(request, mock_context)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])