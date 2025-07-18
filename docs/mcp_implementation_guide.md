# Complete Guide to Model Context Protocol (MCP) Server Implementation

## Table of Contents
1. [What is Model Context Protocol (MCP)?](#what-is-model-context-protocol-mcp)
2. [How MCP Works](#how-mcp-works)
3. [Setting Up Your Development Environment](#setting-up-your-development-environment)
4. [Building Your First MCP Server](#building-your-first-mcp-server)
5. [Advanced MCP Features](#advanced-mcp-features)
6. [Integration with Claude Code](#integration-with-claude-code)
7. [Testing and Debugging](#testing-and-debugging)
8. [Deployment and Distribution](#deployment-and-distribution)
9. [Best Practices and Security](#best-practices-and-security)

## What is Model Context Protocol (MCP)?

### Conceptual Overview

Model Context Protocol (MCP) is an open standard created by Anthropic that enables AI models like Claude to interact with external tools, applications, and data sources through a unified interface. Think of MCP as a "universal adapter" for AI - it standardizes how AI models communicate with external systems.

### Why MCP Matters

**Before MCP:**
- Each AI application needed custom integrations for every external tool
- Developers had to build separate connectors for databases, APIs, file systems, etc.
- No standardization meant lots of duplicated effort

**With MCP:**
- One standard protocol for all AI-tool interactions
- Modular, plug-and-play architecture
- AI models can discover and use tools dynamically
- Tools can be shared across different AI applications

### Key Concepts

**MCP Server**: A program that exposes tools, resources, or capabilities to AI models
**MCP Client**: An AI application (like Claude Code) that uses MCP servers
**Tools**: Functions that the AI can call to perform actions
**Resources**: Data sources that the AI can read from
**Prompts**: Pre-written templates that help users accomplish tasks

### Real-World Analogy

Imagine MCP as a "software power strip" for AI:
- Just like a power strip has standardized outlets that any device can plug into
- MCP provides standardized "connection points" that any tool can plug into
- The AI can then "power" any connected tool through the same interface

## How MCP Works

### Architecture Overview

```
┌─────────────────┐    JSON-RPC     ┌─────────────────┐
│   AI Client     │◄──────────────►│   MCP Server    │
│  (Claude Code)  │    over stdio   │  (Your Tool)    │
└─────────────────┘    or HTTP      └─────────────────┘
```

### Communication Protocol

MCP uses JSON-RPC 2.0 for communication between clients and servers. This means:
- All messages are JSON formatted
- Standardized request/response pattern
- Support for notifications and error handling

### Transport Methods

**1. Standard I/O (stdio)**
- Server runs as a subprocess
- Communication through stdin/stdout
- Most common for local tools

**2. HTTP/HTTPS**
- Server runs as web service
- Communication through HTTP requests
- Better for remote or cloud-based tools

**3. Server-Sent Events (SSE)**
- Real-time streaming communication
- Good for live data feeds

### Message Flow Example

```json
// Client requests available tools
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}

// Server responds with tool list
{
  "jsonrpc": "2.0", 
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "read_file",
        "description": "Read contents of a file",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          }
        }
      }
    ]
  }
}

// Client calls a tool
{
  "jsonrpc": "2.0",
  "id": 2, 
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {"path": "/home/user/document.txt"}
  }
}

// Server executes and responds
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Hello, this is the file content!"
      }
    ]
  }
}
```

## Setting Up Your Development Environment

### Prerequisites

**Python Environment:**
```bash
# Install Python 3.8 or higher
python3 --version

# Create virtual environment
python3 -m venv mcp-dev
source mcp-dev/bin/activate  # On Windows: mcp-dev\Scripts\activate

# Install MCP SDK
pip install mcp
```

**Node.js Environment:**
```bash
# Install Node.js 18 or higher
node --version

# Create new project
mkdir my-mcp-server
cd my-mcp-server
npm init -y

# Install MCP SDK
npm install @modelcontextprotocol/sdk
```

### Development Tools

**MCP Inspector** (for testing):
```bash
npm install -g @modelcontextprotocol/inspector
```

**Claude Code** (for integration testing):
```bash
npm install -g @anthropic-ai/claude-code
```

## Building Your First MCP Server

### Example 1: Simple File Operations Server (Python)

Let's build a basic MCP server that provides file operations.

**Step 1: Create the basic server structure**

```python
# file_server.py
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Create server instance
server = Server("file-operations")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="read_file",
            description="Read the contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="write_file", 
            description="Write content to a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string", 
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        types.Tool(
            name="list_directory",
            description="List contents of a directory", 
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    }
                },
                "required": ["path"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """Handle tool calls"""
    
    if name == "read_file":
        path = arguments.get("path")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [types.TextContent(type="text", text=content)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error reading file: {str(e)}")]
    
    elif name == "write_file":
        path = arguments.get("path")
        content = arguments.get("content")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return [types.TextContent(type="text", text=f"Successfully wrote to {path}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error writing file: {str(e)}")]
    
    elif name == "list_directory":
        import os
        path = arguments.get("path") 
        try:
            items = os.listdir(path)
            item_list = "\n".join(items)
            return [types.TextContent(type="text", text=f"Directory contents:\n{item_list}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error listing directory: {str(e)}")]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream, 
            InitializationOptions(
                server_name="file-operations",
                server_version="0.1.0", 
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test your server**

```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector python file_server.py

# This opens a web interface where you can:
# 1. See available tools
# 2. Call tools with parameters
# 3. View responses
```

### Example 2: Weather Server (Node.js)

```javascript
// weather-server.js
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';

class WeatherServer {
  constructor() {
    this.server = new Server(
      {
        name: 'weather-server',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
  }

  setupToolHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'get_weather',
            description: 'Get current weather for a location',
            inputSchema: {
              type: 'object',
              properties: {
                location: {
                  type: 'string',
                  description: 'City name or coordinates',
                },
              },
              required: ['location'],
            },
          },
          {
            name: 'get_forecast',
            description: 'Get weather forecast for a location',
            inputSchema: {
              type: 'object', 
              properties: {
                location: {
                  type: 'string',
                  description: 'City name or coordinates',
                },
                days: {
                  type: 'number',
                  description: 'Number of days to forecast',
                  minimum: 1,
                  maximum: 7,
                },
              },
              required: ['location'],
            },
          },
        ],
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      if (name === 'get_weather') {
        return await this.getCurrentWeather(args.location);
      } else if (name === 'get_forecast') {
        return await this.getWeatherForecast(args.location, args.days || 3);
      } else {
        throw new McpError(
          ErrorCode.MethodNotFound,
          `Unknown tool: ${name}`
        );
      }
    });
  }

  async getCurrentWeather(location) {
    // In a real implementation, you'd call a weather API
    // For this example, we'll return mock data
    const mockWeather = {
      location: location,
      temperature: Math.floor(Math.random() * 30) + 5,
      condition: ['sunny', 'cloudy', 'rainy', 'snowy'][Math.floor(Math.random() * 4)],
      humidity: Math.floor(Math.random() * 100),
      windSpeed: Math.floor(Math.random() * 20),
    };

    return {
      content: [
        {
          type: 'text',
          text: `Current weather in ${mockWeather.location}:
Temperature: ${mockWeather.temperature}°C
Condition: ${mockWeather.condition}
Humidity: ${mockWeather.humidity}%
Wind Speed: ${mockWeather.windSpeed} km/h`,
        },
      ],
    };
  }

  async getWeatherForecast(location, days) {
    // Mock forecast data
    const forecast = [];
    for (let i = 0; i < days; i++) {
      forecast.push({
        day: i + 1,
        temperature: Math.floor(Math.random() * 25) + 10,
        condition: ['sunny', 'cloudy', 'rainy'][Math.floor(Math.random() * 3)],
      });
    }

    const forecastText = forecast
      .map(day => `Day ${day.day}: ${day.temperature}°C, ${day.condition}`)
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `${days}-day forecast for ${location}:\n${forecastText}`,
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Weather MCP server running on stdio');
  }
}

const server = new WeatherServer();
server.run().catch(console.error);
```

**Package.json for Node.js server:**
```json
{
  "name": "weather-mcp-server",
  "version": "0.1.0",
  "type": "module",
  "main": "weather-server.js",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.5.0"
  },
  "scripts": {
    "start": "node weather-server.js"
  }
}
```

### Example 3: Database Query Server

```python
# database_server.py
import asyncio
import sqlite3
import json
from typing import List
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

server = Server("database-query")

# In-memory database for demo
def init_demo_database():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # Create demo table
    cursor.execute('''
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            salary INTEGER
        )
    ''')
    
    # Insert demo data
    employees = [
        (1, 'Alice Johnson', 'Engineering', 95000),
        (2, 'Bob Smith', 'Marketing', 72000),
        (3, 'Carol Davis', 'Engineering', 88000),
        (4, 'David Wilson', 'Sales', 65000)
    ]
    
    cursor.executemany('INSERT INTO employees VALUES (?, ?, ?, ?)', employees)
    conn.commit()
    return conn

# Global database connection
db_conn = init_demo_database()

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="execute_query",
            description="Execute a SQL query on the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="describe_tables",
            description="Get information about database tables",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    if name == "execute_query":
        query = arguments.get("query")
        try:
            cursor = db_conn.cursor()
            cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                # For SELECT queries, return results
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                if not rows:
                    return [types.TextContent(type="text", text="Query executed successfully. No rows returned.")]
                
                # Format results as table
                result = f"Columns: {', '.join(columns)}\n\n"
                for row in rows:
                    result += f"{', '.join(str(val) for val in row)}\n"
                
                return [types.TextContent(type="text", text=result)]
            else:
                # For non-SELECT queries
                db_conn.commit()
                return [types.TextContent(type="text", text=f"Query executed successfully. {cursor.rowcount} rows affected.")]
                
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error executing query: {str(e)}")]
    
    elif name == "describe_tables":
        try:
            cursor = db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            result = "Database Tables:\n\n"
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                
                result += f"Table: {table_name}\n"
                for col in columns:
                    result += f"  - {col[1]} ({col[2]})\n"
                result += "\n"
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error describing tables: {str(e)}")]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="database-query",
                server_version="0.1.0",
                capabilities=server.get_capabilities()
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
```

## Advanced MCP Features

### Resources

Resources provide AI models with access to data that can be read but not modified.

```python
@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            uri="file://logs/app.log",
            name="Application Logs",
            description="Current application log file",
            mimeType="text/plain"
        ),
        types.Resource(
            uri="config://settings.json", 
            name="App Configuration",
            description="Application configuration settings",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "file://logs/app.log":
        with open("/var/logs/app.log", "r") as f:
            return f.read()
    elif uri == "config://settings.json":
        return json.dumps({
            "database_url": "postgresql://localhost/myapp",
            "debug_mode": True,
            "max_connections": 100
        }, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")
```

### Prompts

Prompts are pre-written templates that help users accomplish specific tasks.

```python
@server.list_prompts()
async def handle_list_prompts() -> List[types.Prompt]:
    return [
        types.Prompt(
            name="analyze_code",
            description="Analyze code for potential issues",
            arguments=[
                types.PromptArgument(
                    name="code",
                    description="Code to analyze",
                    required=True
                ),
                types.PromptArgument(
                    name="language", 
                    description="Programming language",
                    required=False
                )
            ]
        )
    ]

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict) -> types.GetPromptResult:
    if name == "analyze_code":
        code = arguments.get("code")
        language = arguments.get("language", "unknown")
        
        prompt_text = f"""Please analyze the following {language} code for potential issues:

```{language}
{code}
```

Look for:
1. Potential bugs or logic errors
2. Security vulnerabilities  
3. Performance issues
4. Code style and best practices
5. Suggestions for improvement

Provide detailed explanations and specific recommendations."""

        return types.GetPromptResult(
            description=f"Code analysis for {language} code",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text", 
                        text=prompt_text
                    )
                )
            ]
        )
    else:
        raise ValueError(f"Unknown prompt: {name}")
```

### Error Handling

Proper error handling is crucial for robust MCP servers:

```python
from mcp.types import McpError, ErrorCode

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    try:
        if name == "risky_operation":
            # Validate inputs
            if not arguments.get("required_param"):
                raise McpError(
                    ErrorCode.InvalidParams,
                    "Missing required parameter: required_param"
                )
            
            # Perform operation
            result = perform_risky_operation(arguments)
            return [types.TextContent(type="text", text=str(result))]
        else:
            raise McpError(
                ErrorCode.MethodNotFound,
                f"Unknown tool: {name}"
            )
            
    except PermissionError:
        raise McpError(
            ErrorCode.InternalError,
            "Permission denied: insufficient privileges"
        )
    except FileNotFoundError as e:
        raise McpError(
            ErrorCode.InvalidParams, 
            f"File not found: {str(e)}"
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        raise McpError(
            ErrorCode.InternalError,
            "An unexpected error occurred"
        )
```

## Integration with Claude Code

### Step 1: Install Your MCP Server

**For Python servers:**
```bash
# Make your server executable
chmod +x file_server.py

# Test it works
python file_server.py
```

**For Node.js servers:**
```bash
# Install dependencies
npm install

# Test it works
node weather-server.js
```

### Step 2: Configure Claude Code

Add your server to Claude Code's MCP configuration:

```bash
claude mcp add
```

This opens an interactive wizard, or you can add manually:

**For global configuration:**
```bash
# Edit ~/.claude/config.json
{
  "mcpServers": {
    "file-operations": {
      "command": "python",
      "args": ["/path/to/your/file_server.py"]
    },
    "weather": {
      "command": "node", 
      "args": ["/path/to/your/weather-server.js"]
    }
  }
}
```

**For project-specific configuration:**
```bash
# Create .claude/config.json in your project
{
  "mcpServers": {
    "local-database": {
      "command": "python",
      "args": ["./database_server.py"]
    }
  }
}
```

### Step 3: Use Your Server in Claude Code

```bash
# Start Claude Code
claude

# Claude can now use your tools automatically
> "Please read the contents of config.txt and summarize it"
# Claude will automatically call your read_file tool

> "What's the weather like in San Francisco?"
# Claude will call your get_weather tool

> "Show me all employees in the Engineering department"
# Claude will call your execute_query tool
```

### Step 4: Advanced Integration

**Custom Slash Commands:**
```markdown
# .claude/commands/weather-check.md
Check weather for a location:

Please use the weather MCP server to get current weather and 3-day forecast for $LOCATION.

Usage: /weather-check "San Francisco"
```

**Hooks Integration:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "get_weather",
        "hooks": [
          {
            "type": "command", 
            "command": "echo 'Fetching weather data...'"
          }
        ]
      }
    ]
  }
}
```

## Testing and Debugging

### Testing with MCP Inspector

The MCP Inspector provides a web interface for testing your servers:

```bash
# Test any MCP server
npx @modelcontextprotocol/inspector python file_server.py

# Opens browser with:
# - Tool list and schemas
# - Interactive tool calling
# - Resource browsing  
# - Prompt testing
```

### Unit Testing Your Server

**Python Example:**
```python
# test_file_server.py
import pytest
import asyncio
import tempfile
import os
from file_server import server

class TestFileServer:
    @pytest.mark.asyncio
    async def test_read_file(self):
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            # Test the tool
            result = await server.call_tool("read_file", {"path": temp_path})
            assert len(result) == 1
            assert result[0].text == "test content"
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_write_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        
        try:
            # Test writing
            result = await server.call_tool("write_file", {
                "path": temp_path,
                "content": "new content"
            })
            assert "Successfully wrote" in result[0].text
            
            # Verify content
            with open(temp_path, 'r') as f:
                assert f.read() == "new content"
        finally:
            os.unlink(temp_path)

# Run tests
# pytest test_file_server.py
```

### Integration Testing with Claude Code

```bash
# Test your server with Claude Code
claude --mcp-debug

# This shows detailed MCP communication logs
```

### Debugging Common Issues

**1. Server doesn't start:**
```bash
# Check if server runs standalone
python your_server.py
# Should show no errors and wait for input

# Check dependencies
pip list | grep mcp
```

**2. Tools not appearing in Claude Code:**
```bash
# Check MCP configuration
cat ~/.claude/config.json

# Test server with inspector
npx @modelcontextprotocol/inspector python your_server.py
```

**3. Tool calls fail:**
```python
# Add debug logging to your server
import logging
logging.basicConfig(level=logging.DEBUG)

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    logging.debug(f"Tool called: {name} with args: {arguments}")
    # ... rest of your code
```

## Deployment and Distribution

### Option 1: Python Package Distribution

**Setup.py:**
```python
from setuptools import setup, find_packages

setup(
    name="my-mcp-server",
    version="0.1.0", 
    packages=find_packages(),
    install_requires=[
        "mcp>=0.5.0",
    ],
    entry_points={
        'console_scripts': [
            'my-mcp-server=my_mcp_server.main:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com", 
    description="A custom MCP server",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/my-mcp-server",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
```

**Distribution:**
```bash
# Build package
python setup.py sdist bdist_wheel

# Upload to PyPI
pip install twine
twine upload dist/*

# Users can then install with:
pip install my-mcp-server
```

### Option 2: NPM Package Distribution

**Package.json:**
```json
{
  "name": "my-mcp-server",
  "version": "0.1.0",
  "description": "A custom MCP server",
  "main": "index.js",
  "type": "module",
  "bin": {
    "my-mcp-server": "./index.js"
  },
  "scripts": {
    "start": "node index.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.5.0"
  },
  "keywords": ["mcp", "ai", "tools"],
  "author": "Your Name",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/yourusername/my-mcp-server.git"
  }
}
```

**Distribution:**
```bash
# Publish to NPM
npm publish

# Users can then install with:
npm install -g my-mcp-server
```

### Option 3: Docker Distribution

**Dockerfile:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "server.py", "--http", "--port", "8000"]
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  mcp-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MCP_SERVER_PORT=8000
    volumes:
      - ./data:/app/data
```

## Best Practices and Security

### Security Best Practices

**1. Input Validation:**
```python
def validate_file_path(path: str) -> str:
    """Validate and sanitize file paths"""
    import os.path
    
    # Prevent path traversal
    if ".." in path or path.startswith("/"):
        raise ValueError("Invalid path: path traversal not allowed")
    
    # Restrict to allowed directories
    allowed_dirs = ["/tmp", "/home/user/workspace"]
    abs_path = os.path.abspath(path)
    
    if not any(abs_path.startswith(allowed) for allowed in allowed_dirs):
        raise ValueError(f"Path not in allowed directories: {path}")
    
    return abs_path
```

**2. Resource Limits:**
```python
import resource

def set_resource_limits():
    # Limit memory usage to 100MB
    resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, -1))
    
    # Limit CPU time to 60 seconds
    resource.setrlimit(resource.RLIMIT_CPU, (60, -1))
    
    # Limit number of open files
    resource.setrlimit(resource.RLIMIT_NOFILE, (100, -1))
