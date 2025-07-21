#!/usr/bin/env python3
"""
Interactive Automation MCP Server - FastMCP Implementation
Provides expect/pexpect-style automation for interactive programs

Core tools:
- execute_command: Execute commands with automation (creates temporary sessions)
- expect_and_respond: Single-step automation on existing sessions
- list_sessions: Show active sessions
- destroy_session: Clean up sessions
"""

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .automation_engine import AutomationEngine
from .models import (
    DestroySessionRequest,
    DestroySessionResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ExpectAndRespondRequest,
    ListSessionsResponse,
    SessionInfo,
)
from .security import SecurityManager
from .session_manager import SessionManager
from .utils import wrap_command

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
    automation_engine: AutomationEngine
    security_manager: SecurityManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with initialized components"""
    logger.info("Initializing Interactive Automation MCP Server...")

    # Initialize components
    session_manager = SessionManager()
    automation_engine = AutomationEngine(session_manager)
    security_manager = SecurityManager()

    try:
        yield AppContext(
            session_manager=session_manager,
            automation_engine=automation_engine,
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
    Use this to monitor workflows, debug issues, and get session IDs.

    No parameters required.

    Returns:
    - Session IDs and commands for identification
    - Session states (active, waiting, error, terminated)
    - Creation timestamps and last activity times
    - Total session count (max 50 concurrent)
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

    return ListSessionsResponse(success=True, sessions=session_list, total_sessions=len(session_list))


@mcp.tool()
async def destroy_session(request: DestroySessionRequest, ctx: Context) -> DestroySessionResponse:
    """Terminate and cleanup an interactive session

    Properly closes a session and frees up resources.
    Always destroy sessions when automation is complete.

    Parameters:
    - session_id: ID of the session to destroy

    Use this to:
    - Clean up finished automation sessions
    - Force-close unresponsive sessions
    - Free up session slots (max 50 concurrent)

    Returns success status and cleanup message.
    """
    app_ctx = ctx.request_context.lifespan_context

    success = await app_ctx.session_manager.destroy_session(request.session_id)

    return DestroySessionResponse(
        success=success,
        session_id=request.session_id,
        message="Session destroyed" if success else "Session not found",
    )


# Basic Automation Tools
@mcp.tool()
async def expect_and_respond(request: ExpectAndRespondRequest, ctx: Context) -> dict[str, Any]:
    """Wait for a pattern in session output and automatically respond

    Single-step automation for interactive programs. Waits for a regex pattern to appear
    in the session output, then sends the specified response.

    Parameters:
    - session_id: Session ID from execute_command or active session
    - expect_pattern: Regex pattern to wait for (e.g., 'Password:', '\\(Pdb\\)', 'mysql>')
    - response: Text to send when pattern matches
    - timeout: Max seconds to wait (default: 30)
    - case_sensitive: Whether pattern matching is case-sensitive (default: false)

    Examples:
    - Debugger: expect '\\(Pdb\\)' respond 'n' (step to next line)
    - SSH login: expect 'Password:' respond 'mypassword'
    - Database: expect 'mysql>' respond 'SHOW DATABASES;'
    - Shell: expect '\\$ ' respond 'ls -la'

    For complex workflows, chain multiple expect_and_respond calls on the same session.
    Returns detailed matching information, session state, and captured output.
    """
    app_ctx = ctx.request_context.lifespan_context

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return {"success": False, "error": "Session not found", "output": None}

    result = await session.expect_and_respond(
        pattern=request.expect_pattern,
        response=request.response,
        timeout=request.timeout,
        case_sensitive=request.case_sensitive,
    )

    # Capture output for debugging, especially on timeout
    # Add small delay to ensure all output is captured
    await asyncio.sleep(0.2)
    output = None
    try:
        output = await session.get_output()
    except Exception as e:
        logger.warning(f"Failed to capture output: {e}")

    # Add output to the result
    result["output"] = output

    return result  # type: ignore


# Universal Command Execution Tool
@mcp.tool()
async def execute_command(request: ExecuteCommandRequest, ctx: Context) -> ExecuteCommandResponse:
    """Execute any command with optional automation patterns and follow-up commands

    All-in-one automation tool that combines session creation, automation, and cleanup.
    Perfect for one-off commands and simple automation workflows.

    Parameters:
    - command: Command to execute (e.g., 'ssh host', 'python script.py', 'gemini')
    - automation_patterns: List of pattern/response pairs for prompt handling (optional)
    - follow_up_commands: Additional commands to run after automation (optional)
    - wait_after_automation: Seconds to wait before capturing output (optional)
    - execution_timeout: Max seconds for command execution (default: 30)
    - environment: Environment variables to set (optional)
    - working_directory: Directory to run command in (optional)

    Automation pattern format:
    - pattern: Regex to match prompts (e.g., 'Password:', 'Continue.*\\?')
    - response: Text to send when pattern matches
    - delay_before_response: Seconds to wait before sending response (optional)

    IMPORTANT: For interactive programs that buffer output, use unbuffered mode.
    Buffered output means prompts may not appear immediately, causing automation
    timeouts when expect patterns cannot see the text until buffers flush.
    Use flags like: python -u, stdbuf -o0, or program-specific unbuffered options.

    Examples:
    - SSH with password: command='ssh user@host', patterns=[{pattern:'Password:', response:'mypass'}]
    - Interactive installer: command='./install.sh', patterns=[{pattern:'Continue\\?', response:'y'}]
    - AI chatbot: command='gemini', patterns=[{pattern:'>', response:'Hello'}], wait_after_automation=5

    For multi-step workflows:
    - Use execute_command to start a session
    - Chain expect_and_respond calls for subsequent interactions
    - Sessions persist until destroyed or timeout

    Returns execution results, automation statistics, and captured output.
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
        # Create session and get initial state
        session_id = await _create_session(app_ctx.session_manager, full_command, request)

        # Check for immediate completion
        immediate_result = await _check_immediate_completion(
            app_ctx.session_manager, session_id, full_command
        )
        if immediate_result:
            return immediate_result

        # Handle automation patterns
        automation_result = await _handle_automation_patterns(
            app_ctx, session_id, full_command, request
        )
        if automation_result:
            return automation_result

        automation_patterns_used = len(request.automation_patterns or [])

        # If no automation patterns were provided, check if process is waiting for input
        # In this case, return session for manual interaction via expect_and_respond
        if not request.automation_patterns:
            session = await app_ctx.session_manager.get_session(session_id)
            if session and session.is_process_alive():
                logger.info("[DEBUG] No automation patterns provided and process is waiting - returning session for manual interaction")
                # Get current output and return session for manual interaction
                current_output = await _safe_get_output(app_ctx.session_manager, session_id)
                return ExecuteCommandResponse(
                    success=True,
                    session_id=session_id,
                    command=full_command,
                    executed=True,
                    automation_patterns_used=0,
                    follow_up_commands_executed=0,
                    output=current_output,
                )

        # Execute follow-up commands and finalize
        follow_up_commands_executed = await _execute_follow_up_commands(
            app_ctx.session_manager, session_id, request.follow_up_commands or []
        )

        await _wait_for_additional_output(request.wait_after_automation)

        output = await _capture_final_output(app_ctx.session_manager, session_id)

        

        return _create_success_response(
            session_id, full_command, automation_patterns_used,
            follow_up_commands_executed, output
        )

    except Exception as e:
        return _handle_execution_error(e, full_command)


