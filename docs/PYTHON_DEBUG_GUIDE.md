# Python Debugging with Interactive Automation MCP Server

## Overview

Yes, you can absolutely do Python debugging with this MCP server! The server includes comprehensive Python debugging capabilities through the Python Debugger (PDB) integration.

## Universal Python Debugging Approach

### 1. `execute_command` - The Universal Tool
Use the universal `execute_command` tool to start any Python debugging command.

**Examples:**
- `python -m pdb script.py` - Start PDB debugger
- `python -c "import pdb; pdb.run('exec(open("script.py").read())')"`
- `python -m ipdb script.py` - If you have ipdb installed
- Any custom Python debugging setup

**Example usage:**
```json
{
  "tool": "execute_command",
  "arguments": {
    "command": "python -m pdb script.py",
    "automation_patterns": [
      {"pattern": "\(Pdb\)", "response": "b main"}
    ]
  }
}
```

### 2. `expect_and_respond` - Interactive Debugging
Use for step-by-step debugging interactions.

### 3. `multi_step_automation` - Automated Debugging Workflows
Execute complex debugging sequences automatically.

## Python Debugging Capabilities

### **Automatic Breakpoint Setting**
- Set breakpoints by line number: `"main.py:15"`
- Set breakpoints by function name: `"calculate_result"`
- Set breakpoints by file and line: `"utils.py:42"`

### **Interactive Debugging**
- Step through code line by line
- Inspect variables and their values
- Navigate the call stack
- Execute arbitrary Python code in the debugger

### **Error Analysis**
- Automatic error detection and reporting
- Stack trace analysis
- Variable inspection at error points

## Usage Examples

### Example 1: Basic Python Debugging
```
"Use execute_command to start debugging my Python script example_debug.py with PDB"
```

Claude will:
1. Use `execute_command` with `python -m pdb example_debug.py`
2. Use `multi_step_automation` to set breakpoints
3. Guide you through debugging with `expect_and_respond`
4. Help analyze any errors or issues

### Example 2: Error Investigation
```
"Run my Python script with PDB to investigate a ZeroDivisionError"
```

Claude will:
1. Use `execute_command` to start the debugging session
2. Use automation patterns to set strategic breakpoints
3. Help you trace the error interactively
4. Suggest fixes for the issue

### Example 3: Performance Debugging
```
"My Python function is running slowly. Debug it and help me identify the bottleneck."
```

Claude will:
1. Set breakpoints in the slow function
2. Help you step through the code
3. Analyze execution flow
4. Identify performance issues

## PDB Commands Available

Once in a debugging session, you can use standard PDB commands:

- `n` (next): Execute next line
- `s` (step): Step into function calls
- `c` (continue): Continue execution
- `l` (list): Show current code
- `p <variable>`: Print variable value
- `pp <variable>`: Pretty-print variable
- `w` (where): Show current stack trace
- `u` (up): Move up in stack
- `d` (down): Move down in stack
- `b <line>`: Set breakpoint
- `cl` (clear): Clear breakpoints

## Advanced Features

### **Conditional Breakpoints**
```python
# In debugging session
b 15, x > 10  # Break at line 15 only when x > 10
```

### **Post-Mortem Debugging**
If your script crashed, you can start debugging from the crash point:
```python
python -m pdb -c continue crashed_script.py
```

### **Remote Debugging**
Debug Python scripts running on remote servers through SSH automation.

## Integration with Other Tools

### **Combined with SSH**
```
"SSH into my server and debug the Python script that's failing in production"
```

### **Database Debugging**
```
"Debug my Python script that's having database connection issues"
```

### **Multi-Language Debugging**
```
"Debug my Python script that calls a C extension, switching between PDB and GDB as needed"
```

## Best Practices

1. **Set Strategic Breakpoints**: Place breakpoints at key decision points
2. **Use Conditional Breakpoints**: Only break when specific conditions are met
3. **Inspect Variables**: Check variable values at each breakpoint
4. **Follow the Call Stack**: Understand the execution flow
5. **Test Fixes Incrementally**: Make small changes and test each one

## Security Features

The Python debugging functionality includes:
- Path validation to prevent access to sensitive files
- Command filtering to block dangerous operations
- Session management to prevent resource exhaustion
- Comprehensive logging for audit trails

## Example Session

Here's what a typical debugging session looks like:

```
Claude: I'll help you debug your Python script. Let me start a PDB session.

1. Starting Python debugging session for example_debug.py
2. Setting breakpoints at main function and line 25
3. PDB session started successfully

Current location: example_debug.py:1
(Pdb) n
> /path/to/example_debug.py:25
-> div_result = divide_numbers(10, 2)

(Pdb) s
> /path/to/example_debug.py:15
-> def divide_numbers(a, b):

(Pdb) p a
10
(Pdb) p b
2
(Pdb) n
> /path/to/example_debug.py:17
-> return a / b

The function looks correct. Let's continue and see where the error occurs...
```

## Troubleshooting

**Common Issues:**
1. **Script not found**: Ensure the script path is correct
2. **Breakpoints not hitting**: Check line numbers and function names
3. **Session hangs**: Use Ctrl+C to interrupt and restart
4. **Permission errors**: Ensure proper file permissions

**Solutions:**
- Use absolute paths for scripts
- Verify breakpoint syntax
- Check that the script is executable
- Ensure proper virtual environment activation

The Python debugging capabilities make this MCP server a powerful tool for both development and production debugging workflows!