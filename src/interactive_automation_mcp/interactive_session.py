import asyncio
import logging
import os
import signal
from typing import Any

import pexpect

from .interaction_logger import InteractionLogger
from .types import ExpectAndRespondResult
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
    ) -> ExpectAndRespondResult:
        """Wait for pattern and send response"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        # Setup and preparation
        context = self._setup_expect_context(pattern, case_sensitive, timeout)

        # Check for existing matches first
        existing_match = await self._check_for_existing_match(
            context, response, delay_before_response
        )
        if existing_match:
            self.process.timeout = context.original_timeout
            return existing_match

        # Process with pexpect
        return await self._execute_expect_with_cleanup(
            context, response, delay_before_response
        )

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
        last_output = ""
        stable_count = 0
        
        # Enhanced detection: look for process completion OR stable output indicating waiting for input
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Check if process has finished - this should be fast
            if not self.process.isalive():
                # Process has terminated, get final output
                final_output = await self.get_output()
                return True, final_output

            # Check if output has stabilized (indicating process is waiting for input)
            current_output = await self._get_output_fast()
            if current_output == last_output:
                stable_count += 1
                # If output hasn't changed for multiple checks, likely waiting for input
                if stable_count >= 4:  # 4 * 0.1s = 0.4s of stable output
                    return False, current_output
            else:
                # Output is still changing, reset counter
                stable_count = 0
                last_output = current_output

            # Shorter sleep for more responsive detection
            await asyncio.sleep(0.1)  # Check every 100ms
            
        # Timeout reached - assume process is waiting for input
        all_output = await self._get_output_fast()
        return False, all_output

    async def _get_output_fast(self) -> str:
        """Get output without calling get_current_screen_content (which can hang)"""
        output_parts = []

        # Get automatically captured output
        if hasattr(self, 'output_capture') and self.output_capture:
            captured = self.output_capture.getvalue()
            if captured:
                output_parts.append(captured)

        # Add manual buffer as fallback
        if self.output_buffer:
            output_parts.extend(self.output_buffer)

        # Don't call get_current_screen_content() here as it can hang
        return "\n".join(output_parts)

    def _setup_expect_context(
        self, pattern: str | list[str], case_sensitive: bool, timeout: int | None
    ) -> Any:
        """Setup context for expect operation"""
        patterns = self._prepare_patterns(pattern, case_sensitive)
        patterns_with_special = patterns + [pexpect.EOF, pexpect.TIMEOUT]

        original_timeout = self.process.timeout if self.process else 30
        effective_timeout = timeout or 30

        if self.process:
            self.process.timeout = effective_timeout

        pattern_str = patterns[0] if len(patterns) == 1 else str(patterns)
        self.interaction_logger.log_wait_start(pattern_str, effective_timeout)

        # Create context object
        from types import SimpleNamespace
        return SimpleNamespace(
            patterns=patterns,
            patterns_with_special=patterns_with_special,
            original_timeout=original_timeout,
            effective_timeout=effective_timeout
        )

    async def _check_for_existing_match(
        self, context: Any, response: str, delay_before_response: float
    ) -> ExpectAndRespondResult | None:
        """Check if pattern already exists in current output"""
        # Use fast output method to avoid hanging on interactive processes
        pre_wait_content = await self._get_output_fast()
        if pre_wait_content:
            self.interaction_logger.log_screen_content(pre_wait_content, "before_expect")

        return await self._check_existing_pattern_match(
            context.patterns, pre_wait_content, response, delay_before_response
        )

    async def _execute_expect_with_cleanup(
        self, context: Any, response: str, delay_before_response: float
    ) -> ExpectAndRespondResult:
        """Execute expect with proper cleanup"""
        try:
            return await self._wait_and_process_pattern(
                context.patterns_with_special, context.patterns, response,
                delay_before_response, context.effective_timeout
            )
        except (pexpect.exceptions.TIMEOUT, OSError) as e:
            return self._create_error_result(
                "expect_error", str(e), context.effective_timeout,
                "Check if process is responsive or adjust patterns"
            )
        except Exception as e:
            return self._create_error_result(
                "error", str(e), context.effective_timeout,
                "Check session state and command validity"
            )
        finally:
            if self.process:
                self.process.timeout = context.original_timeout

    def _create_error_result(
        self, reason: str, error: str, timeout_used: int, suggestion: str
    ) -> ExpectAndRespondResult:
        """Create standardized error result"""
        return {
            "success": False,
            "reason": reason,
            "error": error,
            "timeout_used": timeout_used,
            "suggestion": suggestion,
        }

    def _prepare_patterns(self, pattern: str | list[str], case_sensitive: bool) -> list[str]:
        """Prepare patterns with case sensitivity handling"""
        if isinstance(pattern, str):
            patterns = [pattern]
        else:
            patterns = pattern

        if not case_sensitive:
            # Use (?i) flag for case insensitive regex patterns
            processed_patterns = []
            for p in patterns:
                if not p.startswith("(?i)"):
                    processed_patterns.append(f"(?i){p}")
                else:
                    processed_patterns.append(p)
            patterns = processed_patterns

        return patterns

    async def _check_existing_pattern_match(
        self,
        patterns: list[str],
        pre_wait_content: str | None,
        response: str,
        delay_before_response: float
    ) -> ExpectAndRespondResult | None:
        """Check if pattern already exists in current output"""
        current_output = "\n".join(self.output_buffer) + "\n" + (pre_wait_content or "")

        import re
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, current_output)
                if match:
                    # Pattern found in existing content
                    matched_text = match.group()
                    before_text = current_output[:match.start()]
                    after_text = current_output[match.start():]

                    self.interaction_logger.log_wait_result(
                        success=True,
                        matched_text=matched_text,
                        timeout_occurred=False
                    )

                    await self._send_response_if_needed(response, delay_before_response)

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
        return None

    async def _send_response_if_needed(self, response: str, delay_before_response: float) -> None:
        """Send response if provided, with optional delay"""
        if response and self.process:
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

    async def _wait_and_process_pattern(
        self,
        patterns_with_special: list[Any],
        patterns: list[str],
        response: str,
        delay_before_response: float,
        effective_timeout: int
    ) -> ExpectAndRespondResult:
        """Wait for pattern using pexpect and process the result"""
        # Wait for pattern with retry logic
        loop = asyncio.get_event_loop()
        if self.process is None:
            raise RuntimeError("Process is None")
        process = self.process  # Type narrowing for mypy
        index = await loop.run_in_executor(None, lambda: process.expect(patterns_with_special))

        # Process result based on what matched
        if index < len(patterns):  # Pattern matched
            return await self._handle_pattern_match(index, patterns, response, delay_before_response, effective_timeout)
        elif index == len(patterns):  # EOF
            return self._handle_process_ended(effective_timeout)
        else:  # TIMEOUT
            return await self._handle_timeout(patterns, effective_timeout)

    async def _handle_pattern_match(
        self,
        index: int,
        patterns: list[str],
        response: str,
        delay_before_response: float,
        effective_timeout: int
    ) -> ExpectAndRespondResult:
        """Handle successful pattern match"""
        if not self.process:
            raise RuntimeError("Process is None")

        # Extract match data
        match_data = self._extract_match_data(index, patterns)

        # Process the match
        await self._process_successful_match(match_data, response, delay_before_response)

        # Return success result
        return self._create_success_result(match_data, response, effective_timeout)

    def _handle_process_ended(self, effective_timeout: int) -> ExpectAndRespondResult:
        """Handle process termination (EOF)"""
        if not self.process:
            raise RuntimeError("Process is None")

        self.is_active = False
        self.exit_code = self.process.exitstatus
        return {
            "success": False,
            "reason": "process_ended",
            "exit_code": self.exit_code,
            "before": self.process.before or "",
            "timeout_used": effective_timeout,
        }

    async def _handle_timeout(self, patterns: list[str], effective_timeout: int) -> ExpectAndRespondResult:
        """Handle timeout case"""
        if not self.process:
            raise RuntimeError("Process is None")

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

    async def _log_and_capture_before_input(self, input_text: str, add_newline: bool) -> None:
        """Log input and capture screen before sending"""
        log_type = "direct_input" + ("_with_newline" if add_newline else "_no_newline")
        self.interaction_logger.log_input_sent(input_text, log_type)

        pre_input_content = await self.get_current_screen_content()
        if pre_input_content:
            self.interaction_logger.log_screen_content(pre_input_content, "before_send_input")

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
            self.interaction_logger.log_screen_content(post_input_content, "after_send_input")
            self.output_buffer.append(post_input_content)

    def _extract_match_data(self, index: int, patterns: list[str]) -> dict[str, Any]:
        """Extract data from successful pattern match"""
        if not self.process:
            raise RuntimeError("Process is None")

        return {
            "matched_pattern": patterns[index],
            "matched_index": index,
            "before": str(self.process.before or ""),
            "after": str(self.process.after or ""),
        }

    async def _process_successful_match(
        self, match_data: dict[str, Any], response: str, delay_before_response: float
    ) -> None:
        """Process successful match - store output, log, and send response"""
        # Store output
        self.output_buffer.append(match_data["before"])
        if match_data["after"]:
            self.output_buffer.append(match_data["after"])

        # Log the successful match
        self.interaction_logger.log_wait_result(
            success=True,
            matched_text=match_data["after"],
            timeout_occurred=False
        )

        # Capture screen after match
        post_match_content = await self.get_current_screen_content()
        if post_match_content:
            self.interaction_logger.log_screen_content(post_match_content, "after_match")

        # Send response if provided
        if response:
            await self._send_match_response(response, delay_before_response)

    async def _send_match_response(self, response: str, delay_before_response: float) -> None:
        """Send response after successful pattern match"""
        if not self.process:
            raise RuntimeError("Process is None")

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

    def _create_success_result(
        self, match_data: dict[str, Any], response: str, effective_timeout: int
    ) -> ExpectAndRespondResult:
        """Create success result from match data"""
        return {
            "success": True,
            "matched_pattern": match_data["matched_pattern"],
            "matched_index": match_data["matched_index"],
            "before": match_data["before"],
            "after": match_data["after"],
            "response_sent": response,
            "timeout_used": effective_timeout,
        }
