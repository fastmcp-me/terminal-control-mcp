#!/usr/bin/env python3
"""
Pydantic models for Interactive Automation MCP Server
"""


from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Information about a session"""

    session_id: str
    command: str
    state: str
    created_at: float
    last_activity: float


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
    """Request to get current screen content from a session"""

    session_id: str = Field(description="ID of the session to get screen content from")


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


class ExecuteCommandRequest(BaseModel):
    """Request to execute a command and create a session"""

    command: str = Field(description="Command to execute")
    command_args: list[str] | None = Field(
        None, description="Additional command arguments"
    )
    execution_timeout: int = Field(
        30,
        description="Timeout in seconds for process startup (agents control interaction timing)",
    )
    environment: dict[str, str] | None = Field(
        None, description="Environment variables"
    )
    working_directory: str | None = Field(None, description="Working directory")


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


class ExecuteCommandResponse(BaseModel):
    """Response from command execution"""

    success: bool
    session_id: str
    command: str