```

**3. Rate Limiting:**
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls = defaultdict(list)
    
    def allow_call(self, client_id: str) -> bool:
        now = time.time()
        # Clean old calls
        self.calls[client_id] = [
            call_time for call_time in self.calls[client_id]
            if now - call_time < self.window_seconds
        ]
        
        if len(self.calls[client_id]) >= self.max_calls:
            return False
        
        self.calls[client_id].append(now)
        return True

# Usage in tool handler
rate_limiter = RateLimiter(max_calls=100, window_seconds=60)

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    client_id = "default"  # In real implementation, get from request context
    
    if not rate_limiter.allow_call(client_id):
        raise McpError(ErrorCode.InternalError, "Rate limit exceeded")
    
    # ... rest of tool logic
```

### Performance Best Practices

**1. Async Operations:**
```python
import aiofiles
import aiohttp

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "read_large_file":
        # Use async file operations for large files
        async with aiofiles.open(arguments["path"], 'r') as f:
            content = await f.read()
        return [types.TextContent(type="text", text=content)]
    
    elif name == "fetch_url":
        # Use async HTTP requests
        async with aiohttp.ClientSession() as session:
            async with session.get(arguments["url"]) as response:
                content = await response.text()
        return [types.TextContent(type="text", text=content)]
```

