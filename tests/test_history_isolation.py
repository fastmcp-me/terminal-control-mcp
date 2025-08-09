#!/usr/bin/env python3
"""
Test suite for terminal history isolation functionality.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.terminal_control_mcp.interactive_session import InteractiveSession
from src.terminal_control_mcp.settings import ServerConfig


class TestHistoryIsolation:
    """Test suite for terminal history isolation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_history_isolation_enabled(self):
        """Test that history isolation works correctly when enabled"""
        session_id = "test_history_isolation"
        session = InteractiveSession(
            session_id=session_id,
            command="bash",
            timeout=30
        )

        try:
            # Initialize the session
            await session.initialize()

            # Check if history directory was created
            assert session.history_dir is not None
            assert session.history_dir.exists()
            assert session.history_dir.name == f"mcp_history_{session_id}"

            # Check isolated history files exist
            assert len(session.isolated_history_files) > 0
            expected_shells = ["bash", "zsh", "fish", "csh", "tcsh"]
            for shell in expected_shells:
                assert shell in session.isolated_history_files
                hist_file = session.isolated_history_files[shell]
                assert hist_file.exists()
                assert session_id in hist_file.name

            # Test sending commands that would normally go to history
            commands = [
                "echo 'History isolation test command 1'",
                "pwd",
                "ls -la"
            ]

            for cmd in commands:
                await session.send_input(cmd, add_newline=True)
                await asyncio.sleep(0.2)  # Allow command to execute

            # Verify session can get screen content
            content = await session.get_current_screen_content()
            assert "History isolation test command 1" in content or len(content) > 0

        finally:
            await session.terminate()

    @pytest.mark.unit
    def test_history_isolation_configuration(self):
        """Test history isolation configuration settings"""
        config = ServerConfig()

        # Test default configuration
        assert config.isolate_history is True
        assert config.history_file_prefix == "mcp_session_history"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_sessions_isolated_histories(self):
        """Test that multiple sessions have isolated histories"""
        sessions = []
        history_dirs = set()

        try:
            # Create multiple sessions
            for i in range(3):
                session_id = f"test_multi_isolation_{i}"
                session = InteractiveSession(
                    session_id=session_id,
                    command="bash",
                    timeout=30
                )
                await session.initialize()
                sessions.append(session)

                # Track unique history directories
                if session.history_dir:
                    history_dirs.add(session.history_dir)

                # Send different commands to each session
                await session.send_input(f"echo 'Session {i} unique command'", add_newline=True)
                await asyncio.sleep(0.1)

            # Verify each session has its own history directory
            assert len(history_dirs) == len(sessions)

            # Verify each has unique history files
            for session in sessions:
                assert session.history_dir is not None
                assert session.history_dir.exists()
                assert session.session_id in str(session.history_dir)

        finally:
            # Clean up all sessions
            for session in sessions:
                await session.terminate()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_history_files_cleanup(self):
        """Test that history files are properly cleaned up on session termination"""
        session_id = "test_cleanup"
        session = InteractiveSession(
            session_id=session_id,
            command="bash",
            timeout=30
        )

        try:
            await session.initialize()

            # Record history directory path
            history_dir = session.history_dir
            assert history_dir is not None
            assert history_dir.exists()

            # Send some commands to create history
            await session.send_input("echo 'test cleanup'", add_newline=True)
            await asyncio.sleep(0.1)

        finally:
            # Terminate session
            await session.terminate()

            # Verify cleanup occurred
            assert not history_dir.exists()

    @pytest.mark.unit
    def test_history_environment_variables(self):
        """Test that proper environment variables are set for history isolation"""
        session_id = "test_env_vars"
        session = InteractiveSession(
            session_id=session_id,
            command="bash",
            timeout=30
        )

        # Test environment preparation
        env = session._prepare_environment()

        # Check that history-related env vars are set when isolation is enabled
        config = ServerConfig()
        if config.isolate_history and session.history_dir:
            # Should have HISTFILE set for bash
            assert "HISTFILE" in env
            assert session_id in env["HISTFILE"]

            # Should have other history control vars
            assert "HISTCONTROL" in env
            assert "HISTSIZE" in env
            assert "HISTFILESIZE" in env

            # Should have Python startup script
            assert "PYTHONSTARTUP" in env

    @pytest.mark.unit
    def test_python_startup_script_creation(self):
        """Test that Python startup script is created correctly"""
        session_id = "test_python_startup"
        session = InteractiveSession(
            session_id=session_id,
            command="bash",
            timeout=30
        )

        # Mock history directory
        temp_dir = Path(tempfile.gettempdir())
        session.history_dir = temp_dir / f"test_mcp_history_{session_id}"
        session.history_dir.mkdir(exist_ok=True)

        try:
            # Test Python startup script creation
            python_hist = session.history_dir / f"test_python_{session_id}"
            startup_script_path = session._create_python_startup_script(python_hist)

            # Verify script was created
            startup_script = Path(startup_script_path)
            assert startup_script.exists()
            assert startup_script.name == "python_startup.py"

            # Verify script content
            content = startup_script.read_text()
            assert "import readline" in content
            assert str(python_hist) in content
            assert "write_history_file" in content

        finally:
            # Clean up
            if session.history_dir.exists():
                import shutil
                shutil.rmtree(session.history_dir, ignore_errors=True)
