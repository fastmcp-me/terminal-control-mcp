#!/usr/bin/env python3
"""
Terminal Control MCP Server - FastMCP Implementation
Provides interactive terminal session management for LLM agents

Core tools:
- tercon_execute_command: Execute commands and create sessions
- tercon_get_screen_content: Get current terminal output from sessions
- tercon_send_input: Send input to interactive sessions
- tercon_list_sessions: Show active sessions
- tercon_destroy_session: Clean up sessions
"""

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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

# Import web server components optionally to support testing without web dependencies
try:
    from .web_server import WebServer, get_external_web_host, get_web_host, get_web_port

    WEB_INTERFACE_AVAILABLE = True
except ImportError:
    # Fallback for testing environments without web dependencies
    WebServer = None  # type: ignore
    WEB_INTERFACE_AVAILABLE = False

    def get_web_host() -> str:
        return "127.0.0.1"

    def get_web_port() -> int:
        return 8080

    def get_external_web_host() -> Any:  # type: ignore
        return None


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("terminal-control")


# Application context and lifecycle management


@dataclass
class AppContext:
    """Application context with all managers"""

    session_manager: SessionManager
    security_manager: SecurityManager
    web_server: WebServer | None = None


async def _initialize_web_server(
    session_manager: SessionManager,
) -> tuple[WebServer | None, asyncio.Task[None] | None]:
    """Initialize web server if available"""
    if not WEB_INTERFACE_AVAILABLE or WebServer is None:
        logger.info("Web interface not available (missing dependencies or disabled)")
        return None, None

    web_port = get_web_port()
    web_server = WebServer(session_manager, port=web_port)
    web_task = asyncio.create_task(web_server.start())
    logger.info(f"Web interface available at http://{get_web_host()}:{web_port}")
    return web_server, web_task


async def _cleanup_web_server(web_task: asyncio.Task[None] | None) -> None:
    """Clean up web server task"""
    if web_task is not None:
        web_task.cancel()
        try:
            await web_task
        except asyncio.CancelledError:
            pass


async def _cleanup_sessions(session_manager: SessionManager) -> None:
    """Clean up all active sessions"""
    sessions = await session_manager.list_sessions()
    for session_metadata in sessions:
        await session_manager.destroy_session(session_metadata.session_id)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with initialized components"""
    logger.info("Initializing Terminal Control MCP Server...")

    # Initialize components
    session_manager = SessionManager()
    security_manager = SecurityManager()
    web_server, web_task = await _initialize_web_server(session_manager)

    try:
        yield AppContext(
            session_manager=session_manager,
            security_manager=security_manager,
            web_server=web_server,
        )
    finally:
        logger.info("Shutting down Terminal Control MCP Server...")
        await _cleanup_web_server(web_task)
        await _cleanup_sessions(session_manager)


def _get_display_web_host() -> str:
    """Get the web host for display in URLs (handles 0.0.0.0 binding)"""
    external_host = get_external_web_host()
    web_host = external_host or get_web_host()

    # If binding to 0.0.0.0, provide a more user-friendly URL
    if web_host == "0.0.0.0":
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                web_host = s.getsockname()[0]
        except Exception:
            web_host = "localhost"

    return web_host


# Create FastMCP server with lifespan management
mcp = FastMCP("Terminal Control", lifespan=app_lifespan)


# Session Management Tools
@mcp.tool()
async def tercon_list_sessions(ctx: Context) -> ListSessionsResponse:
    """Show all currently running terminal sessions

    Use this when users ask "list my sessions", "what sessions are running", "show active sessions",
    "what terminals are open", or to find session IDs for other operations.

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

    Web interface URLs for each session are logged and can be shared with users for direct
    browser access to view terminal output and send manual input. The URLs are automatically
    configured based on the server's network settings and can be customized via environment
    variables for remote access.

    Use with: tercon_get_screen_content, tercon_send_input, tercon_destroy_session
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

    # Add web interface information to the response
    response = ListSessionsResponse(
        success=True, sessions=session_list, total_sessions=len(session_list)
    )

    # Add web URLs for user access (agent can share these with users)
    if session_list and WEB_INTERFACE_AVAILABLE:
        web_host = _get_display_web_host()
        web_port = get_web_port()

        logger.info(
            f"Sessions available via web interface at http://{web_host}:{web_port}/"
        )
        for session in session_list:
            session_url = f"http://{web_host}:{web_port}/session/{session.session_id}"
            logger.info(f"Session {session.session_id}: {session_url}")

    return response


@mcp.tool()
async def tercon_destroy_session(
    request: DestroySessionRequest, ctx: Context
) -> DestroySessionResponse:
    """Close and clean up a terminal session

    Use this when users ask to "close", "stop", "terminate", "kill", "exit", "end", or "clean up" a session.
    Examples: "close that session", "stop the debugger", "clean up when done", "exit that program".

    Properly closes a session and frees up resources.

    Parameters (DestroySessionRequest):
    - session_id: str - ID of the session to destroy (from tercon_list_sessions or tercon_execute_command)

    Returns DestroySessionResponse with:
    - success: bool - True if session was found and destroyed, False if not found
    - session_id: str - Echo of the requested session ID
    - message: str - "Session destroyed" or "Session not found"

    Use this to:
    - Clean up finished automation sessions
    - Force-close unresponsive sessions
    - Free up session slots (max 50 concurrent)

    IMPORTANT: Only destroy sessions when the user explicitly requests it or when the session is no longer needed.
    """
    app_ctx = ctx.request_context.lifespan_context

    success = await app_ctx.session_manager.destroy_session(request.session_id)

    return DestroySessionResponse(
        success=success,
        session_id=request.session_id,
        message="Session destroyed" if success else "Session not found",
    )


