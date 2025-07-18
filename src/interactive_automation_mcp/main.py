#!/usr/bin/env python3
"""
Interactive Automation MCP Server
Provides expect/pexpect-style automation for interactive programs
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Import our components
from .session_manager import SessionManager
from .automation_engine import AutomationEngine
from .security import SecurityManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("interactive-automation-mcp")

class InteractiveAutomationServer:
    """Main MCP server for interactive automation"""
    
    def __init__(self):
        self.server = Server("interactive-automation")
        self.session_manager = SessionManager()
        self.automation_engine = AutomationEngine(self.session_manager)
        self.security_manager = SecurityManager()
        
        # Tool dispatch table for clean routing
        self._tool_handlers = {
            "create_interactive_session": self._handle_create_session,
            "list_sessions": self._handle_list_sessions,
            "destroy_session": self._handle_destroy_session,
            "expect_and_respond": self._handle_expect_and_respond,
            "multi_step_automation": self._handle_multi_step_automation,
            "execute_command": self._handle_execute_command,
        }
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up MCP request handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List all available tools"""
            return [
                # Session Management Tools
                types.Tool(
                    name="create_interactive_session",
                    description="Create a new interactive session for program automation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to execute (e.g., 'ssh user@host', 'mysql -u root -p')"
                            },
                            "session_name": {
                                "type": "string",
                                "description": "Optional human-readable name for the session"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Session timeout in seconds",
                                "default": 3600
                            },
                            "environment": {
                                "type": "object",
                                "description": "Environment variables to set"
                            },
                            "working_directory": {
                                "type": "string",
                                "description": "Working directory for the command"
                            }
                        },
                        "required": ["command"]
                    }
                ),
                
                types.Tool(
                    name="list_sessions",
                    description="List all active interactive sessions",
                    inputSchema={"type": "object", "properties": {}}
                ),
                
                types.Tool(
                    name="destroy_session",
                    description="Terminate and cleanup an interactive session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "ID of the session to destroy"
                            }
                        },
                        "required": ["session_id"]
                    }
                ),
                
                # Automation Tools
                types.Tool(
                    name="expect_and_respond",
                    description="Wait for a pattern in session output and automatically respond",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "expect_pattern": {"type": "string"},
                            "response": {"type": "string"},
                            "timeout": {"type": "integer", "default": 30},
                            "case_sensitive": {"type": "boolean", "default": False}
                        },
                        "required": ["session_id", "expect_pattern", "response"]
                    }
                ),
                
                types.Tool(
                    name="multi_step_automation",
                    description="Execute a sequence of expect/respond patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "steps": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "expect": {"type": "string"},
                                        "respond": {"type": "string"},
                                        "timeout": {"type": "integer", "default": 30},
                                        "optional": {"type": "boolean", "default": False}
                                    },
                                    "required": ["expect", "respond"]
                                }
                            },
                            "stop_on_failure": {"type": "boolean", "default": True}
                        },
                        "required": ["session_id", "steps"]
                    }
                ),
                
                # High-Level Automation Tools
                types.Tool(
                    name="execute_command",
                    description="Execute any command with optional automation patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to execute (e.g., 'ssh user@host', 'mysql -u root -p', 'gdb program')"
                            },
                            "command_args": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional command arguments as separate array items"
                            },
                            "automation_patterns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "pattern": {"type": "string", "description": "Regex pattern to match"},
                                        "response": {"type": "string", "description": "Response to send when pattern matches"},
                                        "secret": {"type": "boolean", "default": false, "description": "Whether response contains sensitive data"}
                                    },
                                    "required": ["pattern", "response"]
                                },
                                "description": "Optional automation patterns to handle (e.g., password prompts, confirmations, any interactive prompts)"
                            },
                            "execution_timeout": {
                                "type": "integer",
                                "default": 30,
                                "description": "Timeout in seconds for command execution"
                            },
                            "follow_up_commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Commands to execute after successful command execution"
                            },
                            "environment": {
                                "type": "object",
                                "description": "Environment variables for the session"
                            },
                            "working_directory": {
                                "type": "string",
                                "description": "Working directory for the command"
                            }
                        },
                        "required": ["command"]
                    }
                ),
                
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            """Handle tool calls"""
            
            logger.info(f"Tool called: {name} with arguments: {arguments}")
            
            try:
                # Security validation
                if not self.security_manager.validate_tool_call(name, arguments):
                    return [types.TextContent(
                        type="text",
                        text=f"Security violation: Tool call rejected"
                    )]
                
                # Route to appropriate handler using dispatch table
                handler = self._tool_handlers.get(name)
                if handler:
                    result = await handler(arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                return [types.TextContent(
                    type="text",
                    text=self._format_result(result)
                )]
                
            except Exception as e:
                logger.error(f"Error in tool {name}: {str(e)}")
                return [types.TextContent(
                    type="text", 
                    text=f"Error executing {name}: {str(e)}"
                )]
    
    async def _handle_create_session(self, args: dict) -> dict:
        """Handle create_interactive_session tool call"""
        command = args["command"]
        timeout = args.get("timeout", 3600)
        environment = args.get("environment")
        working_directory = args.get("working_directory")
        
        session_id = await self.session_manager.create_session(
            command=command,
            timeout=timeout,
            environment=environment,
            working_directory=working_directory
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "command": command,
            "timeout": timeout
        }
    
    async def _handle_list_sessions(self, args: dict) -> dict:
        """Handle list_sessions tool call"""
        sessions = await self.session_manager.list_sessions()
        
        session_list = []
        for session in sessions:
            session_list.append({
                "session_id": session.session_id,
                "command": session.command,
                "state": session.state.value,
                "created_at": session.created_at,
                "last_activity": session.last_activity
            })
        
        return {
            "success": True,
            "sessions": session_list,
            "total_sessions": len(session_list)
        }
    
    async def _handle_destroy_session(self, args: dict) -> dict:
        """Handle destroy_session tool call"""
        session_id = args["session_id"]
        success = await self.session_manager.destroy_session(session_id)
        
        return {
            "success": success,
            "session_id": session_id,
            "message": "Session destroyed" if success else "Session not found"
        }
    
    async def _handle_expect_and_respond(self, args: dict) -> dict:
        """Handle expect_and_respond tool call"""
        session_id = args["session_id"]
        expect_pattern = args["expect_pattern"]
        response = args["response"]
        timeout = args.get("timeout", 30)
        case_sensitive = args.get("case_sensitive", False)
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        result = await session.expect_and_respond(
            pattern=expect_pattern,
            response=response,
            timeout=timeout,
            case_sensitive=case_sensitive
        )
        
        return result
    
    async def _handle_multi_step_automation(self, args: dict) -> dict:
        """Handle multi_step_automation tool call"""
        session_id = args["session_id"]
        steps = args["steps"]
        stop_on_failure = args.get("stop_on_failure", True)
        
        results = await self.automation_engine.multi_step_automation(
            session_id=session_id,
            steps=steps,
            stop_on_failure=stop_on_failure
        )
        
        return {
            "success": all(r["success"] for r in results if not r.get("optional")),
            "step_results": results,
            "total_steps": len(steps),
            "successful_steps": sum(1 for r in results if r["success"])
        }
    
    async def _handle_execute_command(self, args: dict) -> dict:
        """Handle execute_command tool call - truly universal for any command"""
        command = args["command"]
        command_args = args.get("command_args", [])
        automation_patterns = args.get("automation_patterns", args.get("auth_patterns", []))  # Support both names for backward compatibility
        execution_timeout = args.get("execution_timeout", args.get("connection_timeout", 30))  # Support both names
        follow_up_commands = args.get("follow_up_commands", args.get("post_connect_commands", []))  # Support both names
        environment = args.get("environment", {})
        working_directory = args.get("working_directory")
        
        # Build the full command
        full_command = command
        if command_args:
            full_command += " " + " ".join(command_args)
        
        # Create the session
        session_id = await self.session_manager.create_session(
            command=full_command,
            timeout=execution_timeout,
            environment=environment,
            working_directory=working_directory
        )
        
        # Handle automation patterns if provided
        if automation_patterns:
            try:
                # Convert auth patterns to automation engine format
                automation_steps = []
                for pattern_config in automation_patterns:
                    automation_steps.append({
                        "pattern": pattern_config["pattern"],
                        "response": pattern_config["response"],
                        "timeout": execution_timeout
                    })
                
                # Execute authentication automation
                auth_result = await self.automation_engine.multi_step_automation(
                    session_id=session_id,
                    steps=automation_steps,
                    stop_on_failure=True
                )
                
                if not auth_result["success"]:
                    await self.session_manager.destroy_session(session_id)
                    return {
                        "success": False,
                        "error": f"Authentication failed: {auth_result.get('error', 'Unknown error')}"
                    }
                    
            except Exception as e:
                await self.session_manager.destroy_session(session_id)
                return {
                    "success": False,
                    "error": f"Authentication error: {str(e)}"
                }
        
        # Execute follow-up commands if provided
        if follow_up_commands:
            try:
                session = await self.session_manager.get_session(session_id)
                if session:
                    for cmd in follow_up_commands:
                        await session.send_input(cmd)
                        # Give time for command execution
                        await asyncio.sleep(0.5)
            except Exception as e:
                # Don't fail the execution if follow-up commands fail
                pass
        
        return {
            "success": True,
            "session_id": session_id,
            "command": full_command,
            "executed": True,
            "automation_patterns_used": len(automation_patterns),
            "follow_up_commands_executed": len(follow_up_commands)
        }


    
    def _format_result(self, result: dict) -> str:
        """Format result for display"""
        import json
        return json.dumps(result, indent=2, default=str)
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="interactive-automation",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

async def main():
    """Main entry point"""
    server = InteractiveAutomationServer()
    await server.run()

def main_sync():
    """Synchronous entry point for console scripts"""
    asyncio.run(main())

if __name__ == "__main__":
    main_sync()