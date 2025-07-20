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

    Universal tool for starting ANY interactive program that requires user input.

    Examples:
    - Debuggers: 'python -u -m pdb script.py', 'gdb ./program', 'node inspect app.js'
    - Remote access: 'ssh user@host', 'telnet server', 'kubectl exec -it pod -- bash'
    - Databases: 'mysql -u root -p', 'psql -h host -U user db', 'redis-cli'
    - Development: 'npm run dev', 'docker exec -it container bash', 'make test'
    - System tools: 'top', 'htop', 'vim file.txt', any interactive CLI tool

    Returns a session_id for use with expect_and_respond and multi_step_automation.
    Sessions auto-cleanup after timeout (default: 1 hour, max: 24 hours).

    Pro tip: For one-off commands with simple automation, use execute_command instead.
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
    """List all active interactive sessions with detailed status information

    Shows comprehensive session information:
    - Session IDs and commands for identification
    - Session states (active, waiting, error, terminated)
    - Creation timestamps and last activity times
    - Resource usage and timeout information

    Use this to:
    - Monitor multiple concurrent automation workflows
    - Debug session issues and identify stuck processes
    - Clean up unused sessions before hitting limits (max 50 concurrent)
    - Get session IDs for use with other automation tools
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

    Universal single-step automation for ANY interactive program.

    Pattern matching features:
    - Supports regex patterns (e.g., '\\(Pdb\\)', 'Password.*:', 'Continue\\?.*')
    - Case-sensitive or case-insensitive matching
    - Automatic timeout handling with helpful error messages
    - Enhanced error recovery and debugging information

    Common use cases:
    - Debugger: expect '\\(Pdb\\)' respond 'n' (step to next line)
    - SSH login: expect 'Password:' respond 'secretpass'
    - Database: expect 'mysql>' respond 'SHOW DATABASES;'
    - Installer: expect 'Continue\\? \\[y/N\\]' respond 'y'
    - Shell: expect '\\$ ' respond 'ls -la'

    For complex multi-step workflows, use multi_step_automation instead.
    Returns detailed matching information and session state.
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
    """Execute a sequence of expect/respond patterns for complex automation workflows

    Universal multi-step automation engine for orchestrating complex interactive workflows.

    Advanced features:
    - Automatic error recovery with consecutive failure tracking
    - Optional steps for conditional workflows
    - Case-sensitive/insensitive pattern matching per step
    - Detailed completion statistics and failure analysis
    - Smart timeout handling with helpful suggestions

    Real-world examples:
    - SSH workflow: login → navigate → execute commands → collect results
    - Database admin: connect → authenticate → run queries → backup
    - Debugging session: set breakpoints → step through → inspect variables
    - System deployment: connect → upload → configure → restart services
    - Testing workflow: setup → run tests → collect results → cleanup

    Configuration options:
    - 'optional: true' - Skip failed steps without stopping workflow
    - 'stop_on_failure: false' - Continue workflow even when steps fail
    - 'case_sensitive: true' - Exact pattern matching (default: false)
    - 'timeout: 60' - Custom timeout per step (default: 30 seconds)

    Returns comprehensive results with success rates, failure analysis, and suggestions.
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
    """Execute any command with optional automation patterns and follow-up commands

    The most convenient automation tool - combines session creation, automation, and cleanup.
    Perfect for one-off commands and simple automation workflows.

    Universal command execution:
    - ANY command: 'ssh host', 'python script.py', 'docker run -it image', 'make install'
    - Automatic prompt handling with regex patterns
    - Follow-up command chaining for post-execution tasks
    - Environment variables and working directory control
    - Built-in session lifecycle management (create → automate → cleanup)

    Automation patterns (optional):
    - Pattern: regex to match prompts (e.g., 'Password:', 'Continue.*\\?')
    - Response: text to send when pattern matches
    - Automatic retry logic and error recovery

    Follow-up commands (optional):
    - Execute additional commands after automation completes
    - Perfect for logging, cleanup, or chaining operations
    - Example: ['echo "Task completed"', 'date', 'whoami']

    When to use:
    - Quick automation tasks with simple prompt handling
    - One-off command execution with known prompts
    - Scripts that need automated responses to continue

    When to use create_interactive_session instead:
    - Long-running debugging or interactive sessions
    - Complex workflows requiring multiple tools
    - Sessions you want to manage manually

    Returns detailed execution results, automation statistics, and any errors.
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
                        "expect": pattern_config.pattern,
                        "respond": pattern_config.response,
                        "timeout": request.execution_timeout,
                    }
                )

            # Execute automation
            auth_results = await app_ctx.automation_engine.multi_step_automation(
                session_id=session_id, steps=automation_steps, stop_on_failure=True
            )

            automation_patterns_used = len(request.automation_patterns)

            # Check if any automation step failed
            automation_success = all(result["success"] for result in auth_results)
            if not automation_success:
                await app_ctx.session_manager.destroy_session(session_id)
                failed_steps = [r for r in auth_results if not r["success"]]
                error_msg = f"Automation failed: {failed_steps[0].get('reason', 'Unknown error')}"
                return ExecuteCommandResponse(
                    success=False,
                    session_id=session_id,
                    command=full_command,
                    executed=False,
                    automation_patterns_used=automation_patterns_used,
                    follow_up_commands_executed=0,
                    error=error_msg,
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
