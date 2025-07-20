#!/usr/bin/env python3
"""
Pydantic models for Interactive Automation MCP Server
"""


from pydantic import BaseModel, Field


# Request/Response Models for Session Management
class CreateSessionRequest(BaseModel):
    """Request to create a new interactive session"""

    command: str = Field(
        description="Command to execute (e.g., 'ssh user@host', 'mysql -u root -p')"
    )
    session_name: str | None = Field(
        None, description="Optional human-readable name for the session"
    )
    timeout: int = Field(3600, description="Session timeout in seconds")
    environment: dict[str, str] | None = Field(
        None, description="Environment variables to set"
    )
    working_directory: str | None = Field(
        None, description="Working directory for the command"
    )


class CreateSessionResponse(BaseModel):
    """Response from creating a session"""

    success: bool
    session_id: str
    command: str
    timeout: int


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


class AutomationStep(BaseModel):
    """A single automation step"""

    name: str | None = Field(None, description="Human-readable step description for debugging")
    expect: str = Field(description="Regex pattern to wait for (e.g., '(Pdb)', 'Password:', 'Continue\\\\? \\\\[y/N\\\\]')")
    respond: str = Field(description="Text to send when pattern matches (e.g., 'b main', 'mypassword', 'y')")
    timeout: int = Field(30, description="Timeout for this step")
    optional: bool = Field(False, description="Whether this step is optional")


class MultiStepAutomationRequest(BaseModel):
    """Request for multi-step automation"""

    session_id: str
    steps: list[AutomationStep]
    stop_on_failure: bool = Field(True, description="Whether to stop on first failure")


# Request/Response Models for Universal Command Execution
class AutomationPattern(BaseModel):
    """Automation pattern for command execution"""

    pattern: str = Field(description="Regex pattern to match in output (e.g., 'Password:', 'Are you sure\\\\?', 'Enter.*:')")
    response: str = Field(description="Text to send when pattern matches (e.g., 'mypassword', 'yes', 'config_value')")
    secret: bool = Field(False, description="Whether response contains sensitive data")


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


class ExecuteCommandResponse(BaseModel):
    """Response from command execution"""

    success: bool
    session_id: str
    command: str
    executed: bool
    automation_patterns_used: int
    follow_up_commands_executed: int
    error: str | None = None
