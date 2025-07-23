#!/usr/bin/env python3
"""
Unit tests for SecurityManager
Focused on testing individual security validation methods without integration
"""

import json
import os
import tempfile
import time
from unittest.mock import patch

import pytest

from src.terminal_control_mcp.security import (
    DEFAULT_MAX_CALLS_PER_MINUTE,
    DEFAULT_MAX_SESSIONS,
    EXPECTED_MIN_BASE_PATHS,
    MAX_LOG_VALUE_LENGTH,
    RateLimitData,
)


class TestRateLimitData:
    """Test RateLimitData class functionality"""

    def test_rate_limit_data_creation(self):
        """Test creating RateLimitData instance"""
        data = RateLimitData("test_client")
        assert data.client_id == "test_client"
        assert data.call_timestamps == []
        assert data.get_recent_call_count() == 0

    def test_add_call(self):
        """Test adding calls to rate limit data"""
        data = RateLimitData("test_client")
        now = time.time()

        data.add_call(now)
        assert len(data.call_timestamps) == 1
        assert data.get_recent_call_count() == 1

    def test_clean_old_calls(self):
        """Test cleaning old calls from rate limit data"""
        data = RateLimitData("test_client")
        now = time.time()

        # Add old call (65 seconds ago)
        data.add_call(now - 65)
        # Add recent call (30 seconds ago)
        data.add_call(now - 30)

        expected_call_count = 2
        assert data.get_recent_call_count() == expected_call_count

        # Clean calls older than 60 seconds
        data.clean_old_calls(60)
        assert data.get_recent_call_count() == 1


class TestSecurityManagerInit:
    """Test SecurityManager initialization"""

    def test_security_manager_initialization(self, security_manager):
        """Test SecurityManager initialization with proper defaults"""
        assert security_manager.max_calls_per_minute == DEFAULT_MAX_CALLS_PER_MINUTE
        assert security_manager.max_sessions == DEFAULT_MAX_SESSIONS
        assert len(security_manager.blocked_command_patterns) > 0
        assert len(security_manager.allowed_base_paths) >= EXPECTED_MIN_BASE_PATHS
        assert len(security_manager.blocked_extensions) > 0
        assert len(security_manager.protected_env_vars) > 0


class TestCommandValidation:
    """Test command validation security features"""

    def test_validate_safe_commands(self, security_manager, safe_commands):
        """Test that safe commands are allowed"""
        for command in safe_commands:
            assert security_manager._validate_command(command) is True

    def test_block_dangerous_commands(self, security_manager, dangerous_commands):
        """Test that dangerous commands are blocked"""
        for command in dangerous_commands:
            assert security_manager._validate_command(command) is False

    def test_empty_command_validation(self, security_manager):
        """Test validation of empty or whitespace commands"""
        empty_commands = ["", "   ", "\t\n", None]
        for cmd in empty_commands:
            if cmd is not None:
                assert security_manager._validate_command(cmd) is False


class TestInputValidation:
    """Test input validation and injection prevention"""

    def test_validate_safe_input(self, security_manager, safe_inputs):
        """Test that safe input strings are allowed"""
        for input_str in safe_inputs:
            assert security_manager._validate_input(input_str) is True

    def test_block_injection_patterns(self, security_manager, malicious_inputs):
        """Test blocking shell injection patterns"""
        for input_str in malicious_inputs:
            assert security_manager._validate_input(input_str) is False

    def test_block_null_bytes_and_control_chars(self, security_manager):
        """Test blocking null bytes and control characters"""
        malicious_inputs = [
            "test\x00",  # null byte
            "test\x01\x02",  # control chars
            "test\x1f",  # control char (31 < 32)
        ]

        for input_str in malicious_inputs:
            assert security_manager._validate_input(input_str) is False

    def test_allow_safe_control_chars(self, security_manager):
        """Test allowing safe control characters (tab, newline, carriage return)"""
        safe_control_inputs = [
            "test\ttab",
            "test\nnewline",
            "test\rcarriage return",
            "multi\nline\ttext\rwith\tall\nsafe\tcontrol\rchars",
        ]

        for input_str in safe_control_inputs:
            assert security_manager._validate_input(input_str) is True

    def test_validate_interactive_input_text(self, security_manager, safe_inputs):
        """Test safe interactive input text validation"""
        interactive_safe_inputs = [
            "ls -la",
            "print('hello')",
            "2 + 2",
            "yes",
            "n",
            "quit()",
            "exit",
        ]

        # Test both centralized safe inputs and interactive-specific ones
        for input_str in safe_inputs + interactive_safe_inputs:
            assert security_manager._validate_input_text(input_str) is True

    def test_block_dangerous_interactive_input(
        self, security_manager, malicious_inputs
    ):
        """Test blocking dangerous interactive input"""
        interactive_dangerous_inputs = [
            "sudo apt install malware",
            "su - root",
            "passwd",
            "\\x41\\x42\\x43",  # hex escape sequences
        ]

        # Test both centralized malicious inputs and interactive-specific ones
        for input_str in malicious_inputs + interactive_dangerous_inputs:
            assert security_manager._validate_input_text(input_str) is False


