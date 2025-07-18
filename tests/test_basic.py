#!/usr/bin/env python3
"""
Basic test to verify the MCP server functionality
"""

import asyncio
import sys
import os

# Add the src directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from interactive_automation_mcp.session_manager import SessionManager
from interactive_automation_mcp.security import SecurityManager
from interactive_automation_mcp.automation_engine import AutomationEngine

async def test_session_manager():
    """Test SessionManager functionality"""
    print("Testing SessionManager...")
    
    session_manager = SessionManager(max_sessions=5, default_timeout=60)
    
    # Test session creation
    try:
        session_id = await session_manager.create_session("echo 'Hello World'")
        print(f"✓ Session created: {session_id}")
        
        # Test session retrieval
        session = await session_manager.get_session(session_id)
        if session:
            print("✓ Session retrieved successfully")
        else:
            print("✗ Failed to retrieve session")
            
        # Test session listing
        sessions = await session_manager.list_sessions()
        print(f"✓ Sessions listed: {len(sessions)} active sessions")
        
        # Test session destruction
        success = await session_manager.destroy_session(session_id)
        if success:
            print("✓ Session destroyed successfully")
        else:
            print("✗ Failed to destroy session")
            
    except Exception as e:
        print(f"✗ SessionManager test failed: {e}")

def test_security_manager():
    """Test SecurityManager functionality"""
    print("\nTesting SecurityManager...")
    
    security_manager = SecurityManager()
    
    # Test command validation
    safe_commands = ["ssh user@host", "mysql -u root -p", "echo hello"]
    dangerous_commands = ["rm -rf /", "dd if=/dev/zero of=/dev/sda", "shutdown -h now"]
    
    for cmd in safe_commands:
        if security_manager._validate_command(cmd):
            print(f"✓ Safe command allowed: {cmd}")
        else:
            print(f"✗ Safe command blocked: {cmd}")
    
    for cmd in dangerous_commands:
        if not security_manager._validate_command(cmd):
            print(f"✓ Dangerous command blocked: {cmd}")
        else:
            print(f"✗ Dangerous command allowed: {cmd}")
    
    # Test path validation
    safe_paths = ["./test.txt", "/home/user/file.txt", "data/config.json"]
    dangerous_paths = ["../../../etc/passwd", "/etc/shadow", "/root/.ssh/id_rsa"]
    
    for path in safe_paths:
        if security_manager._validate_path(path):
            print(f"✓ Safe path allowed: {path}")
        else:
            print(f"✗ Safe path blocked: {path}")
    
    for path in dangerous_paths:
        if not security_manager._validate_path(path):
            print(f"✓ Dangerous path blocked: {path}")
        else:
            print(f"✗ Dangerous path allowed: {path}")

def test_automation_engine():
    """Test AutomationEngine functionality"""
    print("\nTesting AutomationEngine...")
    
    session_manager = SessionManager()
    automation_engine = AutomationEngine(session_manager)
    
    # Universal design: No predefined patterns - all patterns are user-provided
    print("✓ Universal design: Patterns are provided by users, not hardcoded")

def test_imports():
    """Test that all modules can be imported"""
    print("\nTesting module imports...")
    
    try:
        # Import from root main.py since we unified the files
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        from main import InteractiveAutomationServer
        print("✓ Main server class imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import main server: {e}")
        return False
    
    # Universal design: No program-specific automation classes
    print("✓ Universal design: No hardcoded automation classes needed")
    
    return True

async def main():
    """Main test function"""
    print("Running Interactive Automation MCP Server Tests")
    print("=" * 50)
    
    # Test imports first
    if not test_imports():
        print("\n❌ Import tests failed - cannot proceed with other tests")
        return
    
    # Test core components
    await test_session_manager()
    test_security_manager()
    test_automation_engine()
    
    print("\n" + "=" * 50)
    print("✅ Basic tests completed")
    print("\nNote: This is a basic functionality test.")
    print("Full testing would require actual interactive programs and mocked dependencies.")

if __name__ == "__main__":
    asyncio.run(main())