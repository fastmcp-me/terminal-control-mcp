# Terminal Control MCP Server

A modern MCP server that enables AI agents to control terminal sessions through persistent tmux-based sessions. Features real-time web interface for direct user access, comprehensive security controls, and support for interactive terminal programs including debuggers, SSH connections, and database clients.

## ✨ Features

### 🖥️ **Tmux-Based Terminal Control**
- **Reliable Backend**: Built on tmux and libtmux for stable terminal multiplexing
- **Session Persistence**: Long-running sessions with automatic cleanup and monitoring
- **Raw Stream Capture**: Direct terminal output via tmux pipe-pane
- **Agent-Controlled**: AI agents manage timing and interaction flow without automatic timeouts
- **Flexible Content Modes**: Get screen, history, since-input, or tail output for optimal workflow control
- **Dual Access**: Both agent (MCP tools) and user (web browser) can interact simultaneously

### 🌐 **Optional Web Interface**
- **Real-time Terminal**: Live xterm.js terminal emulator with WebSocket updates
- **Session URLs**: Direct browser access to any terminal session
- **Zero Setup**: Automatic web server startup with configurable networking
- **Manual Control**: Send commands directly without interrupting agent workflows
- **Session Management**: View all active sessions and their status

### 🛡️ **Comprehensive Security**
- **Command Filtering**: Block dangerous operations (`rm -rf /`, `sudo`, disk formatting, etc.)
- **Path Protection**: Restrict access to user directories only
- **Rate Limiting**: 60 calls/minute with session limits (max 50 concurrent)
- **Audit Logging**: Complete security event tracking
- **Input Validation**: Multi-layer validation for all inputs
- **Configurable Levels**: Off, low, medium, high protection levels

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

**Python Requirements**: Python 3.11 or later

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install the package
pip install .

# Or install in development mode
pip install -e ".[dev]"
```

### Configuration

The server supports configuration through TOML files and environment variables:

#### **Claude Code (Anthropic)**

1. **Install the package** (required for console script):
   ```bash
   pip install .
   ```

2. **Add the MCP server**:
   ```bash
   # Recommended: User scope (available across all projects)
   claude mcp add terminal-control -s user terminal-control-mcp
   
   # Alternative: Project scope (current project only)
   claude mcp add terminal-control terminal-control-mcp
   ```

3. **Verify installation**:
   ```bash
   claude mcp list
   ```

The MCP server will be automatically launched by Claude Code when needed. The web interface starts automatically (if enabled) for direct session access.

#### **Other MCP Clients**

For other MCP clients, add to your configuration:

```json
{
  "mcpServers": {
    "terminal-control": {
      "command": "terminal-control-mcp",
      "cwd": "/path/to/working/directory"
    }
  }
}
```

## 🔧 Configuration

### **Configuration Methods**

The server supports two configuration methods:

1. **TOML Configuration File** (recommended): `terminal-control.toml`
2. **Environment Variables**: Override TOML settings for deployment

### **Configuration Options**

#### **Web Server**
```bash
# Enable/disable web interface (default: false)
export TERMINAL_CONTROL_WEB_ENABLED=false

# Web server networking
export TERMINAL_CONTROL_WEB_HOST=0.0.0.0     # Default: bind to all interfaces
export TERMINAL_CONTROL_WEB_PORT=8080        # Default port
export TERMINAL_CONTROL_WEB_AUTO_PORT=true   # Automatic unique port selection
export TERMINAL_CONTROL_EXTERNAL_HOST=server.example.com  # External hostname for URLs
```

**Web Interface Modes:**
- **Enabled** (`web_enabled=true`): Real-time web interface with xterm.js terminal emulator
- **Disabled** (`web_enabled=false`): Automatically opens system terminal windows attached to tmux sessions

#### **Security**
```bash
# Security level (default: high)
export TERMINAL_CONTROL_SECURITY_LEVEL=high  # off, low, medium, high

# Rate limiting and session limits
export TERMINAL_CONTROL_MAX_CALLS_PER_MINUTE=60
export TERMINAL_CONTROL_MAX_SESSIONS=50
```

**Security Levels:**
- **`off`**: No validation (⚠️ **USE WITH EXTREME CAUTION**)
- **`low`**: Basic input validation only
- **`medium`**: Standard protection (blocks common dangerous commands)
- **`high`**: Full protection (comprehensive validation and filtering)

#### **Session Configuration**
```bash
# Default shell and timeout
export TERMINAL_CONTROL_DEFAULT_SHELL=bash
export TERMINAL_CONTROL_SESSION_TIMEOUT=30
```

#### **Terminal Configuration**
```bash
# Terminal dimensions
export TERMINAL_CONTROL_TERMINAL_WIDTH=120
export TERMINAL_CONTROL_TERMINAL_HEIGHT=30

# Performance tuning
export TERMINAL_CONTROL_TERMINAL_POLLING_INTERVAL=0.05
export TERMINAL_CONTROL_TERMINAL_SEND_INPUT_DELAY=0.1

