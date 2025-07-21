import asyncio
import logging
import os
import signal
from typing import Any

import pexpect

from .interaction_logger import InteractionLogger


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
        self.command = self._wrap_command(command)
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

    def _wrap_command(self, command: str) -> str:
        """Wrap command in sh -c to ensure shell environment and consistent behavior"""
        if command.strip().startswith("sh -c"):
            return command

        # Escape single quotes in the command and wrap in sh -c
        escaped = command.replace("'", "'\\''")
        return f"sh -c '{escaped}'"

    async def initialize(self) -> None:
        """Initialize the interactive session"""
        try:
            # Log command execution
            self.interaction_logger.log_command_execution(
                command=self.command,
                working_dir=self.working_directory
            )

            # Set up environment
            env = dict(os.environ)

            # Add standard locale settings for consistent command output
            # This ensures commands like 'ls', 'ps', 'df' return predictable English output
            # Also add PYTHONUNBUFFERED for automatic Python buffering handling
            env.update({
                'LC_ALL': 'C.UTF-8',
                'LANG': 'C.UTF-8',
                'LC_MESSAGES': 'C',
                'PYTHONUNBUFFERED': '1',  # Universal Python unbuffering
            })

            # User-provided environment variables override defaults
            env.update(self.environment)

            # Set up automatic output capture for better buffering handling
            import io
            self.output_capture = io.StringIO()

            # Spawn the process with optimized buffering settings
            self.process = pexpect.spawn(
                self.command,
                timeout=self.timeout,
                env=env,  # type: ignore
                cwd=self.working_directory,
                encoding="utf-8",
                codec_errors="replace",
                maxread=1,  # Character-by-character reading for real-time output
                searchwindowsize=1000,  # Optimize pattern matching
                echo=False,  # Reduce duplicate output
                use_poll=True,  # Better I/O performance on Linux
            )

            # Enable automatic output logging to our capture buffer
            self.process.logfile_read = self.output_capture

            self.is_active = True

            # Log session state
            self.interaction_logger.log_session_state("initialized", {
                "command": self.command,
                "timeout": self.timeout,
                "environment_vars": len(self.environment),
                "working_directory": self.working_directory
            })

            # Capture initial screen content and store in buffer
            await asyncio.sleep(0.5)  # Brief pause for process to start
            initial_content = await self.get_current_screen_content()
            if initial_content:
                self.interaction_logger.log_screen_content(initial_content, "initial_screen")
                # Also store in output buffer for get_output()
                self.output_buffer.append(initial_content)

        except Exception as e:
            self.interaction_logger.log_error("initialization_error", str(e))
            raise RuntimeError(f"Failed to initialize session: {str(e)}") from e

    async def expect_and_respond(
        self,
        pattern: str | list[str],
        response: str,
        timeout: int | None = None,
        case_sensitive: bool = False,
        delay_before_response: float = 0.0,
    ) -> dict[str, Any]:
        """Wait for pattern and send response"""

        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        # Prepare patterns with case sensitivity handling
        if isinstance(pattern, str):
            patterns = [pattern]
        else:
            patterns = pattern

        # Apply case insensitive matching if requested
        if not case_sensitive:
            # Use (?i) flag for case insensitive regex patterns
            processed_patterns = []
            for p in patterns:
                if not p.startswith("(?i)"):
                    processed_patterns.append(f"(?i){p}")
                else:
                    processed_patterns.append(p)
            patterns = processed_patterns

        # Add EOF and TIMEOUT to patterns
        patterns_with_special: list[Any] = patterns + [pexpect.EOF, pexpect.TIMEOUT]

        # Set timeout with default fallback
        original_timeout = self.process.timeout
        effective_timeout = timeout or 30  # Default to 30 seconds
        self.process.timeout = effective_timeout

        # Log the wait start
        pattern_str = patterns[0] if len(patterns) == 1 else str(patterns)
        self.interaction_logger.log_wait_start(pattern_str, effective_timeout)

        # Capture screen content before waiting
        pre_wait_content = await self.get_current_screen_content()
        if pre_wait_content:
            self.interaction_logger.log_screen_content(pre_wait_content, "before_expect")

        # First check if pattern already exists in current output
        current_output = "\n".join(self.output_buffer) + "\n" + (pre_wait_content or "")

        import re
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, current_output)
                if match:
                    # Pattern found in existing content - send response immediately
                    matched_text = match.group()
                    before_text = current_output[:match.start()]
                    after_text = current_output[match.start():]

                    self.interaction_logger.log_wait_result(
                        success=True,
                        matched_text=matched_text,
                        timeout_occurred=False
                    )

                    if response:
                        if delay_before_response > 0:
                            await asyncio.sleep(delay_before_response)

                        self.interaction_logger.log_input_sent(response, "expect_response")

                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.process.sendline, response)
                        self.command_history.append(response)
                        self.last_command = response

                        # Capture screen after input
                        await asyncio.sleep(0.2)
                        post_input_content = await self.get_current_screen_content()
                        if post_input_content:
                            self.interaction_logger.log_screen_content(post_input_content, "after_input")
                            # Also add to buffer
                            self.output_buffer.append(post_input_content)

                    return {
                        "success": True,
                        "matched_pattern": pattern,
                        "matched_index": i,
                        "before": before_text,
                        "after": after_text,
                        "response_sent": response,
                        "timeout_used": 0,  # No waiting was needed
                    }
            except re.error:
                # Invalid regex pattern, continue to next pattern
                continue

        try:
            # Wait for pattern with retry logic
            # Run pexpect.expect in thread pool to avoid blocking async event loop
            loop = asyncio.get_event_loop()
            if self.process is None:
                raise RuntimeError("Process is None")
            process = self.process  # Type narrowing for mypy
            index = await loop.run_in_executor(None, lambda: process.expect(patterns_with_special))

            # Process result
            if index < len(patterns):  # Pattern matched
                matched_pattern = patterns[index]
                before_text = str(self.process.before or "")
                after_text = str(self.process.after or "")

                # Store output
                self.output_buffer.append(before_text)
                if after_text:
                    self.output_buffer.append(after_text)

                # Log the successful match
                self.interaction_logger.log_wait_result(
                    success=True,
                    matched_text=after_text,
                    timeout_occurred=False
                )

                # Capture screen after match
                post_match_content = await self.get_current_screen_content()
                if post_match_content:
                    self.interaction_logger.log_screen_content(post_match_content, "after_match")

                # Send response if provided
                if response:
                    # Wait before sending response if delay is specified
                    if delay_before_response > 0:
                        await asyncio.sleep(delay_before_response)

                    # Log the input being sent
                    self.interaction_logger.log_input_sent(response, "expect_response")

                    # Run sendline in thread pool to avoid blocking async event loop
                    await loop.run_in_executor(None, self.process.sendline, response)
                    self.command_history.append(response)
                    self.last_command = response

                    # Capture screen after input
                    await asyncio.sleep(0.2)  # Brief pause for response
                    post_input_content = await self.get_current_screen_content()
                    if post_input_content:
                        self.interaction_logger.log_screen_content(post_input_content, "after_input")

                return {
                    "success": True,
                    "matched_pattern": matched_pattern,
                    "matched_index": index,
                    "before": before_text,
                    "after": after_text,
                    "response_sent": response,
                    "timeout_used": effective_timeout,
                }

            elif index == len(patterns):  # EOF
                self.is_active = False
                self.exit_code = self.process.exitstatus
                return {
                    "success": False,
                    "reason": "process_ended",
                    "exit_code": self.exit_code,
                    "before": self.process.before or "",
                    "timeout_used": effective_timeout,
                }

            else:  # TIMEOUT
                # Provide more context for timeout failures
                recent_output = self.process.before or ""

                # Log the timeout
                self.interaction_logger.log_wait_result(
                    success=False,
                    matched_text=None,
                    timeout_occurred=True
                )

                # Capture final screen content on timeout
                timeout_content = await self.get_current_screen_content()
                if timeout_content:
                    self.interaction_logger.log_screen_content(timeout_content, "timeout_screen")

                return {
                    "success": False,
                    "reason": "timeout",
                    "before": recent_output,
                    "timeout_used": effective_timeout,
                    "patterns_tried": patterns,
                    "suggestion": "Consider increasing timeout or adjusting patterns",
                }

        except (pexpect.exceptions.TIMEOUT, OSError) as e:
            return {
                "success": False,
                "reason": "expect_error",
                "error": str(e),
                "timeout_used": effective_timeout,
                "suggestion": "Check if process is responsive or adjust patterns",
            }
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e),
                "timeout_used": effective_timeout,
                "suggestion": "Check session state and command validity",
            }
        finally:
            # Always restore original timeout
            self.process.timeout = original_timeout

    async def send_input(self, input_text: str, add_newline: bool = True) -> None:
        """Send input to the session"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        loop = asyncio.get_event_loop()

        try:
            # Log the input being sent
            self.interaction_logger.log_input_sent(
                input_text,
                "direct_input" + ("_with_newline" if add_newline else "_no_newline")
            )

            # Capture screen before input
            pre_input_content = await self.get_current_screen_content()
            if pre_input_content:
                self.interaction_logger.log_screen_content(pre_input_content, "before_send_input")

            if add_newline:
                await loop.run_in_executor(None, self.process.sendline, input_text)
            else:
                await loop.run_in_executor(None, self.process.send, input_text)

            self.command_history.append(input_text)
            self.last_command = input_text

            # Capture screen after input (with brief delay)
            await asyncio.sleep(0.3)
            post_input_content = await self.get_current_screen_content()
            if post_input_content:
                self.interaction_logger.log_screen_content(post_input_content, "after_send_input")
                # Add the new content to output buffer
                self.output_buffer.append(post_input_content)

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
                    # Read any available output
                    result = process.read_nonblocking(size=65536)
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
        """Get output from the automatic capture and session buffer"""
        # Use pexpect's automatic output capture first
        output_parts = []

        # Get automatically captured output
        if hasattr(self, 'output_capture') and self.output_capture:
            captured = self.output_capture.getvalue()
            if captured:
                output_parts.append(captured)

        # Add manual buffer as fallback
        if self.output_buffer:
            output_parts.extend(self.output_buffer)

        # Try to capture any remaining current screen content
        current_content = await self.get_current_screen_content()
        if current_content and current_content.strip():
            output_parts.append(current_content)

        full_output = "\n".join(output_parts)

        if lines is None:
            return full_output
        else:
            # Split by lines and return last N lines
            output_lines = full_output.split('\n')
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
                    exit_code=exit_code,
                    final_output=final_content
                )

            except (pexpect.exceptions.TIMEOUT, OSError):
                # Force kill if needed
                self.process.kill(signal.SIGKILL)

                # Log forced termination
                self.interaction_logger.log_session_state("force_killed", {
                    "reason": "graceful_termination_failed"
                })
                self.interaction_logger.close_session(
                    exit_code=-9,  # SIGKILL
                    final_output=""
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

    async def wait_for_completion_or_input(self, timeout: float = 5.0) -> tuple[bool, str]:
        """
        Wait for either:
        1. Process to complete (returns True, output)
        2. Process to be waiting for input (returns False, output)
        3. Timeout (returns False, output)
        
        Returns (process_finished, output)
        """
        if not self.process or not self.is_active:
            return True, ""
            
        start_time = asyncio.get_event_loop().time()
        output_parts = []
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Check if process has finished
            if not self.process.isalive():
                # Process has terminated, get final output
                final_output = await self.get_output()
                return True, final_output
            
            # Try to read any new output without blocking
            try:
                current_content = await self.get_current_screen_content()
                if current_content and current_content.strip():
                    output_parts.append(current_content)
            except Exception:
                pass
            
            # Short sleep to avoid busy waiting
            await asyncio.sleep(0.1)
        
        # Timeout reached - assume process is waiting for input
        all_output = await self.get_output()
        return False, all_output
