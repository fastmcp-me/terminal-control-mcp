# Terminal Control MCP Server

A modern MCP server built with tmux/libtmux that enables AI agents to control terminal programs through persistent sessions. Features real-time web interface for direct user access, comprehensive security controls, and support for any terminal program from simple commands to complex interactive workflows like debugging, SSH, and database sessions.

## ✨ Features

### 🚀 **Tmux-Based Terminal Control**
- **🖥️ Tmux Backend**: Reliable terminal multiplexing with libtmux Python API
- **🔄 Session Persistence**: Maintain long-running terminal sessions with automatic cleanup
- **📡 Raw Stream Capture**: Direct terminal output via tmux pipe-pane for perfect synchronization
- **🎯 Agent Control**: AI agents decide timing and interaction flow without timeouts
- **🌐 Dual Access**: Both agent (MCP) and user (web browser) can interact simultaneously

### 🌐 **Integrated Web Interface**
- **🖥️ Real-time Terminal**: Live xterm.js terminal in browser with WebSocket updates
- **🔗 Session URLs**: Direct browser access to any terminal session
- **⚡ Zero Setup**: Automatic web server startup with configurable networking
- **🎮 Manual Control**: Send commands directly without agent awareness
- **📊 Session Management**: View all active sessions and their status

### 🛡️ **Comprehensive Security**
- **🚫 Command Filtering**: Block dangerous operations (rm -rf /, sudo, etc.)
- **📁 Path Protection**: Restrict access to user directories only
- **⏱️ Rate Limiting**: 60 calls/minute with session limits (max 50 concurrent)
- **📝 Audit Logging**: Complete security event tracking
- **🔍 Input Validation**: Multi-layer validation for all inputs

## 🚀 Quick Start

### System Requirements

This package requires `tmux` for terminal multiplexing:

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y tmux

# macOS
brew install tmux

# CentOS/RHEL/Fedora
sudo yum install tmux  # or sudo dnf install tmux
```

### Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install the package
pip install .

# Or install in development mode
pip install -e ".[dev]"
```

### Configuration

Once installed, configure the MCP server in your AI assistant:

## **🎯 Platform Setup**

### **🤖 Claude Code (Anthropic)**

1. **Install the package first (required for console script)**:  
   \# Install the package to create the console script  
   pip install .

2. **Add the MCP server using Claude Code CLI**:  
   \# Recommended: User scope (available across all projects)  
   claude mcp add terminal-control \-s user terminal-control-mcp

   \# Alternative: Local scope (default \- current project only)  
   claude mcp add terminal-control terminal-control-mcp

   \# Alternative: Project scope (shared via .mcp.json in version control)  
   claude mcp add terminal-control \-s project terminal-control-mcp

3. **Verify the server was added**:  
   claude mcp list

**Note**: The MCP server will be automatically launched by Claude Code when needed \- no manual activation required.  
**Web Interface**: When the server starts, it automatically launches a web interface (default port 8080\) where users can directly view and interact with terminal sessions through their browser. The interface is automatically configured for local or remote access based on your environment settings.

### **♊ Gemini CLI (Google)**

1. **Configure in settings.json**: Open your Gemini settings file. This can be the global file (\~/.gemini/settings.json) or a project-specific file (.gemini/settings.json).  
2. **Add the server configuration**: Add the following JSON block to the mcpServers object. You will need to replace "/path/to/terminal-control-mcp/.venv/bin/terminal-control-mcp" and "/path/to/terminal-control-mcp" with the actual absolute paths on your system.  
   {  
     "mcpServers": {  
       "terminal-control": {  
         "command": "/path/to/terminal-control-mcp/.venv/bin/terminal-control-mcp",  
         "cwd": "/path/to/terminal-control-mcp",  
         "trust": false,  
         "timeout": 60000  
       }  
     }  
   }