# Process timeouts
export TERMINAL_CONTROL_TERMINAL_CLOSE_TIMEOUT=5.0
export TERMINAL_CONTROL_TERMINAL_PROCESS_CHECK_TIMEOUT=1.0
```

**Terminal Emulator Support:**
The system automatically detects and uses available terminal emulators in order of preference:
- **GNOME/GTK**: gnome-terminal
- **KDE**: konsole  
- **XFCE**: xfce4-terminal
- **Elementary OS**: io.elementary.terminal
- **Generic**: x-terminal-emulator, xterm
- **macOS**: Terminal (via `open -a Terminal`)
- **Modern terminals**: alacritty, kitty, terminator

**Custom Terminal Emulator Configuration:**
You can customize terminal emulator preferences through the `[terminal]` section in `terminal-control.toml`:

```toml
[terminal]
# Terminal dimensions and performance settings
width = 120
height = 30
close_timeout = 5.0
process_check_timeout = 1.0
polling_interval = 0.05
send_input_delay = 0.1

# Custom terminal emulator configuration (ordered by preference)
emulators = [
    { name = "my-terminal", command = ["my-terminal", "--exec"] },
    { name = "gnome-terminal", command = ["gnome-terminal", "--"] },
    { name = "konsole", command = ["konsole", "-e"] },
    # ... other terminals
]
```

#### **Multi-Instance Port Management**

**Automatic Port Selection:**
When multiple server instances run simultaneously, ports are automatically selected to avoid conflicts:

```bash
# Automatic port selection (default: enabled)
export TERMINAL_CONTROL_WEB_AUTO_PORT=true

# How it works:
# - Base port: 9000-9999 range
# - Selection: hash(working_dir + process_id) % 1000 + 9000
# - Consistent: Same directory always gets same port
```

### **TOML Configuration Example**

Create `terminal-control.toml` in your project root:

```toml
[web]
enabled = false         # Use terminal windows instead of web interface
host = "0.0.0.0"
port = 8080
auto_port = true        # Automatic unique port selection

[security]
level = "high"
max_calls_per_minute = 60
max_sessions = 50

[session]
default_shell = "bash"
timeout = 30

[terminal]
width = 120
height = 30
close_timeout = 5.0
process_check_timeout = 1.0
polling_interval = 0.05
send_input_delay = 0.1

[logging]
level = "INFO"
```

## 🛠️ MCP Tools (5 Tools)

The server provides 5 MCP tools for complete terminal session lifecycle management:

### **Session Management**

#### **`list_terminal_sessions`**
List all active terminal sessions with status information.

**Returns:**
- Session IDs, commands, and states
- Creation timestamps and last activity
- Total session count (max 50)
- Web interface URLs (if enabled)

#### **`exit_terminal`**
Terminate and cleanup a terminal session.

**Parameters:**
- `session_id`: Session ID to destroy

**Features:**
- **Bidirectional cleanup**: Sessions destroyed when agents call `exit_terminal` OR when users type `exit`
- **Automatic monitoring**: Dead sessions detected and cleaned up every 5 seconds
- **Terminal window management**: Closes associated terminal windows when web interface is disabled

### **Content Retrieval**

#### **`get_screen_content`**
Get terminal content with precise control over output format.

**Parameters:**
- `session_id`: Session to get content from
- `content_mode`: Content retrieval mode
  - `"screen"` (default): Current visible screen only
  - `"since_input"`: Output since last input command
  - `"history"`: Full terminal history
  - `"tail"`: Last N lines (requires `line_count`)
- `line_count`: Number of lines for tail mode

**Returns:**
- Terminal content based on mode
- Process running status
- ISO timestamp for agent timing decisions

### **Input Control**

#### **`send_input`**
Send input to terminal sessions.

**Parameters:**
- `session_id`: Target session
- `input_text`: Text to send (supports escape sequences)

**Important:** Newlines are NOT automatically added. For command execution, explicitly include `\n` (e.g., `"ls\n"`, `"python\n"`).

**Features:**
- Raw input support with escape sequences
- No automatic timeouts (agent-controlled timing)
- Parallel user input possible via web interface

### **Session Creation**

#### **`open_terminal`**
Create new terminal sessions.

**Parameters:**
- `shell`: Shell to use (bash, zsh, fish, sh, etc.)
- `working_directory`: Starting directory (optional)
- `environment`: Environment variables (optional)

**Returns:**
- Unique session ID
- Initial screen content
- Web interface URL (if enabled)
- Process startup status

**Features:**
- Universal shell support
- Environment and directory control
- Immediate screen content availability

## 📚 Usage Examples

### **Basic Commands**

```bash
# Natural language requests to Claude:
"Start a Python session and show me what's on screen"
"List all my active terminal sessions"
"What's currently showing in the terminal?"
"Type 'print(2+2)' in the Python session"
"Close that debugging session"
```

### **Interactive Programs**

```bash
# Complex interactive workflows:
"Start a Python REPL and help me debug this script"
"SSH into the server and check disk space"
"Connect to MySQL and show me the database tables"
"Run the debugger and set breakpoints in the main function"
"Start a docker container and explore the filesystem"
```

### **Debugging Workflow**

Using the included `examples/example_debug.py`:

```bash
# 1. Start debugging session
"Debug the file examples/example_debug.py and show me the code"

