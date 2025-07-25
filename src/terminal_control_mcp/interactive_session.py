import asyncio
import logging
import os
from pathlib import Path

import libtmux

from .interaction_logger import InteractionLogger

logger = logging.getLogger(__name__)


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

        # tmux session name (must be unique)
        self.tmux_session_name = f"mcp_{session_id}"

        # Terminal output stream file for web interface
        self.output_stream_file = Path(f"/tmp/tmux_stream_{session_id}.log")
        self.stream_position = 0  # Track position for incremental reads

        self.is_active = False
        self.exit_code: int | None = None

        # libtmux objects
        self.tmux_server: libtmux.Server | None = None
        self.tmux_session: libtmux.Session | None = None
        self.tmux_window: libtmux.Window | None = None
        self.tmux_pane: libtmux.Pane | None = None

        # Interaction logging
        self.interaction_logger = InteractionLogger(session_id)

    async def initialize(self) -> None:
        """Initialize the tmux session using libtmux"""
        try:
            # Log command execution
            self.interaction_logger.log_command_execution(
                command=self.command, working_dir=self.working_directory
            )

            # Set up environment
            env = dict(os.environ)
            env.update(
                {
                    "LC_ALL": "C.UTF-8",
                    "LANG": "C.UTF-8",
                    "LC_MESSAGES": "C",
                    "PYTHONUNBUFFERED": "1",
                }
            )
            env.update(self.environment)

            # Create tmux server connection
            loop = asyncio.get_event_loop()
            self.tmux_server = await loop.run_in_executor(None, libtmux.Server)
            assert self.tmux_server is not None

            # Create new session with fixed dimensions
            self.tmux_session = await loop.run_in_executor(
                None,
                lambda: self.tmux_server.new_session(
                    session_name=self.tmux_session_name,
                    start_directory=self.working_directory,
                    width=120,
                    height=30,
                    detach=True,
                ),
            )
            assert self.tmux_session is not None

            # Get the default window and pane
            self.tmux_window = self.tmux_session.windows[0]
            self.tmux_pane = self.tmux_window.panes[0]

            # Force resize the session and pane to ensure correct dimensions
            await loop.run_in_executor(
                None,
                lambda: self.tmux_session.cmd("resize-window", "-x", "120", "-y", "30"),
            )

            # Clear any existing stream file and set up pipe-pane for raw terminal output
            if self.output_stream_file.exists():
                self.output_stream_file.unlink()

            # Use pipe-pane to capture all terminal output to file
            await loop.run_in_executor(
                None,
                lambda: self.tmux_pane.cmd(
                    "pipe-pane", "-o", f"cat > {self.output_stream_file}"
                ),
            )

            # Set environment variables in the session
            for key, value in env.items():
                if key not in ["LC_ALL", "LANG", "LC_MESSAGES", "PYTHONUNBUFFERED"]:
                    continue  # Only set our specific env vars
                
                def set_env(k: str, v: str) -> None:
                    assert self.tmux_session is not None
                    self.tmux_session.set_environment(k, v)
                
                await loop.run_in_executor(None, lambda: set_env(key, value))

            # Send the command to the pane
            if self.command != "bash":  # If not just bash, run the command
                await loop.run_in_executor(
                    None, lambda: self.tmux_pane.send_keys(self.command, enter=True)
                )

            self.is_active = True

            # Log session state
            self.interaction_logger.log_session_state(
                "initialized",
                {
                    "command": self.command,
                    "tmux_session": self.tmux_session_name,
                    "working_directory": self.working_directory,
                },
            )

            # Brief pause for session to fully initialize
            await asyncio.sleep(0.5)

        except Exception as e:
            self.interaction_logger.log_error("initialization_error", str(e))
            raise RuntimeError(f"Failed to initialize tmux session: {str(e)}") from e

    async def send_input(self, input_text: str, add_newline: bool = False) -> None:
        """Send input to the tmux session using libtmux"""
        if not self.is_active or not self.tmux_pane:
            raise RuntimeError("Session is not active")

        try:
            # Log input
            self.interaction_logger.log_input_sent(input_text, "tmux_input")

            # Send input to tmux pane
            loop = asyncio.get_event_loop()
            assert self.tmux_pane is not None
            await loop.run_in_executor(
                None, lambda: self.tmux_pane.send_keys(input_text, enter=add_newline)
            )

        except Exception as e:
            self.interaction_logger.log_error("input_send_error", str(e))
            raise RuntimeError(f"Failed to send input: {str(e)}") from e

    async def get_raw_output(self) -> str:
        """Get raw terminal output with ANSI sequences intact using libtmux"""
        if not self.is_active or not self.tmux_pane:
            return ""

        try:
            # Capture pane content with ANSI sequences using libtmux
            loop = asyncio.get_event_loop()
            assert self.tmux_pane is not None
            content = await loop.run_in_executor(
                None,
                lambda: self.tmux_pane.cmd(
                    "capture-pane", "-e", "-S", "-", "-E", "-", "-p"
                ),
            )

            # cmd returns a tmux response object, get the output
            if hasattr(content, "stdout"):
                return str(content.stdout)
            elif isinstance(content, list) and len(content) > 0:
                return "\n".join(str(line) for line in content)

            return str(content) if content else ""

        except Exception as e:
            logger.debug(f"Error getting tmux output: {e}")
            return ""

    async def get_output(self) -> str:
        """Get clean terminal output (ANSI sequences removed)"""
        raw_output = await self.get_raw_output()

        # Remove ANSI escape sequences for clean text
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_output = ansi_escape.sub("", raw_output)

        return clean_output

    async def get_stream_output(self) -> str:
        """Get incremental raw terminal stream output for web interface"""
        if not self.is_active or not self.output_stream_file.exists():
            return ""

        try:
            # Read new content from stream file
            with open(self.output_stream_file, "rb") as f:
                f.seek(self.stream_position)
                new_data = f.read()
                self.stream_position = f.tell()

            return new_data.decode("utf-8", errors="replace")

        except Exception as e:
            logger.debug(f"Error reading stream output: {e}")
            return ""

    async def terminate(self) -> None:
        """Terminate the tmux session using libtmux"""
        if not self.is_active:
            return

        try:
            # Get final output before terminating
            final_output = await self.get_output()

            # Kill the tmux session using libtmux
            if self.tmux_session:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self.tmux_session.kill())

            # Log session end
            self.interaction_logger.close_session(
                exit_code=self.exit_code, final_output=final_output
            )

        except Exception as e:
            logger.debug(f"Error terminating tmux session: {e}")

        finally:
            self.is_active = False
            self.tmux_pane = None
            self.tmux_window = None
            self.tmux_session = None
            self.tmux_server = None

            # Clean up stream file
            try:
                if self.output_stream_file.exists():
                    self.output_stream_file.unlink()
            except Exception:
                pass  # Don't fail termination if cleanup fails

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
