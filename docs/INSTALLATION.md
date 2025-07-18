# Installation and Usage Guide

## Quick Start

1. **Set up the environment**
   ```bash
   # Create virtual environment
   uv venv
   
   # Activate virtual environment
   source .venv/bin/activate
   
   # Install dependencies
   uv pip install -r requirements.txt
   ```

2. **Test the installation**
   ```bash
   # Run core tests
   python test_core.py
   
   # Run comprehensive tests
   python test_basic.py
   ```

3. **Start the server**
   ```bash
   # Start the MCP server
   python main.py
   ```

## Claude Code Integration

Add this to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "interactive-automation": {
      "command": "python",
      "args": ["main.py"],
      "cwd": "/path/to/MCPAutomationServer",
      "env": {
        "PYTHONPATH": "/path/to/MCPAutomationServer"
      }
    }
  }
}
```

## Usage Examples

### SSH Connection Example
```
"Connect to my production server at prod.example.com as admin user using SSH key authentication"
```

### Database Debugging Example
```
"Connect to my MySQL database and investigate slow query performance"
```

### Crash Analysis Example
```
"Debug this segfault in my C++ application using GDB"
```

## Configuration

Edit `config.yaml` to customize:
- Session limits
- Security settings
- Timeout values
- Logging preferences

## Security

The server includes comprehensive security features:
- Command filtering (blocks dangerous commands like `rm -rf /`)
- Path validation (prevents directory traversal)
- Rate limiting (60 calls per minute by default)
- Session management (50 sessions max by default)

## Troubleshooting

If you encounter issues:
1. Check that all dependencies are installed
2. Verify the virtual environment is activated
3. Review the logs for error messages
4. Ensure proper file permissions
5. Check that required system commands are available (ssh, mysql, gdb, etc.)

## Development

To contribute to this project:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request