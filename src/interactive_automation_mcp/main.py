#!/usr/bin/env python3
"""
Interactive Automation MCP Server - FastMCP Implementation
Provides expect/pexpect-style automation for interactive programs
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
    CreateSessionRequest,
    CreateSessionResponse,
    DestroySessionRequest,
    DestroySessionResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ExpectAndRespondRequest,
    ListSessionsResponse,
    MultiStepAutomationRequest,
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
async def create_interactive_session(
    request: CreateSessionRequest, ctx: Context
) -> CreateSessionResponse:
    """Create a new interactive session for program automation

    Use this tool to start any interactive program that requires user input:
    - Python debugger: 'python -u -m pdb script.py'
    - SSH sessions: 'ssh user@host'
    - Database clients: 'mysql -u root -p', 'psql -h localhost -U user'
    - Interactive installers, configuration tools, or any CLI program

    Returns a session_id that you'll use with other automation tools.
    Sessions automatically timeout after the specified duration.
    """
    logger.info(f"Creating session with command: {request.command}")

    app_ctx = ctx.request_context.lifespan_context

    # Security validation
    if not app_ctx.security_manager.validate_tool_call(
        "create_interactive_session", request.model_dump()
    ):
        raise ValueError("Security violation: Tool call rejected")

    session_id = await app_ctx.session_manager.create_session(
        command=request.command,
        timeout=request.timeout,
        environment=request.environment,
        working_directory=request.working_directory,
    )

    return CreateSessionResponse(
        success=True,
        session_id=session_id,
        command=request.command,
        timeout=request.timeout,
    )


@mcp.tool()
async def list_sessions(ctx: Context) -> ListSessionsResponse:
    """List all active interactive sessions

    Use this tool to:
    - Check which sessions are currently running
    - Get session IDs for use with other tools
    - Monitor session states (ACTIVE, WAITING, ERROR, etc.)
    - See session creation times and last activity

    Essential for managing multiple concurrent automation workflows.
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

    Use this tool to:
    - Clean up finished debugging or automation sessions
    - Force-close unresponsive or stuck sessions
    - Free up session slots (max 50 concurrent sessions)
    - Properly cleanup resources and background processes

    Always destroy sessions when automation is complete.
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
async def expect_and_respond(
    request: ExpectAndRespondRequest, ctx: Context
) -> dict[str, Any]:
    """Wait for a pattern in session output and automatically respond

    Use this tool for single-step automation when you need to:
    - Wait for a specific prompt (e.g., 'Password:', '(Pdb)', '$ ')
    - Send a response when the pattern appears
    - Handle login prompts, debugger commands, or confirmation dialogs

    Examples:
    - Debugger: expect '(Pdb)' respond 'n' (next line)
    - SSH: expect 'Password:' respond 'mypassword'
    - Installer: expect 'Continue? [y/N]' respond 'y'

    For multiple steps, use multi_step_automation instead.
    """
    app_ctx = ctx.request_context.lifespan_context

    session = await app_ctx.session_manager.get_session(request.session_id)
    if not session:
        return {"success": False, "error": "Session not found"}

    result = await session.expect_and_respond(
        pattern=request.expect_pattern,
        response=request.response,
        timeout=request.timeout,
        case_sensitive=request.case_sensitive,
    )

    return result  # type: ignore


@mcp.tool()
async def multi_step_automation(
    request: MultiStepAutomationRequest, ctx: Context
) -> dict[str, Any]:
    """Execute a sequence of expect/respond patterns

    Use this tool for complex automation workflows requiring multiple steps:
    - SSH login followed by command execution
    - Database connection with authentication and queries
    - Debugger sessions with multiple breakpoints and commands
    - Software installation with multiple prompts

    Each step waits for its pattern before sending its response.
    Set 'optional: true' for steps that might not appear.
    Set 'stop_on_failure: false' to continue even if some steps fail.

    Perfect for scripting entire interactive workflows.
    """
    app_ctx = ctx.request_context.lifespan_context

    # Convert Pydantic models to dict format expected by automation engine
    steps = [step.model_dump() for step in request.steps]

    results = await app_ctx.automation_engine.multi_step_automation(
        session_id=request.session_id,
        steps=steps,
        stop_on_failure=request.stop_on_failure,
    )

    return {
        "success": all(r["success"] for r in results if not r.get("optional")),
        "step_results": results,
        "total_steps": len(request.steps),
        "successful_steps": sum(1 for r in results if r["success"]),
    }


# Universal Command Execution Tool
@mcp.tool()
async def execute_command(
    request: ExecuteCommandRequest, ctx: Context
) -> ExecuteCommandResponse:
    """Execute any command with optional automation patterns

    Universal tool for running any command with intelligent automation:
    - Automatically handle prompts with regex patterns
    - Execute follow-up commands after success
    - Set custom environment variables and working directory

    Use cases:
    - Run scripts that prompt for input (automated responses)
    - Execute commands requiring authentication (password prompts)
    - Chain multiple commands with automated intermediate steps
    - Handle interactive installers or configuration tools

    Combines session creation, automation, and cleanup in one tool.
    For long-running debugging sessions, use create_interactive_session instead.
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
        # Create the session
        session_id = await app_ctx.session_manager.create_session(
            command=full_command,
            timeout=request.execution_timeout,
            environment=request.environment,
            working_directory=request.working_directory,
        )

        # Handle automation patterns if provided
        automation_patterns_used = 0
        if request.automation_patterns:
            # Convert automation patterns to automation engine format
            automation_steps = []
            for pattern_config in request.automation_patterns:
                automation_steps.append(
                    {
                        "pattern": pattern_config.pattern,
                        "response": pattern_config.response,
                        "timeout": request.execution_timeout,
                    }
                )

            # Execute automation
            auth_result = await app_ctx.automation_engine.multi_step_automation(
                session_id=session_id, steps=automation_steps, stop_on_failure=True
            )

            automation_patterns_used = len(request.automation_patterns)

            if not auth_result["success"]:
                await app_ctx.session_manager.destroy_session(session_id)
                return ExecuteCommandResponse(
                    success=False,
                    session_id=session_id,
                    command=full_command,
                    executed=False,
                    automation_patterns_used=automation_patterns_used,
                    follow_up_commands_executed=0,
                    error=f"Automation failed: {auth_result.get('error', 'Unknown error')}",
                )

        # Execute follow-up commands if provided
        follow_up_commands_executed = 0
        if request.follow_up_commands:
            try:
                session = await app_ctx.session_manager.get_session(session_id)
                if session:
                    for cmd in request.follow_up_commands:
                        await session.send_input(cmd)
                        # Give time for command execution
                        await asyncio.sleep(0.5)
                        follow_up_commands_executed += 1
            except Exception as e:
                # Don't fail the execution if follow-up commands fail
                logger.warning(f"Follow-up command failed: {e}")

        return ExecuteCommandResponse(
            success=True,
            session_id=session_id,
            command=full_command,
            executed=True,
            automation_patterns_used=automation_patterns_used,
            follow_up_commands_executed=follow_up_commands_executed,
        )

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return ExecuteCommandResponse(
            success=False,
            session_id="",
            command=full_command,
            executed=False,
            automation_patterns_used=0,
            follow_up_commands_executed=0,
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
