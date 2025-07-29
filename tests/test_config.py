"""Tests for configuration system with TOML support"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.terminal_control_mcp.config import SecurityLevel, ServerConfig

# Test constants to avoid magic values
DEFAULT_WEB_PORT = 8080
DEFAULT_MAX_CALLS = 60
DEFAULT_MAX_SESSIONS = 50
DEFAULT_SESSION_TIMEOUT = 30
TEST_WEB_PORT_1 = 7777
TEST_WEB_PORT_2 = 8888
TEST_WEB_PORT_3 = 9090
TEST_WEB_PORT_4 = 9999
TEST_MAX_CALLS = 120
TEST_MAX_SESSIONS = 25
TEST_SESSION_TIMEOUT = 60


class TestTOMLConfiguration:
    """Test TOML configuration loading and parsing"""

    def test_default_configuration(self):
        """Test default configuration values without any files or env vars"""
        # Clear environment variables for clean test
        env_vars_to_clear = [
            "TERMINAL_CONTROL_WEB_ENABLED",
            "TERMINAL_CONTROL_WEB_HOST",
            "TERMINAL_CONTROL_WEB_PORT",
            "TERMINAL_CONTROL_EXTERNAL_HOST",
            "TERMINAL_CONTROL_SECURITY_LEVEL",
            "TERMINAL_CONTROL_MAX_CALLS_PER_MINUTE",
            "TERMINAL_CONTROL_MAX_SESSIONS",
            "TERMINAL_CONTROL_DEFAULT_SHELL",
            "TERMINAL_CONTROL_SESSION_TIMEOUT",
            "TERMINAL_CONTROL_LOG_LEVEL",
        ]

        original_values = {}
        for var in env_vars_to_clear:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

        try:
            # Mock the config file loading to return empty config (forcing defaults)
            with patch(
                "src.terminal_control_mcp.config.ServerConfig._load_toml_config",
                return_value={},
            ):
                config = ServerConfig.from_config_and_environment(None)

            # Test default values
            assert config.web_enabled is False
            assert config.web_host == "0.0.0.0"
            assert config.web_port == DEFAULT_WEB_PORT
            assert config.external_web_host is None
            assert config.security_level == SecurityLevel.HIGH
            assert config.max_calls_per_minute == DEFAULT_MAX_CALLS
            assert config.max_sessions == DEFAULT_MAX_SESSIONS
            assert config.default_shell == "bash"
            assert config.session_timeout == DEFAULT_SESSION_TIMEOUT
            assert config.log_level == "INFO"

        finally:
            # Restore original environment
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    def test_toml_configuration_loading(self):
        """Test loading configuration from TOML file"""
        toml_content = """
[web]
enabled = false
host = "127.0.0.1"
port = 9090  # TEST_WEB_PORT_3
external_host = "example.com"

[security]
level = "medium"
max_calls_per_minute = 120  # TEST_MAX_CALLS
max_sessions = 25  # TEST_MAX_SESSIONS

[session]
default_shell = "zsh"
timeout = 60  # TEST_SESSION_TIMEOUT

