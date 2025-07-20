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
        """Execute a sequence of expect/respond steps"""

        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        results = []

        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            expect_pattern = step["expect"]
            response = step.get("respond", "")
            timeout = step.get("timeout", 30)
            optional = step.get("optional", False)

            try:
                result = await session.expect_and_respond(
                    pattern=expect_pattern, response=response, timeout=timeout
                )

                result["step_name"] = step_name
                result["step_index"] = i
                results.append(result)

                # Check if step failed
                if not result["success"]:
                    if optional:
                        continue
                    elif stop_on_failure:
                        break

            except Exception as e:
                error_result = {
                    "success": False,
                    "step_name": step_name,
                    "step_index": i,
                    "reason": "exception",
                    "error": str(e),
                }
                results.append(error_result)

                if not optional and stop_on_failure:
                    break

        return results

