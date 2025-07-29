#!/usr/bin/env python3
"""
Central configuration for Terminal Control MCP Server
All configuration options and environment variable handling
"""

import os
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict


class SecurityLevel(Enum):
    """Security levels for the MCP server"""

    OFF = "off"  # No security validation (allows all commands)
    LOW = "low"  # Basic input validation only
    MEDIUM = "medium"  # Standard protection (blocks common dangerous commands)
    HIGH = "high"  # Full protection (current default behavior)


class TerminalEmulator(TypedDict):
    """Terminal emulator configuration"""
    name: str
    command: list[str]


@dataclass
class ServerConfig:
    """Central configuration for the MCP server"""

    # Web server configuration
    web_enabled: bool = False
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    external_web_host: str | None = None

    # Security configuration
    security_level: SecurityLevel = SecurityLevel.HIGH
    max_calls_per_minute: int = 60
    max_sessions: int = 50

    # Session configuration
    default_shell: str = "bash"
    session_timeout: int = 30

    # Logging configuration
    log_level: str = "INFO"

    # Terminal configuration
    terminal_width: int = 120
    terminal_height: int = 30
    terminal_close_timeout: float = 5.0
    terminal_process_check_timeout: float = 1.0
    terminal_polling_interval: float = 0.05
    terminal_send_input_delay: float = 0.1
    terminal_emulators: list[TerminalEmulator] = field(default_factory=lambda: [])

    # Note: agent_name is handled dynamically per connection, not in static config

    @classmethod
    def from_config_and_environment(
        cls, config_file: str | None = None
    ) -> "ServerConfig":
        """Create configuration from TOML config file and environment variables

        Environment variables take precedence over config file values.
        Config file is loaded from:
        1. Specified config_file path
        2. ./terminal-control.toml
        3. ~/.config/terminal-control.toml
        4. /etc/terminal-control.toml
        """
        config_data = cls._load_toml_config(config_file)

        return cls(
            # Web server
            web_enabled=cls._get_bool_value(
                "TERMINAL_CONTROL_WEB_ENABLED",
                config_data.get("web", {}).get("enabled", True),
            ),
            web_host=cls._get_str_value(
                "TERMINAL_CONTROL_WEB_HOST",
                config_data.get("web", {}).get("host", "0.0.0.0"),
            )
            or "0.0.0.0",
            web_port=cls._get_int_value(
                "TERMINAL_CONTROL_WEB_PORT",
                config_data.get("web", {}).get("port", 8080),
            ),
            external_web_host=cls._get_str_value(
                "TERMINAL_CONTROL_EXTERNAL_HOST",
                config_data.get("web", {}).get("external_host"),
            ),
            # Security
            security_level=cls._get_security_level(
                "TERMINAL_CONTROL_SECURITY_LEVEL",
                config_data.get("security", {}).get("level", "high"),
            ),
            max_calls_per_minute=cls._get_int_value(
                "TERMINAL_CONTROL_MAX_CALLS_PER_MINUTE",
                config_data.get("security", {}).get("max_calls_per_minute", 60),
            ),
            max_sessions=cls._get_int_value(
                "TERMINAL_CONTROL_MAX_SESSIONS",
                config_data.get("security", {}).get("max_sessions", 50),
            ),
            # Sessions
            default_shell=cls._get_str_value(
                "TERMINAL_CONTROL_DEFAULT_SHELL",
                config_data.get("session", {}).get("default_shell", "bash"),
            )
            or "bash",
            session_timeout=cls._get_int_value(
                "TERMINAL_CONTROL_SESSION_TIMEOUT",
                config_data.get("session", {}).get("timeout", 30),
            ),
            # Logging
            log_level=cls._get_str_value(
                "TERMINAL_CONTROL_LOG_LEVEL",
                config_data.get("logging", {}).get("level", "INFO"),
            )
            or "INFO",
            # Terminal
            terminal_width=cls._get_int_value(
                "TERMINAL_CONTROL_TERMINAL_WIDTH",
                config_data.get("terminal", {}).get("width", 120),
            ),
            terminal_height=cls._get_int_value(
                "TERMINAL_CONTROL_TERMINAL_HEIGHT",
                config_data.get("terminal", {}).get("height", 30),
            ),
            terminal_close_timeout=cls._get_float_value(
                "TERMINAL_CONTROL_TERMINAL_CLOSE_TIMEOUT",
                config_data.get("terminal", {}).get("close_timeout", 5.0),
            ),
            terminal_process_check_timeout=cls._get_float_value(
                "TERMINAL_CONTROL_TERMINAL_PROCESS_CHECK_TIMEOUT",
                config_data.get("terminal", {}).get("process_check_timeout", 1.0),
            ),
            terminal_polling_interval=cls._get_float_value(
                "TERMINAL_CONTROL_TERMINAL_POLLING_INTERVAL",
                config_data.get("terminal", {}).get("polling_interval", 0.05),
            ),
            terminal_send_input_delay=cls._get_float_value(
                "TERMINAL_CONTROL_TERMINAL_SEND_INPUT_DELAY",
                config_data.get("terminal", {}).get("send_input_delay", 0.1),
            ),
            terminal_emulators=cls._get_terminal_emulators(
                config_data.get("terminal", {}).get("emulators", [])
            ),
        )

    @classmethod
    def from_environment(cls) -> "ServerConfig":
        """Create configuration from environment variables only (backwards compatibility)"""
        return cls.from_config_and_environment(None)

    @staticmethod
    def _load_toml_config(config_file: str | None) -> dict[str, Any]:
        """Load configuration from TOML file"""
        # If a specific config file is provided, only try that file
        if config_file:
            config_path = Path(config_file)
            if config_path.exists() and config_path.is_file():
                try:
                    with open(config_path, "rb") as f:
                        config_data = tomllib.load(f)
                    print(f"Loaded configuration from: {config_path}")
                    return config_data
                except Exception as e:
                    print(f"Warning: Could not read config file {config_path}: {e}")
            return {}  # Return empty dict if specific file not found/readable

        # If no specific file provided, search default locations
        default_locations = [
            Path("terminal-control.toml"),
            Path(os.path.expanduser("~/.config/terminal-control.toml")),
            Path("/etc/terminal-control.toml"),
        ]

        for config_path in default_locations:
            if config_path.exists() and config_path.is_file():
                try:
                    with open(config_path, "rb") as f:
                        config_data = tomllib.load(f)
                    print(f"Loaded configuration from: {config_path}")
                    return config_data
                except Exception as e:
                    print(f"Warning: Could not read config file {config_path}: {e}")

        return {}  # Return empty dict if no config file found

    @staticmethod
    def _get_str_value(env_var: str, default: str | None) -> str | None:
        """Get string value from environment, falling back to default"""
        env_value = os.environ.get(env_var)
        return env_value if env_value is not None else default

    @staticmethod
    def _get_int_value(env_var: str, default: int) -> int:
        """Get integer value from environment, falling back to default"""
        env_value = os.environ.get(env_var)
        if env_value is not None:
            try:
                return int(env_value)
            except ValueError:
                pass
        return default

    @staticmethod
    def _get_bool_value(env_var: str, default: bool) -> bool:
        """Get boolean value from environment, falling back to default"""
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return env_value.lower() in ("true", "1", "yes", "on")
        return default

    @staticmethod
    def _get_float_value(env_var: str, default: float) -> float:
        """Get float value from environment, falling back to default"""
        env_value = os.environ.get(env_var)
        if env_value is not None:
            try:
                return float(env_value)
            except ValueError:
                pass
        return default

    @staticmethod
    def _get_security_level(env_var: str, default: str) -> SecurityLevel:
        """Get security level from environment, falling back to default"""
        env_value = os.environ.get(env_var)
        level_str = env_value if env_value is not None else default
        try:
            return SecurityLevel(level_str.lower())
        except ValueError:
            return SecurityLevel.HIGH

    @staticmethod
    def _get_terminal_emulators(emulator_configs: list[dict[str, Any]]) -> list[TerminalEmulator]:
        """Parse terminal emulator configurations from TOML"""
        if not emulator_configs:
            # Default terminal emulators if none configured
            return [
                {"name": "gnome-terminal", "command": ["gnome-terminal", "--"]},
                {"name": "konsole", "command": ["konsole", "-e"]},
                {"name": "xfce4-terminal", "command": ["xfce4-terminal", "-e"]},
                {"name": "io.elementary.terminal", "command": ["io.elementary.terminal", "-e"]},
                {"name": "x-terminal-emulator", "command": ["x-terminal-emulator", "-e"]},
                {"name": "xterm", "command": ["xterm", "-e"]},
                {"name": "Terminal", "command": ["open", "-a", "Terminal"]},
                {"name": "alacritty", "command": ["alacritty", "-e"]},
                {"name": "kitty", "command": ["kitty"]},
                {"name": "terminator", "command": ["terminator", "-e"]},
            ]

        emulators: list[TerminalEmulator] = []
        for config in emulator_configs:
            if isinstance(config, dict) and "name" in config and "command" in config:
                emulator: TerminalEmulator = {
                    "name": config["name"],
                    "command": config["command"]
                }
                emulators.append(emulator)

        return emulators


# Global configuration instance (backwards compatibility)
config = ServerConfig.from_config_and_environment()