# Helper functions for execute_command
def _validate_security(security_manager: Any, request: ExecuteCommandRequest) -> None:
    """Validate security for execute_command request"""
    if not security_manager.validate_tool_call("execute_command", request.model_dump()):
        raise ValueError("Security violation: Tool call rejected")

def _build_full_command(request: ExecuteCommandRequest) -> str:
    """Build full command string from request"""
    full_command = request.command
    if request.command_args:
        full_command += " " + " ".join(request.command_args)
    return full_command

async def _create_session(session_manager: Any, full_command: str, request: ExecuteCommandRequest) -> str:
    """Create and return session ID"""
    logger.info(f"[DEBUG] Starting execute_command for: {full_command}")
    logger.info("[DEBUG] Creating session...")
    session_id = await session_manager.create_session(
        command=full_command,
        timeout=request.execution_timeout,
        environment=request.environment,
        working_directory=request.working_directory,
    )
    logger.info(f"[DEBUG] Session created with ID: {session_id}")
    return str(session_id)

async def _check_immediate_completion(
    session_manager: Any, session_id: str, full_command: str
) -> ExecuteCommandResponse | None:
    """Check if process completed immediately and return result if so"""
    session = await session_manager.get_session(session_id)
    if not session:
        return None

    logger.info("[DEBUG] Checking if process has finished or is waiting for input...")
    # Reduced timeout for faster interactive detection
    process_finished, initial_output = await session.wait_for_completion_or_input(timeout=2.0)

    if process_finished:
        logger.info("[DEBUG] Process finished, returning output immediately")

        return ExecuteCommandResponse(
            success=True,
            session_id=session_id,
            command=full_command,
            executed=True,
            automation_patterns_used=0,
            follow_up_commands_executed=0,
            output=initial_output,
        )

    logger.info("[DEBUG] Process still running, continuing with automation patterns if provided...")
    return None

