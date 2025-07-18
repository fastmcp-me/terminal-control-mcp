from typing import Dict, Any, Optional, List
from .session_manager import SessionManager
from .automation_engine import AutomationEngine

class DebuggingAutomation:
    """High-level debugging automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def gdb_debug_session(
        self,
        program: str,
        core_file: Optional[str] = None,
        args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Start GDB debugging session with intelligent automation"""
        
        # Build GDB command
        gdb_command = "gdb"
        if core_file:
            gdb_command += f" {program} {core_file}"
        else:
            gdb_command += f" {program}"
        
        session_id = await self.session_manager.create_session(gdb_command)
        
        # Wait for GDB prompt
        init_result = await self.automation_engine.conditional_automation(
            session_id,
            [
                {
                    "pattern": r"\(gdb\)",
                    "action": "continue"
                }
            ],
            timeout=30
        )
        
        if not init_result["success"]:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "error": "Failed to start GDB"
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "gdb_ready": True
        }
    
    async def analyze_crash(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Perform comprehensive crash analysis"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Define analysis commands
        analysis_commands = [
            ("bt", "Get stack trace"),
            ("info threads", "Check thread status"),
            ("thread apply all bt", "Stack trace for all threads"),
            ("info registers", "CPU register state"),
            ("x/20i $pc", "Disassemble around crash point"),
            ("info locals", "Local variables"),
            ("info args", "Function arguments")
        ]
        
        analysis_results = {}
        
        for command, description in analysis_commands:
            try:
                # Send command
                await session.send_input(command)
                
                # Wait for GDB prompt
                result = await session.expect_and_respond(
                    pattern=r"\(gdb\)",
                    response="",
                    timeout=30
                )
                
                if result["success"]:
                    analysis_results[description] = {
                        "command": command,
                        "output": result.get("before", ""),
                        "success": True
                    }
                else:
                    analysis_results[description] = {
                        "command": command,
                        "error": result.get("error", "Unknown error"),
                        "success": False
                    }
                    
            except Exception as e:
                analysis_results[description] = {
                    "command": command,
                    "error": str(e),
                    "success": False
                }
        
        return {
            "analysis_results": analysis_results,
            "summary": self._generate_crash_summary(analysis_results)
        }
    
    def _generate_crash_summary(self, analysis_results: Dict[str, Any]) -> str:
        """Generate human-readable crash summary"""
        summary = "=== Crash Analysis Summary ===\n\n"
        
        # Extract key information
        stack_trace = analysis_results.get("Get stack trace", {}).get("output", "")
        registers = analysis_results.get("CPU register state", {}).get("output", "")
        locals_info = analysis_results.get("Local variables", {}).get("output", "")
        
        if stack_trace:
            summary += f"Stack Trace:\n{stack_trace}\n\n"
        
        if registers:
            summary += f"Register State:\n{registers}\n\n"
        
        if locals_info:
            summary += f"Local Variables:\n{locals_info}\n\n"
        
        summary += "=== Analysis Complete ===\n"
        summary += "Suggestion: Review the stack trace for the immediate cause of the crash.\n"
        summary += "Check local variables and registers for unexpected values.\n"
        
        return summary
    
    async def python_debug_session(
        self,
        script: str,
        breakpoints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Start Python debugging session with PDB"""
        
        pdb_command = f"python -m pdb {script}"
        session_id = await self.session_manager.create_session(pdb_command)
        
        # Wait for PDB prompt
        init_result = await self.automation_engine.conditional_automation(
            session_id,
            [
                {
                    "pattern": r"\(Pdb\)",
                    "action": "continue"
                }
            ],
            timeout=30
        )
        
        if not init_result["success"]:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "error": "Failed to start PDB"
            }
        
        # Set breakpoints if provided
        if breakpoints:
            for bp in breakpoints:
                await self._set_python_breakpoint(session_id, bp)
        
        return {
            "success": True,
            "session_id": session_id,
            "pdb_ready": True
        }
    
    async def _set_python_breakpoint(self, session_id: str, breakpoint: str):
        """Set a breakpoint in Python debugger"""
        session = await self.session_manager.get_session(session_id)
        if session:
            await session.send_input(f"b {breakpoint}")
            await session.expect_and_respond(r"\(Pdb\)", "", timeout=10)