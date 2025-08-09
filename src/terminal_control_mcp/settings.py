#!/usr/bin/env python3
"""
Streamlined configuration using pydantic-settings
All configuration options loaded from TOML file only
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class SecurityLevel(Enum):
    """Security levels for the MCP server"""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TerminalEmulator(BaseModel):
    """Terminal emulator configuration"""

    name: str
    command: list[str]


class WebSettings(BaseModel):
    """Web server configuration"""

    enabled: bool
    host: str
    port: int
    external_host: str | None = None


class SecuritySettings(BaseModel):
    """Security configuration"""

    level: SecurityLevel
    max_calls_per_minute: int
    max_sessions: int


class SessionSettings(BaseModel):
    """Session configuration"""

    default_shell: str
    timeout: int
    isolate_history: bool = True
    history_file_prefix: str = "mcp_session_history"


class LoggingSettings(BaseModel):
    """Logging configuration"""

    level: str


class TerminalSettings(BaseModel):
    """Terminal configuration"""

    width: int
    height: int
    close_timeout: float
    process_check_timeout: float
    polling_interval: float
    send_input_delay: float
    screen_content_delay: float
    emulators: list[TerminalEmulator]


class ServerConfig(BaseSettings):
    """Central configuration for the MCP server"""

    model_config = SettingsConfigDict(
        toml_file=["terminal-control.toml", "~/.config/terminal-control.toml"],
    )

    web: WebSettings = WebSettings(
        enabled=False,
        host="0.0.0.0",
        port=8080
    )
    security: SecuritySettings = SecuritySettings(
        level=SecurityLevel.HIGH,
        max_calls_per_minute=60,
        max_sessions=50
    )
    session: SessionSettings = SessionSettings(
        default_shell="bash",
        timeout=30
    )
    logging: LoggingSettings = LoggingSettings(
        level="INFO"
    )
    terminal: TerminalSettings = TerminalSettings(
        width=120,
        height=30,
        close_timeout=5.0,
        process_check_timeout=1.0,
        polling_interval=0.05,
        send_input_delay=0.1,
        screen_content_delay=1.0,
        emulators=[
            TerminalEmulator(name="gnome-terminal", command=["gnome-terminal", "--"]),
            TerminalEmulator(name="konsole", command=["konsole", "-e"]),
            TerminalEmulator(name="xfce4-terminal", command=["xfce4-terminal", "-e"]),
            TerminalEmulator(name="io.elementary.terminal", command=["io.elementary.terminal", "-e"]),
            TerminalEmulator(name="x-terminal-emulator", command=["x-terminal-emulator", "-e"]),
            TerminalEmulator(name="xterm", command=["xterm", "-e"]),
            TerminalEmulator(name="Terminal", command=["open", "-a", "Terminal"]),
            TerminalEmulator(name="alacritty", command=["alacritty", "-e"]),
            TerminalEmulator(name="kitty", command=["kitty"]),
            TerminalEmulator(name="terminator", command=["terminator", "-e"]),
        ]
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load settings from TOML file only - no environment variables"""
        # Remove unused parameter warnings
        _ = init_settings, env_settings, dotenv_settings, file_secret_settings
        return (TomlConfigSettingsSource(settings_cls),)

    # Backward compatibility properties
    @property
    def web_enabled(self) -> bool:
        return self.web.enabled

    @property
    def web_host(self) -> str:
        return self.web.host

    @property
    def web_port(self) -> int:
        return self.web.port

    @property
    def web_auto_port(self) -> bool:
        return True  # This was hardcoded in the old system

    @property
    def external_web_host(self) -> str | None:
        return self.web.external_host

    @property
    def security_level(self) -> SecurityLevel:
        return self.security.level

    @property
    def max_calls_per_minute(self) -> int:
        return self.security.max_calls_per_minute

    @property
    def max_sessions(self) -> int:
        return self.security.max_sessions

    @property
    def default_shell(self) -> str:
        return self.session.default_shell

    @property
    def session_timeout(self) -> int:
        return self.session.timeout

    @property
    def isolate_history(self) -> bool:
        return self.session.isolate_history

    @property
    def history_file_prefix(self) -> str:
        return self.session.history_file_prefix

    @property
    def log_level(self) -> str:
        return self.logging.level

    @property
    def terminal_width(self) -> int:
        return self.terminal.width

    @property
    def terminal_height(self) -> int:
        return self.terminal.height

    @property
    def terminal_close_timeout(self) -> float:
        return self.terminal.close_timeout

    @property
    def terminal_process_check_timeout(self) -> float:
        return self.terminal.process_check_timeout

    @property
    def terminal_polling_interval(self) -> float:
        return self.terminal.polling_interval

    @property
    def terminal_send_input_delay(self) -> float:
        return self.terminal.send_input_delay

    @property
    def terminal_screen_content_delay(self) -> float:
        return self.terminal.screen_content_delay

    @property
    def terminal_emulators(self) -> list[dict[str, Any]]:
        """Convert TerminalEmulator models to dicts for backward compatibility"""
        return [{"name": e.name, "command": e.command} for e in self.terminal.emulators]


# No global config instance - each module should create ServerConfig() when needed