class TestPathValidation:
    """Test path validation and traversal protection"""

    def test_validate_safe_paths(self, security_manager, safe_paths):
        """Test validation of safe file paths"""
        for path in safe_paths:
            assert security_manager._validate_path(path) is True

    def test_block_path_traversal(self, security_manager, blocked_paths):
        """Test blocking path traversal attempts"""
        for path in blocked_paths:
            assert security_manager._validate_path(path) is False

    def test_block_system_paths(self, security_manager, blocked_paths):
        """Test blocking access to system paths"""
        for path in blocked_paths:
            assert security_manager._validate_path(path) is False

    def test_block_dangerous_extensions(self, security_manager):
        """Test blocking files with dangerous extensions"""
        with tempfile.TemporaryDirectory() as temp_dir:
            dangerous_files = [
                f"{temp_dir}/malware.exe",
                f"{temp_dir}/virus.dll",
                f"{temp_dir}/library.so",
                f"{temp_dir}/script.bat",
                f"{temp_dir}/command.cmd",
                f"{temp_dir}/screen.scr",
            ]

            for file_path in dangerous_files:
                assert security_manager._validate_path(file_path) is False

    def test_empty_path_validation(self, security_manager):
        """Test validation of empty paths"""
        assert security_manager._validate_path("") is False
        assert security_manager._validate_path(None) is False


class TestEnvironmentValidation:
    """Test environment variable validation"""

    def test_validate_safe_environment(self, security_manager, sample_environment_vars):
        """Test validation of safe environment variables"""
        safe_env = sample_environment_vars["safe"]
        assert security_manager._validate_environment(safe_env) is True

    def test_block_protected_environment_vars(
        self, security_manager, sample_environment_vars
    ):
        """Test blocking modification of protected environment variables"""
        dangerous_env = sample_environment_vars["dangerous"]
        assert security_manager._validate_environment(dangerous_env) is False

    def test_validate_environment_data_types(self, security_manager):
        """Test validation of environment variable data types"""
        # Non-string keys should be rejected
        invalid_env = {123: "value"}
        assert security_manager._validate_environment(invalid_env) is False

        # Non-string values should be rejected
        invalid_env = {"KEY": 123}
        assert security_manager._validate_environment(invalid_env) is False

    def test_validate_environment_with_injection(
        self, security_manager, malicious_inputs
    ):
        """Test blocking environment variables with injection patterns"""
        malicious_env = {
            "TEST": malicious_inputs[0],  # "test; rm -rf /"
            "CONFIG": malicious_inputs[2],  # "test$(malicious_command)"
            "PATH_EXTRA": malicious_inputs[1],  # "test`cat /etc/passwd`"
        }

        assert security_manager._validate_environment(malicious_env) is False


