# Interactive Automation MCP Server

A comprehensive MCP (Model Context Protocol) server that enables Claude Code to perform expect/pexpect-style automation for interactive programs. This server provides intelligent automation for programs that require user interaction, such as SSH sessions, database connections, interactive installers, and debugging workflows.

## ✨ Features

- **🔄 Automated Interactive Sessions**: Handle complex multi-step interactions with terminal programs
- **🎯 Pattern-Based Automation**: Wait for specific prompts and automatically respond
- **📊 Session Management**: Maintain persistent interactive sessions across multiple operations
- **🐛 Universal Debugging**: Debug ANY program (GDB, PDB, LLDB, custom debuggers)
- **🚀 Universal Command Execution**: Run ANY terminal command with optional automation
- **🔒 User-Controlled Security**: Maximum flexibility with user responsibility
- **🐍 Universal Programming Support**: Work with any programming language or tool

## 🚀 Quick Start

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

## 🎯 Platform Setup

### 🤖 Claude Code (Anthropic)

1. **Add to your Claude Code configuration**:
   - **Location**: `~/.config/claude-code/mcp_servers.json` (Linux/macOS) or `%APPDATA%\claude-code\mcp_servers.json` (Windows)
   - **Configuration**:
   ```json
   {
     "mcpServers": {
       "interactive-automation": {
         "command": "interactive-automation-mcp",
         "cwd": "/path/to/interactive-automation-mcp",
         "env": {
           "PATH": "/path/to/interactive-automation-mcp/.venv/bin:${PATH}"
         }
       }
     }
   }
   ```

2. **Alternative configuration using Python directly**:
   ```json
   {
     "mcpServers": {
       "interactive-automation": {
         "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
         "args": ["-m", "main"],
         "cwd": "/path/to/interactive-automation-mcp"
       }
     }
   }
   ```

3. **Restart Claude Code** to load the new MCP server

**Note**: The MCP server will be automatically launched by Claude Code when needed - no manual activation required.

### 🔧 Visual Studio Code with GitHub Copilot

1. **Configure in VS Code settings** (MCP extension or built-in support):
   - Open **Settings** (`Ctrl+,` or `Cmd+,`)
   - Search for "MCP" or "Model Context Protocol"
   - Add server configuration:
   ```json
   {
     "mcp.servers": {
       "interactive-automation": {
         "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
         "args": ["-m", "main"],
         "cwd": "/path/to/interactive-automation-mcp"
       }
     }
   }
   ```

2. **Alternative configuration using console script**:
   ```json
   {
     "mcp.servers": {
       "interactive-automation": {
         "command": "/path/to/interactive-automation-mcp/.venv/bin/interactive-automation-mcp",
         "cwd": "/path/to/interactive-automation-mcp"
       }
     }
   }
   ```

3. **Reload VS Code** to apply the configuration

**Note**: The MCP server will be automatically launched by VS Code when needed - no manual activation required.

### 💎 Other MCP-Compatible Clients

**Note**: As of now, the main MCP-compatible clients are Claude Code and VS Code with appropriate extensions. Google's Gemini does not currently have an official CLI with MCP support.

For other MCP clients that may be developed in the future, the general pattern is:

1. **Configure the MCP server**:
   ```json
   {
     "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
     "args": ["-m", "main"],
     "cwd": "/path/to/interactive-automation-mcp"
   }
   ```

2. **Check the client's documentation** for specific MCP server configuration requirements

### 🐳 Docker Setup (Optional)

For containerized environments, you can run the MCP server in a container:

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.10-slim
   
   WORKDIR /app
   COPY . .
   
   RUN pip install -e .
   
   # MCP servers use stdio, not HTTP
   CMD ["python", "main.py"]
   ```

2. **Configure MCP client to use containerized server**:
   ```json
   {
     "command": "docker",
     "args": ["run", "-i", "--rm", "interactive-automation-mcp"]
   }
   ```

**Note**: MCP uses stdio communication, not HTTP. The server will be automatically started by the MCP client when needed.

### 🔧 Troubleshooting

**Common Issues:**

1. **"Command not found"**: Check that the executable path in MCP configuration is correct
2. **"Permission denied"**: Check file permissions for the Python executable and script
3. **"Module not found"**: Verify the working directory (`cwd`) in MCP configuration is correct
4. **"Server won't start"**: Check MCP client logs for detailed error messages

**Debug commands:**
```bash
# Test server manually (for debugging only)
/path/to/.venv/bin/python main.py

# Check installation
pip show interactive-automation-mcp

