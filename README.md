# Interactive Automation MCP Server

A comprehensive MCP (Model Context Protocol) server that enables Claude Code to perform expect/pexpect-style automation for interactive programs. This server provides intelligent automation for programs that require user interaction, such as SSH sessions, database connections, interactive installers, and debugging workflows.

## ✨ Features

- **🔄 Automated Interactive Sessions**: Handle complex multi-step interactions with terminal programs
- **🎯 Pattern-Based Automation**: Wait for specific prompts and automatically respond
- **📊 Session Management**: Maintain persistent interactive sessions across multiple operations
- **🐛 Debugging Integration**: Enable LLM-powered debugging with GDB, PDB, LLDB
- **🚀 High-Level Automation Patterns**: Pre-built workflows for SSH, databases, and common tools
- **🔒 Security-First Design**: Comprehensive security controls and resource management
- **🐍 Python Debugging**: Full PDB integration with automatic breakpoint setting

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

1. **Install and activate the server**:
   ```bash
   cd /path/to/interactive-automation-mcp
   source .venv/bin/activate
   ```

2. **Add to your Claude Code configuration**:
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

3. **Alternative configuration using Python directly**:
   ```json
   {
     "mcpServers": {
       "interactive-automation": {
         "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
         "args": ["-m", "interactive_automation_mcp.main"],
         "cwd": "/path/to/interactive-automation-mcp"
       }
     }
   }
   ```

4. **Restart Claude Code** to load the new MCP server

### 🔧 Visual Studio Code with GitHub Copilot

1. **Install the MCP extension** (if available) or use the built-in MCP support

2. **Configure in VS Code settings**:
   - Open **Settings** (`Ctrl+,` or `Cmd+,`)
   - Search for "MCP" or "Model Context Protocol"
   - Add server configuration:
   ```json
   {
     "mcp.servers": {
       "interactive-automation": {
         "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
         "args": ["-m", "interactive_automation_mcp.main"],
         "cwd": "/path/to/interactive-automation-mcp",
         "env": {
           "PYTHONPATH": "/path/to/interactive-automation-mcp/src"
         }
       }
     }
   }
   ```

3. **Alternative: Use VS Code tasks**:
   - Create `.vscode/tasks.json`:
   ```json
   {
     "version": "2.0.0",
     "tasks": [
       {
         "label": "Start Interactive Automation MCP",
         "type": "shell",
         "command": "source .venv/bin/activate && interactive-automation-mcp",
         "group": "build",
         "presentation": {
           "echo": true,
           "reveal": "always",
           "focus": false,
           "panel": "new"
         },
         "options": {
           "cwd": "/path/to/interactive-automation-mcp"
         }
       }
     ]
   }
   ```

4. **Reload VS Code** to apply the configuration

### 💎 Gemini CLI (Google)

1. **Install Gemini CLI** if not already installed:
   ```bash
   pip install google-generativeai
   ```

2. **Configure MCP server for Gemini**:
   ```bash
   # Create Gemini MCP configuration directory
   mkdir -p ~/.config/gemini-cli/mcp
   
   # Create MCP server configuration
   cat > ~/.config/gemini-cli/mcp/interactive-automation.json << 'EOF'
   {
     "name": "interactive-automation",
     "command": "/path/to/interactive-automation-mcp/.venv/bin/python",
     "args": ["-m", "interactive_automation_mcp.main"],
     "cwd": "/path/to/interactive-automation-mcp",
     "env": {
       "PYTHONPATH": "/path/to/interactive-automation-mcp/src"
     }
   }
   EOF
   ```

3. **Start Gemini CLI with MCP support**:
   ```bash
   gemini-cli --mcp-config ~/.config/gemini-cli/mcp/interactive-automation.json
   ```

4. **Alternative: Use environment variables**:
   ```bash
   export GEMINI_MCP_SERVERS="interactive-automation:/path/to/interactive-automation-mcp/.venv/bin/python:-m:interactive_automation_mcp.main"
   export GEMINI_MCP_CWD="/path/to/interactive-automation-mcp"
   gemini-cli
   ```

### 🐳 Docker Setup (All Platforms)

For containerized deployment:

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.10-slim
   
   WORKDIR /app
   COPY . .
   
   RUN pip install -e .
   
   EXPOSE 8080
   CMD ["interactive-automation-mcp"]
   ```

2. **Build and run**:
   ```bash
   docker build -t interactive-automation-mcp .
   docker run -p 8080:8080 interactive-automation-mcp
   ```

3. **Configure your AI assistant to connect to**:
   ```
   http://localhost:8080
   ```

### 🔧 Troubleshooting

**Common Issues:**

1. **"Command not found"**: Ensure virtual environment is activated and package is installed
2. **"Permission denied"**: Check file permissions and executable paths
3. **"Module not found"**: Verify PYTHONPATH includes the src directory
4. **"Connection refused"**: Ensure MCP server is running and accessible

**Debug commands:**
```bash
# Test server directly
source .venv/bin/activate
interactive-automation-mcp --help

