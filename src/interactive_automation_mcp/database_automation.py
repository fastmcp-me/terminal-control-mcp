from typing import Dict, Any, Optional
from .session_manager import SessionManager
from .automation_engine import AutomationEngine

class DatabaseAutomation:
    """High-level database automation patterns"""
    
    def __init__(self, session_manager: SessionManager, automation_engine: AutomationEngine):
        self.session_manager = session_manager
        self.automation_engine = automation_engine
    
    async def mysql_connect(
        self,
        host: str,
        username: str,
        password: str,
        database: Optional[str] = None,
        port: int = 3306
    ) -> Dict[str, Any]:
        """Connect to MySQL database with interactive authentication"""
        
        # Build MySQL command
        mysql_command = f"mysql -h {host} -P {port} -u {username} -p"
        if database:
            mysql_command += f" {database}"
        
        session_id = await self.session_manager.create_session(mysql_command)
        
        # MySQL connection steps
        connection_steps = [
            {
                "name": "password_prompt",
                "expect": r"Enter password:",
                "respond": password,
                "timeout": 30
            },
            {
                "name": "connection_success",
                "expect": r"mysql>",
                "respond": "",
                "timeout": 30
            }
        ]
        
        # Handle connection
        connection_results = await self.automation_engine.multi_step_automation(
            session_id, connection_steps
        )
        
        success = all(result["success"] for result in connection_results)
        
        if not success:
            await self.session_manager.destroy_session(session_id)
            return {
                "success": False,
                "session_id": None,
                "connection_results": connection_results
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "connection_results": connection_results
        }
    
    async def execute_sql(
        self,
        session_id: str,
        sql_query: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Execute SQL query on established database session"""
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Send SQL query
        await session.send_input(sql_query)
        
        # Wait for prompt
        result = await session.expect_and_respond(
            pattern=r"mysql>",
            response="",
            timeout=timeout
        )
        
        return {
            "query": sql_query,
            "success": result["success"],
            "output": result.get("before", ""),
            "error": result.get("error", None)
        }
    
    async def postgresql_connect(
        self,
        host: str,
        username: str,
        password: str,
        database: str,
        port: int = 5432
    ) -> Dict[str, Any]:
        """Connect to PostgreSQL database"""
        
        # Set PGPASSWORD environment variable for non-interactive auth
        psql_command = f"psql -h {host} -p {port} -U {username} -d {database}"
        session_id = await self.session_manager.create_session(
            psql_command,
            environment={"PGPASSWORD": password}
        )
        
        # PostgreSQL connection steps
        connection_steps = [
            {
                "name": "connection_success",
                "expect": r"[=#]",
                "respond": "",
                "timeout": 30
            }
        ]
        
        connection_results = await self.automation_engine.multi_step_automation(
            session_id, connection_steps
        )
        
        success = all(result["success"] for result in connection_results)
        
        return {
            "success": success,
            "session_id": session_id if success else None,
            "connection_results": connection_results
        }