#!/usr/bin/env python3
"""
Pydantic models for Interactive Automation MCP Server
"""


from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Information about a session"""

    session_id: str
    command: str
    state: str
    created_at: float
    last_activity: float
    web_url: str | None = Field(
        None,
        description="Web interface URL for this session (if web interface is enabled)",
    )


class ListSessionsResponse(BaseModel):
    """Response from listing sessions"""

    success: bool
    sessions: list[SessionInfo]
    total_sessions: int


class DestroySessionRequest(BaseModel):
    """Request to destroy a session"""

    session_id: str = Field(description="ID of the session to destroy")


class DestroySessionResponse(BaseModel):
    """Response from destroying a session"""

    success: bool
    session_id: str
    message: str


class GetScreenContentRequest(BaseModel):
    """Request to get terminal content from a session"""

    session_id: str = Field(description="ID of the session to get content from")
    content_mode: Literal["screen", "since_input", "history", "tail"] = Field(
        "screen",
        description="Content mode: 'screen' (current visible screen), 'since_input' (output since last input), 'history' (full terminal history), 'tail' (last N lines)",
    )
    line_count: int | None = Field(
        None, description="Number of lines for 'tail' mode (ignored for other modes)"
    )


class GetScreenContentResponse(BaseModel):
    """Response with current screen content"""

    success: bool
    session_id: str
    process_running: bool
    screen_content: str | None = None
    timestamp: str | None = Field(
        None, description="ISO timestamp when screen content was captured"
    )
    error: str | None = None


class SendInputRequest(BaseModel):
    """Request to send input to a session"""

    session_id: str = Field(description="ID of the session to send input to")
    input_text: str = Field(description="Text to send to the process")


class SendInputResponse(BaseModel):
    """Response from sending input to a session"""

    success: bool
    session_id: str
    message: str
    screen_content: str | None = Field(
        None, description="Current terminal screen content after input"
    )
    timestamp: str | None = Field(
        None, description="Timestamp when screen content was captured"
    )
    process_running: bool | None = Field(
        None, description="Whether the process is still running"
    )
    error: str | None = None


@dataclass
class EnvironmentConfig:
    """Environment configuration for command execution"""

    variables: dict[str, str]

    def to_dict(self) -> dict[str, str]:
        return self.variables

    @classmethod
    def from_dict(cls, env_dict: dict[str, str]) -> "EnvironmentConfig":
        return cls(variables=env_dict)


@dataclass
class LogEventData:
    """Structured data for logging events"""

    event_type: str
    timestamp: float
    relative_time: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "relative_time": self.relative_time,
            "data": self.data,
        }


class OpenTerminalRequest(BaseModel):
    """Request to open a new terminal session"""

    shell: str = Field("bash", description="Shell to use (bash, zsh, fish, sh, etc.)")
    working_directory: str | None = Field(None, description="Working directory")
    environment: dict[str, str] | None = Field(
        None, description="Environment variables"
    )


class OpenTerminalResponse(BaseModel):
    """Response from opening a terminal session"""

    success: bool
    session_id: str
    shell: str
    web_url: str | None = Field(
        None, description="Web interface URL for direct browser access to this session"
    )
    screen_content: str | None = None
    timestamp: str | None = Field(
        None, description="ISO timestamp when screen content was captured"
    )
    error: str | None = None
