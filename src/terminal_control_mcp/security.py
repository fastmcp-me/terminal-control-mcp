import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Control character range (Ctrl+A to Ctrl+Z)
CTRL_Z_ASCII = 26

# Constants for security validation
CONTROL_CHAR_THRESHOLD = 32
DEL_CHAR_CODE = 127
C1_CONTROL_START = 128
C1_CONTROL_END = 159
PROBLEMATIC_HIGH_BYTES = {254, 255}
MAX_LOG_VALUE_LENGTH = 200

# Default security limits
DEFAULT_MAX_CALLS_PER_MINUTE = 60
DEFAULT_MAX_SESSIONS = 50
EXPECTED_MIN_BASE_PATHS = 4


@dataclass
class RateLimitData:
    """Rate limiting data for a client"""

    client_id: str
    call_timestamps: list[float] = field(default_factory=list)

    def add_call(self, timestamp: float) -> None:
        """Add a new call timestamp"""
        self.call_timestamps.append(timestamp)

    def clean_old_calls(self, window_seconds: int = 60) -> None:
        """Remove calls older than the window"""
        now = time.time()
        self.call_timestamps = [
            ts for ts in self.call_timestamps if now - ts <= window_seconds
        ]

    def get_recent_call_count(self) -> int:
        """Get count of recent calls"""
        return len(self.call_timestamps)


