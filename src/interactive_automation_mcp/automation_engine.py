import re
import asyncio
import pexpect
from typing import List, Dict, Any, Optional, Callable
from .session_manager import SessionManager

class AutomationPattern:
    """Represents an automation pattern with conditions and actions"""
    
    def __init__(
        self,
        name: str,
        description: str,
        patterns: List[Dict[str, Any]],
        timeout: int = 30
    ):
        self.name = name
        self.description = description
        self.patterns = patterns
        self.timeout = timeout

class AutomationEngine:
    """Executes automation patterns and workflows"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.predefined_patterns = self._load_predefined_patterns()
    
    async def multi_step_automation(
        self,
        session_id: str,
        steps: List[Dict[str, Any]],
        stop_on_failure: bool = True
    ) -> List[Dict[str, Any]]:
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
                    pattern=expect_pattern,
                    response=response,
                    timeout=timeout
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
                    "error": str(e)
                }
                results.append(error_result)
                
                if not optional and stop_on_failure:
                    break
        
        return results
    
    async def conditional_automation(
        self,
        session_id: str,
        conditions: List[Dict[str, Any]],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Handle multiple possible prompts with different responses"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Extract patterns and build mapping
        patterns = []
        pattern_mapping = {}
        
        for i, condition in enumerate(conditions):
            pattern = condition["pattern"]
            patterns.append(pattern)
            pattern_mapping[i] = condition
        
        # Add EOF and TIMEOUT
        patterns.extend([pexpect.EOF, pexpect.TIMEOUT])
        
        try:
            index = session.process.expect(patterns, timeout=timeout)
            
            if index < len(conditions):
                # Pattern matched
                condition = pattern_mapping[index]
                action = condition.get("action", "respond")
                response = condition.get("response", "")
                
                if action == "respond":
                    session.process.sendline(response)
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": action,
                        "response_sent": response
                    }
                elif action == "terminate":
                    await session.terminate()
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": "terminate"
                    }
                elif action == "continue":
                    return {
                        "success": True,
                        "matched_condition": condition,
                        "action_taken": "continue"
                    }
            
            elif index == len(patterns) - 2:  # EOF
                return {
                    "success": False,
                    "reason": "process_ended",
                    "exit_code": session.process.exitstatus
                }
            
            else:  # TIMEOUT
                return {
                    "success": False,
                    "reason": "timeout"
                }
                
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e)
            }
    
    def _load_predefined_patterns(self) -> Dict[str, AutomationPattern]:
        """Load predefined automation patterns"""
        patterns = {}
        
        # SSH authentication patterns
        patterns["ssh_password_auth"] = AutomationPattern(
            name="ssh_password_auth",
            description="Handle SSH password authentication",
            patterns=[
                {
                    "expect": r"password:",
                    "action": "respond_with_credential",
                    "credential_key": "password"
                },
                {
                    "expect": r"yes/no",
                    "action": "respond",
                    "response": "yes"
                },
                {
                    "expect": r"Permission denied",
                    "action": "terminate"
                },
                {
                    "expect": r"[$#]",
                    "action": "continue"
                }
            ]
        )
        
        # Database connection patterns
        patterns["mysql_connect"] = AutomationPattern(
            name="mysql_connect",
            description="Handle MySQL connection prompts",
            patterns=[
                {
                    "expect": r"Enter password:",
                    "action": "respond_with_credential",
                    "credential_key": "password"
                },
                {
                    "expect": r"mysql>",
                    "action": "continue"
                },
                {
                    "expect": r"Access denied",
                    "action": "terminate"
                }
            ]
        )
        
        # GDB debugging patterns
        patterns["gdb_debugging"] = AutomationPattern(
            name="gdb_debugging",
            description="Standard GDB debugging workflow",
            patterns=[
                {
                    "expect": r"\(gdb\)",
                    "action": "continue"
                },
                {
                    "expect": r"Program received signal",
                    "action": "respond",
                    "response": "bt"
                }
            ]
        )
        
        return patterns