#!/usr/bin/env python3
"""
Interaction Logger for debugging MCP automation sessions
Captures detailed interaction flows with timestamps and structured data
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class InteractionLogger:
    """Structured logger for debugging interactive automation sessions"""

    def __init__(self, session_id: str, log_dir: str = "logs/interactions"):
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create session-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{session_id}_{timestamp}.json"

        # Initialize log structure
        self.events: list[dict[str, Any]] = []
        self.session_start_time = time.time()

        # Also create a human-readable log
        self.readable_log = self.log_dir / f"session_{session_id}_{timestamp}.txt"

        # Log session start
        self.log_event("session_start", {"session_id": session_id})

    def log_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Log a structured event with timestamp"""
        timestamp = time.time()
        relative_time = timestamp - self.session_start_time

        event = {
            "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
            "relative_time": round(relative_time, 3),
            "event_type": event_type,
            "data": data or {}
        }

        self.events.append(event)

        # Write to JSON file immediately (for real-time debugging)
        self._write_json()

        # Write human-readable version
        self._write_readable(event)

    def log_screen_content(self, content: str, description: str = "screen_capture") -> None:
        """Log current screen content"""
        # Clean up ANSI escape codes for readable version
        clean_content = self._clean_ansi(content)

        self.log_event("screen_content", {
            "description": description,
            "raw_content": content,
            "clean_content": clean_content,
            "content_length": len(content)
        })

    def log_input_sent(self, input_text: str, input_type: str = "user_input") -> None:
        """Log input sent to session"""
        self.log_event("input_sent", {
            "input_text": input_text,
            "input_type": input_type,
            "input_length": len(input_text),
            "input_repr": repr(input_text)  # Shows escape sequences
        })

    def log_wait_start(self, pattern: str, timeout: int) -> None:
        """Log start of expect/wait operation"""
        self.log_event("wait_start", {
            "pattern": pattern,
            "timeout": timeout,
            "action": "waiting_for_pattern"
        })

    def log_wait_result(self, success: bool, matched_text: str | None = None,
                       timeout_occurred: bool = False) -> None:
        """Log result of expect/wait operation"""
        self.log_event("wait_result", {
            "success": success,
            "matched_text": matched_text,
            "timeout_occurred": timeout_occurred
        })

    def log_command_execution(self, command: str, working_dir: str | None = None) -> None:
        """Log command execution"""
        self.log_event("command_execution", {
            "command": command,
            "working_directory": working_dir
        })

    def log_session_state(self, state: str, details: dict[str, Any] | None = None) -> None:
        """Log session state changes"""
        self.log_event("session_state", {
            "state": state,
            "details": details or {}
        })

    def log_automation_step(self, step_number: int, step_type: str,
                           step_data: dict[str, Any]) -> None:
        """Log automation step execution"""
        self.log_event("automation_step", {
            "step_number": step_number,
            "step_type": step_type,
            "step_data": step_data
        })

    def log_error(self, error_type: str, error_message: str,
                  stack_trace: str | None = None) -> None:
        """Log errors and exceptions"""
        self.log_event("error", {
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace
        })

    def close_session(self, exit_code: int | None = None, final_output: str | None = None) -> None:
        """Close the logging session"""
        self.log_event("session_end", {
            "exit_code": exit_code,
            "total_duration": time.time() - self.session_start_time,
            "total_events": len(self.events)
        })

        if final_output:
            self.log_screen_content(final_output, "final_output")

        # Write final summary
        self._write_summary()

    def _write_json(self) -> None:
        """Write events to JSON file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump({
                    "session_id": self.session_id,
                    "session_start_time": self.session_start_time,
                    "events": self.events
                }, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to write interaction log: {e}")

    def _write_readable(self, event: dict[str, Any]) -> None:
        """Write human-readable log entry"""
        try:
            with open(self.readable_log, 'a') as f:
                timestamp = event['timestamp']
                rel_time = event['relative_time']
                event_type = event['event_type']

                f.write(f"\n[{timestamp}] (+{rel_time}s) {event_type.upper()}\n")
                f.write("-" * 60 + "\n")

                data = event.get('data', {})

                if event_type == "screen_content":
                    f.write(f"Description: {data.get('description', 'N/A')}\n")
                    f.write(f"Content Length: {data.get('content_length', 0)} chars\n")
                    f.write("Screen Content:\n")
                    f.write("=" * 40 + "\n")
                    f.write(data.get('clean_content', '') + "\n")
                    f.write("=" * 40 + "\n")

                elif event_type == "input_sent":
                    f.write(f"Input Type: {data.get('input_type', 'unknown')}\n")
                    f.write(f"Input Text: {data.get('input_text', '')}\n")
                    f.write(f"Input Repr: {data.get('input_repr', '')}\n")

                elif event_type == "wait_start":
                    f.write(f"Pattern: {data.get('pattern', '')}\n")
                    f.write(f"Timeout: {data.get('timeout', 0)}s\n")

                elif event_type == "wait_result":
                    f.write(f"Success: {data.get('success', False)}\n")
                    f.write(f"Matched: {data.get('matched_text', 'N/A')}\n")
                    f.write(f"Timeout: {data.get('timeout_occurred', False)}\n")

                else:
                    # Generic data dump
                    for key, value in data.items():
                        f.write(f"{key}: {value}\n")

                f.write("\n")
                f.flush()

        except Exception as e:
            logging.error(f"Failed to write readable log: {e}")

    def _write_summary(self) -> None:
        """Write session summary"""
        try:
            summary_file = self.log_dir / f"session_{self.session_id}_summary.txt"

            with open(summary_file, 'w') as f:
                f.write("INTERACTION LOG SUMMARY\n")
                f.write(f"Session ID: {self.session_id}\n")
                f.write(f"Total Events: {len(self.events)}\n")
                f.write(f"Duration: {time.time() - self.session_start_time:.2f}s\n")
                f.write("Log Files:\n")
                f.write(f"  - JSON: {self.log_file}\n")
                f.write(f"  - Readable: {self.readable_log}\n")
                f.write("\nEvent Types:\n")

                # Count event types
                event_counts: dict[str, int] = {}
                for event in self.events:
                    event_type = event['event_type']
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1

                for event_type, count in sorted(event_counts.items()):
                    f.write(f"  - {event_type}: {count}\n")

        except Exception as e:
            logging.error(f"Failed to write summary: {e}")

    @staticmethod
    def _clean_ansi(text: str) -> str:
        """Remove ANSI escape codes for readable output"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def get_log_files(self) -> dict[str, str]:
        """Get paths to all log files for this session"""
        return {
            "json": str(self.log_file),
            "readable": str(self.readable_log),
            "summary": str(self.log_dir / f"session_{self.session_id}_summary.txt")
        }
