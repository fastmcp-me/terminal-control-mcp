"""Type definitions for the Interactive Automation MCP Server."""

from typing import TypedDict

from typing_extensions import NotRequired, Required


# Session expect_and_respond result types
class ExpectAndRespondSuccessResult(TypedDict):
    """Result when expect_and_respond successfully matches a pattern."""
    success: Required[bool]  # Always True
    matched_pattern: Required[str]
    matched_index: Required[int]
    before: Required[str]
    after: Required[str]
    response_sent: Required[str]
    timeout_used: Required[int]


class ExpectAndRespondProcessEndedResult(TypedDict):
    """Result when the process ends during expect_and_respond."""
    success: Required[bool]  # Always False
    reason: Required[str]  # Always "process_ended"
    exit_code: Required[int | None]
    before: Required[str]
    timeout_used: Required[int]


class ExpectAndRespondTimeoutResult(TypedDict):
    """Result when expect_and_respond times out waiting for a pattern."""
    success: Required[bool]  # Always False
    reason: Required[str]  # Always "timeout"
    before: Required[str]
    timeout_used: Required[int]
    patterns_tried: Required[list[str]]
    suggestion: Required[str]


class ExpectAndRespondErrorResult(TypedDict):
    """Result when expect_and_respond encounters an error."""
    success: Required[bool]  # Always False
    reason: Required[str]  # "expect_error" or "error"
    error: Required[str]
    timeout_used: Required[int]
    suggestion: Required[str]


# Union type for all possible expect_and_respond results
ExpectAndRespondResult = (
    ExpectAndRespondSuccessResult |
    ExpectAndRespondProcessEndedResult |
    ExpectAndRespondTimeoutResult |
    ExpectAndRespondErrorResult
)


# Automation engine types
class AutomationSummary(TypedDict):
    """Summary statistics for multi-step automation."""
    total_steps: Required[int]
    successful_steps: Required[int]
    failed_steps: Required[int]
    completion_rate: Required[float]
    stopped_early: Required[bool]


class AutomationStepSuccessResult(TypedDict):
    """Result for a successful automation step."""
    success: Required[bool]  # Always True
    matched_pattern: Required[str]
    matched_index: Required[int]
    before: Required[str]
    after: Required[str]
    response_sent: Required[str]
    timeout_used: Required[int]
    step_name: Required[str]
    step_index: Required[int]
    # First step gets summary
    automation_summary: NotRequired[AutomationSummary]


class AutomationStepFailureResult(TypedDict):
    """Result for a failed automation step."""
    success: Required[bool]  # Always False
    reason: Required[str]
    step_name: Required[str]
    step_index: Required[int]
    consecutive_failures: NotRequired[int]
    max_failures_reached: NotRequired[bool]
    suggestion: NotRequired[str]
    # Additional fields depending on failure type
    exit_code: NotRequired[int | None]
    before: NotRequired[str]
    timeout_used: NotRequired[int]
    patterns_tried: NotRequired[list[str]]
    error: NotRequired[str]
    # First step gets summary
    automation_summary: NotRequired[AutomationSummary]


class AutomationStepExceptionResult(TypedDict):
    """Result for an automation step that threw an exception."""
    success: Required[bool]  # Always False
    step_name: Required[str]
    step_index: Required[int]
    reason: Required[str]  # Always "exception"
    error: Required[str]
    consecutive_failures: Required[int]
    suggestion: Required[str]
    # First step gets summary
    automation_summary: NotRequired[AutomationSummary]


# Union type for all possible automation step results
AutomationStepResult = (
    AutomationStepSuccessResult |
    AutomationStepFailureResult |
    AutomationStepExceptionResult
)