class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_rate_limit_under_threshold(self, security_manager):
        """Test that calls under the rate limit are allowed"""
        client_id = "test_client"

        # Make 50 calls (under the 60 per minute limit)
        for _ in range(50):
            assert security_manager._check_rate_limit(client_id) is True

    def test_rate_limit_over_threshold(self, security_manager):
        """Test that calls over the rate limit are blocked"""
        client_id = "test_client"

        # Make 60 calls to hit the limit
        for _ in range(60):
            security_manager._check_rate_limit(client_id)

        # The 61st call should be blocked
        assert security_manager._check_rate_limit(client_id) is False

    def test_rate_limit_per_client(self, security_manager):
        """Test that rate limits are enforced per client"""
        client1 = "client1"
        client2 = "client2"

        # Max out client1
        for _ in range(60):
            security_manager._check_rate_limit(client1)

        # client1 should be blocked
        assert security_manager._check_rate_limit(client1) is False

        # client2 should still be allowed
        assert security_manager._check_rate_limit(client2) is True

    def test_rate_limit_time_window(self, security_manager):
        """Test that rate limit resets after time window"""
        client_id = "test_client"

        # Mock time to test time window
        with patch("time.time") as mock_time:
            # Start at time 0
            mock_time.return_value = 0

            # Max out the rate limit
            for _ in range(60):
                security_manager._check_rate_limit(client_id)

            # Should be blocked
            assert security_manager._check_rate_limit(client_id) is False

            # Move forward 65 seconds (past the 60-second window)
            mock_time.return_value = 65

            # Should be allowed again
            assert security_manager._check_rate_limit(client_id) is True


class TestSessionLimits:
    """Test session limit validation"""

    def test_session_limit_under_threshold(self, security_manager):
        """Test session creation under limit"""
        assert security_manager.validate_session_limits(25) is True
        assert security_manager.validate_session_limits(49) is True

    def test_session_limit_at_threshold(self, security_manager):
        """Test session creation at limit"""
        assert security_manager.validate_session_limits(50) is False

    def test_session_limit_over_threshold(self, security_manager):
        """Test session creation over limit"""
        assert security_manager.validate_session_limits(51) is False
        assert security_manager.validate_session_limits(100) is False


class TestToolCallValidation:
    """Test overall tool call validation"""

    def test_validate_safe_execute_command(self, security_manager):
        """Test validation of safe execute_command calls"""
        arguments = {
            "command": "ls -la",
            "working_directory": "/tmp",
            "environment": {"DEBUG": "true"},
        }

        assert (
            security_manager.validate_tool_call("tercon_execute_command", arguments)
            is True
        )

    def test_block_dangerous_execute_command(self, security_manager):
        """Test blocking dangerous execute_command calls"""
        dangerous_args = [
            {"command": "rm -rf /"},
            {"command": "ls", "working_directory": "/etc"},
            {"command": "ls", "environment": {"PATH": "/malicious"}},
            {"command": "echo 'test'; rm -rf /"},
        ]

        for args in dangerous_args:
            assert (
                security_manager.validate_tool_call("tercon_execute_command", args)
                is False
            )

    def test_validate_safe_send_input(self, security_manager):
        """Test validation of safe send_input calls"""
        arguments = {"input_text": "print('hello')"}

        assert (
            security_manager.validate_tool_call("tercon_send_input", arguments) is True
        )

    def test_block_dangerous_send_input(self, security_manager):
        """Test blocking dangerous send_input calls"""
        dangerous_args = [
            {"input_text": "sudo rm -rf /"},
            {"input_text": "su - root"},
            {"input_text": "passwd"},
        ]

        for args in dangerous_args:
            assert (
                security_manager.validate_tool_call("tercon_send_input", args) is False
            )

    def test_validate_other_tool_calls(self, security_manager):
        """Test validation of other tool calls (should pass)"""
        arguments = {"session_id": "test123"}

        assert (
            security_manager.validate_tool_call("tercon_list_sessions", arguments)
            is True
        )
        assert (
            security_manager.validate_tool_call("tercon_destroy_session", arguments)
            is True
        )
        assert (
            security_manager.validate_tool_call("tercon_get_screen_content", arguments)
            is True
        )

    def test_rate_limiting_in_tool_validation(self, security_manager):
        """Test that rate limiting is enforced in tool call validation"""
        arguments = {"command": "ls"}

        # Max out rate limit
        for _ in range(60):
            security_manager.validate_tool_call(
                "tercon_execute_command", arguments, "test_client"
            )

        # Next call should be blocked due to rate limit
        assert (
            security_manager.validate_tool_call(
                "tercon_execute_command", arguments, "test_client"
            )
            is False
        )