async def _handle_automation_patterns(
    app_ctx: Any, session_id: str, full_command: str, request: ExecuteCommandRequest
) -> ExecuteCommandResponse | None:
    """Handle automation patterns if provided"""
    if not request.automation_patterns:
        return None

    logger.info(f"[DEBUG] Processing {len(request.automation_patterns)} automation patterns")
    automation_steps = _convert_automation_patterns(request)

    logger.info("[DEBUG] Starting automation...")
    auth_results = await app_ctx.automation_engine.multi_step_automation(
        session_id=session_id, steps=automation_steps, stop_on_failure=True
    )
    logger.info("[DEBUG] Automation completed")

    automation_success = all(result["success"] for result in auth_results)
    if not automation_success:
        return await _handle_automation_failure(
            app_ctx.session_manager, session_id, full_command, auth_results, len(request.automation_patterns)
        )

    return None

def _convert_automation_patterns(request: ExecuteCommandRequest) -> list[dict[str, Any]]:
    """Convert automation patterns to automation engine format"""
    return [
        {
            "expect": pattern_config.pattern,
            "respond": pattern_config.response,
            "timeout": request.execution_timeout,
            "delay_before_response": pattern_config.delay_before_response,
        }
        for pattern_config in request.automation_patterns or []
    ]

async def _handle_automation_failure(
    session_manager: Any, session_id: str, full_command: str,
    auth_results: list[Any], automation_patterns_used: int
) -> ExecuteCommandResponse:
    """Handle automation failure case"""
    
    failed_steps = [r for r in auth_results if not r["success"]]
    error_msg = f"Automation failed: {failed_steps[0].get('reason', 'Unknown error')}"

    output = await _safe_get_output(session_manager, session_id)

    return ExecuteCommandResponse(
        success=False,
        session_id=session_id,
        command=full_command,
        executed=False,
        automation_patterns_used=automation_patterns_used,
        follow_up_commands_executed=0,
        output=output,
        error=error_msg,
    )

async def _execute_follow_up_commands(
    session_manager: Any, session_id: str, follow_up_commands: list[str]
) -> int:
    """Execute follow-up commands and return count executed"""
    if not follow_up_commands:
        return 0

    executed_count = 0
    try:
        session = await session_manager.get_session(session_id)
        if session:
            for cmd in follow_up_commands:
                await session.send_input(cmd)
                await asyncio.sleep(0.5)
                executed_count += 1
    except Exception as e:
        logger.warning(f"Follow-up command failed: {e}")

    return executed_count

async def _wait_for_additional_output(wait_after_automation: int | None) -> None:
    """Wait for additional output if requested"""
    if wait_after_automation and wait_after_automation > 0:
        logger.info(f"Waiting {wait_after_automation} seconds to capture additional output...")
        await asyncio.sleep(wait_after_automation)
    else:
        await asyncio.sleep(0.5)

async def _capture_final_output(session_manager: Any, session_id: str) -> str | None:
    """Capture final output with retry logic"""
    MAX_ATTEMPTS = 3
    for attempt in range(MAX_ATTEMPTS):
        try:
            session = await session_manager.get_session(session_id)
            if session:
                return str(await session.get_output())
        except Exception as e:
            if attempt == MAX_ATTEMPTS - 1:
                logger.warning(f"Failed to capture output after {attempt + 1} attempts: {e}")
            else:
                await asyncio.sleep(0.2)
    return None

def _handle_execution_error(error: Exception, full_command: str) -> ExecuteCommandResponse:
    """Handle execution error and create error response"""
    logger.error(f"Error executing command: {error}")
    return ExecuteCommandResponse(
        success=False,
        session_id="",
        command=full_command,
        executed=False,
        automation_patterns_used=0,
        follow_up_commands_executed=0,
        output=None,
        error=str(error),
    )

def _create_success_response(
    session_id: str, full_command: str, automation_patterns_used: int,
    follow_up_commands_executed: int, output: str | None
) -> ExecuteCommandResponse:
    """Create successful execution response"""
    return ExecuteCommandResponse(
        success=True,
        session_id=session_id,
        command=full_command,
        executed=True,
        automation_patterns_used=automation_patterns_used,
        follow_up_commands_executed=follow_up_commands_executed,
        output=output,
    )

async def _safe_get_output(session_manager: Any, session_id: str) -> str | None:
    """Safely get output from session without hanging on interactive processes"""
    try:
        session = await session_manager.get_session(session_id)
        if session:
            # Use the fast output method to avoid hanging on interactive processes
            return str(await session._get_output_fast())
    except Exception as e:
        logger.warning(f"Failed to capture output: {e}")
    return None

def main() -> None:
    """Entry point for the server"""
    mcp.run()


def main_sync() -> None:
    """Synchronous entry point for console scripts"""
    main()


if __name__ == "__main__":
    main_sync()