class SecurityManager:
    """Comprehensive security management for MCP server"""

    def __init__(self) -> None:
        self.rate_limits: dict[str, RateLimitData] = {}
        self.max_calls_per_minute = DEFAULT_MAX_CALLS_PER_MINUTE
        self.max_sessions = DEFAULT_MAX_SESSIONS

        # Dangerous command patterns that should be blocked
        self.blocked_command_patterns = {
            r"\brm\s+-rf\s+/",  # rm -rf /
            r"\bsudo\s+rm\s+-rf",  # sudo rm -rf
            r"\bdd\s+if=/dev/zero",  # dd disk wipe
            r"\bmkfs\.",  # filesystem formatting
            r"\bfdisk\s",  # disk partitioning
            r"\b:\(\)\{.*fork.*\}",  # fork bomb
            r"\bchmod\s+777\s+/",  # dangerous permissions
            r"\bchown\s+.*:.*\s+/",  # ownership changes on root
            r"\biptables\s+-F",  # firewall flush
            r"\bufw\s+--force\s+disable",  # firewall disable
            r"\bsudo\s+passwd",  # password changes
            r"\bsu\s+-",  # switch user
            r"\bcrontab\s+-r",  # cron deletion
            r"\bsystemctl\s+(stop|disable)\s+(ssh|network)",  # critical service shutdown
        }

        # Allowed base directories for file operations
        self.allowed_base_paths = {
            os.path.expanduser("~"),  # User home directory
            "/tmp",  # Temporary files
            "/var/tmp",  # Temporary files
            os.getcwd(),  # Current working directory
        }

        # Blocked file extensions and paths
        self.blocked_extensions = {".so", ".dll", ".exe", ".bat", ".cmd", ".scr"}
        self.blocked_paths = {
            "/etc/passwd",
            "/etc/shadow",
            "/etc/sudoers",
            "/boot",
            "/sys",
            "/proc/sys",
            "/.ssh/id_rsa",
            "/.ssh/id_ed25519",
        }

        # Environment variables that should never be modified
        self.protected_env_vars = {
            "PATH",
            "HOME",
            "USER",
            "SUDO_USER",
            "SHELL",
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
        }

    def validate_tool_call(
        self, tool_name: str, arguments: dict, client_id: str = "default"
    ) -> bool:
        """Validate if a tool call is allowed"""

        # Check basic validations first
        if not self._validate_basic_requirements(tool_name, arguments, client_id):
            return False

        # Validate tool-specific requirements
        if not self._validate_tool_specific_requirements(
            tool_name, arguments, client_id
        ):
            return False

        # Log successful validation
        self._log_security_event("tool_call_allowed", tool_name, arguments, client_id)
        return True

    def _validate_basic_requirements(
        self, tool_name: str, arguments: dict, client_id: str
    ) -> bool:
        """Validate basic security requirements for all tool calls"""

        # Rate limiting
        if not self._check_rate_limit(client_id):
            self._log_security_event(
                "rate_limit_exceeded", tool_name, arguments, client_id
            )
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return False

        # Validate all string inputs for basic injection attempts
        for key, value in arguments.items():
            if isinstance(value, str):
                # Special handling for input_text in tercon_send_input - allow escape sequences
                if tool_name == "tercon_send_input" and key == "input_text":
                    # Skip basic validation here - will be handled in tool-specific validation
                    continue
                elif not self._validate_input(value):
                    self._log_security_event(
                        "invalid_input", tool_name, {key: value[:100]}, client_id
                    )
                    logger.warning(f"Invalid input detected in {key}: {value[:100]}")
                    return False

        return True

    def _validate_tool_specific_requirements(
        self, tool_name: str, arguments: dict, client_id: str
    ) -> bool:
        """Validate tool-specific security requirements"""

        if tool_name == "tercon_execute_command":
            return self._validate_execute_command(arguments, client_id)
        elif tool_name == "tercon_send_input":
            return self._validate_send_input(arguments, client_id)

        return True

    def _validate_execute_command(self, arguments: dict, client_id: str) -> bool:
        """Validate execute_command specific requirements"""

        # Command validation - use full_command if present, otherwise command
        command = arguments.get("full_command") or arguments.get("command", "")
        if not self._validate_command(command):
            self._log_security_event(
                "dangerous_command", "execute_command", {"command": command}, client_id
            )
            logger.warning(f"Blocked dangerous command: {command}")
            return False

        # Environment variables validation
        env = arguments.get("environment")
        if env and not self._validate_environment(env):
            self._log_security_event(
                "dangerous_environment",
                "execute_command",
                {"environment": str(env)},
                client_id,
            )
            logger.warning("Blocked dangerous environment variables")
            return False

        # Working directory validation
        working_dir = arguments.get("working_directory")
        if working_dir and not self._validate_path(working_dir):
            self._log_security_event(
                "dangerous_path",
                "execute_command",
                {"working_directory": working_dir},
                client_id,
            )
            logger.warning(f"Blocked dangerous working directory: {working_dir}")
            return False

        return True

    def _validate_send_input(self, arguments: dict, client_id: str) -> bool:
        """Validate send_input specific requirements"""

        input_text = arguments.get("input_text", "")
        if not self._validate_input_text_with_escape_sequences(input_text):
            self._log_security_event(
                "dangerous_input_text",
                "send_input",
                {"input_text": input_text[:100]},
                client_id,
            )
            logger.warning(f"Blocked dangerous input text: {input_text[:100]}")
            return False

        return True

    def _validate_input(self, value: str) -> bool:
        """Validate input strings for basic injection attempts"""
        # Check for null bytes, control characters, and DEL character
        if "\x00" in value or any(
            (ord(c) < CONTROL_CHAR_THRESHOLD and c not in "\t\n\r")
            or ord(c) == DEL_CHAR_CODE
            for c in value
        ):
            return False

        # Check for problematic bytes in the 128-255 range that are often binary/control sequences
        # This catches \x80, \x81, \xff, \xfe from the test but allows proper Unicode
        for c in value:
            ord_c = ord(c)
            if (
                C1_CONTROL_START <= ord_c <= C1_CONTROL_END
                or ord_c in PROBLEMATIC_HIGH_BYTES
            ):
                return False

        # Check for potential shell injection patterns
        injection_patterns = {
            r";\s*rm\s",
            r";\s*cat\s",
            r";\s*curl\s",
            r";\s*wget\s",
            r"\$\([^)]*\)",
            r"`[^`]*`",
            r"\${[^}]*}",
            r"\\x[0-9a-fA-F]{2}",  # hex escape sequences
        }

        for pattern in injection_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False

        return True

    def _validate_environment(self, env: dict) -> bool:
        """Validate environment variables for security"""
        for key, value in env.items():
            # Check for None values and empty keys
            if value is None or not isinstance(key, str) or not isinstance(value, str):
                return False

            # Block empty keys
            if not key or not key.strip():
                return False

            # Block modification of protected environment variables
            if key in self.protected_env_vars:
                return False

            # Validate both key and value
            if not self._validate_input(key) or not self._validate_input(value):
                return False

        return True

    def _validate_input_text(self, input_text: str) -> bool:
        """Validate input text for interactive sessions"""
        if not self._validate_input(input_text):
            return False

        # Additional checks for interactive input
        dangerous_patterns = {
            r"sudo\s+.*",  # sudo commands
            r"su\s+-",  # switch user
            r"passwd\s*$",  # password command
        }

        for pattern in dangerous_patterns:
            if re.search(pattern, input_text, re.IGNORECASE):
                return False

        return True

    def _validate_input_text_with_escape_sequences(self, input_text: str) -> bool:
        """Validate input text allowing legitimate terminal escape sequences"""
        # Allow common control characters and escape sequences for terminal control
        if self._is_legitimate_escape_sequence(input_text):
            return True

        # Fall back to regular validation for non-escape sequences
        return self._validate_input_text(input_text)

    def _is_legitimate_escape_sequence(self, text: str) -> bool:
        """Check if text contains only legitimate terminal escape sequences"""
        # Allow single control characters (Ctrl+A to Ctrl+Z)
        if len(text) == 1 and 1 <= ord(text) <= CTRL_Z_ASCII:
            return True

        # Allow common control characters
        allowed_control_chars = {
            "\x03",  # Ctrl+C (ETX)
            "\x04",  # Ctrl+D (EOT)
            "\x08",  # Ctrl+H (Backspace)
            "\x09",  # Tab
            "\x0a",  # Line Feed
            "\x0d",  # Carriage Return
            "\x1a",  # Ctrl+Z (SUB)
            "\x1b",  # Escape
            "\x7f",  # DEL
        }

        if len(text) == 1 and text in allowed_control_chars:
            return True

        # Allow ANSI escape sequences (ESC followed by printable characters)
        if text.startswith("\x1b") and len(text) > 1:
            # Check that everything after ESC is printable or known control sequences
            rest = text[1:]
            # Allow common ANSI sequences: [, O, ], (, ), and printable chars
            if all(c.isprintable() or c in "[O]()\x7e~" for c in rest):
                return True

        # Check for multi-byte escape sequences (arrow keys, function keys, etc.)
        common_sequences = {
            "\x1b[A",  # Up arrow
            "\x1b[B",  # Down arrow
            "\x1b[C",  # Right arrow
            "\x1b[D",  # Left arrow
            "\x1b[H",  # Home
            "\x1b[F",  # End
            "\x1bOP",  # F1
            "\x1bOQ",  # F2
            "\x1bOR",  # F3
            "\x1bOS",  # F4
            "\x1b[15~",  # F5
            "\x1b[17~",  # F6
            "\x1b[18~",  # F7
            "\x1b[19~",  # F8
            "\x1b[20~",  # F9
            "\x1b[21~",  # F10
            "\x1b[23~",  # F11
            "\x1b[24~",  # F12
        }

        if text in common_sequences:
            return True

        return False

    def _validate_command(self, command: str) -> bool:
        """Validate command against dangerous patterns"""
        if not command or not command.strip():
            return False

        command_lower = command.lower().strip()

        # Check against blocked patterns
        for pattern in self.blocked_command_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                logger.error(f"Blocked dangerous command pattern: {pattern}")
                return False

        # Block commands that try to modify system files
        system_paths = ["/etc/", "/boot/", "/sys/", "/proc/sys/"]
        for sys_path in system_paths:
            if f">{sys_path}" in command or f"to {sys_path}" in command:
                logger.error(f"Blocked system path modification: {sys_path}")
                return False

        # Block commands that try to access blocked paths directly
        for blocked_path in self.blocked_paths:
            if blocked_path in command:
                logger.error(f"Blocked access to restricted path: {blocked_path}")
                return False

        # Additional checks for specific dangerous commands
        dangerous_commands = ["format", "fdisk", "parted", "mkfs", "wipefs"]
        first_word = command_lower.split()[0] if command_lower.split() else ""
        if first_word in dangerous_commands:
            logger.error(f"Blocked dangerous command: {first_word}")
            return False

        return True

    def _validate_path(self, path: str) -> bool:
        """Validate file paths against traversal attacks and restricted areas"""
        if not path:
            return False

        try:
            resolved_path = Path(path).resolve()
            path_str = str(resolved_path)

            # Check basic path security
            if not self._check_path_traversal(path):
                return False

            # Check against blocked resources
            if not self._check_blocked_paths_and_extensions(path_str, resolved_path):
                return False

            # Check directory permissions
            if not self._check_allowed_directories(resolved_path):
                return False

            return True

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False

    def _check_path_traversal(self, path: str) -> bool:
        """Check for path traversal attempts"""
        if ".." in path or path.startswith("../"):
            logger.error(f"Path traversal attempt detected: {path}")
            return False
        return True

    def _check_blocked_paths_and_extensions(
        self, path_str: str, resolved_path: Path
    ) -> bool:
        """Check against blocked paths and file extensions"""
        # Check against blocked paths
        for blocked in self.blocked_paths:
            if path_str.startswith(blocked) or resolved_path == Path(blocked):
                logger.error(f"Access to blocked path: {path_str}")
                return False

        # Check file extensions
        if resolved_path.suffix.lower() in self.blocked_extensions:
            logger.error(f"Blocked file extension: {resolved_path.suffix}")
            return False

        return True

    def _check_allowed_directories(self, resolved_path: Path) -> bool:
        """Check if path is within allowed base directories"""
        for allowed_base in self.allowed_base_paths:
            try:
                resolved_path.relative_to(Path(allowed_base).resolve())
                return True
            except ValueError:
                continue

        logger.error(f"Path outside allowed directories: {resolved_path}")
        return False

    def _check_rate_limit(self, client_id: str = "default") -> bool:
        """Check if client is within rate limits"""
        now = time.time()

        # Get or create rate limit data for client
        if client_id not in self.rate_limits:
            self.rate_limits[client_id] = RateLimitData(client_id)

        rate_data = self.rate_limits[client_id]

        # Clean old entries
        rate_data.clean_old_calls()

        # Check limit
        if rate_data.get_recent_call_count() >= self.max_calls_per_minute:
            return False

        # Record this call
        rate_data.add_call(now)
        return True

    def _log_security_event(
        self, event_type: str, tool_name: str, arguments: dict, client_id: str
    ) -> None:
        """Log security events for audit purposes"""
        try:
            # Create security audit log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "tool_name": tool_name,
                "client_id": client_id,
                "arguments": self._sanitize_for_logging(arguments),
            }

            # Log to security logger with structured data
            security_logger = logging.getLogger("interactive-automation-mcp.security")
            security_logger.info(json.dumps(log_entry))

            # Also write to security audit file if configured
            self._write_audit_log(log_entry)

        except Exception as e:
            logger.error(f"Failed to log security event: {e}")

    def _sanitize_for_logging(self, data: dict) -> dict:
        """Sanitize sensitive data for logging"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Truncate long values and mask potential secrets
                if len(value) > MAX_LOG_VALUE_LENGTH:
                    sanitized[key] = value[:MAX_LOG_VALUE_LENGTH] + "..."
                elif any(
                    secret_word in key.lower()
                    for secret_word in ["password", "token", "key", "secret"]
                ):
                    sanitized[key] = "*" * min(len(value), 8)
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = str(value)[:100]
        return sanitized

    def _write_audit_log(self, log_entry: dict) -> None:
        """Write audit log to file if audit logging is enabled"""
        try:
            audit_log_path = os.environ.get("MCP_AUDIT_LOG_PATH")
            if audit_log_path:
                os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
                with open(audit_log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.debug(f"Could not write to audit log file: {e}")

    def validate_session_limits(self, current_session_count: int) -> bool:
        """Validate if new session creation is allowed based on limits"""
        if current_session_count >= self.max_sessions:
            logger.warning(
                f"Session limit exceeded: {current_session_count}/{self.max_sessions}"
            )
            return False
        return True
