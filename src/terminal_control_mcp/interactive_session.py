import asyncio
import logging
import os
import signal

import pexpect

from .interaction_logger import InteractionLogger
from .utils import wrap_command


class InteractiveSession:
    """Represents a single interactive terminal session"""

    def __init__(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
        environment: dict[str, str] | None = None,
        working_directory: str | None = None,
    ):
        self.session_id = session_id
        # Wrap all commands in sh -c to ensure shell environment and consistent behavior
        self.command = wrap_command(command)
        self.timeout = timeout
        self.environment = environment or {}
        self.working_directory = working_directory

        self.process: pexpect.spawn | None = None
        self.output_buffer: list[str] = []
        self.is_active = False
        self.exit_code: int | None = None

        # State tracking
        self.last_command: str | None = None
        self.command_history: list[str] = []

        # Interaction logging
        self.interaction_logger = InteractionLogger(session_id)

    async def initialize(self) -> None:
        """Initialize the interactive session"""
        try:
            # Log command execution
            self.interaction_logger.log_command_execution(
                command=self.command, working_dir=self.working_directory
            )

            # Set up environment
            env = dict(os.environ)

            # Add standard locale settings for consistent command output
            # This ensures commands like 'ls', 'ps', 'df' return predictable English output
            # Also add PYTHONUNBUFFERED for automatic Python buffering handling
            env.update(
                {
                    "LC_ALL": "C.UTF-8",
                    "LANG": "C.UTF-8",
                    "LC_MESSAGES": "C",
                    "PYTHONUNBUFFERED": "1",  # Universal Python unbuffering
                }
            )

            # User-provided environment variables override defaults
            env.update(self.environment)

            # Set up automatic output capture for better buffering handling
            import io

            self.output_capture = io.StringIO()

            # Spawn the process with simplified settings (no pattern matching optimization needed)
            self.process = pexpect.spawn(
                self.command,
                timeout=self.timeout,  # Only for process startup
                env=env,  # type: ignore
                cwd=self.working_directory,
                encoding="utf-8",
                codec_errors="replace",
                echo=True,  # Show input commands in output
                use_poll=True,  # Better I/O performance on Linux
            )

            # Enable automatic output logging to our capture buffer
            self.process.logfile_read = self.output_capture

            self.is_active = True

            # Log session state
            self.interaction_logger.log_session_state(
                "initialized",
                {
                    "command": self.command,
                    "timeout": self.timeout,
                    "environment_vars": len(self.environment),
                    "working_directory": self.working_directory,
                },
            )

            # Capture initial screen content and store in buffer
            await asyncio.sleep(0.5)  # Brief pause for process to start
            initial_content = await self.get_current_screen_content()
            if initial_content:
                self.interaction_logger.log_screen_content(
                    initial_content, "initial_screen"
                )
                # Also store in output buffer for get_output()
                self.output_buffer.append(initial_content)

        except Exception as e:
            self.interaction_logger.log_error("initialization_error", str(e))
            raise RuntimeError(f"Failed to initialize session: {str(e)}") from e

    async def send_input(self, input_text: str, add_newline: bool = True) -> None:
        """Send input to the session"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        try:
            await self._log_and_capture_before_input(input_text, add_newline)
            await self._execute_input_command(input_text, add_newline)
            self._update_command_history(input_text)
            await self._capture_after_input()
        except Exception as e:
            self.interaction_logger.log_error("input_send_error", str(e))
            raise RuntimeError(f"Failed to send input: {str(e)}") from e

    async def send_signal(self, sig: int) -> None:
        """Send signal to the process"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        self.process.kill(sig)

    async def get_current_screen_content(self) -> str:
        """Get the current terminal screen content"""
        if not self.process or not self.is_active:
            return ""

        try:
            # Try to read any available output without blocking
            loop = asyncio.get_event_loop()

            # Use a very short timeout to get current content
            def _read_nonblocking() -> str:
                if self.process is None:
                    return ""
                process = self.process  # Type narrowing for mypy
                try:
                    # Read any available output with a very short timeout
                    result = process.read_nonblocking(size=65536, timeout=0.1)
                    return str(result) if result is not None else ""
                except (pexpect.TIMEOUT, pexpect.EOF):
                    # Return what we have so far
                    before = process.before
                    return str(before) if before is not None else ""
                except Exception:
                    return ""

            content = await loop.run_in_executor(None, _read_nonblocking)
            return content
        except Exception as e:
            # Log thread pool errors for debugging
            logger = logging.getLogger(__name__)
            logger.debug(f"Thread pool error reading screen content: {e}")
            return ""

    async def get_output(self, lines: int | None = None) -> str:
        """Get output from the automatic capture, prioritizing most recent content"""
        # Priority: automatic capture > current screen content > manual buffer

        # First try automatic capture (most reliable for both interactive and non-interactive)
        if hasattr(self, "output_capture") and self.output_capture:
            captured = self.output_capture.getvalue()
            if captured and captured.strip():
                full_output = captured
            else:
                # Fallback to current screen content
                current_content = await self.get_current_screen_content()
                if current_content and current_content.strip():
                    full_output = current_content
                else:
                    # Final fallback to manual buffer
                    full_output = (
                        "\n".join(self.output_buffer) if self.output_buffer else ""
                    )
        else:
            # No automatic capture, try current screen content then manual buffer
            current_content = await self.get_current_screen_content()
            if current_content and current_content.strip():
                full_output = current_content
            else:
                full_output = (
                    "\n".join(self.output_buffer) if self.output_buffer else ""
                )

        if lines is None:
            return full_output
        else:
            # Split by lines and return last N lines
            output_lines = full_output.split("\n")
            return "\n".join(output_lines[-lines:])

    async def clear_output_buffer(self) -> None:
        """Clear the output buffer"""
        self.output_buffer.clear()

    async def terminate(self) -> None:
        """Terminate the session"""
        if self.process and self.is_active:
            try:
                # Capture final screen content before termination
                final_content = await self.get_current_screen_content()

                # Try graceful termination first
                self.process.terminate()
                self.process.wait()

                # Log session end
                exit_code = self.process.exitstatus if self.process else None
                self.interaction_logger.close_session(
                    exit_code=exit_code, final_output=final_content
                )

            except (pexpect.exceptions.TIMEOUT, OSError):
                # Force kill if needed
                self.process.kill(signal.SIGKILL)

                # Log forced termination
                self.interaction_logger.log_session_state(
                    "force_killed", {"reason": "graceful_termination_failed"}
                )
                self.interaction_logger.close_session(
                    exit_code=-9, final_output=""  # SIGKILL
                )

            finally:
                self.is_active = False
                if hasattr(self.process, "logfile_read") and self.process.logfile_read:
                    self.process.logfile_read.close()  # type: ignore

    def get_log_files(self) -> dict[str, str]:
        """Get paths to all log files for this session"""
        return self.interaction_logger.get_log_files()

    def is_process_alive(self) -> bool:
        """Check if the process is still running"""
        if not self.process or not self.is_active:
            return False
        return self.process.isalive()

    def get_exit_code(self) -> int | None:
        """Get the process exit code if it has terminated"""
        if not self.process:
            return None
        return self.process.exitstatus

    def has_process_finished(self) -> bool:
        """Check if the process has completed (either successfully or with error)"""
        if not self.process or not self.is_active:
            return True

        # Check if process is still alive
        if not self.process.isalive():
            return True

        return False

    async def _log_and_capture_before_input(
        self, input_text: str, add_newline: bool
    ) -> None:
        """Log input and capture screen before sending"""
        log_type = "direct_input" + ("_with_newline" if add_newline else "_no_newline")
        self.interaction_logger.log_input_sent(input_text, log_type)

        pre_input_content = await self.get_current_screen_content()
        if pre_input_content:
            self.interaction_logger.log_screen_content(
                pre_input_content, "before_send_input"
            )

    async def _execute_input_command(self, input_text: str, add_newline: bool) -> None:
        """Execute the input command via pexpect"""
        if not self.process:
            raise RuntimeError("Process is None")

        loop = asyncio.get_event_loop()
        if add_newline:
            await loop.run_in_executor(None, self.process.sendline, input_text)
        else:
            await loop.run_in_executor(None, self.process.send, input_text)

    def _update_command_history(self, input_text: str) -> None:
        """Update command history with new input"""
        self.command_history.append(input_text)
        self.last_command = input_text

    async def _capture_after_input(self) -> None:
        """Capture screen content after input with delay"""
        await asyncio.sleep(0.3)
        post_input_content = await self.get_current_screen_content()
        if post_input_content:
            self.interaction_logger.log_screen_content(
                post_input_content, "after_send_input"
            )
            self.output_buffer.append(post_input_content)