3. **Verify the server is discovered**: Run the /mcp command in the Gemini CLI to ensure it connects to the server successfully.  
   /mcp

**Note**: The Gemini CLI will automatically launch the MCP server as a background process when it starts.

### **🔧 Visual Studio Code with GitHub Copilot**

1. **Configure in VS Code settings** (MCP extension or built-in support):  
   * Open **Settings** (Ctrl+, or Cmd+,)  
   * Search for "MCP" or "Model Context Protocol"  
   * Add server configuration:

{  
  "mcp.servers": {  
    "terminal-control": {  
      "command": "/path/to/terminal-control-mcp/.venv/bin/python",  
      "args": \["-m", "terminal\_control\_mcp.main"\],  
      "cwd": "/path/to/terminal-control-mcp"  
    }  
  }  
}

2. **Alternative configuration using console script**:  
   {  
     "mcp.servers": {  
       "terminal-control": {  
         "command": "/path/to/terminal-control-mcp/.venv/bin/terminal-control-mcp",  
         "cwd": "/path/to/terminal-control-mcp"  
       }  
     }  
   }

3. **Reload VS Code** to apply the configuration

## 🌐 Web Interface

Each terminal session is accessible through a web interface that provides:

### ✨ **Real-Time Terminal Access**
- **Live terminal output** - See exactly what agents see in real-time
- **Manual input capability** - Send commands directly to sessions without going through the agent
- **WebSocket updates** - Automatic screen refreshes as output changes
- **Session management** - View all active sessions and their status

### 🔗 **Session URLs**
- **Individual session pages**: `http://localhost:8080/session/{session_id}`
- **Session overview**: `http://localhost:8080/` (lists all active sessions)
- **Direct browser access** - No additional software needed
- **Transparent to agents** - Agents remain unaware of direct user interaction

### ⚙️ **Configuration**

#### Local Development
```bash
# Default configuration - web interface only accessible locally
export TERMINAL_CONTROL_WEB_HOST=127.0.0.1   # Default: 0.0.0.0 (changed for security)
export TERMINAL_CONTROL_WEB_PORT=8080        # Default: 8080
```

#### Remote/Network Access
```bash
# For MCP servers running on remote machines
export TERMINAL_CONTROL_WEB_HOST=0.0.0.0            # Bind to all interfaces
export TERMINAL_CONTROL_WEB_PORT=8080               # Choose available port
export TERMINAL_CONTROL_EXTERNAL_HOST=your-server.com  # External hostname/IP for URLs
```

**Remote Access Example:**
- MCP server runs on `server.example.com`
- Set `TERMINAL_CONTROL_EXTERNAL_HOST=server.example.com`
- Users access sessions at `http://server.example.com:8080/session/{session_id}`
- Agent logs show the correct external URLs for sharing

## 🛠️ Complete Tool Set (5 Agent-Controlled Tools)

### 📋 Session Management (2 tools)

#### **`list_terminal_sessions`**
List all active terminal sessions with detailed status information.

Shows comprehensive session information:
- Session IDs and commands for identification
- Session states (active, waiting, error, terminated)
- Creation timestamps and last activity times
- Total session count (max 50 concurrent)
- **Web interface URLs** logged for user access

#### **`exit_terminal`**
Terminate and cleanup a terminal session safely.

### 🤖 Agent-Controlled Interaction (2 tools)

#### **`get_screen_content`**
Get current terminal screen content with timestamp.

**Key features:**
- Returns current terminal output visible to user
- Includes ISO timestamp for agent timing decisions
- Process running status
- Agents decide when to wait longer based on timestamps

**Agent workflow:**
1. Call `get_screen_content` to see current terminal state
2. Analyze screen content and timestamp
3. Decide whether to wait longer or take action
4. Use `send_input` when process is ready for input

**User access**: Same content visible in web interface for direct interaction

#### **`send_input`**
Send text input to a terminal session.