# Test Python module
python -m interactive_automation_mcp.main --help

# Check installation
pip show interactive-automation-mcp
```

## 🛠️ Complete Tool Set (7 Truly Universal Tools)

### 📋 Session Management (3 tools)
- **`create_interactive_session`**: Create new interactive sessions for any program
- **`list_sessions`**: List all active sessions with detailed information
- **`destroy_session`**: Terminate and cleanup sessions safely

### 🤖 Basic Automation (2 tools)
- **`expect_and_respond`**: Wait for pattern and send response (universal)
- **`multi_step_automation`**: Execute sequence of automation steps (any program)

### 🔗 Universal Connection Tool (1 tool)
- **`connect_with_auth`**: Connect to ANY interactive program with authentication
  - **SSH**: `program_type: "ssh"` - SSH connections with password/key auth
  - **MySQL**: `program_type: "mysql"` - MySQL database connections
  - **PostgreSQL**: `program_type: "postgresql"` - PostgreSQL database connections
  - **MongoDB**: `program_type: "mongodb"` - MongoDB database connections
  - **Redis**: `program_type: "redis"` - Redis database connections
  - **FTP/SFTP**: `program_type: "ftp"/"sftp"` - File transfer protocols
  - **Telnet**: `program_type: "telnet"` - Telnet connections
  - **GDB**: `program_type: "gdb"` - GNU Debugger for C/C++
  - **PDB**: `program_type: "pdb"` - Python Debugger
  - **LLDB**: `program_type: "lldb"` - LLVM Debugger
  - **Node.js**: `program_type: "node"` - Node.js Inspector
  - **PHP**: `program_type: "php"` - PHP Xdebug
  - **Ruby**: `program_type: "ruby"` - Ruby Debugger
  - **Java**: `program_type: "java"` - Java Debugger (JDB)
  - **Custom**: `program_type: "custom"` - Any custom program with custom_command

### 🔍 Universal Analysis Tool (1 tool)
- **`analyze_session`**: Perform comprehensive analysis of any interactive session
  - **Crash Analysis**: `analysis_type: "crash"` - Crash analysis (auto-detects debugger)
  - **Performance Analysis**: `analysis_type: "performance"` - Performance profiling
  - **Security Analysis**: `analysis_type: "security"` - Security vulnerability analysis
  - **Debug Analysis**: `analysis_type: "debug"` - General debugging analysis
  - **Log Analysis**: `analysis_type: "log"` - Log parsing and analysis
  - **Custom Analysis**: `analysis_type: "custom"` - Custom analysis with custom commands

## 💡 Usage Examples

### 🔑 Universal Connection Examples
```bash
# Natural language commands to Claude:
"Connect to prod.example.com via SSH and check disk usage"
"Connect to my MySQL database on localhost and show tables"
"Connect to my PostgreSQL server and analyze slow queries"
"Connect to my Redis instance and check memory usage"
"Connect to my MongoDB cluster and show collections"
"Connect to my FTP server and list files"
"Connect to my C++ program with GDB and set breakpoints at main and init"
"Connect to my Python script with PDB and break at line 15"
"Connect to my crashed program using the core dump file with GDB"
"Connect to my Node.js application with inspector"
"Connect to my PHP script with Xdebug"
"Connect to my Java application with JDB"
"Connect to my custom application using 'myapp --interactive'"
```

### 🔍 Universal Analysis Examples
```bash
# Natural language commands to Claude:
"Analyze my debugging session for crash information"
"Analyze my session for performance issues"
"Analyze my session for security vulnerabilities"
"Analyze my session for general debugging information"
"Analyze my session logs for error patterns"
"Analyze my session with custom analysis commands"
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

This server operates with comprehensive security restrictions:
- **Command filtering** to prevent dangerous operations (`rm -rf /`, `shutdown`, etc.)
- **Path validation** to prevent directory traversal attacks
- **Rate limiting** to prevent abuse (60 calls per minute)
- **Session limits** to prevent resource exhaustion (50 concurrent sessions)
- **Signal restrictions** to only allow safe signals
- **Comprehensive logging** for audit trails

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
- **[Complete Tool List](docs/COMPLETE_TOOL_LIST.md)** - All 17 available tools

## 🚀 Development Status

- ✅ **Production Ready** - All 17 tools implemented and tested
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