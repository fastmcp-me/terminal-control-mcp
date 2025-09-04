[![Add to Cursor](https://fastmcp.me/badges/cursor_dark.svg)](https://fastmcp.me/MCP/Details/824/terminal-control)
[![Add to VS Code](https://fastmcp.me/badges/vscode_dark.svg)](https://fastmcp.me/MCP/Details/824/terminal-control)
[![Add to Claude](https://fastmcp.me/badges/claude_dark.svg)](https://fastmcp.me/MCP/Details/824/terminal-control)
[![Add to ChatGPT](https://fastmcp.me/badges/chatgpt_dark.svg)](https://fastmcp.me/MCP/Details/824/terminal-control)

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
- **History Isolation**: Prevent terminal sessions from polluting system history
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

**Python Requirements**: Python 3.9 or later

### Installation

#### **From PyPI (Recommended)**

```bash
# Install directly from PyPI
pip install terminal-control-mcp
```

#### **From Source**

```bash
# Clone the repository
git clone https://github.com/wehnsdaefflae/terminal-control-mcp.git
cd terminal-control-mcp

# Create virtual environment (choose one)
python -m venv .venv          # Using standard venv
# OR
uv venv                       # Using uv (faster)

# Activate virtual environment
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate      # Windows

# Install the package
pip install .

# Or install in development mode
pip install -e ".[dev]"
```

### Configuration

The server supports configuration through TOML files and environment variables:

#### **Claude Code (Anthropic)**

```bash
# Add the MCP server
claude mcp add terminal-control -s user terminal-control-mcp

# Verify installation
claude mcp list
```

The MCP server will be automatically launched by Claude Code when needed.

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

The server uses TOML configuration files with optional environment variable overrides. Environment variables can override any TOML setting for deployment flexibility.

### **Configuration File Locations**

The server looks for configuration files in this order:
1. `./terminal-control.toml` (current working directory)
2. `~/.config/terminal-control.toml` (user configuration directory)
3. `/etc/terminal-control.toml` (system-wide configuration)
4. Built-in defaults (if no config file found)

### **Configuration Sections**

#### **[web] - Web Interface Settings**

```toml
[web]
enabled = false         # Enable web interface (default: false)
host = "0.0.0.0"       # Bind address (default: "0.0.0.0")
port = 8080            # Port number (default: 8080)
auto_port = true       # Automatic unique port selection (default: true)
external_host = ""     # External hostname for URLs (optional)
```

**Web Interface Modes:**
- **Enabled**: Real-time web interface with xterm.js terminal emulator
- **Disabled**: Automatically opens system terminal windows attached to tmux sessions

**Auto Port Selection:** When `auto_port=true`, ports are automatically selected in the 9000-9999 range using `hash(working_dir + process_id) % 1000 + 9000` to avoid conflicts between multiple instances.

#### **[security] - Security Settings**

```toml
[security]
level = "high"              # Security level: off, low, medium, high
max_calls_per_minute = 60   # Rate limiting (calls per minute)
max_sessions = 50           # Maximum concurrent sessions
```

**Security Levels:**
- **`off`**: No validation (⚠️ **USE WITH EXTREME CAUTION**)
- **`low`**: Basic input validation only
- **`medium`**: Standard protection (blocks common dangerous commands)
- **`high`**: Full protection (comprehensive validation and filtering)

#### **[session] - Session Management**

```toml
[session]
default_shell = "bash"                      # Default shell for new sessions
timeout = 30                                # Session startup timeout (seconds)
isolate_history = true                      # Prevent sessions from polluting system history
history_file_prefix = "mcp_session_history" # Prefix for isolated history files
```

**History Isolation Features:**
- **Automatic Isolation**: Each session gets isolated history files in temporary directories
- **Multi-Shell Support**: Supports bash, zsh, fish, csh, tcsh, Python REPL, Node.js, PostgreSQL, MySQL
- **Session-Specific Files**: History files are prefixed with session IDs for complete isolation
- **Automatic Cleanup**: All history files are automatically deleted when sessions terminate
- **Configurable**: Can be disabled via `isolate_history = false` if system history is preferred

**Supported Applications:**
- **Bash**: `HISTFILE`, `HISTCONTROL`, `HISTSIZE`, `HISTFILESIZE`
- **Zsh**: `HISTFILE`, `ZDOTDIR`, `SAVEHIST`, `HISTSIZE`  
- **Fish**: `XDG_CONFIG_HOME`, `XDG_DATA_HOME`
- **Python**: `PYTHONSTARTUP` with readline configuration
- **Node.js**: `NODE_REPL_HISTORY`
- **PostgreSQL**: `PSQL_HISTORY`
- **MySQL**: `MYSQL_HISTFILE`

#### **[terminal] - Terminal Settings**

```toml
[terminal]
width = 120                      # Terminal width (columns)
height = 30                      # Terminal height (rows)
close_timeout = 5.0              # Terminal close timeout (seconds)
process_check_timeout = 1.0      # Process health check timeout (seconds)
polling_interval = 0.05          # Output polling interval (seconds)
send_input_delay = 0.1           # Delay after sending input (seconds)
```

**Terminal Emulator Support:**
The system automatically detects available terminal emulators in order of preference:
- **GNOME/GTK**: gnome-terminal
- **KDE**: konsole  
- **XFCE**: xfce4-terminal
- **Elementary OS**: io.elementary.terminal
- **Generic**: x-terminal-emulator, xterm
- **macOS**: Terminal (via `open -a Terminal`)
- **Modern terminals**: alacritty, kitty, terminator

**Custom Terminal Emulator Configuration:**
```toml
[terminal]
# Custom terminal emulator preferences (ordered by preference)
emulators = [
    { name = "my-terminal", command = ["my-terminal", "--exec"] },
    { name = "gnome-terminal", command = ["gnome-terminal", "--"] },
    { name = "konsole", command = ["konsole", "-e"] },
]
```

#### **[logging] - Logging Configuration**

```toml
[logging]
level = "INFO"    # Log level: DEBUG, INFO, WARNING, ERROR
```

### **Complete Configuration Example**

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

## 🛠️ MCP Tools (6 Tools)

The server provides 6 MCP tools for complete terminal session lifecycle management:

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

#### **`await_output`** 🆕
Wait for specific regex patterns to appear in terminal output.

**Parameters:**
- `session_id`: Session to monitor
- `pattern`: Regular expression pattern to match
- `timeout`: Maximum wait time in seconds (default: 10.0)

**Returns:**
- `match_text`: The matched text if pattern found, `null` if timeout
- `screen_content`: Current screen content when match occurred or timeout reached
- `elapsed_time`: Time elapsed before match or timeout
- `success`: Whether operation completed without errors

**Features:**
- **Regex pattern matching**: Full regular expression support for flexible output detection
- **Configurable timeout**: Control maximum wait time per pattern
- **Non-blocking**: Polls every 100ms without blocking other operations
- **Precise timing**: Returns exact elapsed time for performance optimization

**Use Cases:**
- Wait for build completion: `await_output(session_id, r"Build successful|BUILD SUCCESS", 300.0)`
- Monitor for errors: `await_output(session_id, r"ERROR|FAILED|Exception", 30.0)`  
- Detect prompt return: `await_output(session_id, r"\$\s*$|>\s*$", 5.0)`
- Wait for program startup: `await_output(session_id, r"Server running on|Listening on", 60.0)`

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

**Pro tip:** If you set `web_enabled=true` in your configuration, you can also access the debugging session directly in your browser for real-time interaction.

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
│   ├── main.py                  # FastMCP server with 6 MCP tools
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
- ✅ **Agent Control**: 6 MCP tools for complete session management
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
