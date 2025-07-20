from typing import Any

from .session_manager import SessionManager


class AutomationEngine:
    """Executes automation patterns and workflows"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        # Universal design: No predefined patterns - all patterns are user-provided

    async def multi_step_automation(
        self, session_id: str, steps: list[dict[str, Any]], stop_on_failure: bool = True
    ) -> list[dict[str, Any]]:
        """Execute a sequence of expect/respond steps with enhanced error recovery"""

        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        results = []
        consecutive_failures = 0
        max_consecutive_failures = 3

        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            expect_pattern = step["expect"]
            response = step.get("respond", "")
            timeout = step.get("timeout", 30)
            optional = step.get("optional", False)
            case_sensitive = step.get("case_sensitive", False)

            try:
                result = await session.expect_and_respond(
                    pattern=expect_pattern,
                    response=response,
                    timeout=timeout,
                    case_sensitive=case_sensitive
                )

                result["step_name"] = step_name
                result["step_index"] = i
                results.append(result)

                # Check if step succeeded
                if result["success"]:
                    consecutive_failures = 0  # Reset failure counter on success
                else:
                    consecutive_failures += 1

                    # Add retry information
                    result["consecutive_failures"] = consecutive_failures
                    result["max_failures_reached"] = consecutive_failures >= max_consecutive_failures

                    # If too many consecutive failures, suggest stopping
                    if consecutive_failures >= max_consecutive_failures:
                        result["suggestion"] = "Consider checking session state or adjusting automation strategy"

                    if optional:
                        continue
                    elif stop_on_failure:
                        break

            except Exception as e:
                consecutive_failures += 1
                error_result = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": i,
                    "reason": "exception",
                    "error": str(e),
                    "consecutive_failures": consecutive_failures,
                    "suggestion": "Check session state and step configuration",
                }
                results.append(error_result)

                if not optional and stop_on_failure:
                    break

        # Add summary information
        total_steps = len(steps)
        successful_steps = sum(1 for r in results if r["success"])
        failed_steps = len(results) - successful_steps

        # Add metadata to first result if any results exist
        if results:
            results[0]["automation_summary"] = {
                "total_steps": total_steps,
                "successful_steps": successful_steps,
                "failed_steps": failed_steps,
                "completion_rate": successful_steps / total_steps if total_steps > 0 else 0,
                "stopped_early": len(results) < total_steps,
            }

        return results

