#!/usr/bin/env python3
"""
Terminal Control MCP Server - FastMCP Implementation
Provides interactive terminal session management for LLM agents

Core tools:
- open_terminal: Open new terminal sessions with specified shell
- get_screen_content: Get current terminal output from sessions
- send_input: Send input to interactive sessions
- list_terminal_sessions: Show active sessions
- exit_terminal: Clean up sessions
"""

import asyncio
import logging
import shutil
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
    GetScreenContentRequest,
    GetScreenContentResponse,
    ListSessionsResponse,
    OpenTerminalRequest,
    OpenTerminalResponse,
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


# System dependency checks
def check_tmux_available() -> None:
    """Check if tmux is available on the system"""
    if not shutil.which("tmux"):
        logger.error("tmux is not installed or not found in PATH")
        logger.error("Please install tmux:")
        logger.error("  Ubuntu/Debian: sudo apt update && sudo apt install -y tmux")
        logger.error("  macOS: brew install tmux")
        logger.error("  CentOS/RHEL/Fedora: sudo yum install tmux")
        sys.exit(1)

    logger.info("tmux dependency check passed")


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

    # Check system dependencies
    check_tmux_available()

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
async def list_terminal_sessions(ctx: Context) -> ListSessionsResponse:
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

    Use with: get_screen_content, send_input, exit_terminal
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
async def exit_terminal(
    request: DestroySessionRequest, ctx: Context
) -> DestroySessionResponse:
    """Close and clean up a terminal session

    Use this when users ask to "close", "stop", "terminate", "kill", "exit", "end", or "clean up" a session.
    Examples: "close that session", "stop the debugger", "clean up when done", "exit that program".

    Properly closes a session and frees up resources.

    Parameters (DestroySessionRequest):
    - session_id: str - ID of the session to destroy (from list_terminal_sessions or open_terminal)

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
async def get_screen_content(
    request: GetScreenContentRequest, ctx: Context
) -> GetScreenContentResponse:
    """See what's currently displayed in a terminal session

    Use this when users ask "what's on screen", "show me the output", "what's currently showing",
    "what do you see", or to check the current state of a terminal.

    Returns the current terminal output visible to the user. This allows the agent
    to see what's currently on screen and decide what to do next.

    Parameters (GetScreenContentRequest):
    - session_id: str - ID of the session to get screen content from (from open_terminal or list_terminal_sessions)

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

    Use with: open_terminal (to get session_id), send_input (when ready for input)
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
async def send_input(request: SendInputRequest, ctx: Context) -> SendInputResponse:
    """Type commands or input into an interactive terminal session

    Use this when users ask to "type", "send", "enter", "input", "respond", "answer", or "press" something.
    Examples: "type 'ls -la'", "send 'print(2+2)'", "enter my password", "respond 'yes'", "press Enter".

    Sends text input to the running process in the specified session.
    Use this when the agent determines the process is ready for input.

    Parameters (SendInputRequest):
    - session_id: str - ID of the session to send input to (from open_terminal or list_terminal_sessions)
    - input_text: str - Text to send to the process (supports escape sequences for keyboard shortcuts)

    Keyboard Shortcuts & Escape Sequences Support:
    The input_text parameter supports terminal escape sequences for sending keyboard shortcuts:

    Control Characters (Ctrl+Key):
    - "\\x03" - Ctrl+C (interrupt/SIGINT)
    - "\\x04" - Ctrl+D (EOF)
    - "\\x08" - Ctrl+H (backspace)
    - "\\x09" - Tab
    - "\\x0a" - Enter/Line Feed
    - "\\x0d" - Carriage Return
    - "\\x1a" - Ctrl+Z (suspend)
    - "\\x1b" - Escape key

    Arrow Keys:
    - "\\x1b[A" - Up arrow
    - "\\x1b[B" - Down arrow
    - "\\x1b[C" - Right arrow
    - "\\x1b[D" - Left arrow

    Function Keys:
    - "\\x1bOP" - F1
    - "\\x1bOQ" - F2
    - "\\x1b[15~" - F5
    - "\\x1b[17~" - F6
    (F3-F12 and other special keys supported)

    Returns SendInputResponse with:
    - success: bool - True if input was sent successfully, False if failed
    - session_id: str - Echo of the requested session ID
    - message: str - Confirmation message with echoed input text
    - error: str | None - Error message if operation failed (None on success)

    Use this tool to:
    - Respond to prompts in interactive programs
    - Enter commands in shells or REPL environments
    - Provide input when programs are waiting for user response
    - Send keyboard shortcuts to debuggers, editors, and interactive programs
    - Navigate menus and interfaces using arrow keys and function keys

    Use this tool to send commands, respond to prompts, or provide input to running processes.
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "send_input", request.model_dump()
    ):
        raise ValueError("Security violation: Tool call rejected")

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return SendInputResponse(
            success=False,
            session_id=request.session_id,
            message="Session not found",
            screen_content=None,
            timestamp=None,
            process_running=None,
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

        # Give a moment for the command to process and update the terminal
        await asyncio.sleep(0.1)

        # Capture current screen content after input
        screen_content = await session.get_raw_output()
        timestamp = datetime.now().isoformat()
        process_running = session.is_process_alive()

        return SendInputResponse(
            success=True,
            session_id=request.session_id,
            message=f"Input sent successfully: '{request.input_text}'",
            screen_content=screen_content,
            timestamp=timestamp,
            process_running=process_running,
        )
    except Exception as e:
        logger.warning(f"Failed to send input to session {request.session_id}: {e}")
        return SendInputResponse(
            success=False,
            session_id=request.session_id,
            message="Failed to send input",
            screen_content=None,
            timestamp=None,
            process_running=None,
            error=str(e),
        )


# Terminal Opening Tool
@mcp.tool()
async def open_terminal(
    request: OpenTerminalRequest, ctx: Context
) -> OpenTerminalResponse:
    """Open a new terminal session with a specified shell

    Use this when users ask to "open a terminal", "start a shell", "open bash", "create a new session".
    Examples: "open a terminal", "start a bash session", "create a new terminal with zsh".

    Creates a new terminal session with the specified shell and automatically returns the current
    screen content. The terminal is ready for interactive use immediately.

    Parameters (OpenTerminalRequest):
    - shell: str - Shell to use (bash, zsh, fish, sh, etc.) - defaults to "bash"
    - working_directory: str | None - Directory to start the terminal in (optional)
    - environment: Dict[str, str] | None - Environment variables to set (optional)

    Returns OpenTerminalResponse with:
    - success: bool - True if session was created successfully, False if failed
    - session_id: str - Unique session identifier for use with other tools
    - shell: str - Shell that was started
    - web_url: str | None - URL for web interface to view session output (if available)
    - screen_content: str | None - Current terminal output immediately after opening
    - timestamp: str | None - ISO timestamp when screen content was captured
    - error: str | None - Error message if operation failed (None on success)

    The session's web interface URL can be shared with users for direct browser access to view terminal
    output and send manual input.

    Agent workflow:
    1. open_terminal - Creates session and returns initial screen content
    2. send_input - Send commands or input to the terminal
    3. get_screen_content - Check current terminal state if needed
    4. exit_terminal - Clean up when finished (required for ALL sessions)

    Use with: send_input, get_screen_content, list_terminal_sessions, exit_terminal
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "open_terminal", request.model_dump()
    ):
        raise ValueError("Security violation: Tool call rejected")

    try:
        # Create session with the specified shell
        logger.info(f"Creating terminal session with shell: {request.shell}")
        session_id = await app_ctx.session_manager.create_session(
            command=request.shell,
            timeout=30,  # Fixed timeout for shell startup
            environment=request.environment,
            working_directory=request.working_directory,
        )

        # Get web interface URL for this session
        web_host = _get_display_web_host()
        web_port = get_web_port()
        web_url = f"http://{web_host}:{web_port}/session/{session_id}"
        logger.info(f"Terminal session {session_id} created. Web interface: {web_url}")

        # Get initial screen content
        session = await app_ctx.session_manager.get_session(session_id)
        screen_content = None
        if session:
            try:
                screen_content = await session.get_output()
            except Exception as e:
                logger.warning(f"Failed to get initial screen content: {e}")

        return OpenTerminalResponse(
            success=True,
            session_id=session_id,
            shell=request.shell,
            web_url=web_url,
            screen_content=screen_content,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error opening terminal: {e}")
        return OpenTerminalResponse(
            success=False,
            session_id="",
            shell=request.shell,
            web_url=None,
            timestamp=datetime.now().isoformat(),
            error=str(e),
        )


def main() -> None:
    """Entry point for the server"""
    mcp.run()


def main_sync() -> None:
    """Synchronous entry point for console scripts"""
    main()


if __name__ == "__main__":
    main_sync()
