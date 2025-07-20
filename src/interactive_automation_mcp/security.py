import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class SecurityManager:
    """Comprehensive security management for MCP server"""

    def __init__(self) -> None:
        # Universal design: No command blocking - user is responsible for security
        # Any command is allowed - maximum flexibility

        # Universal design: No command whitelist - only block dangerous patterns
        # Any command is allowed as long as it doesn't match blocked patterns

        self.rate_limits: dict[str, list[float]] = defaultdict(list)
        self.max_calls_per_minute = 60
        self.max_sessions = 50

    def validate_tool_call(self, tool_name: str, arguments: dict[str, str]) -> bool:
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
        """Universal design: All commands are allowed - user is responsible for security"""
        # No validation - maximum flexibility and universality
        return True

    def _validate_path(self, path: str) -> bool:
        """Universal design: All paths are allowed - user is responsible for security"""
        # No validation - maximum flexibility and universality
        return True

    def _check_rate_limit(self, client_id: str = "default") -> bool:
        """Check if client is within rate limits"""
        now = time.time()

        # Clean old entries
        self.rate_limits[client_id] = [
            timestamp
            for timestamp in self.rate_limits[client_id]
            if now - timestamp < 60  # 1 minute window
        ]

        # Check limit
        if len(self.rate_limits[client_id]) >= self.max_calls_per_minute:
            return False

        # Record this call
        self.rate_limits[client_id].append(now)
        return True
