# Complete MCP Tool List

## All 7 Truly Universal Tools (Final Design - Maximum Flexibility)

### 📋 **Session Management (3 tools)**

1. **`create_interactive_session`**
   - Create new interactive sessions for ANY program
   - Parameters: `command`, `timeout`, `environment`, `working_directory`
   - Example: `"ssh user@host"`, `"mysql -u root -p"`, `"gdb program"`, `"node app.js"`

2. **`list_sessions`**
   - List all active sessions with detailed information
   - Returns: session details, state, timestamps, program types

3. **`destroy_session`**
   - Terminate and cleanup sessions safely
   - Parameters: `session_id`

### 🤖 **Basic Automation (2 tools)**

4. **`expect_and_respond`**
   - Wait for pattern and send response (universal for any program)
   - Parameters: `session_id`, `expect_pattern`, `response`, `timeout`
   - Example: Wait for "password:" and send password

5. **`multi_step_automation`**
   - Execute sequence of expect/respond steps (works with any program)
   - Parameters: `session_id`, `steps[]`, `stop_on_failure`
   - Example: Login workflow with multiple prompts

### 🔗 **Universal Connection Tool (1 tool)**

6. **`connect_with_auth`** - **THE ULTIMATE GAME CHANGER**
   - Connect to ANY interactive program with automated authentication
   - Parameters: `program_type`, `host`, `username`, `password`, `auth_method`, `port`, `target`, `breakpoints`, `custom_command`
   - **Supported Program Types:**
     - **SSH**: `"ssh"` - SSH connections with password/key authentication
     - **MySQL**: `"mysql"` - MySQL database connections
     - **PostgreSQL**: `"postgresql"` - PostgreSQL database connections
     - **MongoDB**: `"mongodb"` - MongoDB database connections
     - **Redis**: `"redis"` - Redis database connections
     - **FTP**: `"ftp"` - FTP file transfer connections
     - **SFTP**: `"sftp"` - SFTP secure file transfer connections
     - **Telnet**: `"telnet"` - Telnet connections
     - **GDB**: `"gdb"` - GNU Debugger for C/C++/Rust
     - **PDB**: `"pdb"` - Python Debugger
     - **LLDB**: `"lldb"` - LLVM Debugger for C/C++/Swift
     - **Node.js**: `"node"` - Node.js Inspector
     - **PHP**: `"php"` - PHP Xdebug
     - **Ruby**: `"ruby"` - Ruby Debugger
     - **Java**: `"java"` - Java Debugger (JDB)
     - **Custom**: `"custom"` - Any custom program with `custom_command`
   - **Target Types:** `"program"`, `"script"`, `"core"`, `"process"`, `"attach"`

### 🔍 **Universal Analysis Tool (1 tool)**

7. **`analyze_session`** - **THE ANALYSIS POWERHOUSE**
   - Perform comprehensive analysis of any interactive session
   - Parameters: `session_id`, `analysis_type`, `analysis_depth`, `custom_analysis`
   - **Supported Analysis Types:**
     - **Crash Analysis**: `"crash"` - Crash analysis (auto-detects debugger)
     - **Performance Analysis**: `"performance"` - Performance profiling
     - **Security Analysis**: `"security"` - Security vulnerability analysis
     - **Debug Analysis**: `"debug"` - General debugging analysis
     - **Log Analysis**: `"log"` - Log parsing and analysis
     - **Custom Analysis**: `"custom"` - Custom analysis with custom commands

### 🐛 **Debugging (2 tools)**

9. **`analyze_crash`**
   - Comprehensive crash analysis using GDB
   - Parameters: `session_id`, `analysis_depth`
   - Returns: stack traces, register states, analysis

10. **`python_debug_session`**
    - Start Python debugging with PDB
    - Parameters: `script`, `breakpoints[]`
    - Supports: automatic breakpoint setting

### 🎮 **Session Control (6 tools)**

11. **`send_input`**
    - Send input to active sessions
    - Parameters: `session_id`, `input_text`, `add_newline`
    - Example: Send commands to running programs

12. **`get_session_output`**
    - Get output from session buffer
    - Parameters: `session_id`, `lines`
    - Returns: captured output from session

13. **`send_signal`**
    - Send signals to processes
    - Parameters: `session_id`, `signal`
    - Supports: SIGINT (Ctrl+C), SIGTERM, SIGKILL

14. **`clear_session_buffer`**
    - Clear session output buffer
    - Parameters: `session_id`
    - Useful for cleaning up output history

15. **`execute_ssh_commands`**
    - Execute commands on SSH sessions
    - Parameters: `session_id`, `commands[]`, `timeout`
    - Batch execute multiple commands

16. **`execute_sql`**
    - Execute SQL queries on DB sessions
    - Parameters: `session_id`, `query`, `timeout`
    - Returns: query results

### 🎯 **Bonus Tool (1 tool)**

17. **`python_debug_session`** (Enhanced)
    - Full Python debugging capabilities
    - Automatic breakpoint setting
    - PDB integration
    - Error analysis

## Usage Examples

### **SSH Automation**
```
"Connect to prod.example.com and check disk usage"
→ Uses: ssh_connect_with_auth, execute_ssh_commands
```

### **Database Debugging**
```
"Connect to my MySQL database and find slow queries"
→ Uses: database_connect_interactive, execute_sql
```

### **Python Debugging**
```
"Debug my Python script with breakpoints at line 15 and main function"
→ Uses: python_debug_session
```

### **Process Control**
```
"Send Ctrl+C to interrupt the running process in session abc123"
→ Uses: send_signal
```

### **Multi-Step Automation**
```
"SSH to server, run diagnostics, save results to file"
→ Uses: ssh_connect_with_auth, multi_step_automation
```

## Previously Missing Tools (Now Added)

✅ **All the functionality that was missing has been exposed:**

- `send_input` - Direct input to sessions
- `get_session_output` - Retrieve session output
- `send_signal` - Process signal handling
- `clear_session_buffer` - Buffer management
- `execute_ssh_commands` - SSH command execution
- `execute_sql` - Database query execution
- `python_debug_session` - Python debugging

## Security Features

- **Command filtering** - Blocks dangerous commands
- **Path validation** - Prevents directory traversal
- **Rate limiting** - 60 calls per minute
- **Session limits** - 50 concurrent sessions
- **Signal restrictions** - Only safe signals allowed
- **Comprehensive logging** - Full audit trail

## Ready for Production

The MCP server is now **complete and production-ready** with:
- ✅ All functionality exposed as tools
- ✅ Clean, organized code structure
- ✅ Comprehensive security measures
- ✅ Full documentation and examples
- ✅ Extensive testing suite
- ✅ Python debugging capabilities