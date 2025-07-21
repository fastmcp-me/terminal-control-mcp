from typing import Any, cast

from .session_manager import SessionManager
from .types import (
    AutomationStepResult,
    ExpectAndRespondErrorResult,
    ExpectAndRespondProcessEndedResult,
    ExpectAndRespondResult,
    ExpectAndRespondSuccessResult,
    ExpectAndRespondTimeoutResult,
)


class AutomationEngine:
    """Executes automation patterns and workflows"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        # Universal design: No predefined patterns - all patterns are user-provided

    async def multi_step_automation(
        self, session_id: str, steps: list[dict[str, Any]], stop_on_failure: bool = True
    ) -> list[AutomationStepResult]:
        """Execute a sequence of expect/respond steps with enhanced error recovery"""
        session = await self._get_session(session_id)
        state = self._init_automation_state()
        results = await self._execute_steps(session, steps, stop_on_failure, state)
        self._add_summary(results, len(steps))
        return results

    async def _get_session(self, session_id: str) -> Any:
        """Get session or raise error"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session

    def _init_automation_state(self) -> dict[str, int]:
        """Initialize automation state"""
        return {
            "consecutive_failures": 0,
            "max_consecutive_failures": 3,
        }

    async def _execute_steps(
        self, session: Any, steps: list[dict[str, Any]],
        stop_on_failure: bool, state: dict[str, int]
    ) -> list[AutomationStepResult]:
        """Execute all automation steps"""
        results = []
        for i, step in enumerate(steps):
            result = await self._execute_single_step(session, step, i, state)
            results.append(result)
            if self._should_stop(result, step.get("optional", False), stop_on_failure):
                break
        return results

    async def _execute_single_step(
        self, session: Any, step: dict[str, Any], index: int, state: dict[str, int]
    ) -> AutomationStepResult:
        """Execute a single automation step"""
        step_name = step.get("name", f"step_{index}")
        try:
            expect_result = await self._call_expect_and_respond(session, step)
            return self._convert_to_automation_result(
                expect_result, step_name, index,
                state["consecutive_failures"], state["max_consecutive_failures"]
            )
        except Exception as e:
            return self._create_exception_result(step_name, index, e, state)

    async def _call_expect_and_respond(self, session: Any, step: dict[str, Any]) -> Any:
        """Call expect_and_respond with step parameters"""
        return await session.expect_and_respond(
            pattern=step["expect"],
            response=step.get("respond", ""),
            timeout=step.get("timeout", 30),
            case_sensitive=step.get("case_sensitive", False),
            delay_before_response=step.get("delay_before_response", 0.0)
        )

    def _create_exception_result(
        self, step_name: str, index: int, exception: Exception, state: dict[str, int]
    ) -> AutomationStepResult:
        """Create result for exception case"""
        state["consecutive_failures"] += 1
        return {
            "success": False,
            "step_name": step_name,
            "step_index": index,
            "reason": "exception",
            "error": str(exception),
            "consecutive_failures": state["consecutive_failures"],
            "suggestion": "Check session state and step configuration",
        }

    def _should_stop(self, result: AutomationStepResult, optional: bool, stop_on_failure: bool) -> bool:
        """Check if automation should stop"""
        if result["success"]:
            return False
        return not optional and stop_on_failure

    def _add_summary(self, results: list[AutomationStepResult], total_steps: int) -> None:
        """Add summary to first result"""
        if not results:
            return

        successful_steps = sum(1 for r in results if r["success"])
        results[0]["automation_summary"] = {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": len(results) - successful_steps,
            "completion_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "stopped_early": len(results) < total_steps,
        }

    def _convert_to_automation_result(
        self,
        expect_result: ExpectAndRespondResult,
        step_name: str,
        step_index: int,
        consecutive_failures: int,
        max_consecutive_failures: int
    ) -> AutomationStepResult:
        """Convert ExpectAndRespondResult to AutomationStepResult"""

        if expect_result["success"]:
            # Type narrow to success result
            success_result = cast(ExpectAndRespondSuccessResult, expect_result)
            return {
                "success": True,
                "matched_pattern": success_result["matched_pattern"],
                "matched_index": success_result["matched_index"],
                "before": success_result["before"],
                "after": success_result["after"],
                "response_sent": success_result["response_sent"],
                "timeout_used": success_result["timeout_used"],
                "step_name": step_name,
                "step_index": step_index,
            }
        else:
            # Handle different failure types
            consecutive_failures += 1
            reason = expect_result.get("reason", "unknown")

            if reason == "process_ended":
                # Type narrow to process ended result
                process_result = cast(ExpectAndRespondProcessEndedResult, expect_result)
                result: AutomationStepResult = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": step_index,
                    "consecutive_failures": consecutive_failures,
                    "max_failures_reached": consecutive_failures >= max_consecutive_failures,
                    "reason": process_result["reason"],
                    "exit_code": process_result["exit_code"],
                    "before": process_result["before"],
                    "timeout_used": process_result["timeout_used"],
                }
                return result

            elif reason == "timeout":
                # Type narrow to timeout result
                timeout_result = cast(ExpectAndRespondTimeoutResult, expect_result)
                result = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": step_index,
                    "consecutive_failures": consecutive_failures,
                    "max_failures_reached": consecutive_failures >= max_consecutive_failures,
                    "reason": timeout_result["reason"],
                    "before": timeout_result["before"],
                    "timeout_used": timeout_result["timeout_used"],
                    "patterns_tried": timeout_result["patterns_tried"],
                    "suggestion": timeout_result["suggestion"],
                }
                return result

            else:
                # Type narrow to error result (expect_error or error)
                error_result = cast(ExpectAndRespondErrorResult, expect_result)
                result = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": step_index,
                    "consecutive_failures": consecutive_failures,
                    "max_failures_reached": consecutive_failures >= max_consecutive_failures,
                    "reason": error_result["reason"],
                    "error": error_result["error"],
                    "timeout_used": error_result["timeout_used"],
                    "suggestion": error_result["suggestion"],
                }

                # Add generic failure suggestion if none provided and max failures reached
                if consecutive_failures >= max_consecutive_failures:
                    # Override suggestion for max failures reached
                    result["suggestion"] = "Consider checking session state or adjusting automation strategy"

                return result

