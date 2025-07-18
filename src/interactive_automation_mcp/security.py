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
            "npm", "pip", "cargo",
            "echo", "cat", "ls", "pwd",
            "cd", "which", "whoami"
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