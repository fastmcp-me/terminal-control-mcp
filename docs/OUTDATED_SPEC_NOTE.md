# Notice: Outdated Specification

⚠️ **WARNING**: The file `interactive_automation_mcp_spec.md` contains **outdated specifications** that do not match the current implementation.

## Current Implementation (Accurate)

The actual MCP server implements:

- **6 Universal Tools**: `create_interactive_session`, `list_sessions`, `destroy_session`, `expect_and_respond`, `multi_step_automation`, `execute_command`
- **Universal Design**: Execute ANY command with optional automation patterns
- **User-Responsibility Security**: No command blocking, user controls access
- **Package Structure**: `src/interactive_automation_mcp/main.py`

## Refer to These Documents Instead

- **README.md** - Current accurate overview
- **COMPLETE_TOOL_LIST.md** - Accurate tool descriptions
- **PYTHON_DEBUG_GUIDE.md** - Universal debugging approach

## Action Required

The `interactive_automation_mcp_spec.md` file should be either:
1. Completely rewritten to match current implementation, or
2. Removed to prevent confusion

The current specification document describes a different architecture that was replaced by the universal 6-tool design.