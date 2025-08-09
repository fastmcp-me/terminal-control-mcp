#!/usr/bin/env python3
"""
Edge case and error handling tests for the MCP server
Tests unusual scenarios, error conditions, and boundary cases
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.terminal_control_mcp.main import (
    exit_terminal,
    get_screen_content,
    open_terminal,
    send_input,
)
from src.terminal_control_mcp.models import OpenTerminalRequest
from src.terminal_control_mcp.security import (
    CONTROL_CHAR_THRESHOLD,
    DEFAULT_MAX_CALLS_PER_MINUTE,
    RateLimitData,
    SecurityManager,
)


class TestSecurityEdgeCases:
    """Test edge cases in security validation"""

    def test_empty_and_whitespace_inputs(self, security_manager: Any) -> None:
        """Test handling of empty and whitespace-only inputs"""
        # Empty strings
        assert security_manager._validate_command("") is False
        assert security_manager._validate_path("") is False

        # Whitespace only
        assert security_manager._validate_command("   ") is False
        assert security_manager._validate_command("\t\n") is False

        # Null input should be handled gracefully
        try:
            security_manager._validate_path(None)
        except (TypeError, AttributeError):
            pass  # Expected for None input

    def test_unicode_and_special_characters(self, security_manager: Any) -> None:
        """Test handling of unicode and special characters"""
        unicode_tests = [
            "echo 'Hello 世界'",  # Unicode characters
            "echo 'café'",  # Accented characters
            "echo '🚀'",  # Emoji
            "echo 'test\u200b'",  # Zero-width space
        ]

        for command in unicode_tests:
            # These should be allowed (safe unicode)
            assert security_manager._validate_command(command) is True

    def test_very_long_inputs(self, security_manager: Any) -> None:
        """Test handling of very long inputs"""
        # Very long command
        long_command = "echo '" + "A" * 10000 + "'"
        assert security_manager._validate_command(long_command) is True

        # Very long path
        long_path = "/tmp/" + "a" * 1000 + ".txt"
        # This might fail due to filesystem limits, but shouldn't crash
        try:
            result = security_manager._validate_path(long_path)
            # Result can be True or False, but shouldn't raise exception
            assert isinstance(result, bool)
        except OSError:
            pass  # Expected for extremely long paths

    def test_binary_and_non_printable_data(self, security_manager: Any) -> None:
        """Test handling of binary and non-printable data"""
        binary_inputs = [
            "test\x00binary",  # Null bytes
            "test\xff\xfe",  # High bytes
            "test\x01\x02\x03",  # Low control chars
            "test\x7f\x80\x81",  # DEL and high control chars
        ]

        for input_data in binary_inputs:
            # Should be blocked due to control characters
            assert security_manager._validate_input(input_data) is False

    def test_nested_injection_attempts(self, security_manager: Any) -> None:
        """Test deeply nested injection attempts"""
        nested_attacks = [
            r"echo `echo `echo \`rm -rf /\``",
            "echo $(echo $(rm -rf /))",
            "echo '$(echo `rm -rf /`)'",
            "test; echo `cat /etc/passwd | base64`",
        ]

        for attack in nested_attacks:
            assert security_manager._validate_input(attack) is False

    def test_encoding_bypass_attempts(self, security_manager: Any) -> None:
        """Test attempts to bypass validation with encoding"""
        bypass_attempts = [
            "echo \\x72\\x6d\\x20\\x2d\\x72\\x66",  # Hex encoded 'rm -rf'
            "echo $'\\x72\\x6d\\x20\\x2d\\x72\\x66'",  # Bash hex escape
            "echo $(printf '\\x72\\x6d')",  # Printf hex
        ]

        for attempt in bypass_attempts:
            # Our current validation should catch most of these
            result = security_manager._validate_command(attempt)
            # Some may pass command validation but fail input validation
            if result:
                assert security_manager._validate_input(attempt) is False


class TestRateLimitingEdgeCases:
    """Test edge cases in rate limiting"""

    @pytest.fixture
    def security_manager(self) -> SecurityManager:
        return SecurityManager()

    def test_concurrent_rate_limiting(self, security_manager: Any) -> None:
        """Test rate limiting with concurrent requests"""
        import threading

        client_id = "concurrent_test"
        results = []

        def make_request() -> None:
            result = security_manager._check_rate_limit(client_id)
            results.append(result)

        # Start many threads simultaneously
        threads = []
        for _ in range(100):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have some successes and some failures due to rate limiting
        successes = sum(results)
        assert successes <= DEFAULT_MAX_CALLS_PER_MINUTE  # Max allowed per minute
        assert successes > 0  # Some should succeed

    def test_time_window_edge_cases(self, security_manager: Any) -> None:
        """Test edge cases around time windows"""
        client_id = "time_test"

        with patch("time.time") as mock_time:
            # Test exactly at window boundary
            mock_time.return_value = 0

            # Fill up the rate limit
            for _ in range(60):
                security_manager._check_rate_limit(client_id)

            # Should be blocked
            assert security_manager._check_rate_limit(client_id) is False

            # Move to exactly 60 seconds later
            mock_time.return_value = 60.0

            # Should still be blocked (edge case)
            assert security_manager._check_rate_limit(client_id) is False

            # Move to 60.1 seconds later
            mock_time.return_value = 60.1

            # Should be allowed
            assert security_manager._check_rate_limit(client_id) is True

    def test_rate_limit_data_edge_cases(self) -> None:
        """Test RateLimitData with edge cases"""
        data = RateLimitData("test")

        # Test with no calls
        data.clean_old_calls()
        assert data.get_recent_call_count() == 0

        # Test with future timestamps (clock skew)
        future_time = time.time() + 3600  # 1 hour in future
        data.add_call(future_time)
        data.clean_old_calls()

        # Future calls should still be counted
        assert data.get_recent_call_count() == 1

    def test_rate_limit_with_extreme_values(self, security_manager: Any) -> None:
        """Test rate limiting with extreme values"""
        client_id = "extreme_test"

        with patch("time.time") as mock_time:
            # Test with very large timestamps
            mock_time.return_value = 1e10

            # Should still work
            assert security_manager._check_rate_limit(client_id) is True

            # Test with zero timestamp
            mock_time.return_value = 0
            assert security_manager._check_rate_limit(client_id) is True


class TestPathValidationEdgeCases:
    """Test edge cases in path validation"""

    @pytest.fixture
    def security_manager(self) -> SecurityManager:
        return SecurityManager()

    def test_symbolic_links_and_aliases(
        self, security_manager: Any, temp_dir: str
    ) -> None:
        """Test handling of symbolic links"""
        if os.name == "posix":  # Unix-like systems
            # Create a symbolic link
            target_file = os.path.join(temp_dir, "target.txt")
            link_file = os.path.join(temp_dir, "link.txt")

            with open(target_file, "w") as f:
                f.write("test")

            try:
                os.symlink(target_file, link_file)

                # Test validation of the link
                result = security_manager._validate_path(link_file)
                # Should resolve to the actual path and be validated
                assert isinstance(result, bool)
            except (OSError, NotImplementedError):
                # Skip if symlinks not supported
                pass

    def test_relative_path_resolution(self, security_manager: Any) -> None:
        """Test resolution of relative paths"""
        relative_paths = [
            "./test.txt",
            "../test.txt",
            "../../test.txt",
            "./subdir/../test.txt",
            "test/../other/file.txt",
        ]

        for path in relative_paths:
            try:
                result = security_manager._validate_path(path)
                assert isinstance(result, bool)
            except Exception:
                # Some paths may cause validation errors, which is expected
                pass

    def test_case_sensitivity(self, security_manager: Any) -> None:
        """Test case sensitivity in path validation"""
        if os.name == "nt":  # Windows
            # Windows paths are case-insensitive
            paths = ["/ETC/passwd", "/etc/PASSWD", "/EtC/PaSSWd"]

            for path in paths:
                # Should be blocked regardless of case
                assert security_manager._validate_path(path) is False

    def test_path_normalization_bypasses(self, security_manager: Any) -> None:
        """Test attempts to bypass path validation with normalization"""
        bypass_attempts = [
            "/etc//passwd",  # Double slashes
            "/etc/./passwd",  # Current directory
            "/etc/subdir/../passwd",  # Parent directory reference
            r"/etc\passwd",  # Backslash (Windows-style)
            "/etc/passwd/",  # Trailing slash
        ]

        for path in bypass_attempts:
            # Should be blocked after path resolution
            result = security_manager._validate_path(path)
            if "/etc/passwd" in str(Path(path).resolve()):
                assert result is False


class TestEnvironmentEdgeCases:
    """Test edge cases in environment variable validation"""

    @pytest.fixture
    def security_manager(self) -> SecurityManager:
        return SecurityManager()

    def test_environment_case_sensitivity(self, security_manager: Any) -> None:
        """Test case sensitivity in environment variable names"""
        # Test mixed case versions of protected variables
        # HOME should definitely be blocked
        assert security_manager._validate_environment({"HOME": "/tmp/fake"}) is False

        # Test case sensitivity - depends on system
        # On most Unix systems, environment variables are case-sensitive

    def test_empty_environment_values(self, security_manager: Any) -> None:
        """Test empty and None environment values"""
        test_cases = [
            {"TEST_VAR": ""},  # Empty string
            {"TEST_VAR": None},  # None value - should fail type check
            {"": "value"},  # Empty key - should fail
        ]

        for env in test_cases:
            try:
                result = security_manager._validate_environment(env)
                if (hasattr(env, "values") and None in env.values()) or (
                    hasattr(env, "keys") and "" in env.keys()
                ):
                    assert result is False
            except (TypeError, AttributeError):
                # Expected for invalid types
                pass

    def test_environment_with_special_characters(self, security_manager: Any) -> None:
        """Test environment variables with special characters"""
        special_char_env = {
            "VAR_WITH_UNICODE": "café",
            "VAR_WITH_NEWLINE": "line1\nline2",
            "VAR_WITH_NULL": "test\x00null",
            "VAR_WITH_CONTROL": "test\x01\x02",
        }

        # Some should pass, others should fail based on input validation
        for key, value in special_char_env.items():
            env = {key: value}
            result = security_manager._validate_environment(env)
            if "\x00" in value or any(
                ord(c) < CONTROL_CHAR_THRESHOLD and c not in "\t\n\r" for c in value
            ):
                assert result is False


class TestAsyncEdgeCases:
    """Test edge cases in async operations"""

    @pytest.mark.asyncio
    async def test_rapid_session_creation_destruction(self, mock_context: Any) -> None:
        """Test rapid creation and destruction of sessions"""
        session_ids = []

        try:
            # Create multiple sessions rapidly
            for _ in range(5):
                request = OpenTerminalRequest(
                    shell="bash", working_directory=None, environment=None
                )
                result = await open_terminal(request, mock_context)
                if result.success:
                    session_ids.append(result.session_id)

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)

            # Verify sessions were created
            assert len(session_ids) > 0

            # Destroy all sessions rapidly
            for session_id in session_ids:
                from src.terminal_control_mcp.models import DestroySessionRequest

                destroy_request = DestroySessionRequest(session_id=session_id)
                await exit_terminal(destroy_request, mock_context)

        except Exception as e:
            # Clean up any remaining sessions
            for session_id in session_ids:
                try:
                    from src.terminal_control_mcp.models import DestroySessionRequest

                    destroy_request = DestroySessionRequest(session_id=session_id)
                    await exit_terminal(destroy_request, mock_context)
                except Exception:
                    pass
            raise e

    @pytest.mark.asyncio
    async def test_timeout_edge_cases(self, mock_context: Any) -> None:
        """Test various timeout scenarios"""
        # Very short timeout
        request = OpenTerminalRequest(
            shell="bash", working_directory=None, environment=None
        )

        result = await open_terminal(request, mock_context)
        # May succeed or fail depending on timing

        if result.success:
            # Send a sleep command that would timeout
            from src.terminal_control_mcp.models import SendInputRequest

            input_request = SendInputRequest(
                session_id=result.session_id, input_text="sleep 10\n"
            )
            await send_input(input_request, mock_context)

            # Clean up
            from src.terminal_control_mcp.models import DestroySessionRequest

            destroy_request = DestroySessionRequest(session_id=result.session_id)
            await exit_terminal(destroy_request, mock_context)

    @pytest.mark.asyncio
    async def test_concurrent_operations_same_session(self, mock_context: Any) -> None:
        """Test concurrent operations on the same session"""
        # Start a session
        request = OpenTerminalRequest(
            shell="python3", working_directory=None, environment=None
        )
        result = await open_terminal(request, mock_context)

        if not result.success:
            return

        session_id = result.session_id

        try:
            # Send a Python command that waits for input
            from src.terminal_control_mcp.models import SendInputRequest

            input_request = SendInputRequest(
                session_id=session_id,
                input_text="import time; input('wait: '); print('done')\n",
            )
            await send_input(input_request, mock_context)

            await asyncio.sleep(0.5)  # Let session start

            # Try concurrent operations
            tasks = []

            # Get screen content
            from src.terminal_control_mcp.models import (
                GetScreenContentRequest,
                SendInputRequest,
            )

            screen_request = GetScreenContentRequest(
                session_id=session_id, content_mode="screen", line_count=None
            )
            tasks.append(get_screen_content(screen_request, mock_context))

            # Send input
            input_request = SendInputRequest(session_id=session_id, input_text="test\n")
            tasks.append(send_input(input_request, mock_context))

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # At least one should succeed
            successes = sum(
                1
                for r in results
                if not isinstance(r, Exception) and getattr(r, "success", False)
            )
            assert successes >= 1

        finally:
            # Clean up
            try:
                from src.terminal_control_mcp.models import DestroySessionRequest

                destroy_request = DestroySessionRequest(session_id=session_id)
                await exit_terminal(destroy_request, mock_context)
            except Exception:
                pass


class TestErrorHandling:
    """Test error handling in various scenarios"""

    @pytest.fixture
    def security_manager(self) -> SecurityManager:
        return SecurityManager()

    def test_malformed_requests(self, security_manager: Any) -> None:
        """Test handling of malformed requests"""
        # Test with various malformed arguments
        malformed_args = [
            None,
            {},
            {"shell": None},
            {"shell": 123},  # Wrong type
            {"environment": "not_a_dict"},  # Wrong type
            {"working_directory": 123},  # Wrong type
        ]

        for args in malformed_args:
            try:
                if args is None:
                    continue
                result = security_manager.validate_tool_call("open_terminal", args)
                # Should either return False or raise an exception
                assert isinstance(result, bool)
            except (TypeError, AttributeError, ValueError):
                # Expected for malformed input
                pass

    def test_filesystem_errors(self, security_manager: Any) -> None:
        """Test handling of filesystem-related errors"""
        # Test with non-existent paths
        nonexistent_paths = [
            "/this/path/does/not/exist",
            "/dev/null/cannot/be/parent",
            "/proc/nonexistent/path",
        ]

        for path in nonexistent_paths:
            try:
                result = security_manager._validate_path(path)
                assert isinstance(result, bool)
            except (OSError, PermissionError):
                # Expected for some invalid paths
                pass

    def test_resource_exhaustion_simulation(self, security_manager: Any) -> None:
        """Test behavior under simulated resource exhaustion"""
        # Simulate memory pressure by creating many rate limit entries
        for i in range(1000):
            client_id = f"test_client_{i}"
            security_manager._check_rate_limit(client_id)

        # Should still work for new clients
        result = security_manager._check_rate_limit("new_client")
        assert result is True

    @patch("logging.getLogger")
    def test_logging_errors(self, mock_get_logger: Any, security_manager: Any) -> None:
        """Test handling of logging errors"""
        # Mock logger to raise exception
        mock_logger = MagicMock()
        mock_logger.info.side_effect = Exception("Logging failed")
        mock_get_logger.return_value = mock_logger

        # Should not crash when logging fails
        try:
            security_manager._log_security_event(
                "test_event", "test_tool", {}, "test_client"
            )
        except Exception as e:
            # Should be handled gracefully
            assert "Logging failed" not in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