# Verify executable exists
ls -la /path/to/.venv/bin/interactive-automation-mcp
```

**Note**: The MCP server should start automatically when the MCP client needs it. Manual activation is only for debugging purposes.

## 🛠️ Complete Tool Set (6 Truly Universal Tools)

### 📋 Session Management (3 tools)
- **`create_interactive_session`**: Create new interactive sessions for any program
- **`list_sessions`**: List all active sessions with detailed information
- **`destroy_session`**: Terminate and cleanup sessions safely

### 🤖 Basic Automation (2 tools)
- **`expect_and_respond`**: Wait for pattern and send response (universal)
- **`multi_step_automation`**: Execute sequence of automation steps (any program)

### 🔗 Universal Command Execution (1 tool)
- **`execute_command`**: Execute ANY command with optional automation - truly universal!
  - **Examples**: `ssh user@host`, `mysql -u root -p`, `gdb program`, `echo hello`, `ls -la`
  - **Automation**: Optional automation patterns for interactive prompts
  - **Arguments**: Optional `command_args` array for cleaner argument handling
  - **Supports**: Any terminal command - interactive or non-interactive

**Note**: Analysis, debugging, and advanced session control are all handled through the universal `execute_command` tool by running any command, and then using `expect_and_respond` or `multi_step_automation` to interact with the session.

## 💡 Usage Examples

### 🔑 Universal Connection Examples
```bash
# Natural language commands to Claude:
"Connect to prod.example.com via SSH and check disk usage"
"Connect to my MySQL database and show tables"
"Connect to my PostgreSQL server and analyze slow queries"
"Connect to my Redis instance and check memory usage"
"Connect to my MongoDB cluster and show collections"
"Connect to my FTP server and list files"
"Connect to my C++ program with GDB and set breakpoints"
"Connect to my Python script with PDB for debugging"
"Connect to my crashed program using GDB with core dump"
"Connect to my Node.js application with inspector"
"Connect to my Docker container and run commands"
"Connect to my Kubernetes pod and debug issues"
"Connect to my custom interactive application"
"Connect to any program that accepts interactive input"
```

### 🚀 Truly Universal Examples
```bash
# ANY command that runs in a terminal:
"Connect using command: ssh user@host"
"Connect using command: docker exec -it myapp bash"
"Connect using command: kubectl exec -it pod-name -- sh"
"Connect using command: nc -l 8080"
"Connect using command: socat - TCP:localhost:3000"
"Connect using command: python3 -c 'import code; code.interact()'"
"Connect using command: ./my-custom-repl --debug"
"Connect using command: minicom /dev/ttyUSB0"
"Connect using command: screen /dev/ttyACM0 9600"
"Connect using command: tmux attach-session -t main"
```

### 🔍 Universal Analysis Examples
```bash
# Natural language commands to Claude:
"Connect to my crashed program with GDB and analyze the crash"
"Connect to my Python script with PDB and set breakpoints"
"Connect to my performance monitoring tool and gather metrics"
"Connect to my log analysis tool and find error patterns"
"Connect to any program and then send commands to analyze it"
```

### 🔧 Advanced Automation
```bash
# Natural language commands to Claude:
"Connect to SSH, then connect to database, run diagnostics, and generate report"
"Debug the crashed server binary, analyze the core dump, and suggest fixes"
"Connect to multiple servers, check their status, and restart services if needed"
"Set up debugging session with custom debugger and analyze the issue"
```

### 🎯 Program-Specific Examples
```bash
# SSH with different auth methods:
"Connect to server using SSH key authentication"
"Connect to server using password authentication"

# Database-specific operations:
"Connect to MySQL with SSL and execute performance queries"
"Connect to PostgreSQL and analyze table statistics"

# Debugging with different targets:
"Debug program with core dump analysis"
"Attach debugger to running process ID 1234"
"Debug script with custom environment variables"
```

## 🔒 Security

**Universal Design Philosophy**: Maximum flexibility with user responsibility
- **No command filtering** - All commands allowed (including `sudo`, `su`, system commands)
- **No path restrictions** - All paths accessible (user controls access)
- **Rate limiting** - 60 calls per minute to prevent abuse
- **Session limits** - 50 concurrent sessions to prevent resource exhaustion
- **Comprehensive logging** - Full audit trail of all operations
- **User responsibility** - Security is managed by the user, not the MCP server

## 📁 Project Structure

```
interactive-automation-mcp/
├── main.py                     # Main entry point
├── pyproject.toml              # Modern Python project configuration
├── README.md                   # This file
├── src/
│   └── interactive_automation_mcp/
│       ├── main.py            # Core MCP server
│       ├── session_manager.py # Session lifecycle management
│       ├── security.py        # Security controls
│       └── ...                # Other modules
├── tests/                      # Test suite
├── docs/                       # Documentation
└── examples/                   # Example scripts
```

## 🧪 Testing

```bash
# Run tests
python tests/test_core.py
python tests/test_basic.py

# Install with development dependencies
pip install -e ".[dev]"

# Run with pytest
pytest tests/
```

## 📚 Documentation

- **[Installation Guide](docs/INSTALLATION.md)** - Detailed setup instructions
- **[Python Debug Guide](docs/PYTHON_DEBUG_GUIDE.md)** - Python debugging tutorial
- **[Complete Tool List](docs/COMPLETE_TOOL_LIST.md)** - All 6 universal tools

## 🚀 Development Status

- ✅ **Production Ready** - All 6 universal tools implemented and tested
- ✅ **Complete Security** - Comprehensive security controls
- ✅ **Full Documentation** - Complete guides and examples
- ✅ **Clean Architecture** - Well-organized, maintainable code
- ✅ **Python Debugging** - Full PDB integration
- ✅ **Modern Tooling** - pyproject.toml, uv, type hints

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 🙏 Acknowledgments

- Built on the [Model Context Protocol (MCP)](https://github.com/anthropics/mcp) by Anthropic
- Uses [pexpect](https://pexpect.readthedocs.io/) for terminal automation
- Inspired by the need for intelligent interactive automation in AI workflows