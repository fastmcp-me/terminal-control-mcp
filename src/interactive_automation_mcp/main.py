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
from .ssh_automation import SSHAutomation
from .database_automation import DatabaseAutomation
from .debugging_automation import DebuggingAutomation
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
                    name="connect_with_auth",
                    description="Connect to any interactive program with automated authentication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "program_type": {
                                "type": "string",
                                "enum": ["ssh", "mysql", "postgresql", "mongodb", "redis", "ftp", "sftp", "telnet", "gdb", "pdb", "lldb", "node", "php", "ruby", "java", "custom"],
                                "description": "Type of program to connect to"
                            },
                            "host": {"type": "string", "description": "Hostname or IP address"},
                            "port": {"type": "integer", "description": "Port number (optional, uses default for program type)"},
                            "username": {"type": "string", "description": "Username for authentication"},
                            "password": {"type": "string", "description": "Password for authentication"},
                            "auth_method": {
                                "type": "string",
                                "enum": ["password", "key", "certificate", "token"],
                                "default": "password",
                                "description": "Authentication method"
                            },
                            "key_path": {"type": "string", "description": "Path to private key file (for key auth)"},
                            "key_passphrase": {"type": "string", "description": "Passphrase for private key"},
                            "database": {"type": "string", "description": "Database name (for database connections)"},
                            "connection_options": {
                                "type": "object",
                                "description": "Additional connection options as key-value pairs"
                            },
                            "post_connect_commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Commands to execute after successful connection"
                            },
                            "custom_command": {
                                "type": "string",
                                "description": "Custom command to execute (for program_type=custom)"
                            },
                            "target": {
                                "type": "string",
                                "description": "Target to debug (for debugger program types) - program path, script path, etc."
                            },
                            "target_type": {
                                "type": "string",
                                "enum": ["program", "script", "core", "process", "attach"],
                                "default": "program",
                                "description": "Type of target being debugged (for debugger program types)"
                            },
                            "core_file": {
                                "type": "string",
                                "description": "Core dump file path (for core debugging)"
                            },
                            "process_id": {
                                "type": "integer",
                                "description": "Process ID to attach to (for process debugging)"
                            },
                            "args": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Arguments to pass to the target program"
                            },
                            "breakpoints": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Initial breakpoints to set (for debugger program types)"
                            },
                            "environment": {
                                "type": "object",
                                "description": "Environment variables for the session"
                            }
                        },
                        "required": ["program_type", "host", "username"]
                    }
                ),
                
                types.Tool(
                    name="analyze_session",
                    description="Perform comprehensive analysis of any interactive session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "analysis_type": {
                                "type": "string",
                                "enum": ["crash", "performance", "security", "debug", "log", "custom"],
                                "default": "crash",
                                "description": "Type of analysis to perform"
                            },
                            "analysis_depth": {
                                "type": "string",
                                "enum": ["basic", "comprehensive", "deep"],
                                "default": "comprehensive",
                                "description": "Depth of analysis to perform"
                            },
                            "custom_analysis": {
                                "type": "string",
                                "description": "Custom analysis commands (for analysis_type=custom)"
                            }
                        },
                        "required": ["session_id"]
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
                elif name == "connect_with_auth":
                    result = await self._handle_connect_with_auth(arguments)
                elif name == "analyze_session":
                    result = await self._handle_analyze_session(arguments)
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
    
    async def _handle_connect_with_auth(self, args: dict) -> dict:
        """Handle connect_with_auth tool call - supports multiple program types"""
        program_type = args["program_type"]
        host = args["host"]
        username = args["username"]
        auth_method = args.get("auth_method", "password")
        port = args.get("port")
        post_connect_commands = args.get("post_connect_commands", [])
        
        # Set default ports based on program type
        if port is None:
            port_defaults = {
                "ssh": 22,
                "mysql": 3306,
                "postgresql": 5432,
                "mongodb": 27017,
                "redis": 6379,
                "ftp": 21,
                "sftp": 22,
                "telnet": 23
            }
            port = port_defaults.get(program_type, 22)
        
        # Handle different program types
        if program_type == "ssh":
            return await self._handle_ssh_connection(args, host, username, auth_method, port, post_connect_commands)
        elif program_type in ["mysql", "postgresql"]:
            return await self._handle_database_connection(args, program_type, host, username, port, post_connect_commands)
        elif program_type in ["gdb", "pdb", "lldb", "node", "php", "ruby", "java"]:
            return await self._handle_debugger_connection(args, program_type, post_connect_commands)
        elif program_type == "custom":
            return await self._handle_custom_connection(args)
        else:
            # Generic connection handling for other program types
            return await self._handle_generic_connection(args, program_type, host, username, auth_method, port, post_connect_commands)

    async def _handle_ssh_connection(self, args: dict, host: str, username: str, auth_method: str, port: int, post_connect_commands: list) -> dict:
        """Handle SSH connections"""
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
            return {"success": False, "error": f"Unsupported auth method: {auth_method}"}
        
        return result

    async def _handle_database_connection(self, args: dict, db_type: str, host: str, username: str, port: int, post_connect_commands: list) -> dict:
        """Handle database connections"""
        password = args.get("password")
        database = args.get("database")
        
        if not password:
            return {"success": False, "error": "Password required for database authentication"}
        
        result = await self.database_automation.connect_interactive(
            db_type=db_type,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            initial_commands=post_connect_commands
        )
        return result

    async def _handle_generic_connection(self, args: dict, program_type: str, host: str, username: str, auth_method: str, port: int, post_connect_commands: list) -> dict:
        """Handle generic program connections"""
        password = args.get("password")
        
        # Build connection command based on program type
        if program_type == "ftp":
            command = f"ftp -p {host} {port}"
        elif program_type == "sftp":
            command = f"sftp -P {port} {username}@{host}"
        elif program_type == "telnet":
            command = f"telnet {host} {port}"
        elif program_type == "redis":
            command = f"redis-cli -h {host} -p {port}"
        elif program_type == "mongodb":
            command = f"mongosh mongodb://{username}:{password}@{host}:{port}"
        else:
            return {"success": False, "error": f"Unsupported program type: {program_type}"}
        
        # Create session and handle authentication
        session_id = await self.session_manager.create_session(command)
        
        # Basic authentication handling for common prompts
        auth_patterns = []
        if password:
            auth_patterns.extend([
                {"pattern": r"[Pp]assword:", "response": password},
                {"pattern": r"Password for", "response": password},
                {"pattern": r"Enter password:", "response": password}
            ])
        
        if auth_patterns:
            result = await self.automation_engine.multi_step_automation(
                session_id=session_id,
                steps=auth_patterns,
                stop_on_failure=True
            )
            
            if not result["success"]:
                await self.session_manager.destroy_session(session_id)
                return {"success": False, "error": "Authentication failed"}
        
        # Execute post-connect commands
        if post_connect_commands:
            for command in post_connect_commands:
                session = await self.session_manager.get_session(session_id)
                if session:
                    await session.send_input(command)
        
        return {
            "success": True,
            "session_id": session_id,
            "program_type": program_type,
            "connected": True
        }

    async def _handle_custom_connection(self, args: dict) -> dict:
        """Handle custom program connections"""
        custom_command = args.get("custom_command")
        if not custom_command:
            return {"success": False, "error": "custom_command required for custom program type"}
        
        session_id = await self.session_manager.create_session(custom_command)
        
        # Handle authentication if specified
        password = args.get("password")
        if password:
            auth_patterns = [
                {"pattern": r"[Pp]assword:", "response": password},
                {"pattern": r"Password for", "response": password},
                {"pattern": r"Enter password:", "response": password}
            ]
            
            result = await self.automation_engine.multi_step_automation(
                session_id=session_id,
                steps=auth_patterns,
                stop_on_failure=True
            )
            
            if not result["success"]:
                await self.session_manager.destroy_session(session_id)
                return {"success": False, "error": "Authentication failed"}
        
        return {
            "success": True,
            "session_id": session_id,
            "program_type": "custom",
            "connected": True
        }

    async def _handle_debugger_connection(self, args: dict, program_type: str, post_connect_commands: list) -> dict:
        """Handle debugger connections"""
        target = args.get("target")
        if not target:
            return {"success": False, "error": "target required for debugger connections"}
        
        target_type = args.get("target_type", "program")
        core_file = args.get("core_file")
        process_id = args.get("process_id")
        args_list = args.get("args", [])
        breakpoints = args.get("breakpoints", [])
        environment = args.get("environment", {})
        
        # Build debugger command based on program type and target type
        if program_type == "gdb":
            if target_type == "core" and core_file:
                command = f"gdb {target} {core_file}"
            elif target_type == "process" and process_id:
                command = f"gdb -p {process_id}"
            else:
                command = f"gdb {target}"
                if args_list:
                    command += f" --args {' '.join(args_list)}"
        
        elif program_type == "pdb":
            command = f"python -m pdb {target}"
            if args_list:
                command += f" {' '.join(args_list)}"
        
        elif program_type == "lldb":
            if target_type == "core" and core_file:
                command = f"lldb -c {core_file} {target}"
            elif target_type == "process" and process_id:
                command = f"lldb -p {process_id}"
            else:
                command = f"lldb {target}"
                if args_list:
                    command += f" -- {' '.join(args_list)}"
        
        elif program_type == "node":
            command = f"node --inspect-brk {target}"
            if args_list:
                command += f" {' '.join(args_list)}"
        
        elif program_type == "php":
            command = f"php -d xdebug.remote_enable=1 {target}"
            if args_list:
                command += f" {' '.join(args_list)}"
        
        elif program_type == "ruby":
            command = f"ruby -rdebug {target}"
            if args_list:
                command += f" {' '.join(args_list)}"
        
        elif program_type == "java":
            command = f"jdb -sourcepath . {target}"
            if args_list:
                command += f" {' '.join(args_list)}"
        
        else:
            return {"success": False, "error": f"Unsupported debugger type: {program_type}"}
        
        # Create debugging session
        session_id = await self.session_manager.create_session(command, environment=environment)
        
        # Wait for debugger prompt and set breakpoints
        if program_type == "gdb":
            # Wait for GDB prompt
            session = await self.session_manager.get_session(session_id)
            if session:
                await session.expect_and_respond(r"\\(gdb\\)", "", timeout=30)
                
                # Set breakpoints
                for bp in breakpoints:
                    await session.send_input(f"b {bp}")
                    await session.expect_and_respond(r"\\(gdb\\)", "", timeout=10)
        
        elif program_type == "pdb":
            # Wait for PDB prompt
            session = await self.session_manager.get_session(session_id)
            if session:
                await session.expect_and_respond(r"\\(Pdb\\)", "", timeout=30)
                
                # Set breakpoints
                for bp in breakpoints:
                    await session.send_input(f"b {bp}")
                    await session.expect_and_respond(r"\\(Pdb\\)", "", timeout=10)
        
        # Execute post-connect commands
        if post_connect_commands:
            session = await self.session_manager.get_session(session_id)
            if session:
                for command in post_connect_commands:
                    await session.send_input(command)
        
        return {
            "success": True,
            "session_id": session_id,
            "program_type": program_type,
            "target": target,
            "target_type": target_type,
            "connected": True
        }
    
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
    
    async def _handle_analyze_session(self, args: dict) -> dict:
        """Handle analyze_session tool call - universal analysis"""
        session_id = args["session_id"]
        analysis_type = args.get("analysis_type", "crash")
        analysis_depth = args.get("analysis_depth", "comprehensive")
        custom_analysis = args.get("custom_analysis")
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        # Determine analysis approach based on session type and analysis type
        if analysis_type == "crash":
            return await self._handle_crash_analysis(session_id, analysis_depth)
        elif analysis_type == "performance":
            return await self._handle_performance_analysis(session_id, analysis_depth)
        elif analysis_type == "security":
            return await self._handle_security_analysis(session_id, analysis_depth)
        elif analysis_type == "debug":
            return await self._handle_debug_analysis(session_id, analysis_depth)
        elif analysis_type == "log":
            return await self._handle_log_analysis(session_id, analysis_depth)
        elif analysis_type == "custom":
            return await self._handle_custom_analysis(session_id, custom_analysis)
        else:
            return {"success": False, "error": f"Unsupported analysis type: {analysis_type}"}

    async def _handle_crash_analysis(self, session_id: str, analysis_depth: str) -> dict:
        """Handle crash analysis (previously analyze_crash)"""
        # Use the existing debugging automation for crash analysis
        result = await self.debugging_automation.analyze_crash(session_id)
        return result

    async def _handle_performance_analysis(self, session_id: str, analysis_depth: str) -> dict:
        """Handle performance analysis"""
        # Generic performance analysis
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        # Send performance analysis commands
        perf_commands = [
            "info proc",
            "info threads",
            "thread apply all bt",
            "info memory"
        ]
        
        results = {}
        for cmd in perf_commands:
            await session.send_input(cmd)
            # Wait for response (this is simplified - real implementation would be more sophisticated)
            await asyncio.sleep(1)
            results[cmd] = "Performance data collected"
        
        return {
            "success": True,
            "analysis_type": "performance",
            "results": results
        }

    async def _handle_security_analysis(self, session_id: str, analysis_depth: str) -> dict:
        """Handle security analysis"""
        return {
            "success": True,
            "analysis_type": "security",
            "message": "Security analysis not yet implemented",
            "suggestions": ["Check for buffer overflows", "Verify input validation", "Review privilege escalation"]
        }

    async def _handle_debug_analysis(self, session_id: str, analysis_depth: str) -> dict:
        """Handle debug analysis"""
        return {
            "success": True,
            "analysis_type": "debug",
            "message": "Debug analysis not yet implemented",
            "suggestions": ["Check variable states", "Review call stack", "Examine memory"]
        }

    async def _handle_log_analysis(self, session_id: str, analysis_depth: str) -> dict:
        """Handle log analysis"""
        return {
            "success": True,
            "analysis_type": "log",
            "message": "Log analysis not yet implemented",
            "suggestions": ["Parse error messages", "Identify patterns", "Extract timestamps"]
        }

    async def _handle_custom_analysis(self, session_id: str, custom_analysis: str) -> dict:
        """Handle custom analysis"""
        if not custom_analysis:
            return {"success": False, "error": "custom_analysis required for custom analysis type"}
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        # Execute custom analysis commands
        await session.send_input(custom_analysis)
        
        return {
            "success": True,
            "analysis_type": "custom",
            "command": custom_analysis,
            "message": "Custom analysis executed"
        }

    async def _handle_gdb_debug_session(self, args: dict, target: str, target_type: str) -> dict:
        """Handle GDB debugging sessions"""
        core_file = args.get("core_file")
        process_id = args.get("process_id")
        args_list = args.get("args", [])
        breakpoints = args.get("breakpoints", [])
        
        if target_type == "core" and core_file:
            result = await self.debugging_automation.gdb_debug_session(
                program=target,
                core_file=core_file,
                args=args_list
            )
        elif target_type == "process" and process_id:
            # Attach to process
            command = f"gdb -p {process_id}"
            session_id = await self.session_manager.create_session(command)
            result = {"success": True, "session_id": session_id, "debugger_type": "gdb"}
        else:
            # Regular program debugging
            result = await self.debugging_automation.gdb_debug_session(
                program=target,
                args=args_list
            )
        
        # Set breakpoints if debugging session started successfully
        if result["success"] and breakpoints:
            session_id = result["session_id"]
            for bp in breakpoints:
                session = await self.session_manager.get_session(session_id)
                if session:
                    await session.send_input(f"b {bp}")
        
        return result

    async def _handle_pdb_debug_session(self, args: dict, target: str, target_type: str) -> dict:
        """Handle Python PDB debugging sessions"""
        breakpoints = args.get("breakpoints", [])
        
        result = await self.debugging_automation.python_debug_session(
            script=target,
            breakpoints=breakpoints
        )
        return result

    async def _handle_lldb_debug_session(self, args: dict, target: str, target_type: str) -> dict:
        """Handle LLDB debugging sessions"""
        core_file = args.get("core_file")
        process_id = args.get("process_id")
        args_list = args.get("args", [])
        breakpoints = args.get("breakpoints", [])
        
        if target_type == "core" and core_file:
            command = f"lldb -c {core_file} {target}"
        elif target_type == "process" and process_id:
            command = f"lldb -p {process_id}"
        else:
            command = f"lldb {target}"
            if args_list:
                command += f" -- {' '.join(args_list)}"
        
        session_id = await self.session_manager.create_session(command)
        
        # Set breakpoints
        if breakpoints:
            for bp in breakpoints:
                session = await self.session_manager.get_session(session_id)
                if session:
                    await session.send_input(f"b {bp}")
        
        return {"success": True, "session_id": session_id, "debugger_type": "lldb"}

    async def _handle_generic_debug_session(self, args: dict, debugger_type: str, target: str, target_type: str) -> dict:
        """Handle generic debugger sessions"""
        args_list = args.get("args", [])
        environment = args.get("environment", {})
        
        # Build command based on debugger type
        if debugger_type == "node":
            command = f"node --inspect-brk {target}"
        elif debugger_type == "php":
            command = f"php -d xdebug.remote_enable=1 {target}"
        elif debugger_type == "ruby":
            command = f"ruby -rdebug {target}"
        elif debugger_type == "java":
            command = f"jdb -sourcepath . {target}"
        else:
            return {"success": False, "error": f"Unsupported debugger type: {debugger_type}"}
        
        if args_list:
            command += f" {' '.join(args_list)}"
        
        session_id = await self.session_manager.create_session(command, environment=environment)
        
        return {"success": True, "session_id": session_id, "debugger_type": debugger_type}

    async def _handle_custom_debug_session(self, args: dict) -> dict:
        """Handle custom debugger sessions"""
        custom_command = args.get("custom_command")
        if not custom_command:
            return {"success": False, "error": "custom_command required for custom debugger type"}
        
        environment = args.get("environment", {})
        session_id = await self.session_manager.create_session(custom_command, environment=environment)
        
        return {"success": True, "session_id": session_id, "debugger_type": "custom"}
    
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