**Features:**
- Send any text input to the running process
- Automatic newline appending
- No timeouts - agents control timing
- Works with any terminal program
- **Parallel user input** possible through web interface

### 🔗 Session Creation (1 tool)

#### **`open_terminal`**
Execute any command and create a terminal session.

**Universal command execution:**
- ANY command: `ssh host`, `python script.py`, `ls`, `docker run -it image`, `make install`
- ALL commands create persistent sessions (interactive and non-interactive)
- Process startup timeout only (default: 30 seconds)
- Environment variables and working directory control
- Returns initial screen content immediately - agents can see terminal state right away
- Returns session ID for agent-controlled interaction
- **Web interface URL** logged for direct user access

**Agent-controlled workflow:**
1. `open_terminal` - Creates session with specified shell and returns initial screen content
2. `send_input` - Agent sends commands or input to the terminal
3. `get_screen_content` - Agent checks current terminal state when needed
4. Repeat steps 2-3 as needed (agent controls timing)
5. `exit_terminal` - Clean up when finished (REQUIRED for all sessions)

## 📚 Usage Examples & Tutorial

### Prerequisites

- Python 3.10+ installed
- Claude Code CLI installed and configured
- Basic familiarity with command line tools

### Quick Start Commands

```bash
# Install and activate
pip install -e ".[dev]"
claude mcp add terminal-control -s user terminal-control-mcp

# Verify installation
claude mcp list

# Test
python tests/conftest.py
```

### Essential Tool Examples

#### Basic Commands
```bash
# Just ask Claude naturally:
"Start a Python session and show me what's on screen"
"List all my active terminal sessions" 
"What's currently showing in the terminal?"
"Type 'print(2+2)' in the Python session"
"Close that debugging session for me"

# Claude will provide web interface URLs for direct access:
# "Session created! You can also access it directly at http://localhost:8080/session/session_abc123"
```

#### Interactive Programs
```bash
# Natural requests:
"Start a Python REPL and help me calculate 2+2"
"SSH into that server and check disk space" 
"Connect to mysql and show me the tables"
"Debug this script and set some breakpoints"
"Run ls -la and tell me what files are there"
"Check git status and tell me what changed"
```

#### Complex Workflows  
```bash
# Just describe what you want:
"Debug this Python script - set a breakpoint and step through it"
"SSH to the server, enter my password when prompted, then check logs"
"Install this software and handle any prompts that come up"
```

### 🌐 Web Interface Usage Examples

#### Direct Terminal Access
```bash
# After creating a session with Claude:
1. Claude: "I've started a Python debugger session. You can also access it directly at http://localhost:8080/session/session_abc123"
2. User opens the URL in browser
3. User sees live terminal output and can type commands directly
4. Both agent and user can interact with the same session simultaneously
```

#### Monitoring Long-Running Processes
```bash
# For monitoring builds, deployments, or long-running scripts:
1. Agent starts process: "Starting your build process..."
2. User opens web interface to monitor progress in real-time
3. User can send manual commands if needed (like stopping the process)
4. Agent continues to monitor and respond as needed
```

### 🐛 Complete Debugging Tutorial with `examples/example_debug.py`

This walkthrough shows how to debug a real Python script using natural language with Claude.

#### Getting Started
```
> "Debug the file examples/example_debug.py in a terminal session and show me what we're working with"
```

Claude will start the Python debugger and show you:
```
> /path/to/examples/example_debug.py(36)main()
-> print("Starting calculations...")
(Pdb) 
```

**Pro tip**: Claude will also provide a web interface URL where you can view the same debugger session in your browser and send commands directly if needed.

#### Exploring the Code
```
> "Show me the source code around the current line"
```

Claude types `l` in the debugger and you see the code context.

#### Finding the Bug
```
> "Set a breakpoint where the bug is, then run the program"
```

Claude sets the breakpoint with `b [line_number]`, continues with `c`, and the program runs until it hits the buggy loop.