# 2. Explore and set breakpoints
"Show me the source code around the current line"
"Set a breakpoint where the bug occurs"

# 3. Investigate the problem
"Step through the buggy loop and show variable values"
"What variables do we have here? Show their values"

# 4. Clean up
"We found the bug! Clean up this debugging session"
```

**Pro tip:** The MCP server logs web interface URLs that you can use to view and interact with the same debugger session in your browser.

### **Web Interface Usage**

When web interface is enabled:
1. Agent creates session: `"Starting debugger session..."`
2. Agent provides URL: `"You can also access it at http://localhost:9123/session/abc123"`
3. User opens URL in browser for direct interaction
4. Both agent and user can send commands simultaneously

## 🌐 Web Interface

### **Real-Time Terminal Access**
- **Live output**: See exactly what agents see in real-time
- **Manual input**: Send commands directly without agent awareness
- **WebSocket updates**: Automatic screen refreshes
- **Session overview**: View all active sessions at once

### **Session URLs**
- **Individual sessions**: `http://localhost:8080/session/{session_id}`
- **Session overview**: `http://localhost:8080/`
- **Direct browser access**: No additional software required
- **Transparent to agents**: Manual interaction doesn't interfere with agent control

## 🔒 Security

### **Defense-in-Depth Approach**
- **Command filtering**: Blocks dangerous operations (`rm -rf /`, `sudo`, `dd`, etc.)
- **Path restrictions**: Commands run in specified directories only
- **Input validation**: Multi-layer validation for all inputs
- **Environment protection**: Protects critical variables (`PATH`, `LD_PRELOAD`, etc.)
- **Rate limiting**: Prevents abuse with configurable limits
- **Audit logging**: Complete security event tracking

### **Agent-Controlled Philosophy**
- **Maximum flexibility**: Security balanced with functionality
- **User responsibility**: Security managed by user and agent choices
- **Transparent operation**: All commands create persistent sessions
- **No hidden automation**: Agents control all timing and interaction

## 📁 Project Structure

```
terminal-control-mcp/
├── src/terminal_control_mcp/
│   ├── main.py                  # FastMCP server with 5 MCP tools
│   ├── session_manager.py       # Session lifecycle management
│   ├── interactive_session.py   # Tmux/libtmux process control
│   ├── terminal_utils.py        # Terminal window management
│   ├── web_server.py           # FastAPI web interface
│   ├── security.py             # Multi-layer security validation
│   ├── config.py               # TOML configuration handling
│   ├── models.py               # Pydantic request/response models
│   ├── templates/              # Web interface templates
│   │   ├── index.html          # Session overview page
│   │   └── session.html        # Individual session interface
│   └── static/                 # Web interface assets
│       ├── css/                # Stylesheets
│       └── js/                 # JavaScript modules
├── tests/                      # Comprehensive test suite
│   ├── test_security_manager.py
│   ├── test_execute_command.py
│   ├── test_session_lifecycle.py
│   └── test_mcp_integration.py
├── examples/
│   └── example_debug.py        # Sample debugging script
├── logs/interactions/          # Session interaction logs
├── CLAUDE.md                   # Development guidance
├── terminal-control.toml       # TOML configuration
└── pyproject.toml             # Python packaging configuration
```

## 🧪 Development

### **Testing**

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest -m unit        # Unit tests
pytest -m integration # Integration tests
pytest -m security    # Security tests

# Run with coverage
pytest --cov=src/terminal_control_mcp tests/
```

### **Code Quality**

```bash
# Type checking
mypy src/ --ignore-missing-imports

# Linting and formatting
ruff check src/ tests/
black src/ tests/

# Check for dead code
vulture src/
```

### **Development Installation**

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Test basic functionality
python tests/conftest.py
```

## 🚀 Development Status

- ✅ **Tmux Integration**: Complete libtmux-based terminal control
- ✅ **Web Interface**: Real-time xterm.js with WebSocket synchronization
- ✅ **Agent Control**: 5 MCP tools for complete session management
- ✅ **Security Layer**: Multi-layer validation and audit logging
- ✅ **TOML Configuration**: Structured configuration with environment overrides
- ✅ **Type Safety**: Full Pydantic models and mypy coverage
- ✅ **Test Coverage**: Comprehensive test suite with multiple categories
- ✅ **Production Ready**: Reliable session management with proper cleanup

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and add tests
4. Ensure all tests pass: 
   ```bash
   ruff check src/ tests/ && mypy src/ --ignore-missing-imports && pytest tests/
   ```
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 🙏 Acknowledgments

- Built on the [Model Context Protocol (MCP)](https://github.com/anthropics/mcp) by Anthropic
- Uses [libtmux](https://libtmux.git-pull.com/) for reliable terminal multiplexing
- Powered by [FastAPI](https://fastapi.tiangolo.com/) and [xterm.js](https://xtermjs.org/) for the web interface