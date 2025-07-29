#!/usr/bin/env python3
"""
Terminal utility functions for session management
Shared utilities for terminal window management and tmux operations
"""

import asyncio
import logging
import shutil

logger = logging.getLogger(__name__)


def detect_terminal_emulator() -> str | None:
    """Detect available terminal emulator"""
    terminal_emulators = [
        # GNOME/GTK
        ("gnome-terminal", ["gnome-terminal", "--"]),
        # KDE
        ("konsole", ["konsole", "-e"]),
        # XFCE
        ("xfce4-terminal", ["xfce4-terminal", "-e"]),
        # Elementary OS
        ("io.elementary.terminal", ["io.elementary.terminal", "-e"]),
        # Generic
        ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
        ("xterm", ["xterm", "-e"]),
        # macOS
        ("Terminal", ["open", "-a", "Terminal"]),
        # Fallback
        ("alacritty", ["alacritty", "-e"]),
        ("kitty", ["kitty"]),
        ("terminator", ["terminator", "-e"]),
    ]

    for name, cmd in terminal_emulators:
        if shutil.which(cmd[0]):
            logger.info(f"Detected terminal emulator: {name}")
            return cmd[0]

    return None


def _build_terminal_command(terminal_cmd: str, tmux_session_name: str) -> list[str]:
    """Build the appropriate command for different terminal emulators"""
    if terminal_cmd == "open":  # macOS
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
    elif terminal_cmd in ["gnome-terminal"]:
        return [
            "gnome-terminal",
            "--",
            "tmux",
            "attach-session",
            "-t",
            tmux_session_name,
        ]
    elif terminal_cmd in [
        "konsole",
        "xfce4-terminal",
        "io.elementary.terminal",
        "x-terminal-emulator",
        "xterm",
        "alacritty",
        "terminator",
    ]:
        return [terminal_cmd, "-e", "tmux", "attach-session", "-t", tmux_session_name]
    elif terminal_cmd == "kitty":
        return ["kitty", "tmux", "attach-session", "-t", tmux_session_name]
    else:
        # Generic fallback
        return [terminal_cmd, "-e", "tmux", "attach-session", "-t", tmux_session_name]


def _prepare_environment() -> dict[str, str]:
    """Prepare environment variables for terminal process"""
    import os

    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY", ":0")
    return env


async def _check_process_result(
    process: asyncio.subprocess.Process, session_id: str, cmd: list[str]
) -> bool:
    """Check if the terminal process started successfully"""
    try:
        await asyncio.wait_for(process.wait(), timeout=1.0)
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
        await asyncio.wait_for(process.wait(), timeout=5.0)

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
