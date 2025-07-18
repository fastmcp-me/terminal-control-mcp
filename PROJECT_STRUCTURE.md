# Project Structure

## Clean, Organized Directory Layout

```
MCPAutomationServer/
├── main.py                    # Main entry point (imports from src/)
├── requirements.txt           # Dependencies
├── setup.py                   # Package setup
├── .venv/                     # Virtual environment
├── src/
│   └── interactive_automation_mcp/
│       ├── __init__.py
│       ├── main.py           # Core MCP server implementation
│       ├── session_manager.py
│       ├── interactive_session.py
│       ├── automation_engine.py
│       ├── security.py
│       ├── ssh_automation.py
│       ├── database_automation.py
│       └── debugging_automation.py
├── tests/
│   ├── test_core.py          # Core logic tests
│   └── test_basic.py         # Comprehensive tests
├── docs/
│   ├── README.md             # Main documentation
│   ├── INSTALLATION.md       # Installation guide
│   ├── PYTHON_DEBUG_GUIDE.md # Python debugging guide
│   ├── config.yaml           # Server configuration
│   ├── interactive_automation_mcp_spec.md  # Original spec
│   └── mcp_implementation_guide.md         # Implementation guide
└── examples/
    └── example_debug.py      # Python debugging example
```

## Key Improvements Made

### 1. **Organized Structure**
- Source code in `src/interactive_automation_mcp/`
- Tests in `tests/`
- Documentation in `docs/`
- Examples in `examples/`

### 2. **Added Missing Tools**
- `send_input` - Send input to active sessions
- `get_session_output` - Get output from session buffer
- `send_signal` - Send signals (Ctrl+C, etc.)
- `clear_session_buffer` - Clear session output
- `execute_ssh_commands` - Execute commands on SSH sessions
- `execute_sql` - Execute SQL queries on DB sessions
- `python_debug_session` - Python debugging with PDB

### 3. **Complete Tool Set (17 Tools Total)**

#### Session Management (3 tools)
- `create_interactive_session`
- `list_sessions`
- `destroy_session`

#### Basic Automation (2 tools)
- `expect_and_respond`
- `multi_step_automation`

#### High-Level Automation (3 tools)
- `ssh_connect_with_auth`
- `database_connect_interactive`
- `gdb_debug_session`

#### Debugging (2 tools)
- `analyze_crash`
- `python_debug_session`

#### Session Control (6 tools)
- `send_input`
- `get_session_output`
- `send_signal`
- `clear_session_buffer`
- `execute_ssh_commands`
- `execute_sql`

### 4. **Enhanced Features**
- Python debugging with PDB
- Signal handling (Ctrl+C, SIGTERM, etc.)
- Session buffer management
- Direct command execution on established connections
- Comprehensive error handling

## Usage

### Start the Server
```bash
# Activate virtual environment
source .venv/bin/activate

# Run server
python main.py
```

### Run Tests
```bash
# Core tests
python tests/test_core.py

# Full tests
python tests/test_basic.py
```

### Example Usage
```bash
# Python debugging
"Debug my Python script examples/example_debug.py"

# SSH automation
"Connect to my server and run system diagnostics"

# Database debugging
"Connect to my database and analyze slow queries"

# Process control
"Send Ctrl+C to session abc123 to interrupt the running process"
```

## Security Features

- Command filtering (blocks dangerous commands)
- Path validation (prevents directory traversal)
- Rate limiting (60 calls/minute)
- Session limits (50 concurrent sessions)
- Signal restrictions (only safe signals allowed)
- Comprehensive logging and audit trails

## All Missing Functionality Now Exposed

✅ **Everything is now properly exposed as MCP tools!**

The server now provides complete interactive automation capabilities with a clean, organized structure that's easy to maintain and extend.