#### Investigating Variables
```
> "What variables do we have here? Show me their values"
```

Claude uses `pp locals()` to show you all the local variables at that point.

#### Understanding the Problem  
```
> "Step through this loop and show me what's happening with the index"
```

Claude steps through with `n` and checks `p i, len(data)` to reveal the off-by-one error.

#### Wrapping Up
```
> "We found the bug! Clean up this debugging session"
```

Claude terminates the debugger and cleans up the session.

### Advanced Usage Examples

#### Multi-Step Interactive Sessions

**Python Debugging**:
> "Start a Python debugger session, wait for the (Pdb) prompt, set a breakpoint, then continue execution and examine variables when we hit it."

**SSH Session Management**:
> "Connect to SSH server, wait for password prompt, authenticate, then navigate to log directory and monitor the latest log file."

**Database Interaction**:
> "Start mysql client, wait for connection, authenticate when prompted, then show databases and describe table structure."

### Real-World Applications

**Development Workflows**:
- Interactive debugging with GDB, PDB, LLDB
- Git operations requiring user input
- Docker container interaction
- Kubernetes pod debugging

**System Administration**:
- SSH server management
- Database administration
- Interactive installers and configurators
- System monitoring and diagnostics

**Testing and QA**:
- Interactive test runners
- Manual testing of CLI tools
- Integration testing across systems

### Troubleshooting

#### Common Issues

**Session Won't Start**:
- Verify the command exists and is executable
- Check file permissions and paths
- Ensure working directory is correct

**Process Not Responding**:
- Use `get_screen_content` to see current state
- Check timestamps to see if output is recent
- Look for blocking prompts requiring input

**Session Becomes Unresponsive**:
- Use `list_terminal_sessions` to check session state
- Use `exit_terminal` to clean up and start fresh
- Check for programs waiting for input

#### Debug Mode

Enable verbose logging:
```bash
export INTERACTIVE_AUTOMATION_LOG_LEVEL=DEBUG
claude code
```

### Development Testing

```bash
# Run functionality tests
python tests/conftest.py

# Install with development dependencies
pip install -e ".[dev]"

# Run code quality checks
ruff check src/ tests/
mypy src/ --ignore-missing-imports

# Run all tests
pytest tests/
```

## 💡 Universal Examples

### 🔑 Agent-Controlled Interactive Examples
```bash
# Natural language commands to Claude:
"Start SSH session to prod.example.com, wait for prompts, handle authentication"
"Launch Python debugger, set breakpoints when ready, step through execution"
"Start mysql client, authenticate when prompted, then run diagnostic queries"
"Connect to docker container interactively, explore filesystem step by step"
"Launch Redis CLI, wait for connection, then check memory usage"
```

### 🚀 Terminal Program Examples
```bash
# Primary use cases - Interactive and long-running commands:
"Start session: ssh user@host"
"Launch: docker exec -it myapp bash"
"Run: kubectl exec -it pod-name -- sh"
"Debug: gdb ./myprogram"
"Profile: python -m pdb myscript.py"
"Monitor: tail -f /var/log/syslog"
"Stream: nc -l 8080"
"Connect: minicom /dev/ttyUSB0"
"Attach: tmux attach-session -t main"

# Also works with simple commands (though direct execution may be more efficient):
"Execute: ls -la /var/log"
"Run: git status"
"Check: ps aux | grep python"
```

### 🐍 Agent-Controlled Debugging
```bash
# Natural language commands to Claude:
"Start PDB debugging session, wait for prompt, then set strategic breakpoints"
"Launch debugger, examine crash point, analyze variables step by step"
"Debug Flask app interactively: set breakpoints, trace requests, inspect state"
"Attach to running process, debug live issues with agent timing control"
```

