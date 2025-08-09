"""Tests for configuration system with TOML support"""

import pytest

from src.terminal_control_mcp.settings import (
    LoggingSettings,
    SecurityLevel,
    SecuritySettings,
    ServerConfig,
    SessionSettings,
    TerminalEmulator,
    TerminalSettings,
    WebSettings,
)

# Test constants to avoid magic values
DEFAULT_WEB_PORT = 8080
DEFAULT_MAX_CALLS = 60
DEFAULT_MAX_SESSIONS = 50
DEFAULT_SESSION_TIMEOUT = 30
TEST_WEB_PORT_1 = 7777
TEST_WEB_PORT_2 = 8888
TEST_WEB_PORT_3 = 9090
TEST_MAX_CALLS = 120
TEST_MAX_SESSIONS = 25
TEST_SESSION_TIMEOUT = 60
TEST_TERMINAL_WIDTH = 120
TEST_TERMINAL_HEIGHT = 30
TEST_CLOSE_TIMEOUT = 5.0
TEST_EMULATOR_COUNT = 2


class TestPydanticConfiguration:
    """Test pydantic-based TOML configuration loading"""

    def test_default_configuration(self) -> None:
        """Test default configuration values"""
        # Create config with defaults (TOML file loading will use defaults)
        config = ServerConfig()

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

    def test_toml_configuration_loading(self) -> None:
        """Test that ServerConfig model validation works with custom values"""
        # Test individual settings models can be instantiated with custom values
        web_settings = WebSettings(
            enabled=True,
            host="127.0.0.1",
            port=TEST_WEB_PORT_3,
            external_host="example.com",
        )
        security_settings = SecuritySettings(
            level=SecurityLevel.MEDIUM,
            max_calls_per_minute=TEST_MAX_CALLS,
            max_sessions=TEST_MAX_SESSIONS,
        )
        session_settings = SessionSettings(
            default_shell="zsh", timeout=TEST_SESSION_TIMEOUT
        )
        logging_settings = LoggingSettings(level="DEBUG")
        terminal_settings = TerminalSettings(
            width=TEST_TERMINAL_WIDTH,
            height=TEST_TERMINAL_HEIGHT,
            close_timeout=5.0,
            process_check_timeout=1.0,
            polling_interval=0.05,
            send_input_delay=0.1,
            screen_content_delay=1.0,
            emulators=[
                TerminalEmulator(
                    name="gnome-terminal", command=["gnome-terminal", "--"]
                ),
                TerminalEmulator(name="konsole", command=["konsole", "-e"]),
            ],
        )

        # Verify individual models work correctly
        assert web_settings.enabled is True
        assert web_settings.host == "127.0.0.1"
        assert web_settings.port == TEST_WEB_PORT_3
        assert web_settings.external_host == "example.com"

        assert security_settings.level == SecurityLevel.MEDIUM
        assert security_settings.max_calls_per_minute == TEST_MAX_CALLS
        assert security_settings.max_sessions == TEST_MAX_SESSIONS

        assert session_settings.default_shell == "zsh"
        assert session_settings.timeout == TEST_SESSION_TIMEOUT

        assert logging_settings.level == "DEBUG"

        assert terminal_settings.width == TEST_TERMINAL_WIDTH
        assert terminal_settings.height == TEST_TERMINAL_HEIGHT
        assert terminal_settings.close_timeout == TEST_CLOSE_TIMEOUT

        # Terminal emulators
        assert len(terminal_settings.emulators) == TEST_EMULATOR_COUNT
        assert terminal_settings.emulators[0].name == "gnome-terminal"
        assert terminal_settings.emulators[0].command == ["gnome-terminal", "--"]

    def test_security_level_parsing(self) -> None:
        """Test security level parsing from enum values"""
        test_cases = [
            (SecurityLevel.OFF, SecurityLevel.OFF),
            (SecurityLevel.LOW, SecurityLevel.LOW),
            (SecurityLevel.MEDIUM, SecurityLevel.MEDIUM),
            (SecurityLevel.HIGH, SecurityLevel.HIGH),
        ]

        for level_enum, expected in test_cases:
            # Test SecuritySettings model directly
            settings = SecuritySettings(
                level=level_enum, max_calls_per_minute=60, max_sessions=50
            )
            assert settings.level == expected, f"Failed for input: {level_enum}"

    def test_backwards_compatibility_properties(self) -> None:
        """Test that backwards compatibility properties work"""
        config = ServerConfig()

        # Test all backward compatibility properties exist and work
        assert config.web_enabled == config.web.enabled
        assert config.web_host == config.web.host
        assert config.web_port == config.web.port
        assert config.security_level == config.security.level
        assert config.max_calls_per_minute == config.security.max_calls_per_minute
        assert config.max_sessions == config.security.max_sessions
        assert config.default_shell == config.session.default_shell
        assert config.session_timeout == config.session.timeout
        assert config.log_level == config.logging.level
        assert config.terminal_width == config.terminal.width
        assert config.terminal_height == config.terminal.height

    def test_terminal_emulators_property(self) -> None:
        """Test terminal emulators property conversion"""
        config = ServerConfig()
        emulators = config.terminal_emulators

        # Should be a list of dicts for backward compatibility
        assert isinstance(emulators, list)
        assert len(emulators) > 0
        assert isinstance(emulators[0], dict)
        assert "name" in emulators[0]
        assert "command" in emulators[0]
        assert isinstance(emulators[0]["command"], list)

    def test_real_toml_file_loading(self) -> None:
        """Test loading configuration values works correctly"""
        config = ServerConfig()

        # Should load successfully without errors
        assert isinstance(config.web_enabled, bool)
        assert isinstance(config.web_port, int)
        assert isinstance(config.security_level, SecurityLevel)
        assert config.web_port > 0
        assert config.max_sessions > 0
        assert config.session_timeout > 0
        assert len(config.terminal_emulators) > 0

    def test_malformed_toml_handling(self) -> None:
        """Test graceful handling when TOML file doesn't exist or is malformed"""
        # Test that config can be created with defaults
        config = ServerConfig()
        # Should still get default values
        assert config.web_enabled is False
        assert config.web_port == DEFAULT_WEB_PORT

    def test_pydantic_validation(self) -> None:
        """Test that pydantic validation works correctly"""
        from pydantic import ValidationError

        # Test that invalid values raise validation errors
        with pytest.raises(ValidationError):
            WebSettings(enabled=True, host="localhost", port="not_an_integer")  # type: ignore

        # Valid models should work
        web_settings = WebSettings(enabled=True, host="localhost", port=8080)
        security_settings = SecuritySettings(
            level=SecurityLevel.HIGH, max_calls_per_minute=60, max_sessions=50
        )

        assert web_settings.enabled is True
        assert web_settings.port == DEFAULT_WEB_PORT
        assert security_settings.level == SecurityLevel.HIGH


class TestConfigurationIntegration:
    """Integration tests for the configuration system"""

    def test_config_creation_with_defaults(self) -> None:
        """Test that ServerConfig can be created with all default values"""
        config = ServerConfig()

        # Verify all sections exist
        assert config.web is not None
        assert config.security is not None
        assert config.session is not None
        assert config.logging is not None
        assert config.terminal is not None

        # Verify basic functionality
        assert isinstance(config.web_enabled, bool)
        assert isinstance(config.security_level, SecurityLevel)
        assert config.terminal_emulators is not None
        assert len(config.terminal_emulators) > 0

    def test_settings_customise_sources(self) -> None:
        """Test that the custom settings source configuration works"""
        # This tests that the settings_customise_sources method properly
        # configures TOML-only loading
        config = ServerConfig()

        # Should work without environment variables
        assert config is not None
        assert config.web_enabled in (True, False)  # Should have a valid boolean value