@mcp.tool()
async def tercon_get_screen_content(
    request: GetScreenContentRequest, ctx: Context
) -> GetScreenContentResponse:
    """See what's currently displayed in a terminal session

    Use this when users ask "what's on screen", "show me the output", "what's currently showing",
    "what do you see", or after starting any command with execute_command.

    ALWAYS use this immediately before tercon_send_input to see if the process is ready for input.

    Returns the current terminal output visible to the user. This allows the agent
    to see what's currently on screen and decide what to do next.

    Parameters (GetScreenContentRequest):
    - session_id: str - ID of the session to get screen content from (from tercon_execute_command or tercon_list_sessions)

    Returns GetScreenContentResponse with:
    - success: bool - Operation success status
    - session_id: str - Echo of the requested session ID
    - process_running: bool - True if process is still active, False if terminated
    - screen_content: str | None - Current terminal output (None if error)
    - timestamp: str - ISO timestamp when screen content was captured
    - error: str | None - Error message if operation failed

    The session's web interface URL is logged for user access to view the same content
    in their browser and send manual input. The URL adapts to the server's network
    configuration for both local and remote access scenarios.

    Use this tool to:
    - Check what's currently displayed in the terminal
    - See if a process is waiting for input
    - Monitor progress of long-running commands
    - Debug interactive program behavior
    - Get timing information for agent decision-making

    Use with: tercon_execute_command (to get session_id), tercon_send_input (when ready for input)
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
        # Use xterm.js buffer as source of truth if web server is available
        if app_ctx.web_server and app_ctx.web_server.is_xterm_active(
            request.session_id
        ):
            screen_content = await app_ctx.web_server.mcp_get_screen_content(
                request.session_id
            )
        else:
            screen_content = await session.get_output()
        process_running = session.is_process_alive()
        timestamp = datetime.now().isoformat()

        # Log web interface URL for user access if available
        if WEB_INTERFACE_AVAILABLE:
            web_host = _get_display_web_host()
            web_port = get_web_port()
            session_url = f"http://{web_host}:{web_port}/session/{request.session_id}"
            logger.info(f"Session {request.session_id} web interface: {session_url}")

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
async def tercon_send_input(
    request: SendInputRequest, ctx: Context
) -> SendInputResponse:
    """Type commands or input into an interactive terminal session

    Use this when users ask to "type", "send", "enter", "input", "respond", "answer", or "press" something.
    Examples: "type 'ls -la'", "send 'print(2+2)'", "enter my password", "respond 'yes'", "press Enter".

    Sends text input to the running process in the specified session.
    Use this when the agent determines the process is ready for input.

    Parameters (SendInputRequest):
    - session_id: str - ID of the session to send input to (from tercon_execute_command or tercon_list_sessions)
    - input_text: str - Text to send to the process (without implicit newline)

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

    IMPORTANT: Always do tercon_get_screen_content before tercon_send_input to check if the process is ready for input.
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "tercon_send_input", request.model_dump()
    ):
        raise ValueError("Security violation: Tool call rejected")

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return SendInputResponse(
            success=False, session_id=request.session_id, message="Session not found"
        )

    try:
        # Use xterm.js input queue if web server is available
        if app_ctx.web_server and app_ctx.web_server.is_xterm_active(
            request.session_id
        ):
            queue_success = await app_ctx.web_server.mcp_send_input(
                request.session_id, request.input_text
            )
            if not queue_success:
                # Fallback to direct session input if xterm queue fails
                await session.send_input(request.input_text)
        else:
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
async def tercon_execute_command(
    request: ExecuteCommandRequest, ctx: Context
) -> ExecuteCommandResponse:
    """Start any terminal command or program in a new session

    Use this when users ask to "start", "run", "launch", "execute", "debug", "connect to", or "open" any program.
    Examples: "start Python", "debug this script", "connect to SSH", "run mysql client", "launch git status".

    Creates a session and executes the specified command. Commands create a persistent session that must be managed by
    the agent. No output is returned - agents must use tercon_get_screen_content to see terminal state.

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
    - web_url: str | None - URL for web interface to view session output (if available)
    - error: str | None - Error message if operation failed (None on success)

    The session's web interface URL can be shared with users for direct browser access to view terminal
    output and send manual input.

    IMPORTANT: For interactive programs that buffer output, use unbuffered mode.
    Use flags like: python -u, stdbuf -o0, or program-specific unbuffered options.

    Agent workflow:
    1. tercon_execute_command - Creates session and starts process
    2. tercon_get_screen_content - Agent sees current terminal state (output or interface)
    3. tercon_send_input - Agent sends input if process is waiting for interaction
    4. Repeat steps 2-3 as needed (agent controls timing)
    5. tercon_destroy_session - Clean up when finished (required for ALL sessions)

    Use with: tercon_get_screen_content (required), tercon_send_input (if needed), tercon_list_sessions, tercon_destroy_session (required)
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "tercon_execute_command", request.model_dump()
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

        # Get web interface URL for this session if available
        web_url = None
        if WEB_INTERFACE_AVAILABLE:
            web_host = _get_display_web_host()
            web_port = get_web_port()
            web_url = f"http://{web_host}:{web_port}/session/{session_id}"
            logger.info(f"Session {session_id} created. Web interface: {web_url}")

        return ExecuteCommandResponse(
            success=True,
            session_id=session_id,
            command=full_command,
            web_url=web_url,
        )

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        # For session creation failures, we could raise an exception instead
        # but for now, return failure with empty session_id
        return ExecuteCommandResponse(
            success=False,
            session_id="",
            command=full_command,
            web_url=None,
        )


def main() -> None:
    """Entry point for the server"""
    mcp.run()


def main_sync() -> None:
    """Synchronous entry point for console scripts"""
    main()


if __name__ == "__main__":
    main_sync()
