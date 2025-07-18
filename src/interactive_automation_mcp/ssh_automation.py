import asyncio
from typing import Dict, Any, Optional, List
from .session_manager import SessionManager
from .automation_engine import AutomationEngine

class SSHAutomation:
    """High-level SSH automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def connect_with_password(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        post_connect_commands: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Connect to SSH server with password authentication"""
        
        # Create SSH session
        ssh_command = f"ssh -p {port} {username}@{host}"
        session_id = await self.session_manager.create_session(ssh_command)
        
        # Define authentication steps
        auth_steps = [
            {
                "name": "host_key_verification",
                "expect": r"yes/no",
                "respond": "yes",
                "optional": True,
                "timeout": 10
            },
            {
                "name": "password_prompt",
                "expect": r"password:",
                "respond": password,
                "timeout": 30
            },
            {
                "name": "login_success",
                "expect": r"[$#]",
                "respond": "",
                "timeout": 30
            }
        ]
        
        # Execute authentication
        auth_results = await self.automation_engine.multi_step_automation(
            session_id, auth_steps
        )
        
        # Check if authentication succeeded
        if not all(result["success"] for result in auth_results if not result.get("optional")):
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "auth_results": auth_results
            }
        
        # Execute post-connect commands
        if post_connect_commands:
            for command in post_connect_commands:
                session = await self.session_manager.get_session(session_id)
                await session.send_input(command)
                await asyncio.sleep(1)  # Brief pause between commands
        
        return {
            "success": True,
            "session_id": session_id,
            "auth_results": auth_results
        }
    
    async def connect_with_key(
        self,
        host: str,
        username: str,
        key_path: str,
        passphrase: Optional[str] = None,
        port: int = 22
    ) -> Dict[str, Any]:
        """Connect to SSH server with key authentication"""
        
        # Build SSH command with key
        ssh_command = f"ssh -i {key_path} -p {port} {username}@{host}"
        session_id = await self.session_manager.create_session(ssh_command)
        
        auth_steps = [
            {
                "name": "host_key_verification", 
                "expect": r"yes/no",
                "respond": "yes",
                "optional": True
            }
        ]
        
        # Add passphrase step if needed
        if passphrase:
            auth_steps.append({
                "name": "key_passphrase",
                "expect": r"Enter passphrase",
                "respond": passphrase
            })
        
        auth_steps.append({
            "name": "login_success",
            "expect": r"[$#]",
            "respond": ""
        })
        
        auth_results = await self.automation_engine.multi_step_automation(
            session_id, auth_steps
        )
        
        return {
            "success": all(result["success"] for result in auth_results if not result.get("optional")),
            "session_id": session_id if all(result["success"] for result in auth_results if not result.get("optional")) else None,
            "auth_results": auth_results
        }
    
    async def execute_commands(
        self,
        session_id: str,
        commands: List[str],
        timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """Execute commands on established SSH session"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        results = []
        
        for command in commands:
            # Send command
            await session.send_input(command)
            
            # Wait for prompt
            result = await session.expect_and_respond(
                pattern=r"[$#]",
                response="",
                timeout=timeout
            )
            
            results.append({
                "command": command,
                "success": result["success"],
                "output": result.get("before", ""),
                "error": result.get("error", None)
            })
        
        return results