class TestAuditLogging:
    """Test security audit logging functionality"""

    def test_sanitize_for_logging(self, security_manager):
        """Test data sanitization for logging"""
        test_data = {
            "normal_field": "normal_value",  # Changed to avoid "key" in name
            "long_value": "x" * 300,
            "password": "secret123",
            "api_token": "token456",
            "secret_key": "key789",
            "non_string": 12345,
        }

        sanitized = security_manager._sanitize_for_logging(test_data)

        # Normal values should be unchanged
        assert sanitized["normal_field"] == "normal_value"

        # Long values should be truncated
        expected_truncated_length = MAX_LOG_VALUE_LENGTH + 3  # 200 chars + "..."
        assert len(sanitized["long_value"]) == expected_truncated_length
        assert sanitized["long_value"].endswith("...")

        # Secrets should be masked (min of len(value), 8 stars)
        assert sanitized["password"] == "********"  # 8 chars -> 8 stars
        assert sanitized["api_token"] == "********"  # 8 chars -> 8 stars
        assert sanitized["secret_key"] == "******"  # 6 chars -> 6 stars

        # Non-strings should be converted and truncated
        assert sanitized["non_string"] == "12345"

    def test_write_audit_log(self, security_manager, mock_audit_log_path):
        """Test writing audit logs to file"""
        log_entry = {
            "timestamp": "2023-01-01T00:00:00",
            "event_type": "test_event",
            "tool_name": "test_tool",
            "client_id": "test_client",
        }

        # Write the log entry
        security_manager._write_audit_log(log_entry)

        # Check that the file was created and contains the log entry
        assert os.path.exists(mock_audit_log_path)

        with open(mock_audit_log_path) as f:
            written_content = f.read().strip()
            assert json.loads(written_content) == log_entry

    def test_log_security_event(self, security_manager):
        """Test logging security events"""
        with patch.object(security_manager, "_write_audit_log") as mock_write:
            with patch("logging.getLogger") as mock_logger:
                mock_security_logger = mock_logger.return_value

                arguments = {"test": "data"}
                security_manager._log_security_event(
                    "test_event", "test_tool", arguments, "test_client"
                )

                # Check that logger was called
                mock_security_logger.info.assert_called_once()

                # Check that audit log was written
                mock_write.assert_called_once()

                # Verify log entry structure
                log_entry = mock_write.call_args[0][0]
                assert log_entry["event_type"] == "test_event"
                assert log_entry["tool_name"] == "test_tool"
                assert log_entry["client_id"] == "test_client"
                assert "timestamp" in log_entry


class TestSecurityIntegration:
    """Integration tests for security features"""

    def test_complete_security_workflow(self, security_manager):
        """Test a complete security validation workflow"""
        # This should pass all security checks
        safe_arguments = {
            "command": "python -c 'print(\"hello\")'",
            "working_directory": "/tmp",
            "environment": {"DEBUG": "false"},
        }

        result = security_manager.validate_tool_call(
            "tercon_execute_command", safe_arguments, "integration_test_client"
        )

        assert result is True

    def test_multi_layer_security_blocking(self, security_manager):
        """Test that multiple security layers can block malicious requests"""
        # This should be blocked by command validation
        malicious_arguments = {
            "command": "rm -rf / && echo 'pwned'",
            "working_directory": "../../../etc",  # This would also be blocked
            "environment": {"PATH": "/malicious"},  # This would also be blocked
        }

        result = security_manager.validate_tool_call(
            "tercon_execute_command", malicious_arguments, "malicious_client"
        )

        assert result is False

    def test_security_across_different_clients(self, security_manager):
        """Test security isolation between different clients"""
        safe_args = {"command": "echo hello"}

        # Each client should have independent rate limiting
        assert (
            security_manager.validate_tool_call(
                "tercon_execute_command", safe_args, "client1"
            )
            is True
        )
        assert (
            security_manager.validate_tool_call(
                "tercon_execute_command", safe_args, "client2"
            )
            is True
        )
        assert (
            security_manager.validate_tool_call(
                "tercon_execute_command", safe_args, "client3"
            )
            is True
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
