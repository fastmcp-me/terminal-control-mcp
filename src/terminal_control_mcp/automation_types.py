"""Type definitions for the Interactive Automation MCP Server."""

from dataclasses import dataclass


# Session expect_and_respond result types
@dataclass
class ExpectAndRespondSuccessResult:
    """Result when expect_and_respond successfully matches a pattern."""

    success: bool  # Always True
    matched_pattern: str
    matched_index: int
    before: str
    after: str
    response_sent: str
    timeout_used: int


@dataclass
class ExpectAndRespondProcessEndedResult:
    """Result when the process ends during expect_and_respond."""

    success: bool  # Always False
    reason: str  # Always "process_ended"
    exit_code: int | None
    before: str
    timeout_used: int


@dataclass
class ExpectAndRespondTimeoutResult:
    """Result when expect_and_respond times out waiting for a pattern."""

    success: bool  # Always False
    reason: str  # Always "timeout"
    before: str
    timeout_used: int
    patterns_tried: list[str]
    suggestion: str


@dataclass
class ExpectAndRespondErrorResult:
    """Result when expect_and_respond encounters an error."""

    success: bool  # Always False
    reason: str  # "expect_error" or "error"
    error: str
    timeout_used: int
    suggestion: str


# Union type for all possible expect_and_respond results
ExpectAndRespondResult = (
    ExpectAndRespondSuccessResult
    | ExpectAndRespondProcessEndedResult
    | ExpectAndRespondTimeoutResult
    | ExpectAndRespondErrorResult
)


# Automation engine types
@dataclass
class AutomationSummary:
    """Summary statistics for multi-step automation."""

    total_steps: int
    successful_steps: int
    failed_steps: int
    completion_rate: float
    stopped_early: bool


@dataclass
class AutomationStepSuccessResult:
    """Result for a successful automation step."""

    success: bool  # Always True
    matched_pattern: str
    matched_index: int
    before: str
    after: str
    response_sent: str
    timeout_used: int
    step_name: str
    step_index: int
    # First step gets summary
    automation_summary: AutomationSummary | None = None


@dataclass
class AutomationStepFailureResult:
    """Result for a failed automation step."""

    success: bool  # Always False
    reason: str
    step_name: str
    step_index: int
    consecutive_failures: int | None = None
    max_failures_reached: bool | None = None
    suggestion: str | None = None
    # Additional fields depending on failure type
    exit_code: int | None | None = None
    before: str | None = None
    timeout_used: int | None = None
    patterns_tried: list[str] | None = None
    error: str | None = None
    # First step gets summary
    automation_summary: AutomationSummary | None = None


@dataclass
class AutomationStepExceptionResult:
    """Result for an automation step that threw an exception."""

    success: bool  # Always False
    step_name: str
    step_index: int
    reason: str  # Always "exception"
    error: str
    consecutive_failures: int
    suggestion: str
    # First step gets summary
    automation_summary: AutomationSummary | None = None


# Union type for all possible automation step results
AutomationStepResult = (
    AutomationStepSuccessResult
    | AutomationStepFailureResult
    | AutomationStepExceptionResult
)
