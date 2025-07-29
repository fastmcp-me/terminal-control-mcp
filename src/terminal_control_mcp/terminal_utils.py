#!/usr/bin/env python3
"""
Terminal utility functions for session management
Shared utilities for terminal window management and tmux operations
"""

import asyncio
import logging
import shutil

from .config import config

logger = logging.getLogger(__name__)


def detect_terminal_emulator() -> str | None:
    """Detect available terminal emulator using configuration"""
    terminal_emulators = config.terminal_emulators

    for emulator in terminal_emulators:
        name = emulator["name"]
        command = emulator["command"]
        if shutil.which(command[0]):
            logger.info(f"Detected terminal emulator: {name}")
            return command[0]

    return None


def _build_terminal_command(terminal_cmd: str, tmux_session_name: str) -> list[str]:
    """Build the appropriate command for different terminal emulators using configuration"""
    # Find the matching emulator configuration
    for emulator in config.terminal_emulators:
        if emulator["command"][0] == terminal_cmd:
            # Get the base command from configuration
            base_command = emulator["command"].copy()

            # Handle special cases for different terminal types
            if terminal_cmd == "open":  # macOS Terminal
                return [
                    "open",
                    "-a",
                    "Terminal",
                    "--args",
                    "tmux",
                    "attach-session",
                    "-t",
                    tmux_session_name,
                ]
            elif terminal_cmd == "kitty":  # Kitty doesn't use -e
                return ["kitty", "tmux", "attach-session", "-t", tmux_session_name]
            else:
                # Most terminals use the pattern: terminal [args] tmux attach-session -t session
                return base_command + ["tmux", "attach-session", "-t", tmux_session_name]

    # Fallback if not found in configuration
    return [terminal_cmd, "-e", "tmux", "attach-session", "-t", tmux_session_name]


def _prepare_environment() -> dict[str, str]:
    """Prepare environment variables for terminal process"""
    import os

    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY", ":0")

    # Remove Snap-related environment variables to fix VS Code/Snap conflicts
    # VS Code (Snap package) sets various environment variables that redirect
    # system commands to use Snap's bundled libraries, causing symbol lookup errors
    snap_vars_to_remove = [
        "LD_LIBRARY_PATH",
        "GTK_PATH",
        "GTK_EXE_PREFIX",
        "GIO_MODULE_DIR",
        "GSETTINGS_SCHEMA_DIR",
        "GTK_IM_MODULE_FILE",
        "LOCPATH",
        "XDG_DATA_HOME",
        "XDG_DATA_DIRS",
    ]

    for var in snap_vars_to_remove:
        env.pop(var, None)

    # Restore original values if they exist (VS Code saves originals with _VSCODE_SNAP_ORIG suffix)
    snap_orig_vars = {
        "XDG_CONFIG_DIRS": "XDG_CONFIG_DIRS_VSCODE_SNAP_ORIG",
        "GDK_BACKEND": "GDK_BACKEND_VSCODE_SNAP_ORIG",
        "GIO_MODULE_DIR": "GIO_MODULE_DIR_VSCODE_SNAP_ORIG",
        "GSETTINGS_SCHEMA_DIR": "GSETTINGS_SCHEMA_DIR_VSCODE_SNAP_ORIG",
        "GTK_IM_MODULE_FILE": "GTK_IM_MODULE_FILE_VSCODE_SNAP_ORIG",
        "XDG_DATA_HOME": "XDG_DATA_HOME_VSCODE_SNAP_ORIG",
        "GTK_EXE_PREFIX": "GTK_EXE_PREFIX_VSCODE_SNAP_ORIG",
        "GTK_PATH": "GTK_PATH_VSCODE_SNAP_ORIG",
        "XDG_DATA_DIRS": "XDG_DATA_DIRS_VSCODE_SNAP_ORIG",
        "LOCPATH": "LOCPATH_VSCODE_SNAP_ORIG",
    }

    for env_var, orig_var in snap_orig_vars.items():
        if orig_var in env and env[orig_var]:
            env[env_var] = env[orig_var]
        # Remove the _VSCODE_SNAP_ORIG variables as they're not needed
        env.pop(orig_var, None)

    return env


async def _check_process_result(
    process: asyncio.subprocess.Process, session_id: str, cmd: list[str]
) -> bool:
    """Check if the terminal process started successfully"""
    try:
        await asyncio.wait_for(process.wait(), timeout=config.terminal_process_check_timeout)
        if process.returncode == 0:
            logger.info(f"Terminal window opened successfully for session {session_id}")
            return True
        else:
            stderr = (
                await process.stderr.read()
                if process.stderr
                else b"No stderr available"
            )
            logger.warning(
                f"Terminal window failed with return code {process.returncode}: {stderr.decode()}"
            )
            return False
    except TimeoutError:
        # Process is still running, which is good - terminal is open
        logger.info(f"Terminal window opened for session {session_id}: {' '.join(cmd)}")
        return True


async def open_terminal_window(session_id: str) -> bool:
    """Open a terminal window that attaches to the tmux session"""
    terminal_cmd = detect_terminal_emulator()
    if not terminal_cmd:
        logger.warning(
            f"No terminal emulator found - user will need to manually attach with: tmux attach -t {session_id}"
        )
        return False

    try:
        tmux_session_name = f"mcp_{session_id}"
        cmd = _build_terminal_command(terminal_cmd, tmux_session_name)
        env = _prepare_environment()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        return await _check_process_result(process, session_id, cmd)

    except Exception as e:
        logger.warning(f"Failed to open terminal window for session {session_id}: {e}")
        logger.info(
            f"User can manually attach with: tmux attach-session -t mcp_{session_id}"
        )
        return False


async def close_terminal_window(session_id: str) -> bool:
    """Close terminal windows that are attached to the tmux session"""
    try:
        # Build the tmux session name (sessions are prefixed with 'mcp_')
        tmux_session_name = f"mcp_{session_id}"

        # Use tmux to kill the session, which will close attached terminals
        cmd = ["tmux", "kill-session", "-t", tmux_session_name]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )

        # Wait for the command to complete
        await asyncio.wait_for(process.wait(), timeout=config.terminal_close_timeout)

        if process.returncode == 0:
            logger.info(f"Terminal window closed successfully for session {session_id}")
            return True
        else:
            stderr = (
                await process.stderr.read()
                if process.stderr
                else b"No stderr available"
            )
            logger.warning(
                f"Failed to close terminal window for session {session_id}: {stderr.decode()}"
            )
            return False

    except TimeoutError:
        logger.warning(f"Timeout closing terminal window for session {session_id}")
        return False
    except Exception as e:
        logger.error(f"Error closing terminal window for session {session_id}: {e}")
        return False