**2. Caching:**
```python
import asyncio
from functools import lru_cache

class CachedMCPServer:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def cached_operation(self, key: str, operation):
        now = asyncio.get_event_loop().time()
        
        # Check cache
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            if now - timestamp < self._cache_ttl:
                return cached_data
        
        # Perform operation and cache result
        result = await operation()
        self._cache[key] = (result, now)
        return result
```

**3. Connection Pooling:**
```python
import asyncpg

class DatabaseMCPServer:
    def __init__(self):
        self.db_pool = None
    
    async def initialize(self):
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/database",
            min_size=1,
            max_size=10
        )
    
    async def execute_query(self, query: str):
        async with self.db_pool.acquire() as connection:
            return await connection.fetch(query)
```

### Error Handling Best Practices

**1. Structured Error Responses:**
```python
class MCPServerError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict = None):
        self.code = code
        self.message = message 
        self.details = details or {}
        super().__init__(message)

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    try:
        # Tool logic here
        pass
    except FileNotFoundError as e:
        raise MCPServerError(
            ErrorCode.InvalidParams,
            "File not found",
            {"path": arguments.get("path"), "error": str(e)}
        )
    except PermissionError:
        raise MCPServerError(
            ErrorCode.InternalError, 
            "Permission denied",
            {"required_permissions": ["read", "write"]}
        )
```

