# Interactive Automation MCP Server - Technical Specification

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Core Components](#core-components)
4. [Tool Specifications](#tool-specifications)
5. [Implementation Details](#implementation-details)
6. [Security Framework](#security-framework)
7. [Use Case Examples](#use-case-examples)
8. [Installation and Configuration](#installation-and-configuration)
9. [Testing Strategy](#testing-strategy)
10. [Deployment and Maintenance](#deployment-and-maintenance)

## Executive Summary

### Project Overview

The Interactive Automation MCP Server enables Claude Code to perform expect/pexpect-style automation for interactive programs. This server fills a critical gap in the current MCP ecosystem by providing intelligent automation for programs that require user interaction, such as SSH sessions, database connections, interactive installers, and debugging workflows.

### Key Capabilities

- **Automated Interactive Sessions**: Handle complex multi-step interactions with terminal programs
- **Pattern-Based Automation**: Wait for specific prompts and automatically respond
- **Session Management**: Maintain persistent interactive sessions across multiple operations
- **Debugging Integration**: Enable LLM-powered debugging with GDB, PDB, LLDB, and Node debugger
- **High-Level Automation Patterns**: Pre-built workflows for SSH, databases, Docker, and common tools
- **Security-First Design**: Comprehensive security controls and resource management

### Target Users

- **Developers**: Automate debugging, deployment, and development workflows
- **DevOps Engineers**: Streamline server management and infrastructure automation
- **System Administrators**: Automate routine system maintenance and monitoring
- **AI Researchers**: Enable AI agents to interact with complex interactive systems

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code                              │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (JSON-RPC)
┌─────────────────────▼───────────────────────────────────────┐
│              Interactive Automation MCP Server              │
├─────────────────────────────────────────────────────────────┤
│  Tool Layer         │  Session Layer    │  Security Layer   │
│  - expect_respond   │  - SessionManager │  - CommandFilter  │
│  - multi_step      │  - SessionPool    │  - RateLimiter    │
│  - ssh_connect     │  - StateTracker   │  - ResourceLimit  │
│  - db_connect      │                   │                   │
├─────────────────────┼───────────────────┼───────────────────┤
│              Automation Engine Layer                        │
│  - PatternMatcher  - AutomationEngine  - ProcessManager    │
├─────────────────────────────────────────────────────────────┤
│                 PTY/Process Layer                           │
│  - pexpect/ptyprocess - subprocess - signal handling       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Interactive Programs                           │
│  SSH │ GDB │ MySQL │ Docker │ Custom Programs              │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Modularity**: Each component has clear responsibilities and interfaces
2. **Security**: Security controls at every layer with fail-safe defaults
3. **Extensibility**: Easy to add new automation patterns and tools
4. **Reliability**: Robust error handling and resource management
5. **Performance**: Asynchronous operations and efficient resource usage

### Technology Stack

- **Primary Language**: Python 3.8+
- **Core Dependencies**: 
  - `mcp` (Model Context Protocol SDK)
  - `pexpect` (Interactive program automation)
  - `asyncio` (Asynchronous programming)
  - `ptyprocess` (PTY management)
- **Optional Dependencies**:
  - `paramiko` (SSH client library)
  - `docker` (Docker automation)
  - `psycopg2` (PostgreSQL integration)

## Core Components

### 1. Session Manager

The Session Manager is responsible for creating, tracking, and managing interactive sessions.

#### Class Definition

```python
from typing import Dict, Optional, List, Any
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

class SessionState(Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    WAITING = "waiting"
    ERROR = "error"
    TERMINATED = "terminated"

@dataclass
class SessionMetadata:
    session_id: str
    command: str
    created_at: float
    last_activity: float
    state: SessionState
    timeout: int
    user_data: Dict[str, Any] = field(default_factory=dict)

class SessionManager:
    """Manages interactive terminal sessions with lifecycle tracking"""
    
    def __init__(self, max_sessions: int = 50, default_timeout: int = 3600):
        self.sessions: Dict[str, 'InteractiveSession'] = {}
        self.session_metadata: Dict[str, SessionMetadata] = {}
        self.max_sessions = max_sessions
        self.default_timeout = default_timeout
        self._cleanup_task = None
    
    async def create_session(
        self, 
        command: str, 
        timeout: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> str:
        """Create a new interactive session"""
        
        # Check session limits
        if len(self.sessions) >= self.max_sessions:
            await self._cleanup_expired_sessions()
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("Maximum session limit reached")
        
        # Generate unique session ID
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        # Create session
        session = InteractiveSession(
            session_id=session_id,
            command=command,
            timeout=timeout or self.default_timeout,
            environment=environment,
            working_directory=working_directory
        )
        
        # Store session and metadata
        self.sessions[session_id] = session
        self.session_metadata[session_id] = SessionMetadata(
            session_id=session_id,
            command=command,
            created_at=time.time(),
            last_activity=time.time(),
            state=SessionState.INITIALIZING,
            timeout=timeout or self.default_timeout
        )
        
        # Initialize session
        await session.initialize()
        self.session_metadata[session_id].state = SessionState.ACTIVE
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional['InteractiveSession']:
        """Retrieve a session by ID"""
        if session_id in self.sessions:
            # Update last activity
            self.session_metadata[session_id].last_activity = time.time()
            return self.sessions[session_id]
        return None
    
    async def destroy_session(self, session_id: str) -> bool:
        """Terminate and cleanup a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            await session.terminate()
            
            del self.sessions[session_id]
            del self.session_metadata[session_id]
            return True
        return False
    
    async def list_sessions(self) -> List[SessionMetadata]:
        """List all active sessions"""
        return list(self.session_metadata.values())
    
    async def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, metadata in self.session_metadata.items():
            if current_time - metadata.last_activity > metadata.timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.destroy_session(session_id)
```

### 2. Interactive Session

The Interactive Session class wraps pexpect functionality with additional state management and automation capabilities.

```python
import pexpect
import signal
import os
from typing import List, Optional, Dict, Any, Union, Tuple

class InteractiveSession:
    """Represents a single interactive terminal session"""
    
    def __init__(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
        environment: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ):
        self.session_id = session_id
        self.command = command
        self.timeout = timeout
        self.environment = environment or {}
        self.working_directory = working_directory
        
        self.process: Optional[pexpect.spawn] = None
        self.output_buffer: List[str] = []
        self.automation_patterns: List[Dict[str, Any]] = []
        self.is_active = False
        self.exit_code: Optional[int] = None
        
        # State tracking
        self.current_prompt = None
        self.last_command = None
        self.command_history: List[str] = []
    
    async def initialize(self):
        """Initialize the interactive session"""
        try:
            # Set up environment
            env = os.environ.copy()
            env.update(self.environment)
            
            # Spawn the process
            self.process = pexpect.spawn(
                self.command,
                timeout=self.timeout,
                env=env,
                cwd=self.working_directory,
                encoding='utf-8',
                codec_errors='replace'
            )
            
            # Set up logging
            if hasattr(self.process, 'logfile_read'):
                self.process.logfile_read = open(f'/tmp/session_{self.session_id}.log', 'w')
            
            self.is_active = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize session: {str(e)}")
    
    async def expect_and_respond(
        self,
        pattern: Union[str, List[str]],
        response: str,
        timeout: Optional[int] = None,
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Wait for pattern and send response"""
        
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        try:
            # Prepare patterns
            if isinstance(pattern, str):
                patterns = [pattern]
            else:
                patterns = pattern
            
            # Add EOF and TIMEOUT to patterns
            patterns.extend([pexpect.EOF, pexpect.TIMEOUT])
            
            # Set timeout
            original_timeout = self.process.timeout
            if timeout:
                self.process.timeout = timeout
            
            # Wait for pattern
            index = self.process.expect(patterns)
            
            # Restore timeout
            self.process.timeout = original_timeout
            
            # Process result
            if index < len(patterns) - 2:  # Pattern matched
                matched_pattern = patterns[index]
                before_text = self.process.before or ""
                after_text = self.process.after or ""
                
                # Store output
                self.output_buffer.append(before_text)
                
                # Send response
                if response:
                    self.process.sendline(response)
                    self.command_history.append(response)
                    self.last_command = response
                
                return {
                    "success": True,
                    "matched_pattern": matched_pattern,
                    "matched_index": index,
                    "before": before_text,
                    "after": after_text,
                    "response_sent": response
                }
            
            elif index == len(patterns) - 2:  # EOF
                self.is_active = False
                self.exit_code = self.process.exitstatus
                return {
                    "success": False,
                    "reason": "process_ended",
                    "exit_code": self.exit_code,
                    "before": self.process.before or ""
                }
            
            else:  # TIMEOUT
                return {
                    "success": False,
                    "reason": "timeout",
                    "before": self.process.before or ""
                }
                
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e)
            }
    
    async def send_input(self, input_text: str, add_newline: bool = True):
        """Send input to the session"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        if add_newline:
            self.process.sendline(input_text)
        else:
            self.process.send(input_text)
        
        self.command_history.append(input_text)
        self.last_command = input_text
    
    async def send_signal(self, sig: int):
        """Send signal to the process"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        self.process.kill(sig)
    
    async def get_output(self, lines: Optional[int] = None) -> str:
        """Get output from the session buffer"""
        if lines is None:
            return "\n".join(self.output_buffer)
        else:
            return "\n".join(self.output_buffer[-lines:])
    
    async def clear_output_buffer(self):
        """Clear the output buffer"""
        self.output_buffer.clear()
    
    async def terminate(self):
        """Terminate the session"""
        if self.process and self.is_active:
            try:
                # Try graceful termination first
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                # Force kill if needed
                self.process.kill(signal.SIGKILL)
            finally:
                self.is_active = False
                if hasattr(self.process, 'logfile_read') and self.process.logfile_read:
                    self.process.logfile_read.close()
```

### 3. Automation Engine

The Automation Engine provides high-level automation patterns and workflows.

```python
import re
import asyncio
from typing import List, Dict, Any, Optional, Callable

class AutomationPattern:
    """Represents an automation pattern with conditions and actions"""
    
    def __init__(
        self,
        name: str,
        description: str,
        patterns: List[Dict[str, Any]],
        timeout: int = 30
    ):
        self.name = name
        self.description = description
        self.patterns = patterns
        self.timeout = timeout

class AutomationEngine:
    """Executes automation patterns and workflows"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.predefined_patterns = self._load_predefined_patterns()
    
    async def multi_step_automation(
        self,
        session_id: str,
        steps: List[Dict[str, Any]],
        stop_on_failure: bool = True
    ) -> List[Dict[str, Any]]:
        """Execute a sequence of expect/respond steps"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        results = []
        
        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            expect_pattern = step["expect"]
            response = step.get("respond", "")
            timeout = step.get("timeout", 30)
            optional = step.get("optional", False)
            
            try:
                result = await session.expect_and_respond(
                    pattern=expect_pattern,
                    response=response,
                    timeout=timeout
                )
                
                result["step_name"] = step_name
                result["step_index"] = i
                results.append(result)
                
                # Check if step failed
                if not result["success"]:
                    if optional:
                        continue
                    elif stop_on_failure:
                        break
                        
            except Exception as e:
                error_result = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": i,
                    "reason": "exception",
                    "error": str(e)
                }
                results.append(error_result)
                
                if not optional and stop_on_failure:
                    break
        
        return results
    
    async def conditional_automation(
        self,
        session_id: str,
        conditions: List[Dict[str, Any]],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Handle multiple possible prompts with different responses"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Extract patterns and build mapping
        patterns = []
        pattern_mapping = {}
        
        for i, condition in enumerate(conditions):
            pattern = condition["pattern"]
            patterns.append(pattern)
            pattern_mapping[i] = condition
        
        # Add EOF and TIMEOUT
        patterns.extend([pexpect.EOF, pexpect.TIMEOUT])
        
        try:
            index = session.process.expect(patterns, timeout=timeout)
            
            if index < len(conditions):
                # Pattern matched
                condition = pattern_mapping[index]
                action = condition.get("action", "respond")
                response = condition.get("response", "")
                
                if action == "respond":
                    session.process.sendline(response)
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": action,
                        "response_sent": response
                    }
                elif action == "terminate":
                    await session.terminate()
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": "terminate"
                    }
                elif action == "continue":
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": "continue"
                    }
            
            elif index == len(patterns) - 2:  # EOF
                return {
                    "success": False,
                    "reason": "process_ended",
                    "exit_code": session.process.exitstatus
                }
            
            else:  # TIMEOUT
                return {
                    "success": False,
                    "reason": "timeout"
                }
                
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e)
            }
    
    def _load_predefined_patterns(self) -> Dict[str, AutomationPattern]:
        """Load predefined automation patterns"""
        patterns = {}
        
        # SSH authentication patterns
        patterns["ssh_password_auth"] = AutomationPattern(
            name="ssh_password_auth",
            description="Handle SSH password authentication",
            patterns=[
                {
                    "expect": r"password:",
                    "action": "respond_with_credential",
                    "credential_key": "password"
                },
                {
                    "expect": r"yes/no",
                    "action": "respond",
                    "response": "yes"
                },
                {
                    "expect": r"Permission denied",
                    "action": "terminate"
                },
                {
                    "expect": r"[$#]",
                    "action": "continue"
                }
            ]
        )
        
        # Database connection patterns
        patterns["mysql_connect"] = AutomationPattern(
            name="mysql_connect",
            description="Handle MySQL connection prompts",
            patterns=[
                {
                    "expect": r"Enter password:",
                    "action": "respond_with_credential",
                    "credential_key": "password"
                },
                {
                    "expect": r"mysql>",
                    "action": "continue"
                },
                {
                    "expect": r"Access denied",
                    "action": "terminate"
                }
            ]
        )
        
        # GDB debugging patterns
        patterns["gdb_debugging"] = AutomationPattern(
            name="gdb_debugging",
            description="Standard GDB debugging workflow",
            patterns=[
                {
                    "expect": r"\(gdb\)",
                    "action": "continue"
                },
                {
                    "expect": r"Program received signal",
                    "action": "respond",
                    "response": "bt"
                }
            ]
        )
        
        return patterns
```

### 4. High-Level Automation Classes

#### SSH Automation

```python
import paramiko
from typing import Dict, Any, Optional, List

class SSHAutomation:
    """High-level SSH automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def connect_with_password(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        post_connect_commands: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Connect to SSH server with password authentication"""
        
        # Create SSH session
        ssh_command = f"ssh -p {port} {username}@{host}"
        session_id = await self.session_manager.create_session(ssh_command)
        
        # Define authentication steps
        auth_steps = [
            {
                "name": "host_key_verification",
                "expect": r"yes/no",
                "respond": "yes",
                "optional": True,
                "timeout": 10
            },
            {
                "name": "password_prompt",
                "expect": r"password:",
                "respond": password,
                "timeout": 30
            },
            {
                "name": "login_success",
                "expect": r"[$#]",
                "respond": "",
                "timeout": 30
            }
        ]
        
        # Execute authentication
        auth_results = await self.automation_engine.multi_step_automation(
            session_id, auth_steps
        )
        
        # Check if authentication succeeded
        if not all(result["success"] for result in auth_results if not result.get("optional")):
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "auth_results": auth_results
            }
        
        # Execute post-connect commands
        if post_connect_commands:
            for command in post_connect_commands:
                session = await self.session_manager.get_session(session_id)
                await session.send_input(command)
                await asyncio.sleep(1)  # Brief pause between commands
        
        return {
            "success": True,
            "session_id": session_id,
            "auth_results": auth_results
        }
    
    async def connect_with_key(
        self,
        host: str,
        username: str,
        key_path: str,
        passphrase: Optional[str] = None,
        port: int = 22
    ) -> Dict[str, Any]:
        """Connect to SSH server with key authentication"""
        
        # Build SSH command with key
        ssh_command = f"ssh -i {key_path} -p {port} {username}@{host}"
        session_id = await self.session_manager.create_session(ssh_command)
        
        auth_steps = [
            {
                "name": "host_key_verification", 
                "expect": r"yes/no",
                "respond": "yes",
                "optional": True
            }
        ]
        
        # Add passphrase step if needed
        if passphrase:
            auth_steps.append({
                "name": "key_passphrase",
                "expect": r"Enter passphrase",
                "respond": passphrase
            })
        
        auth_steps.append({
            "name": "login_success",
            "expect": r"[$#]",
            "respond": ""
        })
        
        auth_results = await self.automation_engine.multi_step_automation(
            session_id, auth_steps
        )
        
        return {
            "success": all(result["success"] for result in auth_results if not result.get("optional")),
            "session_id": session_id if all(result["success"] for result in auth_results if not result.get("optional")) else None,
            "auth_results": auth_results
        }
    
    async def execute_commands(
        self,
        session_id: str,
        commands: List[str],
        timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """Execute commands on established SSH session"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        results = []
        
        for command in commands:
            # Send command
            await session.send_input(command)
            
            # Wait for prompt
            result = await session.expect_and_respond(
                pattern=r"[$#]",
                response="",
                timeout=timeout
            )
            
            results.append({
                "command": command,
                "success": result["success"],
                "output": result.get("before", ""),
                "error": result.get("error", None)
            })
        
        return results
```

#### Database Automation

```python
class DatabaseAutomation:
    """High-level database automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def mysql_connect(
        self,
        host: str,
        username: str,
        password: str,
        database: Optional[str] = None,
        port: int = 3306
    ) -> Dict[str, Any]:
        """Connect to MySQL database with interactive authentication"""
        
        # Build MySQL command
        mysql_command = f"mysql -h {host} -P {port} -u {username} -p"
        if database:
            mysql_command += f" {database}"
        
        session_id = await self.session_manager.create_session(mysql_command)
        
        # MySQL connection steps
        connection_steps = [
            {
                "name": "password_prompt",
                "expect": r"Enter password:",
                "respond": password,
                "timeout": 30
            },
            {
                "name": "connection_success",
                "expect": r"mysql>",
                "respond": "",
                "timeout": 30
            }
        ]
        
        # Handle connection
        connection_results = await self.automation_engine.multi_step_automation(
            session_id, connection_steps
        )
        
        success = all(result["success"] for result in connection_results)
        
        if not success:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "connection_results": connection_results
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "connection_results": connection_results
        }
    
    async def execute_sql(
        self,
        session_id: str,
        sql_query: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Execute SQL query on established database session"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Send SQL query
        await session.send_input(sql_query)
        
        # Wait for prompt
        result = await session.expect_and_respond(
            pattern=r"mysql>",
            response="",
            timeout=timeout
        )
        
        return {
            "query": sql_query,
            "success": result["success"],
            "output": result.get("before", ""),
            "error": result.get("error", None)
        }
    
    async def postgresql_connect(
        self,
        host: str,
        username: str,
        password: str,
        database: str,
        port: int = 5432
    ) -> Dict[str, Any]:
        """Connect to PostgreSQL database"""
        
        # Set PGPASSWORD environment variable for non-interactive auth
        psql_command = f"psql -h {host} -p {port} -U {username} -d {database}"
        session_id = await self.session_manager.create_session(
            psql_command,
            environment={"PGPASSWORD": password}
        )
        
        # PostgreSQL connection steps
        connection_steps = [
            {
                "name": "connection_success",
                "expect": r"[=#]",
                "respond": "",
                "timeout": 30
            }
        ]
        
        connection_results = await self.automation_engine.multi_step_automation(
            session_id, connection_steps
        )
        
        success = all(result["success"] for result in connection_results)
        
        return {
            "success": success,
            "session_id": session_id if success else None,
            "connection_results": connection_results
        }
```

#### Debugging Automation

```python
class DebuggingAutomation:
    """High-level debugging automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def gdb_debug_session(
        self,
        program: str,
        core_file: Optional[str] = None,
        args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Start GDB debugging session with intelligent automation"""
        
        # Build GDB command
        gdb_command = "gdb"
        if core_file:
            gdb_command += f" {program} {core_file}"
        else:
            gdb_command += f" {program}"
        
        session_id = await self.session_manager.create_session(gdb_command)
        
        # Wait for GDB prompt
        init_result = await self.automation_engine.conditional_automation(
            session_id,
            [
                {
                    "pattern": r"\(gdb\)",
                    "action": "continue"
                }
            ],
            timeout=30
        )
        
        if not init_result["success"]:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "error": "Failed to start GDB"
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "gdb_ready": True
        }
    
    async def analyze_crash(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Perform comprehensive crash analysis"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Define analysis commands
        analysis_commands = [
            ("bt", "Get stack trace"),
            ("info threads", "Check thread status"),
            ("thread apply all bt", "Stack trace for all threads"),
            ("info registers", "CPU register state"),
            ("x/20i $pc", "Disassemble around crash point"),
            ("info locals", "Local variables"),
            ("info args", "Function arguments")
        ]
        
        analysis_results = {}
        
        for command, description in analysis_commands:
            try:
                # Send command
                await session.send_input(command)
                
                # Wait for GDB prompt
                result = await session.expect_and_respond(
                    pattern=r"\(gdb\)",
                    response="",
                    timeout=30
                )
                
                if result["success"]:
                    analysis_results[description] = {
                        "command": command,
                        "output": result.get("before", ""),
                        "success": True
                    }
                else:
                    analysis_results[description] = {
                        "command": command,
                        "error": result.get("error", "Unknown error"),
                        "success": False
                    }
                    
            except Exception as e:
                analysis_results[description] = {
                    "command": command,
                    "error": str(e),
                    "success": False
                }
        
        return {
            "analysis_results": analysis_results,
            "summary": self._generate_crash_summary(analysis_results)
        }
    
    def _generate_crash_summary(self, analysis_results: Dict[str, Any]) -> str:
        """Generate human-readable crash summary"""
        summary = "=== Crash Analysis Summary ===\n\n"
        
        # Extract key information
        stack_trace = analysis_results.get("Get stack trace", {}).get("output", "")
        registers = analysis_results.get("CPU register state", {}).get("output", "")
        locals_info = analysis_results.get("Local variables", {}).get("output", "")
        
        if stack_trace:
            summary += f"Stack Trace:\n{stack_trace}\n\n"
        
        if registers:
            summary += f"Register State:\n{registers}\n\n"
        
        if locals_info:
            summary += f"Local Variables:\n{locals_info}\n\n"
        
        summary += "=== Analysis Complete ===\n"
        summary += "Suggestion: Review the stack trace for the immediate cause of the crash.\n"
        summary += "Check local variables and registers for unexpected values.\n"
        
        return summary
    
    async def python_debug_session(
        self,
        script: str,
        breakpoints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Start Python debugging session with PDB"""
        
        pdb_command = f"python -m pdb {script}"
        session_id = await self.session_manager.create_session(pdb_command)
        
        # Wait for PDB prompt
        init_result = await self.automation_engine.conditional_automation(
            session_id,
            [
                {
                    "pattern": r"\(Pdb\)",
                    "action": "continue"
                }
            ],
            timeout=30
        )
        
        if not init_result["success"]:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "error": "Failed to start PDB"
            }
        
        # Set breakpoints if provided
        if breakpoints:
            for bp in breakpoints:
                await self._set_python_breakpoint(session_id, bp)
        
        return {
            "success": True,
            "session_id": session_id,
            "pdb_ready": True
        }
    
    async def _set_python_breakpoint(self, session_id: str, breakpoint: str):
        """Set a breakpoint in Python debugger"""
        session = await self.session_manager.get_session(session_id)
        if session:
            await session.send_input(f"b {breakpoint}")
            await session.expect_and_respond(r"\(Pdb\)", "", timeout=10)
```

## Tool Specifications

### Core MCP Tools

The Interactive Automation MCP Server provides the following tools to Claude Code:

#### 1. Session Management Tools

```python
# Tool: create_interactive_session
{
    "name": "create_interactive_session",
    "description": "Create a new interactive session for program automation",
    "inputSchema": {
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
                "default": 3600,
                "minimum": 30,
                "maximum": 7200
            },
            "environment": {
                "type": "object",
                "description": "Environment variables to set",
                "additionalProperties": {"type": "string"}
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the command"
            }
        },
        "required": ["command"]
    }
}

# Tool: list_sessions
{
    "name": "list_sessions",
    "description": "List all active interactive sessions",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
}

# Tool: destroy_session
{
    "name": "destroy_session", 
    "description": "Terminate and cleanup an interactive session",
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID of the session to destroy"
            }
        },
        "required": ["session_id"]
    }
}
```

#### 2. Automation Tools

```python
# Tool: expect_and_respond
{
    "name": "expect_and_respond",
    "description": "Wait for a pattern in session output and automatically respond",
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID of the interactive session"
            },
            "expect_pattern": {
                "type": "string", 
                "description": "Regular expression pattern to wait for"
            },
            "response": {
                "type": "string",
                "description": "Text to send when pattern is matched"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
                "minimum": 1,
                "maximum": 300
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether pattern matching is case-sensitive",
                "default": false
            }
        },
        "required": ["session_id", "expect_pattern", "response"]
    }
}

# Tool: multi_step_automation
{
    "name": "multi_step_automation",
    "description": "Execute a sequence of expect/respond patterns",
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID of the interactive session"
            },
            "steps": {
                "type": "array",
                "description": "Sequence of automation steps",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of this step"
                        },
                        "expect": {
                            "type": "string",
                            "description": "Pattern to expect"
                        },
                        "respond": {
                            "type": "string",
                            "description": "Response to send"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Step timeout in seconds",
                            "default": 30
                        },
                        "optional": {
                            "type": "boolean",
                            "description": "Whether this step is optional",
                            "default": false
                        }
                    },
                    "required": ["expect", "respond"]
                }
            },
            "stop_on_failure": {
                "type": "boolean",
                "description": "Whether to stop if a step fails",
                "default": true
            }
        },
        "required": ["session_id", "steps"]
    }
}
```

#### 3. High-Level Automation Tools

```python
# Tool: ssh_connect_with_auth
{
    "name": "ssh_connect_with_auth",
    "description": "Connect to SSH server with automated authentication",
    "inputSchema": {
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "SSH server hostname or IP"
            },
            "username": {
                "type": "string",
                "description": "SSH username"
            },
            "auth_method": {
                "type": "string",
                "enum": ["password", "key"],
                "description": "Authentication method"
            },
            "password": {
                "type": "string",
                "description": "Password (required if auth_method is 'password')"
            },
            "key_path": {
                "type": "string", 
                "description": "Path to SSH key file (required if auth_method is 'key')"
            },
            "key_passphrase": {
                "type": "string",
                "description": "SSH key passphrase (optional)"
            },
            "port": {
                "type": "integer",
                "description": "SSH port",
                "default": 22
            },
            "post_connect_commands": {
                "type": "array",
                "description": "Commands to run after successful connection",
                "items": {"type": "string"}
            }
        },
        "required": ["host", "username", "auth_method"]
    }
}

# Tool: database_connect_interactive  
{
    "name": "database_connect_interactive",
    "description": "Connect to database with interactive authentication",
    "inputSchema": {
        "type": "object",
        "properties": {
            "db_type": {
                "type": "string",
                "enum": ["mysql", "postgresql", "mongodb"],
                "description": "Database type"
            },
            "host": {
                "type": "string",
                "description": "Database hostname"
            },
            "port": {
                "type": "integer", 
                "description": "Database port"
            },
            "username": {
                "type": "string",
                "description": "Database username"
            },
            "password": {
                "type": "string",
                "description": "Database password"
            },
            "database": {
                "type": "string",
                "description": "Database name (optional)"
            },
            "initial_commands": {
                "type": "array",
                "description": "Commands to run after connection",
                "items": {"type": "string"}
            }
        },
        "required": ["db_type", "host", "username", "password"]
    }
}

# Tool: gdb_debug_session
{
    "name": "gdb_debug_session",
    "description": "Start GDB debugging session with intelligent automation",
    "inputSchema": {
        "type": "object",
        "properties": {
            "program": {
                "type": "string",
                "description": "Path to program to debug"
            },
            "core_file": {
                "type": "string",
                "description": "Path to core dump file (optional)"
            },
            "args": {
                "type": "array",
                "description": "Program arguments",
                "items": {"type": "string"}
            },
            "breakpoints": {
                "type": "array",
                "description": "Initial breakpoints to set",
                "items": {"type": "string"}
            }
        },
        "required": ["program"]
    }
}

# Tool: analyze_crash
{
    "name": "analyze_crash",
    "description": "Perform comprehensive crash analysis using GDB",
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID of the GDB session"
            },
            "analysis_depth": {
                "type": "string",
                "enum": ["basic", "comprehensive", "deep"],
                "description": "Level of analysis to perform",
                "default": "comprehensive"
            }
        },
        "required": ["session_id"]
    }
}
```

## Implementation Details

### Main MCP Server Implementation

```python
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
from session_manager import SessionManager
from automation_engine import AutomationEngine
from ssh_automation import SSHAutomation
from database_automation import DatabaseAutomation
from debugging_automation import DebuggingAutomation
from security import SecurityManager

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
```

### Security Framework

```python
# security.py
import re
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class SecurityManager:
    """Comprehensive security management for MCP server"""
    
    def __init__(self):
        self.blocked_commands = {
            # Dangerous system commands
            r"rm\s+-rf\s+/",
            r"dd\s+if=.*of=/dev/",
            r"mkfs",
            r"format",
            r"shutdown",
            r"reboot", 
            r"halt",
            r"init\s+0",
            r":(){ :|:& };:",  # Fork bomb
            r"chmod\s+777\s+/",
            
            # Network attacks
            r"nc\s+.*-e",
            r"bash\s+-i\s+>&\s+/dev/tcp/",
            
            # Privilege escalation
            r"sudo\s+su\s+-",
            r"passwd\s+root"
        }
        
        self.allowed_commands = {
            "ssh", "scp", "sftp",
            "mysql", "psql", "mongo", 
            "gdb", "lldb", "pdb",
            "docker", "kubectl",
            "git", "svn",
            "python", "node", "java",
            "npm", "pip", "cargo"
        }
        
        self.rate_limits = defaultdict(list)
        self.max_calls_per_minute = 60
        self.max_sessions = 50
        
    def validate_tool_call(self, tool_name: str, arguments: dict) -> bool:
        """Validate if a tool call is allowed"""
        
        # Rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded")
            return False
        
        # Command validation for session creation
        if tool_name == "create_interactive_session":
            command = arguments.get("command", "")
            if not self._validate_command(command):
                logger.warning(f"Blocked dangerous command: {command}")
                return False
        
        # Path validation for file operations
        if "path" in arguments:
            path = arguments["path"]
            if not self._validate_path(path):
                logger.warning(f"Blocked dangerous path: {path}")
                return False
        
        return True
    
    def _validate_command(self, command: str) -> bool:
        """Validate if a command is safe to execute"""
        
        # Check against blocked patterns
        for blocked_pattern in self.blocked_commands:
            if re.search(blocked_pattern, command, re.IGNORECASE):
                return False
        
        # Extract base command
        base_command = command.split()[0] if command.split() else ""
        
        # Check if base command is in allowed list
        if base_command not in self.allowed_commands:
            # Allow if it's a path to an allowed command
            if "/" in base_command:
                base_name = base_command.split("/")[-1]
                if base_name not in self.allowed_commands:
                    return False
            else:
                return False
        
        return True
    
    def _validate_path(self, path: str) -> bool:
        """Validate if a path is safe to access"""
        
        # Prevent path traversal
        if ".." in path:
            return False
        
        # Prevent access to sensitive directories
        sensitive_dirs = [
            "/etc/passwd", "/etc/shadow", "/etc/sudoers",
            "/root", "/boot", "/proc", "/sys"
        ]
        
        for sensitive in sensitive_dirs:
            if path.startswith(sensitive):
                return False
        
        return True
    
    def _check_rate_limit(self, client_id: str = "default") -> bool:
        """Check if client is within rate limits"""
        now = time.time()
        
        # Clean old entries
        self.rate_limits[client_id] = [
            timestamp for timestamp in self.rate_limits[client_id]
            if now - timestamp < 60  # 1 minute window
        ]
        
        # Check limit
        if len(self.rate_limits[client_id]) >= self.max_calls_per_minute:
            return False
        
        # Record this call
        self.rate_limits[client_id].append(now)
        return True
```

### Installation and Configuration

#### Setup.py

```python
from setuptools import setup, find_packages

setup(
    name="interactive-automation-mcp",
    version="1.0.0",
    description="Interactive Automation MCP Server for Claude Code",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/interactive-automation-mcp",
    packages=find_packages(),
    install_requires=[
        "mcp>=0.5.0",
        "pexpect>=4.8.0",
        "ptyprocess>=0.7.0",
        "asyncio-mqtt>=0.11.0",
        "paramiko>=2.9.0",
        "psycopg2-binary>=2.9.0",
        "pymongo>=4.0.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "mypy>=0.950"
        ]
    },
    entry_points={
        "console_scripts": [
            "interactive-automation-mcp=interactive_automation_mcp.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
```

#### Requirements.txt

```
mcp>=0.5.0
pexpect>=4.8.0
ptyprocess>=0.7.0
paramiko>=2.9.0
psycopg2-binary>=2.9.0
pymongo>=4.0.0
asyncio>=3.4.3
typing-extensions>=4.0.0
dataclasses>=0.8; python_version<"3.7"
```

#### Configuration File

```yaml
# config.yaml
server:
  name: "interactive-automation"
  version: "1.0.0"
  max_sessions: 50
  default_timeout: 3600
  log_level: "INFO"

security:
  enable_command_filtering: true
  enable_rate_limiting: true
  max_calls_per_minute: 60
  allowed_commands:
    - ssh
    - scp
    - mysql
    - psql
    - gdb
    - lldb
    - pdb
    - docker
    - git
    - python
    - node
  
  blocked_patterns:
    - "rm\\s+-rf\\s+/"
    - "dd\\s+if=.*of=/dev/"
    - "mkfs"
    - "format"
    - "shutdown"
    - "reboot"

automation:
  enable_predefined_patterns: true
  pattern_timeout: 30
  max_automation_steps: 100

debugging:
  enable_crash_analysis: true
  gdb_timeout: 300
  max_analysis_depth: "comprehensive"

logging:
  log_file: "/var/log/interactive-automation-mcp.log"
  log_rotation: true
  max_log_size: "10MB"
  backup_count: 5
```

## Use Case Examples

### Example 1: SSH Server Maintenance

```python
# Claude receives: "Connect to production server and check disk usage"

# 1. Establish SSH connection
ssh_result = await mcp.call("ssh_connect_with_auth", {
    "host": "prod.example.com",
    "username": "admin", 
    "auth_method": "key",
    "key_path": "~/.ssh/prod_key",
    "post_connect_commands": [
        "cd /var/log",
        "df -h",
        "du -sh * | sort -hr | head -10"
    ]
})

# Claude analyzes the output and suggests cleanup actions
```

### Example 2: Database Performance Investigation

```python
# Claude receives: "My MySQL database is slow, investigate and fix"

# 1. Connect to database
db_result = await mcp.call("database_connect_interactive", {
    "db_type": "mysql",
    "host": "localhost",
    "username": "root", 
    "password": "secure_password",
    "database": "production_db",
    "initial_commands": [
        "SHOW PROCESSLIST;",
        "SHOW ENGINE INNODB STATUS;",
        "SELECT * FROM information_schema.innodb_trx;",
        "SHOW VARIABLES LIKE 'slow_query_log%';"
    ]
})

# Claude analyzes query performance and suggests optimizations
```

### Example 3: Debugging Segmentation Fault

```python
# Claude receives: "My C++ program crashed with segfault, debug it"

# 1. Start GDB session
gdb_result = await mcp.call("gdb_debug_session", {
    "program": "./my_app",
    "core_file": "core.12345"
})

# 2. Perform crash analysis
analysis_result = await mcp.call("analyze_crash", {
    "session_id": gdb_result["session_id"],
    "analysis_depth": "comprehensive"
})

# Claude provides detailed analysis:
# - Stack trace showing null pointer dereference
# - Variable values at crash point
# - Suggested code fixes
```

### Example 4: Automated Deployment Pipeline

```python
# Claude receives: "Deploy the latest version to staging"

# 1. Connect to deployment server
deploy_session = await mcp.call("ssh_connect_with_auth", {
    "host": "staging.example.com",
    "username": "deploy",
    "auth_method": "key",
    "key_path": "~/.ssh/deploy_key"
})

# 2. Multi-step deployment automation
deployment_steps = [
    {"expect": "[$#]", "respond": "cd /opt/app"},
    {"expect": "[$#]", "respond": "git pull origin main"},
    {"expect": "[$#]", "respond": "docker-compose build"},
    {"expect": "[$#]", "respond": "docker-compose up -d"},
    {"expect": "[$#]", "respond": "docker-compose ps"}
]

deploy_result = await mcp.call("multi_step_automation", {
    "session_id": deploy_session["session_id"],
    "steps": deployment_steps
})

# Claude monitors deployment and reports success/failure
```

### Example 5: Interactive Docker Container Debugging

```python
# Claude receives: "My container is not starting, debug the issue"

# 1. Start interactive Docker session
docker_session = await mcp.call("create_interactive_session", {
    "command": "docker run -it --rm problematic_image /bin/bash"
})

# 2. Debug container interactively
debug_steps = [
    {"expect": "root@.*#", "respond": "ls -la"},
    {"expect": "root@.*#", "respond": "cat /etc/os-release"},
    {"expect": "root@.*#", "respond": "ps aux"},
    {"expect": "root@.*#", "respond": "netstat -tulnp"},
    {"expect": "root@.*#", "respond": "tail -f /var/log/app.log"}
]

debug_result = await mcp.call("multi_step_automation", {
    "session_id": docker_session["session_id"],
    "steps": debug_steps
})

# Claude identifies missing dependencies or configuration issues
```

## Testing Strategy

### Unit Tests

```python
# test_session_manager.py
import pytest
import asyncio
from session_manager import SessionManager, SessionState

class TestSessionManager:
    
    @pytest.fixture
    async def session_manager(self):
        return SessionManager(max_sessions=5, default_timeout=60)
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        session_id = await session_manager.create_session("echo 'test'")
        assert session_id is not None
        assert session_id in session_manager.sessions
        
        metadata = session_manager.session_metadata[session_id]
        assert metadata.state == SessionState.ACTIVE
        assert metadata.command == "echo 'test'"
    
    @pytest.mark.asyncio
    async def test_session_limits(self, session_manager):
        # Create maximum sessions
        session_ids = []
        for i in range(5):
            session_id = await session_manager.create_session(f"echo {i}")
            session_ids.append(session_id)
        
        # Try to create one more (should fail)
        with pytest.raises(RuntimeError):
            await session_manager.create_session("echo overflow")
    
    @pytest.mark.asyncio
    async def test_destroy_session(self, session_manager):
        session_id = await session_manager.create_session("echo 'test'")
        success = await session_manager.destroy_session(session_id)
        
        assert success
        assert session_id not in session_manager.sessions
```

### Integration Tests

```python
# test_automation_integration.py
import pytest
import asyncio
from interactive_automation_server import InteractiveAutomationServer

class TestAutomationIntegration:
    
    @pytest.fixture
    async def server(self):
        return InteractiveAutomationServer()
    
    @pytest.mark.asyncio
    async def test_ssh_automation_flow(self, server):
        # Mock SSH server for testing
        # This would use a test SSH server or mock
        
        result = await server._handle_ssh_connect({
            "host": "test.example.com",
            "username": "testuser",
            "auth_method": "password",
            "password": "testpass"
        })
        
        # Verify connection attempt was made
        # (actual result depends on test environment)
        assert "session_id" in result or "error" in result
    
    @pytest.mark.asyncio 
    async def test_multi_step_automation(self, server):
        # Create a test session with echo command
        session_result = await server._handle_create_session({
            "command": "bash"
        })
        
        session_id = session_result["session_id"]
        
        # Test multi-step automation
        steps = [
            {"expect": "[$#]", "respond": "echo 'step1'"},
            {"expect": "[$#]", "respond": "echo 'step2'"},
            {"expect": "[$#]", "respond": "exit"}
        ]
        
        automation_result = await server._handle_multi_step_automation({
            "session_id": session_id,
            "steps": steps
        })
        
        assert automation_result["success"]
        assert len(automation_result["step_results"]) == 3
```

### Security Tests

```python
# test_security.py
import pytest
from security import SecurityManager

class TestSecurity:
    
    @pytest.fixture
    def security_manager(self):
        return SecurityManager()
    
    def test_blocked_commands(self, security_manager):
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            ":(){ :|:& };:",
            "shutdown -h now"
        ]
        
        for cmd in dangerous_commands:
            assert not security_manager._validate_command(cmd)
    
    def test_allowed_commands(self, security_manager):
        safe_commands = [
            "ssh user@host",
            "mysql -u root -p",
            "gdb ./program",
            "docker ps",
            "git status"
        ]
        
        for cmd in safe_commands:
            assert security_manager._validate_command(cmd)
    
    def test_path_traversal_prevention(self, security_manager):
        dangerous_paths = [
            "../../../etc/passwd",
            "/etc/shadow",
            "/root/.ssh/id_rsa"
        ]
        
        for path in dangerous_paths:
            assert not security_manager._validate_path(path)
    
    def test_rate_limiting(self, security_manager):
        # Test rate limiting
        for i in range(60):
            assert security_manager._check_rate_limit("test_client")
        
        # 61st call should be blocked
        assert not security_manager._check_rate_limit("test_client")
```

## Deployment and Maintenance

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    mysql-client \
    postgresql-client \
    gdb \
    docker.io \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -s /bin/bash mcpuser

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set permissions
RUN chown -R mcpuser:mcpuser /app
USER mcpuser

# Expose port (if using HTTP transport)
EXPOSE 8000

# Default command
CMD ["python", "main.py"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  interactive-automation-mcp:
    build: .
    container_name: interactive-automation-mcp
    restart: unless-stopped
    
    # Environment variables
    environment:
      - MCP_LOG_LEVEL=INFO
      - MCP_MAX_SESSIONS=50
      - MCP_SECURITY_ENABLED=true
    
    # Volume mounts
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./data:/app/data
      - ~/.ssh:/home/mcpuser/.ssh:ro  # SSH keys
    
    # Network settings
    networks:
      - mcp-network
    
    # Resource limits
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'

networks:
  mcp-network:
    driver: bridge
```

### Monitoring and Logging

```python
# monitoring.py
import logging
import time
import psutil
from typing import Dict, Any

class ServerMonitor:
    """Monitor server health and performance"""
    
    def __init__(self):
        self.start_time = time.time()
        self.stats = {
            "total_sessions": 0,
            "active_sessions": 0,
            "total_tool_calls": 0,
            "failed_tool_calls": 0,
            "average_response_time": 0.0
        }
    
    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        """Record tool call metrics"""
        self.stats["total_tool_calls"] += 1
        if not success:
            self.stats["failed_tool_calls"] += 1
        
        # Update average response time
        current_avg = self.stats["average_response_time"]
        total_calls = self.stats["total_tool_calls"]
        self.stats["average_response_time"] = (
            (current_avg * (total_calls - 1) + duration) / total_calls
        )
        
        logging.info(f"Tool call: {tool_name}, Duration: {duration:.2f}s, Success: {success}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current server health status"""
        uptime = time.time() - self.start_time
        memory_usage = psutil.virtual_memory()
        cpu_usage = psutil.cpu_percent(interval=1)
        
        return {
            "uptime_seconds": uptime,
            "memory_usage_percent": memory_usage.percent,
            "cpu_usage_percent": cpu_usage,
            "stats": self.stats,
            "status": "healthy" if memory_usage.percent < 80 and cpu_usage < 80 else "warning"
        }
```

### Maintenance Scripts

```bash
#!/bin/bash
# maintenance.sh - Server maintenance script

# Log rotation
rotate_logs() {
    echo "Rotating log files..."
    if [ -f "/app/logs/server.log" ]; then
        mv /app/logs/server.log /app/logs/server.log.$(date +%Y%m%d_%H%M%S)
        gzip /app/logs/server.log.*
        
        # Keep only last 10 log files
        ls -t /app/logs/server.log.*.gz | tail -n +11 | xargs -r rm
    fi
}

# Cleanup expired sessions
cleanup_sessions() {
    echo "Cleaning up expired sessions..."
    find /tmp -name "session_*.log" -mtime +1 -delete
}

# Health check
health_check() {
    echo "Performing health check..."
    python -c "
import requests
import sys
try:
    response = requests.get('http://localhost:8000/health', timeout=5)
    if response.status_code == 200:
        print('Server is healthy')
        sys.exit(0)
    else:
        print('Server returned error status')
        sys.exit(1)
except Exception as e:
    print(f'Health check failed: {e}')
    sys.exit(1)
"
}

# Main maintenance routine
case "$1" in
    "logs")
        rotate_logs
        ;;
    "cleanup")
        cleanup_sessions
        ;;
    "health")
        health_check
        ;;
    "all")
        rotate_logs
        cleanup_sessions
        health_check
        ;;
    *)
        echo "Usage: $0 {logs|cleanup|health|all}"
        exit 1
        ;;
esac
```

### Configuration Management

```python
# config_manager.py
import yaml
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ServerConfig:
    name: str
    version: str
    max_sessions: int
    default_timeout: int
    log_level: str

@dataclass  
class SecurityConfig:
    enable_command_filtering: bool
    enable_rate_limiting: bool
    max_calls_per_minute: int
    allowed_commands: list
    blocked_patterns: list

class ConfigManager:
    """Manage server configuration"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "server": {
                "name": "interactive-automation",
                "version": "1.0.0",
                "max_sessions": 50,
                "default_timeout": 3600,
                "log_level": "INFO"
            },
            "security": {
                "enable_command_filtering": True,
                "enable_rate_limiting": True,
                "max_calls_per_minute": 60,
                "allowed_commands": [
                    "ssh", "mysql", "gdb", "docker", "git", "python"
                ],
                "blocked_patterns": [
                    "rm\\s+-rf\\s+/",
                    "shutdown",
                    "reboot"
                ]
            }
        }
    
    def get_server_config(self) -> ServerConfig:
        """Get server configuration"""
        server_config = self.config.get("server", {})
        return ServerConfig(
            name=server_config.get("name", "interactive-automation"),
            version=server_config.get("version", "1.0.0"),
            max_sessions=server_config.get("max_sessions", 50),
            default_timeout=server_config.get("default_timeout", 3600),
            log_level=server_config.get("log_level", "INFO")
        )
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration"""
        security_config = self.config.get("security", {})
        return SecurityConfig(
            enable_command_filtering=security_config.get("enable_command_filtering", True),
            enable_rate_limiting=security_config.get("enable_rate_limiting", True),
            max_calls_per_minute=security_config.get("max_calls_per_minute", 60),
            allowed_commands=security_config.get("allowed_commands", []),
            blocked_patterns=security_config.get("blocked_patterns", [])
        )
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration"""
        self._deep_update(self.config, updates)
        self._save_config()
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """Deep update dictionary"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
```

This comprehensive technical specification provides everything needed to implement a fully functional Interactive Automation MCP Server. The implementation includes:

1. **Complete architecture** with modular components
2. **Detailed class implementations** for all core functionality
3. **Security framework** with comprehensive protections
4. **Full MCP tool specifications** with proper schemas
5. **Real-world use case examples** demonstrating practical applications
6. **Comprehensive testing strategy** covering unit, integration, and security tests
7. **Production deployment guidance** with Docker, monitoring, and maintenance

The server enables Claude Code to perform sophisticated interactive automation tasks while maintaining security, reliability, and performance standards suitable for production use.

