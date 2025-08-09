import asyncio
import logging
import os
import re
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import libtmux

from .interaction_logger import InteractionLogger
from .settings import ServerConfig

logger = logging.getLogger(__name__)

# ANSI escape sequence pattern for removing terminal formatting
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi_sequences(text: str) -> str:
    """Remove ANSI escape sequences from terminal output"""
    return ANSI_ESCAPE_PATTERN.sub("", text)


class InteractiveSession:
    """Represents a single interactive terminal session using libtmux"""

    def __init__(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
        environment: dict[str, str] | None = None,
        working_directory: str | None = None,
    ):
        self.session_id = session_id
        self.command = command
        self.timeout = timeout
        self.environment = environment or {}
        self.working_directory = working_directory

        self._initialize_tmux_config()
        self._initialize_file_paths()
        self._initialize_history_isolation()
        self._initialize_session_objects()

    def _initialize_tmux_config(self) -> None:
        """Initialize tmux-related configuration"""
        self.tmux_session_name = f"mcp_{self.session_id}"
        self.is_active = False
        self.exit_code: int | None = None

    def _initialize_file_paths(self) -> None:
        """Initialize file paths for session"""
        temp_dir = Path(tempfile.gettempdir())
        self.output_stream_file = temp_dir / f"tmux_stream_{self.session_id}.log"

    def _initialize_history_isolation(self) -> None:
        """Initialize history isolation if enabled"""
        config = ServerConfig()
        if config.isolate_history:
            temp_dir = Path(tempfile.gettempdir())
            self.history_dir: Path | None = temp_dir / f"mcp_history_{self.session_id}"
            self.history_dir.mkdir(exist_ok=True)
            self.isolated_history_files: dict[str, Path] = {}
        else:
            self.history_dir = None
            self.isolated_history_files = {}

    def _initialize_session_objects(self) -> None:
        """Initialize session objects and logging"""
        # libtmux objects
        self.tmux_server: libtmux.Server | None = None
        self.tmux_session: libtmux.Session | None = None
        self.tmux_window: libtmux.Window | None = None
        self.tmux_pane: libtmux.Pane | None = None

        # Interaction logging
        self.interaction_logger = InteractionLogger(self.session_id)

        # Track last input timestamp for "since_input" mode
        self.last_input_timestamp: float = 0

    async def initialize(self) -> None:
        """Initialize the tmux session using libtmux"""
        try:
            self.interaction_logger.log_command_execution(
                command=self.command, working_dir=self.working_directory
            )

            env = self._prepare_environment()
            await self._create_tmux_session(env)
            await self._setup_terminal_output_capture()
            await self._configure_session_environment(env)
            await self._execute_initial_command()
            self._finalize_initialization()

        except Exception as e:
            self.interaction_logger.log_error("initialization_error", str(e))
            raise RuntimeError(f"Failed to initialize tmux session: {str(e)}") from e

    def _prepare_environment(self) -> dict[str, str]:
        """Prepare environment variables for the session"""
        env = dict(os.environ)
        env.update(
            {
                "LC_ALL": "C.UTF-8",
                "LANG": "C.UTF-8",
                "LC_MESSAGES": "C",
                "PYTHONUNBUFFERED": "1",
            }
        )

        # Apply history isolation if enabled
        config = ServerConfig()
        if config.isolate_history and self.history_dir:
            self._configure_history_isolation(env)

        env.update(self.environment)
        return env

    def _configure_history_isolation(self, env: dict[str, str]) -> None:
        """Configure isolated history files for different shells"""
        if not self.history_dir:
            return

        config = ServerConfig()
        self._create_shell_history_files(config)
        self._configure_shell_environments(env, config)
        self._configure_application_histories(env, config)

        logger.debug(f"Configured history isolation for session {self.session_id} in {self.history_dir}")

    def _create_shell_history_files(self, config: ServerConfig) -> None:
        """Create isolated history files for different shells"""
        assert self.history_dir is not None
        history_files = {
            "bash": self.history_dir / f"{config.history_file_prefix}_bash_{self.session_id}",
            "zsh": self.history_dir / f"{config.history_file_prefix}_zsh_{self.session_id}",
            "fish": self.history_dir / f"{config.history_file_prefix}_fish_{self.session_id}",
            "csh": self.history_dir / f"{config.history_file_prefix}_csh_{self.session_id}",
            "tcsh": self.history_dir / f"{config.history_file_prefix}_tcsh_{self.session_id}",
        }

        self.isolated_history_files = history_files

        # Create empty history files
        for _shell, hist_file in history_files.items():
            hist_file.touch(exist_ok=True)

    def _configure_shell_environments(self, env: dict[str, str], config: ServerConfig) -> None:
        """Configure shell-specific environment variables"""
        history_files = self.isolated_history_files

        # Bash configuration
        env.update({
            "HISTFILE": str(history_files["bash"]),
            "HISTCONTROL": "ignoreboth",
            "HISTSIZE": "1000",
            "HISTFILESIZE": "2000",
        })

        # Zsh configuration
        env.update({
            "HISTFILE": str(history_files["zsh"]),
            "ZDOTDIR": str(self.history_dir),
            "SAVEHIST": "1000",
            "HISTSIZE": "1000",
        })

        # Fish configuration
        env.update({
            "XDG_CONFIG_HOME": str(self.history_dir),
            "XDG_DATA_HOME": str(self.history_dir),
        })

        # C shell variants
        env.update({
            "history": "1000",
            "savehist": "1000",
        })

    def _configure_application_histories(self, env: dict[str, str], config: ServerConfig) -> None:
        """Configure history files for various applications"""
        assert self.history_dir is not None

        # Python REPL history
        python_hist = self.history_dir / f"{config.history_file_prefix}_python_{self.session_id}"
        python_hist.touch(exist_ok=True)
        env["PYTHONSTARTUP"] = self._create_python_startup_script(python_hist)

        # Node.js REPL history
        node_hist = self.history_dir / f"{config.history_file_prefix}_node_{self.session_id}"
        node_hist.touch(exist_ok=True)
        env["NODE_REPL_HISTORY"] = str(node_hist)

        # PostgreSQL history
        psql_hist = self.history_dir / f"{config.history_file_prefix}_psql_{self.session_id}"
        psql_hist.touch(exist_ok=True)
        env["PSQL_HISTORY"] = str(psql_hist)

        # MySQL history
        mysql_hist = self.history_dir / f"{config.history_file_prefix}_mysql_{self.session_id}"
        mysql_hist.touch(exist_ok=True)
        env["MYSQL_HISTFILE"] = str(mysql_hist)

    def _create_python_startup_script(self, python_hist: Path) -> str:
        """Create a Python startup script to set history file"""
        assert self.history_dir is not None
        startup_script = self.history_dir / "python_startup.py"
        startup_content = f'''
import os
import atexit
try:
    import readline
    readline.read_history_file("{python_hist}")
    atexit.register(readline.write_history_file, "{python_hist}")
except (ImportError, FileNotFoundError):
    pass
'''
        startup_script.write_text(startup_content)
        return str(startup_script)

    async def _create_tmux_session(self, env: dict[str, str]) -> None:
        """Create the tmux server and session"""
        loop = asyncio.get_event_loop()
        self.tmux_server = await loop.run_in_executor(None, libtmux.Server)
        assert self.tmux_server is not None

        if self.tmux_server is None:
            raise RuntimeError("tmux server is not available")

        tmux_server = self.tmux_server
        config = ServerConfig()
        self.tmux_session = await loop.run_in_executor(
            None,
            lambda: tmux_server.new_session(
                session_name=self.tmux_session_name,
                start_directory=self.working_directory,
                width=config.terminal_width,
                height=config.terminal_height,
                detach=True,
            ),
        )
        assert self.tmux_session is not None

        # Get the default window and pane
        self.tmux_window = self.tmux_session.windows[0]
        self.tmux_pane = self.tmux_window.panes[0]

        # Force resize to ensure correct dimensions
        await self._resize_session()

    async def _resize_session(self) -> None:
        """Resize the tmux session to ensure correct dimensions"""
        if self.tmux_session is None:
            raise RuntimeError("tmux session is not available")

        loop = asyncio.get_event_loop()
        tmux_session = self.tmux_session
        config = ServerConfig()
        await loop.run_in_executor(
            None,
            lambda: tmux_session.cmd(
                "resize-window",
                "-x",
                str(config.terminal_width),
                "-y",
                str(config.terminal_height),
            ),
        )

    async def _setup_terminal_output_capture(self) -> None:
        """Set up pipe-pane for terminal output capture with Android/Termux compatibility"""
        if self.output_stream_file.exists():
            self.output_stream_file.unlink()

        if self.tmux_pane is None:
            raise RuntimeError("tmux pane is not available")

        loop = asyncio.get_event_loop()
        tmux_pane = self.tmux_pane
        output_file = str(self.output_stream_file)

        try:
            # Try standard pipe-pane first
            await loop.run_in_executor(
                None,
                lambda: tmux_pane.cmd("pipe-pane", "-o", f"cat > {output_file}"),
            )

            # Test if pipe-pane is working by checking file creation and initial size
            await asyncio.sleep(0.2)
            if self.output_stream_file.exists():
                logger.debug(
                    f"Pipe-pane working correctly for session {self.session_id}"
                )
            else:
                logger.warning(
                    f"Pipe-pane stream file not created for session {self.session_id}"
                )

        except Exception as e:
            logger.warning(
                f"Failed to setup pipe-pane for session {self.session_id}: {e}"
            )
            logger.info("Web interface will fall back to direct tmux capture")

    async def _configure_session_environment(self, env: dict[str, str]) -> None:
        """Configure environment variables in the tmux session"""
        loop = asyncio.get_event_loop()

        # Set all environment variables that are not from the base system env
        base_env_keys = set(os.environ.keys())
        for key, value in env.items():
            # Only set custom env vars (not inherited from system) or important LC/LANG vars
            if key not in base_env_keys or key in ["LC_ALL", "LANG", "LC_MESSAGES", "PYTHONUNBUFFERED"]:
                def set_env(k: str, v: str) -> None:
                    assert self.tmux_session is not None
                    self.tmux_session.set_environment(k, v)

                # Use local variables to avoid closure issues
                def make_env_setter(k: str, v: str) -> Callable[[], None]:
                    return lambda: set_env(k, v)

                await loop.run_in_executor(None, make_env_setter(key, value))

    async def _execute_initial_command(self) -> None:
        """Execute the initial command if it's not just bash"""
        if self.command != "bash":
            if self.tmux_pane is None:
                raise RuntimeError("tmux pane is not available")

            loop = asyncio.get_event_loop()
            tmux_pane = self.tmux_pane
            command = self.command
            await loop.run_in_executor(
                None, lambda: tmux_pane.send_keys(command, enter=True)
            )

    def _finalize_initialization(self) -> None:
        """Finalize the initialization process"""
        self.is_active = True
        self.interaction_logger.log_session_state(
            "initialized",
            {
                "command": self.command,
                "tmux_session": self.tmux_session_name,
                "working_directory": self.working_directory,
            },
        )

    async def send_input(self, input_text: str, add_newline: bool = False) -> None:
        """Send input to the tmux session using libtmux"""
        if not self.is_active or not self.tmux_pane:
            raise RuntimeError("Session is not active")

        try:
            # Update timestamp for "since_input" mode
            self.last_input_timestamp = time.time()

            # Log input
            self.interaction_logger.log_input_sent(input_text, "tmux_input")

            # Send input to tmux pane
            loop = asyncio.get_event_loop()
            if self.tmux_pane is None:
                raise RuntimeError("tmux pane is not available")

            tmux_pane = self.tmux_pane  # Local variable for lambda
            await loop.run_in_executor(
                None, lambda: tmux_pane.send_keys(input_text, enter=add_newline)
            )

        except Exception as e:
            self.interaction_logger.log_error("input_send_error", str(e))
            raise RuntimeError(f"Failed to send input: {str(e)}") from e

    async def get_current_screen_content(self) -> str:
        """Get current visible screen content (clean, no ANSI sequences)"""
        if not self.is_active or not self.tmux_pane:
            return ""

        try:
            loop = asyncio.get_event_loop()
            tmux_pane = self.tmux_pane

            # Use libtmux's capture_pane() method instead of cmd()
            # This returns a list of strings representing the pane content
            content = await loop.run_in_executor(None, lambda: tmux_pane.capture_pane())

            if isinstance(content, list):
                raw_output = "\n".join(str(line) for line in content)
            else:
                raw_output = str(content) if content else ""

            # Remove ANSI escape sequences
            return _strip_ansi_sequences(raw_output)

        except Exception as e:
            logger.debug(f"Error getting screen content: {e}")
            return ""

    async def get_raw_terminal_output(self) -> str:
        """Get raw terminal output with ANSI sequences intact using libtmux"""
        if not self.is_active or not self.tmux_pane:
            return ""

        try:
            # Capture pane content with ANSI sequences using libtmux
            loop = asyncio.get_event_loop()
            tmux_pane = self.tmux_pane  # Local variable for lambda
            content = await loop.run_in_executor(
                None,
                lambda: tmux_pane.cmd("capture-pane", "-e", "-S", "-", "-E", "-", "-p"),
            )

            # cmd returns a tmux response object, get the output
            if hasattr(content, "stdout"):
                return str(content.stdout)
            elif isinstance(content, list) and len(content) > 0:
                return "\n".join(str(line) for line in content)

            return str(content) if content else ""

        except Exception as e:
            logger.debug(f"Error getting raw tmux output: {e}")
            return ""

    async def get_full_terminal_history(self) -> str:
        """Get full terminal history (ANSI sequences removed)"""
        raw_output = await self.get_raw_terminal_output()

        # Remove ANSI escape sequences for clean text
        clean_output = _strip_ansi_sequences(raw_output)

        return clean_output

    async def get_output_since_last_input(self) -> str:
        """Get output since last input command (approximated using stream file)"""
        if not self.is_active or not self.output_stream_file.exists():
            return ""

        try:
            # For simplicity, return recent output from stream file
            # This is an approximation since tmux doesn't have timestamp-based history
            with open(self.output_stream_file) as f:
                content = f.read()

            # Remove ANSI escape sequences
            clean_content = _strip_ansi_sequences(content)

            # For now, return last APPROX_LINES_SINCE_INPUT lines as approximation
            APPROX_LINES_SINCE_INPUT = 50
            lines = clean_content.split("\n")
            return (
                "\n".join(lines[-APPROX_LINES_SINCE_INPUT:])
                if len(lines) > APPROX_LINES_SINCE_INPUT
                else clean_content
            )

        except Exception as e:
            logger.debug(f"Error getting output since timestamp: {e}")
            return ""

    async def get_tail_output(self, line_count: int) -> str:
        """Get last N lines of terminal output"""
        if not self.is_active or not self.tmux_pane:
            return ""

        try:
            loop = asyncio.get_event_loop()
            tmux_pane = self.tmux_pane
            content = await loop.run_in_executor(
                None,
                lambda: tmux_pane.cmd(
                    "capture-pane", "-e", "-S", f"-{line_count}", "-p"
                ),
            )

            if hasattr(content, "stdout"):
                raw_output = str(content.stdout)
            elif isinstance(content, list) and len(content) > 0:
                raw_output = "\n".join(str(line) for line in content)
            else:
                raw_output = str(content) if content else ""

            # Remove ANSI escape sequences
            return _strip_ansi_sequences(raw_output)

        except Exception as e:
            logger.debug(f"Error getting tail output: {e}")
            return ""

    async def get_content_by_mode(
        self, content_mode: str, line_count: int | None = None
    ) -> str:
        """Get terminal content based on the specified mode"""
        if content_mode == "since_input":
            return await self.get_output_since_last_input()
        elif content_mode == "history":
            return await self.get_full_terminal_history()
        elif content_mode == "tail" and line_count:
            return await self.get_tail_output(line_count)
        else:
            # Default to screen mode (including when content_mode == "screen")
            return await self.get_current_screen_content()

    async def terminate(self) -> None:
        """Terminate the tmux session using libtmux"""
        if not self.is_active:
            return

        try:
            final_output = await self.get_full_terminal_history()
            await self._kill_tmux_session()
            self._log_session_termination(final_output)
        except Exception as e:
            logger.debug(f"Error terminating tmux session: {e}")
        finally:
            self._cleanup_session_resources()

    async def _kill_tmux_session(self) -> None:
        """Kill the tmux session"""
        if self.tmux_session:
            loop = asyncio.get_event_loop()
            tmux_session = self.tmux_session
            await loop.run_in_executor(None, lambda: tmux_session.kill())

    def _log_session_termination(self, final_output: str) -> None:
        """Log the session termination"""
        self.interaction_logger.close_session(
            exit_code=self.exit_code, final_output=final_output
        )

    def _cleanup_session_resources(self) -> None:
        """Clean up all session resources"""
        self._reset_session_state()
        self._cleanup_output_stream()
        self._cleanup_history_isolation()

    def _reset_session_state(self) -> None:
        """Reset session state and tmux objects"""
        self.is_active = False
        self.tmux_pane = None
        self.tmux_window = None
        self.tmux_session = None
        self.tmux_server = None

    def _cleanup_output_stream(self) -> None:
        """Clean up output stream file"""
        try:
            if self.output_stream_file.exists():
                self.output_stream_file.unlink()
        except Exception:
            pass  # Don't fail termination if cleanup fails

    def _cleanup_history_isolation(self) -> None:
        """Clean up history isolation files and directory"""
        if not (self.history_dir and self.history_dir.exists()):
            return

        try:
            import shutil
            shutil.rmtree(self.history_dir, ignore_errors=True)
            logger.debug(f"Cleaned up history directory for session {self.session_id}")
        except Exception as e:
            logger.debug(f"Failed to clean up history directory: {e}")
            self._cleanup_individual_history_files()

    def _cleanup_individual_history_files(self) -> None:
        """Clean up individual history files if directory removal fails"""
        try:
            for hist_file in self.isolated_history_files.values():
                if hist_file.exists():
                    hist_file.unlink()
        except Exception:
            pass

    def is_process_alive(self) -> bool:
        """Check if the tmux session is still active using libtmux"""
        if not self.is_active or not self.tmux_session:
            return False

        try:
            # Refresh session info and check if it still exists
            self.tmux_session.refresh()
            return True
        except Exception:
            return False

    def get_exit_code(self) -> int | None:
        """Get the process exit code if available"""
        return self.exit_code

    def has_process_finished(self) -> bool:
        """Check if the process has completed"""
        return not self.is_process_alive()

    def get_log_files(self) -> dict[str, str]:
        """Get paths to all log files for this session"""
        return self.interaction_logger.get_log_files()

    async def await_output_pattern(
        self, pattern: str, timeout: float = 10.0
    ) -> tuple[str | None, float]:
        """Wait for a specific regex pattern to appear in terminal output

        Args:
            pattern: Regular expression pattern to match
            timeout: Maximum time to wait in seconds

        Returns:
            tuple: (matched_text, elapsed_time) - matched_text is None if timeout occurs
        """
        if not self.is_active:
            return None, 0.0

        start_time = time.time()
        compiled_pattern = re.compile(pattern)

        # Poll interval in seconds - balance between responsiveness and CPU usage
        poll_interval = 0.1

        while time.time() - start_time < timeout:
            try:
                # Get current screen content
                current_content = await self.get_current_screen_content()

                # Search for pattern
                match = compiled_pattern.search(current_content)
                if match:
                    elapsed_time = time.time() - start_time
                    return match.group(0), elapsed_time

                # Wait before next check
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.debug(
                    f"Error checking for pattern in session {self.session_id}: {e}"
                )
                await asyncio.sleep(poll_interval)

        # Timeout occurred
        elapsed_time = time.time() - start_time
        return None, elapsed_time
