#!/usr/bin/env python3
"""
Interactive Automation MCP Server - FastMCP Implementation
Provides interactive terminal session management for LLM agents

Core tools:
- execute_command: Execute commands and create sessions
- get_screen_content: Get current terminal output from sessions
- send_input: Send input to interactive sessions
- list_sessions: Show active sessions
- destroy_session: Clean up sessions
"""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from mcp.server.fastmcp import Context, FastMCP

from .models import (
    DestroySessionRequest,
    DestroySessionResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    GetScreenContentRequest,
    GetScreenContentResponse,
    ListSessionsResponse,
    SendInputRequest,
    SendInputResponse,
    SessionInfo,
)
from .security import SecurityManager
from .session_manager import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("interactive-automation-mcp")


# Application context and lifecycle management


@dataclass
class AppContext:
    """Application context with all managers"""

    session_manager: SessionManager
    security_manager: SecurityManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with initialized components"""
    logger.info("Initializing Interactive Automation MCP Server...")

    # Initialize components
    session_manager = SessionManager()
    security_manager = SecurityManager()

    try:
        yield AppContext(
            session_manager=session_manager,
            security_manager=security_manager,
        )
    finally:
        logger.info("Shutting down Interactive Automation MCP Server...")
        # Cleanup all active sessions
        sessions = await session_manager.list_sessions()
        for session_metadata in sessions:
            await session_manager.destroy_session(session_metadata.session_id)


# Create FastMCP server with lifespan management
mcp = FastMCP("Interactive Automation", lifespan=app_lifespan)


# Session Management Tools
@mcp.tool()
async def list_sessions(ctx: Context) -> ListSessionsResponse:
    """List all active interactive sessions with detailed status information

    Shows session information including IDs, commands, states, and timestamps.
    Use this to monitor workflows, debug issues, and get session IDs for other tools.

    No parameters required.

    Returns ListSessionsResponse with:
    - success: bool - Operation success status
    - sessions: List[SessionInfo] - List of active sessions
      - session_id: str - Unique session identifier for use with other tools
      - command: str - Original command that was executed
      - state: str - Current session state
      - created_at: float - Unix timestamp when session was created
      - last_activity: float - Unix timestamp of last activity
    - total_sessions: int - Total number of active sessions (max 50 concurrent)

    Use with: get_screen_content, send_input, destroy_session
    """
    app_ctx = ctx.request_context.lifespan_context

    sessions = await app_ctx.session_manager.list_sessions()

    session_list = [
        SessionInfo(
            session_id=session.session_id,
            command=session.command,
            state=session.state.value,
            created_at=session.created_at,
            last_activity=session.last_activity,
        )
        for session in sessions
    ]

    return ListSessionsResponse(
        success=True, sessions=session_list, total_sessions=len(session_list)
    )


@mcp.tool()
async def destroy_session(
    request: DestroySessionRequest, ctx: Context
) -> DestroySessionResponse:
    """Terminate and cleanup an interactive session

    Properly closes a session and frees up resources.
    Always destroy sessions when automation is complete.

    Parameters (DestroySessionRequest):
    - session_id: str - ID of the session to destroy (from list_sessions or execute_command)

    Returns DestroySessionResponse with:
    - success: bool - True if session was found and destroyed, False if not found
    - session_id: str - Echo of the requested session ID
    - message: str - "Session destroyed" or "Session not found"

    Use this to:
    - Clean up finished automation sessions
    - Force-close unresponsive sessions
    - Free up session slots (max 50 concurrent)

    Use after: execute_command, get_screen_content, send_input workflows complete
    """
    app_ctx = ctx.request_context.lifespan_context

    success = await app_ctx.session_manager.destroy_session(request.session_id)

    return DestroySessionResponse(
        success=success,
        session_id=request.session_id,
        message="Session destroyed" if success else "Session not found",
    )


@mcp.tool()
async def get_screen_content(
    request: GetScreenContentRequest, ctx: Context
) -> GetScreenContentResponse:
    """Get current screen content from an interactive session

    Returns the current terminal output visible to the user. This allows the agent
    to see what's currently on screen and decide what to do next.

    Parameters (GetScreenContentRequest):
    - session_id: str - ID of the session to get screen content from (from execute_command or list_sessions)

    Returns GetScreenContentResponse with:
    - success: bool - Operation success status
    - session_id: str - Echo of the requested session ID
    - process_running: bool - True if process is still active, False if terminated
    - screen_content: str | None - Current terminal output (None if error)
    - timestamp: str | None - ISO timestamp when screen content was captured
    - error: str | None - Error message if operation failed

    Use this tool to:
    - Check what's currently displayed in the terminal
    - See if a process is waiting for input
    - Monitor progress of long-running commands
    - Debug interactive program behavior
    - Get timing information for agent decision-making

    Use with: execute_command (to get session_id), send_input (when ready for input)
    """
    app_ctx = ctx.request_context.lifespan_context

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return GetScreenContentResponse(
            success=False,
            session_id=request.session_id,
            process_running=False,
            timestamp=datetime.now().isoformat(),
            error="Session not found",
        )

    try:
        screen_content = await session.get_output()
        process_running = session.is_process_alive()
        timestamp = datetime.now().isoformat()

        return GetScreenContentResponse(
            success=True,
            session_id=request.session_id,
            process_running=process_running,
            screen_content=screen_content,
            timestamp=timestamp,
        )
    except Exception as e:
        logger.warning(
            f"Failed to get screen content for session {request.session_id}: {e}"
        )
        return GetScreenContentResponse(
            success=False,
            session_id=request.session_id,
            process_running=False,
            timestamp=datetime.now().isoformat(),
            error=str(e),
        )


@mcp.tool()
async def send_input(request: SendInputRequest, ctx: Context) -> SendInputResponse:
    """Send input to an interactive session

    Sends text input to the running process in the specified session.
    Use this when the agent determines the process is ready for input.

    Parameters (SendInputRequest):
    - session_id: str - ID of the session to send input to (from execute_command or list_sessions)
    - input_text: str - Text to send to the process (newline automatically appended)

    Returns SendInputResponse with:
    - success: bool - True if input was sent successfully, False if failed
    - session_id: str - Echo of the requested session ID
    - message: str - Confirmation message with echoed input text
    - error: str | None - Error message if operation failed (None on success)

    Use this tool to:
    - Respond to prompts in interactive programs
    - Enter commands in shells or REPL environments
    - Provide input when programs are waiting for user response
    - Send keystrokes to any interactive terminal program

    Use after: get_screen_content (to verify process is ready for input)
    
    STRONGLY RECOMMENDED: Run get_screen_content immediately after to see the session's response.
    """
    app_ctx = ctx.request_context.lifespan_context

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return SendInputResponse(
            success=False, session_id=request.session_id, message="Session not found"
        )

    try:
        await session.send_input(request.input_text)
        return SendInputResponse(
            success=True,
            session_id=request.session_id,
            message=f"Input sent successfully: '{request.input_text}'",
        )
    except Exception as e:
        logger.warning(f"Failed to send input to session {request.session_id}: {e}")
        return SendInputResponse(
            success=False,
            session_id=request.session_id,
            message="Failed to send input",
            error=str(e),
        )


# Command Execution Tool
@mcp.tool()
async def execute_command(
    request: ExecuteCommandRequest, ctx: Context
) -> ExecuteCommandResponse:
    """Execute any command and create an interactive session

    Creates a session and executes the specified command. ALL commands (interactive and
    non-interactive) create a persistent session that must be managed by the agent.
    No output is returned - agents must use get_screen_content to see terminal state.

    Parameters (ExecuteCommandRequest):
    - command: str - Command to execute (e.g., 'ssh host', 'python -u script.py', 'ls', 'mysql')
    - command_args: List[str] | None - Additional command arguments (optional)
    - execution_timeout: int - Max seconds for process startup (default: 30, agents control interaction timing)
    - environment: Dict[str, str] | None - Environment variables to set (optional)
    - working_directory: str | None - Directory to run command in (optional)

    Returns ExecuteCommandResponse with:
    - success: bool - True if session was created and command started, False if failed
    - session_id: str - Unique session identifier for use with other tools
    - command: str - Full command that was executed (including args)

    IMPORTANT: For interactive programs that buffer output, use unbuffered mode.
    Use flags like: python -u, stdbuf -o0, or program-specific unbuffered options.

    Agent workflow for ALL commands:
    1. execute_command - Creates session and starts process
    2. get_screen_content - Agent sees current terminal state (output or interface)
    3. send_input - Agent sends input if process is waiting for interaction
    4. Repeat steps 2-3 as needed (agent controls timing)
    5. destroy_session - Clean up when finished (required for ALL sessions)

    Use with: get_screen_content (required), send_input (if needed), list_sessions, destroy_session (required)
    
    STRONGLY RECOMMENDED: Run get_screen_content immediately after to see the session's initial state.
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "execute_command", request.model_dump()
    ):
        raise ValueError("Security violation: Tool call rejected")

    # Build the full command
    full_command = request.command
    if request.command_args:
        full_command += " " + " ".join(request.command_args)

    try:
        # Create session
        logger.info(f"Creating session for command: {full_command}")
        session_id = await app_ctx.session_manager.create_session(
            command=full_command,
            timeout=request.execution_timeout,
            environment=request.environment,
            working_directory=request.working_directory,
        )

        return ExecuteCommandResponse(
            success=True,
            session_id=session_id,
            command=full_command,
        )

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        # For session creation failures, we could raise an exception instead
        # but for now, return failure with empty session_id
        return ExecuteCommandResponse(
            success=False,
            session_id="",
            command=full_command,
        )


def main() -> None:
    """Entry point for the server"""
    mcp.run()


def main_sync() -> None:
    """Synchronous entry point for console scripts"""
    main()


if __name__ == "__main__":
    main_sync()
