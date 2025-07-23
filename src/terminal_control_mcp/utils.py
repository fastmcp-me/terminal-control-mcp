"""
Utility functions shared across the Interactive Automation MCP Server
"""

import shlex


def wrap_command(command: str) -> str:
    """
    Wrap command in sh -c to ensure shell environment and consistent behavior.
    Uses shlex.quote() for proper shell escaping of complex commands.

    Args:
        command: The command to wrap

    Returns:
        The wrapped command ready for execution
    """
    command_stripped = command.strip()

    # Don't double-wrap commands that are already shell invocations
    if command_stripped.startswith(("sh -c", "bash -c")):
        return command

    # Use shlex.quote() for proper shell escaping - handles all quote types correctly
    quoted_command = shlex.quote(command)
    return f"sh -c {quoted_command}"
