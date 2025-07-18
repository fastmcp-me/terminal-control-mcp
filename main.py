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
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from interactive_automation_mcp.session_manager import SessionManager
from interactive_automation_mcp.automation_engine import AutomationEngine
from interactive_automation_mcp.ssh_automation import SSHAutomation
from interactive_automation_mcp.database_automation import DatabaseAutomation
from interactive_automation_mcp.debugging_automation import DebuggingAutomation
from interactive_automation_mcp.security import SecurityManager

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
        self.ssh_automation = SSHAutomation(self.session_manager, self.automation_engine)
        self.db_automation = DatabaseAutomation(self.session_manager, self.automation_engine)
        self.debug_automation = DebuggingAutomation(self.session_manager, self.automation_engine)
        self.security_manager = SecurityManager()
        
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
                    name="ssh_connect_with_auth",
                    description="Connect to SSH server with automated authentication",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "host": {"type": "string"},
                            "username": {"type": "string"},
                            "auth_method": {"type": "string", "enum": ["password", "key"]},
                            "password": {"type": "string"},
                            "key_path": {"type": "string"},
                            "key_passphrase": {"type": "string"},
                            "port": {"type": "integer", "default": 22},
                            "post_connect_commands": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["host", "username", "auth_method"]
                    }
                ),
                
                types.Tool(
                    name="database_connect_interactive",
                    description="Connect to database with interactive authentication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "db_type": {"type": "string", "enum": ["mysql", "postgresql"]},
                            "host": {"type": "string"},
                            "port": {"type": "integer"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                            "database": {"type": "string"},
                            "initial_commands": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["db_type", "host", "username", "password"]
                    }
                ),
                
                types.Tool(
                    name="gdb_debug_session",
                    description="Start GDB debugging session with intelligent automation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "program": {"type": "string"},
                            "core_file": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}},
                            "breakpoints": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["program"]
                    }
                ),
                
                types.Tool(
                    name="analyze_crash",
                    description="Perform comprehensive crash analysis using GDB",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "analysis_depth": {
                                "type": "string",
                                "enum": ["basic", "comprehensive", "deep"],
                                "default": "comprehensive"
                            }
                        },
                        "required": ["session_id"]
                    }
                ),
                
                types.Tool(
                    name="python_debug_session",
                    description="Start Python debugging session with PDB",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script": {
                                "type": "string",
                                "description": "Path to Python script to debug"
                            },
                            "breakpoints": {
                                "type": "array",
                                "description": "List of breakpoints to set (e.g., ['main.py:10', 'function_name'])",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["script"]
                    }
                ),
                
                # Additional Session Control Tools
                types.Tool(
                    name="send_input",
                    description="Send input to an active session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "input_text": {"type": "string"},
                            "add_newline": {"type": "boolean", "default": True}
                        },
                        "required": ["session_id", "input_text"]
                    }
                ),
                
                types.Tool(
                    name="get_session_output",
                    description="Get output from session buffer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "lines": {"type": "integer", "description": "Number of lines to retrieve (all if not specified)"}
                        },
                        "required": ["session_id"]
                    }
                ),
                
                types.Tool(
                    name="send_signal",
                    description="Send signal to session process (e.g., Ctrl+C)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "signal": {"type": "integer", "description": "Signal number (2=SIGINT/Ctrl+C, 9=SIGKILL, 15=SIGTERM)"}
                        },
                        "required": ["session_id", "signal"]
                    }
                ),
                
                types.Tool(
                    name="clear_session_buffer",
                    description="Clear session output buffer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"}
                        },
                        "required": ["session_id"]
                    }
                ),
                
                types.Tool(
                    name="execute_ssh_commands",
                    description="Execute commands on an established SSH session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "commands": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "timeout": {"type": "integer", "default": 30}
                        },
                        "required": ["session_id", "commands"]
                    }
                ),
                
                types.Tool(
                    name="execute_sql",
                    description="Execute SQL query on established database session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "query": {"type": "string"},
                            "timeout": {"type": "integer", "default": 60}
                        },
                        "required": ["session_id", "query"]
                    }
                )
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
                
                # Route to appropriate handler
                if name == "create_interactive_session":
                    result = await self._handle_create_session(arguments)
                elif name == "list_sessions":
                    result = await self._handle_list_sessions(arguments)
                elif name == "destroy_session":
                    result = await self._handle_destroy_session(arguments)
                elif name == "expect_and_respond":
                    result = await self._handle_expect_and_respond(arguments)
                elif name == "multi_step_automation":
                    result = await self._handle_multi_step_automation(arguments)
                elif name == "ssh_connect_with_auth":
                    result = await self._handle_ssh_connect(arguments)
                elif name == "database_connect_interactive":
                    result = await self._handle_database_connect(arguments)
                elif name == "gdb_debug_session":
                    result = await self._handle_gdb_debug(arguments)
                elif name == "analyze_crash":
                    result = await self._handle_analyze_crash(arguments)
                elif name == "python_debug_session":
                    result = await self._handle_python_debug(arguments)
                elif name == "send_input":
                    result = await self._handle_send_input(arguments)
                elif name == "get_session_output":
                    result = await self._handle_get_session_output(arguments)
                elif name == "send_signal":
                    result = await self._handle_send_signal(arguments)
                elif name == "clear_session_buffer":
                    result = await self._handle_clear_session_buffer(arguments)
                elif name == "execute_ssh_commands":
                    result = await self._handle_execute_ssh_commands(arguments)
                elif name == "execute_sql":
                    result = await self._handle_execute_sql(arguments)
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
    
    async def _handle_ssh_connect(self, args: dict) -> dict:
        """Handle ssh_connect_with_auth tool call"""
        host = args["host"]
        username = args["username"]
        auth_method = args["auth_method"]
        port = args.get("port", 22)
        post_connect_commands = args.get("post_connect_commands", [])
        
        if auth_method == "password":
            password = args.get("password")
            if not password:
                return {"success": False, "error": "Password required for password authentication"}
            
            result = await self.ssh_automation.connect_with_password(
                host=host,
                username=username,
                password=password,
                port=port,
                post_connect_commands=post_connect_commands
            )
        
        elif auth_method == "key":
            key_path = args.get("key_path")
            key_passphrase = args.get("key_passphrase")
            
            if not key_path:
                return {"success": False, "error": "Key path required for key authentication"}
            
            result = await self.ssh_automation.connect_with_key(
                host=host,
                username=username,
                key_path=key_path,
                passphrase=key_passphrase,
                port=port
            )
        
        else:
            return {"success": False, "error": f"Unknown auth method: {auth_method}"}
        
        return result
    
    async def _handle_database_connect(self, args: dict) -> dict:
        """Handle database_connect_interactive tool call"""
        db_type = args["db_type"]
        host = args["host"]
        username = args["username"]
        password = args["password"]
        port = args.get("port")
        database = args.get("database")
        initial_commands = args.get("initial_commands", [])
        
        if db_type == "mysql":
            port = port or 3306
            result = await self.db_automation.mysql_connect(
                host=host,
                username=username,
                password=password,
                database=database,
                port=port
            )
        
        elif db_type == "postgresql":
            port = port or 5432
            result = await self.db_automation.postgresql_connect(
                host=host,
                username=username,
                password=password,
                database=database,
                port=port
            )
        
        else:
            return {"success": False, "error": f"Unsupported database type: {db_type}"}
        
        # Execute initial commands if connection succeeded
        if result["success"] and initial_commands:
            session_id = result["session_id"]
            for command in initial_commands:
                await self.db_automation.execute_sql(session_id, command)
        
        return result
    
    async def _handle_gdb_debug(self, args: dict) -> dict:
        """Handle gdb_debug_session tool call"""
        program = args["program"]
        core_file = args.get("core_file")
        args_list = args.get("args", [])
        breakpoints = args.get("breakpoints", [])
        
        result = await self.debug_automation.gdb_debug_session(
            program=program,
            core_file=core_file,
            args=args_list
        )
        
        # Set breakpoints if session was created successfully
        if result["success"] and breakpoints:
            session_id = result["session_id"]
            session = await self.session_manager.get_session(session_id)
            for bp in breakpoints:
                await session.send_input(f"break {bp}")
                await session.expect_and_respond(r"\(gdb\)", "", timeout=10)
        
        return result
    
    async def _handle_analyze_crash(self, args: dict) -> dict:
        """Handle analyze_crash tool call"""
        session_id = args["session_id"]
        analysis_depth = args.get("analysis_depth", "comprehensive")
        
        result = await self.debug_automation.analyze_crash(session_id)
        
        return result
    
    async def _handle_python_debug(self, args: dict) -> dict:
        """Handle python_debug_session tool call"""
        script = args["script"]
        breakpoints = args.get("breakpoints", [])
        
        result = await self.debug_automation.python_debug_session(
            script=script,
            breakpoints=breakpoints
        )
        
        return result
    
    async def _handle_send_input(self, args: dict) -> dict:
        """Handle send_input tool call"""
        session_id = args["session_id"]
        input_text = args["input_text"]
        add_newline = args.get("add_newline", True)
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        try:
            await session.send_input(input_text, add_newline)
            return {
                "success": True,
                "session_id": session_id,
                "input_sent": input_text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_get_session_output(self, args: dict) -> dict:
        """Handle get_session_output tool call"""
        session_id = args["session_id"]
        lines = args.get("lines")
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        try:
            output = await session.get_output(lines)
            return {
                "success": True,
                "session_id": session_id,
                "output": output,
                "lines_retrieved": lines
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_send_signal(self, args: dict) -> dict:
        """Handle send_signal tool call"""
        session_id = args["session_id"]
        signal = args["signal"]
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        try:
            await session.send_signal(signal)
            return {
                "success": True,
                "session_id": session_id,
                "signal_sent": signal
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_clear_session_buffer(self, args: dict) -> dict:
        """Handle clear_session_buffer tool call"""
        session_id = args["session_id"]
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        try:
            await session.clear_output_buffer()
            return {
                "success": True,
                "session_id": session_id,
                "message": "Buffer cleared"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_execute_ssh_commands(self, args: dict) -> dict:
        """Handle execute_ssh_commands tool call"""
        session_id = args["session_id"]
        commands = args["commands"]
        timeout = args.get("timeout", 30)
        
        try:
            results = await self.ssh_automation.execute_commands(
                session_id=session_id,
                commands=commands,
                timeout=timeout
            )
            return {
                "success": True,
                "session_id": session_id,
                "command_results": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_execute_sql(self, args: dict) -> dict:
        """Handle execute_sql tool call"""
        session_id = args["session_id"]
        query = args["query"]
        timeout = args.get("timeout", 60)
        
        try:
            result = await self.db_automation.execute_sql(
                session_id=session_id,
                sql_query=query,
                timeout=timeout
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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

if __name__ == "__main__":
    asyncio.run(main())