[logging]
level = "DEBUG"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            config_file = f.name

        try:
            config = ServerConfig.from_config_and_environment(config_file)

            # Test TOML values are loaded
            assert config.web_enabled is False
            assert config.web_host == "127.0.0.1"
            assert config.web_port == TEST_WEB_PORT_3
            assert config.external_web_host == "example.com"
            assert config.security_level == SecurityLevel.MEDIUM
            assert config.max_calls_per_minute == TEST_MAX_CALLS
            assert config.max_sessions == TEST_MAX_SESSIONS
            assert config.default_shell == "zsh"
            assert config.session_timeout == TEST_SESSION_TIMEOUT
            assert config.log_level == "DEBUG"

        finally:
            os.unlink(config_file)

    def test_environment_overrides_toml(self):
        """Test that environment variables override TOML configuration"""
        toml_content = """
[web]
enabled = false
port = 9090  # TEST_WEB_PORT_3

[security]
level = "low"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            config_file = f.name

        # Set environment variables that should override TOML
        original_env = {}
        env_overrides = {
            "TERMINAL_CONTROL_WEB_ENABLED": "true",
            "TERMINAL_CONTROL_WEB_PORT": str(TEST_WEB_PORT_2),
            "TERMINAL_CONTROL_SECURITY_LEVEL": "high",
        }

        for key, value in env_overrides.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            config = ServerConfig.from_config_and_environment(config_file)

            # Environment should override TOML
            assert config.web_enabled is True  # env override
            assert config.web_port == TEST_WEB_PORT_2  # env override
            assert config.security_level == SecurityLevel.HIGH  # env override

        finally:
            # Clean up
            os.unlink(config_file)
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                elif key in os.environ:
                    del os.environ[key]

    def test_security_level_parsing(self):
        """Test security level parsing from string values"""
        test_cases = [
            ("off", SecurityLevel.OFF),
            ("OFF", SecurityLevel.OFF),
            ("low", SecurityLevel.LOW),
            ("MEDIUM", SecurityLevel.MEDIUM),
            ("high", SecurityLevel.HIGH),
            ("invalid", SecurityLevel.HIGH),  # fallback to HIGH
        ]

        for level_str, expected in test_cases:
            os.environ["TERMINAL_CONTROL_SECURITY_LEVEL"] = level_str
            try:
                config = ServerConfig.from_config_and_environment(None)
                assert (
                    config.security_level == expected
                ), f"Failed for input: {level_str}"
            finally:
                del os.environ["TERMINAL_CONTROL_SECURITY_LEVEL"]

    def test_boolean_parsing(self):
        """Test boolean value parsing from various string formats"""
        true_values = ["true", "TRUE", "1", "yes", "YES", "on", "ON"]
        false_values = ["false", "FALSE", "0", "no", "NO", "off", "OFF", "anything"]

        for true_val in true_values:
            os.environ["TERMINAL_CONTROL_WEB_ENABLED"] = true_val
            try:
                config = ServerConfig.from_config_and_environment(None)
                assert config.web_enabled is True, f"Failed for true value: {true_val}"
            finally:
                del os.environ["TERMINAL_CONTROL_WEB_ENABLED"]

        for false_val in false_values:
            os.environ["TERMINAL_CONTROL_WEB_ENABLED"] = false_val
            try:
                config = ServerConfig.from_config_and_environment(None)
                assert (
                    config.web_enabled is False
                ), f"Failed for false value: {false_val}"
            finally:
                del os.environ["TERMINAL_CONTROL_WEB_ENABLED"]

    def test_integer_parsing_with_fallback(self):
        """Test integer parsing with fallback to defaults on invalid values"""
        # Valid integer
        os.environ["TERMINAL_CONTROL_WEB_PORT"] = str(TEST_WEB_PORT_4)
        try:
            config = ServerConfig.from_config_and_environment(None)
            assert config.web_port == TEST_WEB_PORT_4
        finally:
            del os.environ["TERMINAL_CONTROL_WEB_PORT"]

        # Invalid integer should fall back to default
        os.environ["TERMINAL_CONTROL_WEB_PORT"] = "not_a_number"
        try:
            config = ServerConfig.from_config_and_environment(None)
            assert config.web_port == DEFAULT_WEB_PORT  # default fallback
        finally:
            del os.environ["TERMINAL_CONTROL_WEB_PORT"]

    def test_backwards_compatibility(self):
        """Test that from_environment() method still works for backwards compatibility"""
        os.environ["TERMINAL_CONTROL_WEB_PORT"] = str(TEST_WEB_PORT_1)
        os.environ["TERMINAL_CONTROL_SECURITY_LEVEL"] = "low"

        try:
            config = ServerConfig.from_environment()
            assert config.web_port == TEST_WEB_PORT_1
            assert config.security_level == SecurityLevel.LOW
        finally:
            del os.environ["TERMINAL_CONTROL_WEB_PORT"]
            del os.environ["TERMINAL_CONTROL_SECURITY_LEVEL"]

    def test_config_file_search_order(self):
        """Test that configuration files are found in the correct search order"""
        # Test with None - should try default locations (may find project's terminal-control.toml)
        result = ServerConfig._load_toml_config(None)
        assert isinstance(result, dict)  # Should return dict even if empty

        # Test that providing a specific non-existent file doesn't fall back to defaults
        # Create a temp directory that definitely doesn't exist
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_file = f"{temp_dir}/definitely_does_not_exist/config.toml"
            result = ServerConfig._load_toml_config(non_existent_file)
            assert result == {}

    def test_malformed_toml_handling(self):
        """Test graceful handling of malformed TOML files"""
        malformed_toml = """
[web
enabled = true  # Missing closing bracket
port = "not a valid toml
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(malformed_toml)
            config_file = f.name

        try:
            # Should gracefully fall back to defaults when TOML is malformed
            config = ServerConfig.from_config_and_environment(config_file)

            # Should still get default values despite malformed TOML
            assert config.web_enabled is False
            assert config.web_port == DEFAULT_WEB_PORT

        finally:
            os.unlink(config_file)


class TestConfigurationIntegration:
    """Integration tests for the configuration system"""

    def test_real_toml_file_loading(self):
        """Test loading the actual terminal-control.toml file if it exists"""
        project_root = Path(__file__).parent.parent
        toml_file = project_root / "terminal-control.toml"

        if toml_file.exists():
            config = ServerConfig.from_config_and_environment(str(toml_file))

            # Should load successfully without errors
            assert isinstance(config.web_enabled, bool)
            assert isinstance(config.web_port, int)
            assert isinstance(config.security_level, SecurityLevel)
            assert config.web_port > 0
            assert config.max_sessions > 0
            assert config.session_timeout > 0
        else:
            pytest.skip("terminal-control.toml not found in project root")
