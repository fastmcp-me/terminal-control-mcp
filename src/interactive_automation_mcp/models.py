#!/usr/bin/env python3
"""
Pydantic models for Interactive Automation MCP Server
"""


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


# Request/Response Models for Basic Automation
class ExpectAndRespondRequest(BaseModel):
    """Request for expect and respond operation"""

    session_id: str
    expect_pattern: str = Field(description="Regex pattern to wait for (e.g., '(Pdb)', 'Password:', '$ ')")
    response: str = Field(description="Text to send when pattern matches (e.g., 'n', 'mypassword', 'ls')")
    timeout: int = Field(30, description="Timeout in seconds")
    case_sensitive: bool = Field(
        False, description="Whether pattern matching is case sensitive"
    )



# Request/Response Models for Universal Command Execution
class AutomationPattern(BaseModel):
    """Automation pattern for command execution"""

    pattern: str = Field(description="Regex pattern to match in output (e.g., 'Password:', 'Are you sure\\\\?', 'Enter.*:')")
    response: str = Field(description="Text to send when pattern matches (e.g., 'mypassword', 'yes', 'config_value')")
    secret: bool = Field(False, description="Whether response contains sensitive data")
    delay_before_response: float = Field(0.0, description="Seconds to wait after pattern match before sending response")


class ExecuteCommandRequest(BaseModel):
    """Request to execute a command with optional automation"""

    command: str = Field(description="Command to execute")
    command_args: list[str] | None = Field(
        None, description="Additional command arguments"
    )
    automation_patterns: list[AutomationPattern] | None = Field(
        None, description="Automation patterns to handle prompts (password, confirmation, input requests)"
    )
    execution_timeout: int = Field(
        30, description="Timeout in seconds for command execution"
    )
    follow_up_commands: list[str] | None = Field(
        None, description="Commands to run after automation completes (e.g., ['echo done', 'exit'])"
    )
    environment: dict[str, str] | None = Field(
        None, description="Environment variables"
    )
    working_directory: str | None = Field(None, description="Working directory")
    wait_after_automation: int | None = Field(
        None, description="Seconds to wait after automation completes to capture additional output"
    )



class ExecuteCommandResponse(BaseModel):
    """Response from command execution"""

    success: bool
    session_id: str
    command: str
    executed: bool
    automation_patterns_used: int
    follow_up_commands_executed: int
    output: str | None = None
    error: str | None = None