**2. Logging:**
```python
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),  # MCP uses stderr for logs
        logging.FileHandler('mcp_server.log')
    ]
)

logger = logging.getLogger("mcp-server")

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        result = perform_operation(arguments)
        logger.info(f"Tool {name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool {name} failed: {str(e)}")
        raise
```

### Documentation Best Practices

**1. Tool Documentation:**
```python
@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="advanced_search",
            description="""Search through files with advanced options.
            
            This tool provides powerful search capabilities including:
            - Regular expression matching
            - Case-sensitive/insensitive search
            - Multiple file type filtering
            - Size and date restrictions
            
            Examples:
            - Search for Python functions: {"pattern": "def .*\\(", "file_types": [".py"]}
            - Find recent large files: {"min_size": "1MB", "modified_after": "2024-01-01"}
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (supports regex if regex=true)"
                    },
                    "directory": {
                        "type": "string", 
                        "description": "Directory to search in",
                        "default": "."
                    },
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to include (e.g., ['.py', '.js'])"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search is case-sensitive",
                        "default": False
                    }
                },
                "required": ["pattern"]
            }
        )
    ]
```

**2. README Documentation:**
```markdown
# My MCP Server

## Installation

```bash
pip install my-mcp-server
```

## Configuration

Add to your Claude Code configuration:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "my-mcp-server"
    }
  }
}
```

## Available Tools

### read_file
Read contents of a file.

**Parameters:**
- `path` (string, required): Path to the file

**Example:**
```
Read the contents of config.json
```

### write_file  
Write content to a file.

**Parameters:**
- `path` (string, required): Path to the file
- `content` (string, required): Content to write

**Example:**
```
Write "Hello World" to output.txt
```

## Security

This server operates with the following security restrictions:
- File access limited to current directory and subdirectories
- No access to system files or hidden directories
- Rate limited to 100 requests per minute

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License
```

This comprehensive guide should give you everything you need to understand MCP and build your own servers. The key points to remember:

1. **MCP is a standardized protocol** for AI-tool communication
2. **Servers expose tools, resources, and prompts** to AI models
3. **Implementation is straightforward** with the provided SDKs
4. **Security and performance** are critical considerations
5. **Testing and debugging tools** make development easier
6. **Distribution options** allow sharing your servers

Start with simple examples and gradually add more sophisticated features as you become comfortable with the MCP protocol.