### 🔧 Complex Agent Workflows
```bash
# Natural language commands to Claude:
"SSH to server, authenticate, check services, restart if needed - handle all prompts"
"Debug crashed program: load core dump, analyze stack, suggest fixes interactively"
"Database maintenance: connect, check health, run maintenance, monitor progress"
"Deploy application: upload, configure, test, rollback if issues - handle all interactions"
```

## 🔒 Security

**Agent-Controlled Design Philosophy**: Maximum flexibility with user responsibility
- **Command filtering** - Only allows secure commands (e.g., no `rm -rf /`)
- **Path restrictions** - Commands run in user-specified directories, preventing unauthorized access
- **All commands create sessions** - Both interactive and non-interactive commands create persistent sessions
- **Agent-controlled output** - No direct output from execute_command, agents use get_screen_content
- **Rate limiting** - 60 calls per minute to prevent abuse
- **Session limits** - 50 concurrent sessions to prevent resource exhaustion
- **Comprehensive logging** - Full audit trail of all operations
- **User responsibility** - Security is managed by the user and agent, not the MCP server

## 📁 Project Structure

```
terminal-control-mcp/
├── src/terminal_control_mcp/
│   ├── main.py                 # FastMCP server with 5 MCP tools
│   ├── session_manager.py      # Terminal session lifecycle management
│   ├── interactive_session.py  # Tmux/libtmux terminal process control
│   ├── web_server.py          # FastAPI web interface with WebSocket
│   ├── security.py            # Multi-layer security validation
│   ├── models.py              # Pydantic request/response models
│   ├── interaction_logger.py   # Session interaction logging
│   ├── automation_types.py     # Type definitions for automation
│   ├── utils.py               # Logging and utility functions
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── index.html         # Session overview page template
│   │   └── session.html       # Individual session interface template
│   └── static/               # Web interface static assets
│       ├── css/              # Stylesheets
│       │   ├── main.css      # Overview page styles
│       │   └── session.css   # Session interface styles
│       └── js/               # JavaScript modules
│           ├── overview.js   # Session overview functionality
│           ├── session.js    # Session interface logic
│           └── keyboard-shortcuts.js # Terminal keyboard handling
├── tests/
│   ├── conftest.py            # Pytest fixtures and configuration
│   ├── test_security_manager.py # Security validation tests
│   ├── test_execute_command.py   # MCP tool integration tests
│   ├── test_mcp_integration.py   # End-to-end workflow tests
│   └── test_edge_cases.py        # Edge cases and error handling
├── examples/
│   └── example_debug.py       # Sample debugging script for testing
├── logs/                      # Session interaction logs
│   └── interactions/          # Detailed session logs (JSON & text)
├── CLAUDE.md                  # Development guidance for AI assistants
├── README.md                  # This file
├── pyproject.toml            # Python packaging and tool configuration
└── pytest.ini               # Pytest configuration
```

## 🚀 Development Status

- ✅ **Tmux Integration** - Complete libtmux-based terminal control
- ✅ **Web Interface** - Real-time xterm.js with WebSocket synchronization
- ✅ **Agent Control** - 5 MCP tools for complete session lifecycle management
- ✅ **Security Layer** - Multi-layer input validation and audit logging
- ✅ **Type Safety** - Full Pydantic model validation and mypy coverage
- ✅ **Test Coverage** - 88 passing tests covering security, integration, and edge cases
- ✅ **Code Quality** - Clean architecture with black, ruff, and mypy validation
- ✅ **Production Ready** - Reliable session management with proper cleanup

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `ruff check src/ tests/ && mypy src/ --ignore-missing-imports && pytest tests/`
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 🙏 Acknowledgments

- Built on the [Model Context Protocol (MCP)](https://github.com/anthropics/mcp) by Anthropic
- Uses [libtmux](https://libtmux.git-pull.com/) for reliable terminal multiplexing and session management
- Powered by [FastAPI](https://fastapi.tiangolo.com/) for the web interface and [xterm.js](https://xtermjs.org/) for browser-based terminal emulation