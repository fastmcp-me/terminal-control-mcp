#!/usr/bin/env python3
"""
Terminal Control MCP Server - FastMCP Implementation
Provides interactive terminal session management for LLM agents

Core tools:
- `open_terminal`: Open new terminal sessions with specified shell
- `get_screen_content`: Get current terminal output from sessions
- `send_input`: Send input to interactive sessions (supports key combinations)
- `list_terminal_sessions`: Show active sessions
- `exit_terminal`: Clean up sessions
"""

import asyncio
import logging
import os
import shutil
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .config import ServerConfig
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
from .terminal_utils import open_terminal_window
from .web_server import WebServer

# Load configuration from TOML file and environment variables
config = ServerConfig.from_config_and_environment()

# Always import WebServer for type annotations, handle runtime availability separately
WEB_INTERFACE_AVAILABLE = True


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
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
    config: Any = None  # ServerConfig


async def _initialize_web_server(
    session_manager: SessionManager,
) -> tuple[WebServer | None, asyncio.Task[None] | None]:
    """Initialize web server if enabled and available"""
    if not config.web_enabled:
        logger.info("Web interface disabled by configuration")
        return None, None

    if not WEB_INTERFACE_AVAILABLE or WebServer is None:
        logger.info("Web interface not available (missing dependencies)")
        return None, None

    # Determine web server port
    web_port = _get_effective_web_port()

    web_server = WebServer(session_manager, port=web_port)
    web_task = asyncio.create_task(web_server.start())
    logger.info(f"Web interface available at http://{config.web_host}:{web_port}")
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
    await session_manager.shutdown()


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with initialized components"""
    logger.info("Initializing Terminal Control MCP Server...")

    # Check system dependencies
    check_tmux_available()

    # Initialize components
    session_manager = SessionManager(max_sessions=config.max_sessions)
    security_manager = SecurityManager(
        security_level=config.security_level,
        max_calls_per_minute=config.max_calls_per_minute,
    )
    web_server, web_task = await _initialize_web_server(session_manager)

    try:
        yield AppContext(
            session_manager=session_manager,
            security_manager=security_manager,
            web_server=web_server,
            config=config,
        )
    finally:
        logger.info("Shutting down Terminal Control MCP Server...")
        await _cleanup_web_server(web_task)
        await _cleanup_sessions(session_manager)


def _get_display_web_host() -> str:
    """Get the web host for display in URLs (handles 0.0.0.0 binding)"""
    external_host = config.external_web_host
    web_host = external_host or config.web_host

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


def _get_effective_web_port() -> int:
    """Get the effective web port, using auto-selection if enabled"""
    if not config.web_auto_port:
        return config.web_port

    # Generate unique identifier based on current working directory and process ID
    import hashlib

    unique_id = f"{os.getcwd()}:{os.getpid()}"
    hash_value = int(hashlib.md5(unique_id.encode()).hexdigest()[:4], 16)

    # Use port range 9000-9999 for auto-selected ports (safer range)
    auto_port = 9000 + (hash_value % 1000)

    logger.info(f"Auto-selected port {auto_port} (web_auto_port=true)")
    return auto_port


# Create FastMCP server with lifespan management
mcp = FastMCP("Terminal Control", lifespan=app_lifespan)


# Session Management Tools
@mcp.tool()
async def list_terminal_sessions(ctx: Context) -> ListSessionsResponse:
    """Show all active terminal sessions

    No parameters required.

    Returns ListSessionsResponse with:
    - success: bool - Operation success status
    - sessions: List[SessionInfo] - List of active sessions with session_id, command, state, timestamps, and web URLs (if web interface enabled)
    - total_sessions: int - Total number of active sessions (max 50)

    Use with: `get_screen_content`, `send_input`, `exit_terminal`
    """
    app_ctx = ctx.request_context.lifespan_context

    sessions = await app_ctx.session_manager.list_sessions()

    # Determine if we should include web URLs
    web_host = None
    web_port = None
    if WEB_INTERFACE_AVAILABLE and config.web_enabled:
        web_host = _get_display_web_host()
        web_port = _get_effective_web_port()

    session_list = [
        SessionInfo(
            session_id=session.session_id,
            command=session.command,
            state=session.state.value,
            created_at=session.created_at,
            last_activity=session.last_activity,
            web_url=(
                f"http://{web_host}:{web_port}/session/{session.session_id}"
                if web_host and web_port
                else None
            ),
        )
        for session in sessions
    ]

    # Log web interface information
    if session_list and web_host and web_port:
        logger.info(
            f"Sessions available via web interface at http://{web_host}:{web_port}/"
        )
        for session in session_list:
            if session.web_url:
                logger.info(f"Session {session.session_id}: {session.web_url}")

    return ListSessionsResponse(
        success=True, sessions=session_list, total_sessions=len(session_list)
    )


@mcp.tool()
async def exit_terminal(
    request: DestroySessionRequest, ctx: Context
) -> DestroySessionResponse:
    """Close and clean up a terminal session

    Parameters (DestroySessionRequest):
    - session_id: str - ID of the session to destroy

    Returns DestroySessionResponse with:
    - success: bool - True if session was found and destroyed
    - session_id: str - Echo of the requested session ID
    - message: str - "Session destroyed" or "Session not found"

    Use with: `open_terminal`, `get_screen_content`, `send_input`, `list_terminal_sessions`
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
    """Get terminal content from a session with precise control over what content is returned

    Parameters (GetScreenContentRequest):
    - session_id: str - Session ID (from `open_terminal` or `list_terminal_sessions`)
    - content_mode: "screen" | "since_input" | "history" | "tail" - Content retrieval mode (default: "screen")
      * "screen": Current visible screen only (default)
      * "since_input": Output since last input command
      * "history": Full terminal history
      * "tail": Last N lines (requires line_count)
    - line_count: int | None - Number of lines for "tail" mode (ignored for other modes)

    Returns GetScreenContentResponse with:
    - success: bool - Operation success status
    - session_id: str - Echo of the requested session ID
    - process_running: bool - Whether process is still active
    - screen_content: str | None - Terminal content based on content_mode
    - timestamp: str - ISO timestamp when content was captured
    - error: str | None - Error message if operation failed

    Use with: `open_terminal`, `send_input`, `list_terminal_sessions`, `exit_terminal`
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
        # Always use tmux/libtmux as the source of truth for MCP tools
        screen_content = await session.get_content_by_mode(
            request.content_mode, request.line_count
        )
        process_running = session.is_process_alive()
        timestamp = datetime.now().isoformat()

        # Log web interface URL for user access if available
        if config.web_enabled and WEB_INTERFACE_AVAILABLE:
            web_host = _get_display_web_host()
            web_port = _get_effective_web_port()
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
    """Send input/commands to an interactive terminal session

    Parameters (SendInputRequest):
    - session_id: str - Session ID to send input to
    - input_text: str - Text to send (supports escape sequences: \\x03=Ctrl+C, \\x0a=Enter, \\x1b[A=Up arrow, \\x1b[B=Down arrow, \\x1b[C=Right arrow, \\x1b[D=Left arrow, \\x1b[H=Home, \\x1b[F=End, etc.)

    IMPORTANT: Newlines are NOT added automatically. For commands that need to be executed,
    you must explicitly include \\n at the end (e.g., "ls\\n", "python\\n", "exit\\n").
    Without a newline, the input will appear at the prompt but won't execute.

    Returns SendInputResponse with:
    - success: bool - True if input was sent successfully
    - session_id: str - Echo of the requested session ID
    - message: str - Confirmation message
    - screen_content: str | None - Terminal content after input
    - timestamp: str | None - When content was captured
    - process_running: bool | None - Whether process is still active
    - error: str | None - Error message if operation failed

    Use with: `open_terminal`, `get_screen_content`, `list_terminal_sessions`, `exit_terminal`
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "send_input", request.model_dump()
    ):
        raise ValueError(
            "Security violation: Tool call rejected. If this command is safe, please enter it manually in the terminal."
        )

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
        # Always send input directly to tmux session
        await session.send_input(request.input_text)

        # Give a moment for the command to process and update the terminal
        await asyncio.sleep(config.terminal_send_input_delay)

        # For exit commands, give extra time for tmux to detect shell exit
        if request.input_text.strip().lower() in ["exit", "exit\n"]:
            await asyncio.sleep(0.5)  # Extra delay for exit detection

        # Capture current screen content after input (use screen mode)
        screen_content = await session.get_current_screen_content()
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


async def _create_terminal_session(
    app_ctx: AppContext, request: OpenTerminalRequest
) -> str:
    """Create a new terminal session and return session ID"""
    logger.info(f"Creating terminal session with shell: {request.shell}")
    return await app_ctx.session_manager.create_session(
        command=request.shell,
        timeout=config.session_timeout,
        environment=request.environment,
        working_directory=request.working_directory,
    )


async def _get_session_web_url(session_id: str) -> str | None:
    """Get web interface URL for a session if web is enabled"""
    if not (config.web_enabled and WEB_INTERFACE_AVAILABLE):
        logger.info(f"Terminal session {session_id} created (web interface disabled)")
        return None

    web_host = _get_display_web_host()
    web_port = _get_effective_web_port()
    web_url = f"http://{web_host}:{web_port}/session/{session_id}"
    logger.info(f"Terminal session {session_id} created. Web interface: {web_url}")
    return web_url


async def _get_initial_screen_content(
    app_ctx: AppContext, session_id: str
) -> str | None:
    """Get initial screen content from a session"""
    session = await app_ctx.session_manager.get_session(session_id)
    if not session:
        return None

    try:
        return await session.get_current_screen_content()
    except Exception as e:
        logger.warning(f"Failed to get initial screen content: {e}")
        return None


# Terminal Opening Tool
@mcp.tool()
async def open_terminal(
    request: OpenTerminalRequest, ctx: Context
) -> OpenTerminalResponse:
    """Open a new terminal session with specified shell

    Parameters (OpenTerminalRequest):
    - shell: str - Shell to use (bash, zsh, fish, sh, etc.) - defaults to "bash"
    - working_directory: str | None - Directory to start terminal in (optional)
    - environment: Dict[str, str] | None - Environment variables to set (optional)

    Returns OpenTerminalResponse with:
    - success: bool - True if session was created successfully
    - session_id: str - Unique session identifier for other tools
    - shell: str - Shell that was started
    - web_url: str | None - URL for web interface access
    - screen_content: str | None - Initial terminal output
    - timestamp: str | None - ISO timestamp when content was captured
    - error: str | None - Error message if operation failed

    Use with: `send_input`, `get_screen_content`, `list_terminal_sessions`, `exit_terminal`
    """
    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "open_terminal", request.model_dump()
    ):
        raise ValueError(
            "Security violation: Tool call rejected. If this configuration is safe, please create the terminal manually."
        )

    try:
        session_id = await _create_terminal_session(app_ctx, request)
        web_url = await _get_session_web_url(session_id)
        screen_content = await _get_initial_screen_content(app_ctx, session_id)

        # If web interface is disabled, automatically open a terminal window
        if not config.web_enabled:
            terminal_opened = await open_terminal_window(session_id)
            if terminal_opened:
                logger.info(f"Terminal window opened for session {session_id}")
            else:
                logger.info(f"Manual attachment required: tmux attach -t {session_id}")

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
    # Check if running in an interactive terminal (user ran it manually)
    if sys.stdout.isatty() and sys.stdin.isatty():
        print("\n⚠️  Terminal Control MCP Server")
        print("=" * 40)
        print("This is an MCP (Model Context Protocol) server that requires")
        print("an MCP client to run. You cannot run it directly from the command line.")
        print("\n📋 Setup Instructions:")
        print("\n1. For Claude Code (Anthropic):")
        print("   claude mcp add terminal-control -s user terminal-control-mcp")
        print("\n2. For other MCP clients, add to your configuration:")
        print(
            '   {"mcpServers": {"terminal-control": {"command": "terminal-control-mcp"}}}'
        )
        print("\n3. The server will be automatically launched by your MCP client.")
        print(
            "\n💡 For more information, see: https://github.com/wehnsdaefflae/terminal-control-mcp"
        )
        print()
        sys.exit(0)

    mcp.run()


def main_sync() -> None:
    """Synchronous entry point for console scripts"""
    main()


if __name__ == "__main__":
    main_sync()
