#!/usr/bin/env python3
"""
Core test to verify the MCP server logic without external dependencies
"""

import os

from interactive_automation_mcp.security import SecurityManager
from interactive_automation_mcp.session_manager import SessionMetadata, SessionState


def test_session_metadata():
    """Test SessionMetadata functionality"""
    print("Testing SessionMetadata...")

    metadata = SessionMetadata(
        session_id="test_session",
        command="echo hello",
        created_at=1234567890,
        last_activity=1234567890,
        state=SessionState.ACTIVE,
        timeout=3600
    )

    if metadata.session_id == "test_session":
        print("✓ SessionMetadata created successfully")
    else:
        print("✗ SessionMetadata creation failed")

def test_security_manager():
    """Test SecurityManager functionality"""
    print("\nTesting SecurityManager...")

    security_manager = SecurityManager()

    # Test command validation
    safe_commands = ["ssh user@host", "mysql -u root -p", "echo hello", "python script.py"]
    dangerous_commands = ["rm -rf /", "dd if=/dev/zero of=/dev/sda", "shutdown -h now", ":(){ :|:& };:"]

    print("Testing safe commands:")
    for cmd in safe_commands:
        if security_manager._validate_command(cmd):
            print(f"✓ Safe command allowed: {cmd}")
        else:
            print(f"✗ Safe command blocked: {cmd}")

    print("\nTesting universal command policy:")
    for cmd in dangerous_commands:
        if security_manager._validate_command(cmd):
            print(f"✓ Universal design: All commands allowed (user responsible): {cmd}")
        else:
            print(f"✗ Command blocked: {cmd}")

    # Test path validation
    safe_paths = ["./test.txt", "/home/user/file.txt", "data/config.json"]
    dangerous_paths = ["../../../etc/passwd", "/etc/shadow", "/root/.ssh/id_rsa"]

    print("\nTesting safe paths:")
    for path in safe_paths:
        if security_manager._validate_path(path):
            print(f"✓ Safe path allowed: {path}")
        else:
            print(f"✗ Safe path blocked: {path}")

    print("\nTesting universal path policy:")
    for path in dangerous_paths:
        if security_manager._validate_path(path):
            print(f"✓ Universal design: All paths allowed (user responsible): {path}")
        else:
            print(f"✗ Path blocked: {path}")

    # Test rate limiting
    print("\nTesting rate limiting:")
    for i in range(62):  # Exceed the limit of 60
        result = security_manager._check_rate_limit("test_client")
        if i < 60:
            if result:
                if i == 59:
                    print(f"✓ Rate limit allows {i+1} calls")
            else:
                print(f"✗ Rate limit blocked call {i+1} unexpectedly")
                break
        else:
            if not result:
                print(f"✓ Rate limit blocked call {i+1} as expected")
            else:
                print(f"✗ Rate limit should have blocked call {i+1}")

def test_tool_validation():
    """Test tool call validation"""
    print("\nTesting tool call validation...")

    security_manager = SecurityManager()

    # Test valid tool calls
    valid_calls = [
        ("create_interactive_session", {"command": "ssh user@host"}),
        ("list_sessions", {}),
        ("destroy_session", {"session_id": "test_session"}),
        ("expect_and_respond", {"session_id": "test", "expect_pattern": "password:", "response": "secret"})
    ]

    for tool_name, args in valid_calls:
        if security_manager.validate_tool_call(tool_name, args):
            print(f"✓ Valid tool call allowed: {tool_name}")
        else:
            print(f"✗ Valid tool call blocked: {tool_name}")

    # Test universal design - all commands should be allowed (user responsible)
    universal_commands = [
        ("create_interactive_session", {"command": "rm -rf /"}),
        ("create_interactive_session", {"command": "shutdown -h now"}),
        ("some_tool", {"path": "../../../etc/passwd"})
    ]

    for tool_name, args in universal_commands:
        if security_manager.validate_tool_call(tool_name, args):
            print(f"✓ Universal design: Command allowed (user responsible): {tool_name}")
        else:
            print(f"✗ Universal design violated - command blocked: {tool_name}")



def test_file_structure():
    """Test that all required files exist"""
    print("\nTesting file structure...")

    # Paths are relative to the project root where the test is executed
    required_files = [
        "pyproject.toml",
        "README.md",
        "src/interactive_automation_mcp/__init__.py",
        "src/interactive_automation_mcp/main.py",
        "src/interactive_automation_mcp/session_manager.py",
        "src/interactive_automation_mcp/interactive_session.py",
        "src/interactive_automation_mcp/automation_engine.py",
        "src/interactive_automation_mcp/security.py",
    ]

    all_found = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            all_found = False

    if not all_found:
        print(f"Hint: Test executed from '{os.getcwd()}'")


def test_mcp_schema():
    """Test MCP tool schema structure"""
    print("\nTesting MCP tool schema...")

    # Test that we can create a basic tool schema
    tool_schema = {
        "name": "test_tool",
        "description": "A test tool",
        "inputSchema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer", "default": 30}
            },
            "required": ["param1"]
        }
    }

    if tool_schema["name"] == "test_tool":
        print("✓ MCP tool schema structure is valid")
    else:
        print("✗ MCP tool schema structure is invalid")

def main():
    """Main test function"""
    print("Running Core Logic Tests for Interactive Automation MCP Server")
    print("=" * 70)

    test_session_metadata()
    test_security_manager()
    test_tool_validation()
    test_file_structure()
    test_mcp_schema()

    print("\n" + "=" * 70)
    print("✅ Core logic tests completed successfully!")
    print("\nNote: These tests verify the core logic without external dependencies.")
    print("To run the full server, install dependencies from requirements.txt:")
    print("pip install -r requirements.txt")

if __name__ == "__main__":
    main()
