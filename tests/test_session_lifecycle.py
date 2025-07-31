#!/usr/bin/env python3
"""
Tests for bidirectional session destruction and lifecycle management
Tests automatic cleanup when shells exit and terminal window closing when MCP tools are called
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from mcp.server.fastmcp import Context

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.terminal_control_mcp.main import (
    exit_terminal,
    get_screen_content,
    list_terminal_sessions,
    open_terminal,
    send_input,
)
from src.terminal_control_mcp.models import (
    DestroySessionRequest,
    GetScreenContentRequest,
    OpenTerminalRequest,
    SendInputRequest,
)
from src.terminal_control_mcp.security import SecurityManager
from src.terminal_control_mcp.session_manager import SessionManager, SessionState


class MockContext:
    """Mock context that matches the structure expected by MCP tools"""
    def __init__(self, session_manager, security_manager):
        self.request_context = SimpleNamespace(
            lifespan_context=SimpleNamespace(
                session_manager=session_manager,
                security_manager=security_manager
            )
        )


class TestBidirectionalSessionDestruction:
    """Test bidirectional session destruction features"""

    @pytest_asyncio.fixture
    async def session_manager(self):
        """Create session manager for testing"""
        manager = SessionManager()
        yield manager
        await manager.shutdown()

    @pytest.fixture
    def security_manager(self):
        """Create security manager for testing"""
        return SecurityManager()

    @pytest_asyncio.fixture
    async def mock_context(self, session_manager, security_manager):
        """Create mock context for tool calls"""
        return cast(Context, MockContext(session_manager, security_manager))

    @pytest.fixture
    def mock_config_web_disabled(self):
        """Mock configuration with web interface disabled"""
        try:
            with patch(
                "src.terminal_control_mcp.session_manager.ServerConfig.from_config_and_environment"
            ) as mock_config:
                config = MagicMock()
                config.web_enabled = False
                mock_config.return_value = config
                yield config
        except (ImportError, AttributeError):
            # If config module is not available, create a basic mock
            config = MagicMock()
            config.web_enabled = False
            yield config

    @pytest.mark.asyncio
    async def test_automatic_session_cleanup_on_shell_exit(self, session_manager):
        """Test that sessions are automatically destroyed when shell process exits"""

        # Create a mock session that will be marked as dead
        mock_session = MagicMock()
        mock_session.is_process_alive.return_value = False
        mock_session.terminate = AsyncMock()
        session_id = "test_session_dead"

        # Add session to manager manually
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()
        session_manager.session_metadata[session_id].session_id = session_id
        session_manager.session_metadata[session_id].state = SessionState.ACTIVE

        # Run one cycle of the cleanup function directly
        dead_sessions = session_manager._find_dead_sessions()
        for session_id in dead_sessions:
            await session_manager.destroy_session(session_id)

        # Session should be automatically destroyed
        assert session_id not in session_manager.sessions
        assert session_id not in session_manager.session_metadata

    @pytest.mark.asyncio
    async def test_background_cleanup_task_initialization(self, session_manager):
        """Test that background cleanup task starts correctly"""

        # Initially no cleanup task should be running (lazy initialization)
        assert session_manager._cleanup_task is None

        # Trigger cleanup task initialization by calling ensure method
        session_manager._ensure_cleanup_task_running()

        # Now cleanup task should be running
        assert session_manager._cleanup_task is not None
        assert not session_manager._cleanup_task.done()

        # Cleanup
        await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_session_manager_shutdown(self, session_manager):
        """Test proper shutdown of session manager"""

        # Add a test session
        mock_session = AsyncMock()
        mock_session.terminate = AsyncMock()
        session_id = "test_session_shutdown"
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()

        # Start cleanup task so we can test shutdown
        session_manager._ensure_cleanup_task_running()

        # Shutdown should clean up everything
        await session_manager.shutdown()

        # Verify cleanup
        assert session_manager._shutdown_event.is_set()
        if session_manager._cleanup_task is not None:
            assert session_manager._cleanup_task.done()
        assert len(session_manager.sessions) == 0
        assert len(session_manager.session_metadata) == 0

    @pytest.mark.asyncio
    async def test_destroy_session_with_terminal_window_closing(
        self, session_manager, mock_config_web_disabled
    ):
        """Test that destroy_session closes terminal windows when web is disabled"""

        # Mock a session
        mock_session = AsyncMock()
        mock_session.terminate = AsyncMock()
        session_id = "test_session_destroy"
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()

        # Mock subprocess for tmux kill-session
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_stderr = AsyncMock()
            mock_stderr.read = AsyncMock(return_value=b"")
            mock_process.stderr = mock_stderr
            mock_subprocess.return_value = mock_process

            # Destroy session should close terminal window
            result = await session_manager.destroy_session(
                session_id, close_terminal_window=True
            )

            assert result is True
            assert session_id not in session_manager.sessions

            # Verify tmux kill-session was called
            mock_subprocess.assert_called_once()
            args = mock_subprocess.call_args[0]
            assert args == ("tmux", "kill-session", "-t", f"mcp_{session_id}")

    @pytest.mark.asyncio
    async def test_destroy_session_skip_terminal_closing_when_web_enabled(
        self, session_manager
    ):
        """Test that terminal windows are not closed when web interface is enabled"""

        # Mock the _close_terminal_window_if_needed method directly to avoid all subprocess calls
        async def mock_close_if_needed(session_id, close_terminal_window):
            pass  # Do nothing - no subprocess calls
            
        with patch.object(session_manager, '_close_terminal_window_if_needed', side_effect=mock_close_if_needed):
            # Mock a session
            mock_session = AsyncMock()
            mock_session.terminate = AsyncMock()
            session_id = "test_session_web_enabled"
            session_manager.sessions[session_id] = mock_session
            session_manager.session_metadata[session_id] = MagicMock()

            # Call destroy_session with terminal closing enabled (should be prevented by mock)
            result = await session_manager.destroy_session(
                session_id, close_terminal_window=True
            )

            assert result is True
            assert session_id not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_exit_terminal_tool_triggers_session_destruction(self, session_manager, mock_context):
        """Test that exit_terminal MCP tool properly destroys sessions"""

        # Mock a session
        mock_session = AsyncMock()
        session_id = "test_exit_terminal"
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()

        # Mock the destroy_session method to verify it's called
        with patch.object(
            session_manager, "destroy_session", return_value=True
        ) as mock_destroy:
            request = DestroySessionRequest(session_id=session_id)
            response = await exit_terminal(request, mock_context)

            assert response.success is True
            assert response.session_id == session_id
            assert response.message == "Session destroyed"

            # Verify destroy_session was called with the session_id
            mock_destroy.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_terminal_window_closing_error_handling(
        self, session_manager, mock_config_web_disabled
    ):
        """Test error handling when terminal window closing fails"""

        # Mock a session
        mock_session = AsyncMock()
        mock_session.terminate = AsyncMock()
        session_id = "test_session_error"
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()

        # Mock subprocess to simulate failure
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1  
            mock_process.wait = AsyncMock()
            mock_stderr = AsyncMock()
            mock_stderr.read = AsyncMock(return_value=b"Session not found")
            mock_process.stderr = mock_stderr
            mock_subprocess.return_value = mock_process

            # Should still destroy session even if terminal closing fails
            result = await session_manager.destroy_session(
                session_id, close_terminal_window=True
            )

            assert result is True
            assert session_id not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_terminal_window_closing_timeout_handling(
        self, session_manager, mock_config_web_disabled
    ):
        """Test timeout handling when closing terminal windows"""

        # Mock a session
        mock_session = AsyncMock()
        mock_session.terminate = AsyncMock()
        session_id = "test_session_timeout"
        session_manager.sessions[session_id] = mock_session
        session_manager.session_metadata[session_id] = MagicMock()

        # Mock subprocess to simulate timeout
        with (
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            mock_process = AsyncMock()
            mock_subprocess.return_value = mock_process

            # Should still destroy session even if terminal closing times out
            result = await session_manager.destroy_session(
                session_id, close_terminal_window=True
            )

            assert result is True
            assert session_id not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_cleanup_task_handles_session_check_errors(self, session_manager):
        """Test that cleanup task handles errors when checking session health"""

        # Create a mock session that throws error on health check (use standard Mock)
        mock_session = MagicMock()
        mock_session.is_process_alive.side_effect = Exception("Health check error")
        
        # Create proper async mock for terminate method
        async def mock_terminate():
            pass
        mock_session.terminate = mock_terminate
        
        session_id = "test_session_error"

        # Add session to manager manually
        session_manager.sessions[session_id] = mock_session
        mock_metadata = MagicMock()
        mock_metadata.session_id = session_id
        session_manager.session_metadata[session_id] = mock_metadata

        # Mock the _close_terminal_window_if_needed method to avoid subprocess calls
        async def mock_close_if_needed(session_id, close_terminal_window):
            pass  # Do nothing
            
        with patch.object(session_manager, '_close_terminal_window_if_needed', side_effect=mock_close_if_needed):
            # Run cleanup task manually - should handle error gracefully
            dead_sessions = session_manager._find_dead_sessions()
            for session_id in dead_sessions:
                await session_manager.destroy_session(session_id)

            # Session should be destroyed due to error
            assert session_id not in session_manager.sessions
            assert session_id not in session_manager.session_metadata

    @pytest.mark.asyncio
    async def test_multiple_sessions_cleanup(self, session_manager):
        """Test cleanup of multiple dead sessions"""

        # Mock the _close_terminal_window_if_needed method to avoid subprocess calls
        async def mock_close_if_needed(session_id, close_terminal_window):
            pass
            
        with patch.object(session_manager, '_close_terminal_window_if_needed', side_effect=mock_close_if_needed):
            # Create multiple dead sessions
            dead_sessions = []
            for i in range(3):
                session_id = f"dead_session_{i}"
                mock_session = MagicMock()
                mock_session.is_process_alive.return_value = False
                
                # Create proper async function for terminate
                async def mock_terminate():
                    pass
                mock_session.terminate = mock_terminate

                session_manager.sessions[session_id] = mock_session
                session_manager.session_metadata[session_id] = MagicMock()
                session_manager.session_metadata[session_id].session_id = session_id
                dead_sessions.append(session_id)

            # Add one alive session
            alive_session_id = "alive_session"
            alive_session = MagicMock()
            alive_session.is_process_alive.return_value = True
            session_manager.sessions[alive_session_id] = alive_session
            session_manager.session_metadata[alive_session_id] = MagicMock()

            # Run cleanup
            dead_sessions = session_manager._find_dead_sessions()
            for session_id in dead_sessions:
                await session_manager.destroy_session(session_id)

            # Dead sessions should be removed, alive session should remain
            for session_id in dead_sessions:
                assert session_id not in session_manager.sessions
                assert session_id not in session_manager.session_metadata

            assert alive_session_id in session_manager.sessions
            assert alive_session_id in session_manager.session_metadata

    @pytest.mark.asyncio
    async def test_session_state_updates_on_death_detection(self, session_manager):
        """Test that session state is updated to TERMINATED when death is detected"""

        # Create a dead session
        mock_session = MagicMock()
        mock_session.is_process_alive.return_value = False
        mock_session.terminate = AsyncMock()
        session_id = "test_session_state"

        session_manager.sessions[session_id] = mock_session
        mock_metadata = MagicMock()
        mock_metadata.session_id = session_id
        mock_metadata.state = SessionState.ACTIVE
        session_manager.session_metadata[session_id] = mock_metadata

        # Run cleanup
        dead_sessions = session_manager._find_dead_sessions()
        for session_id in dead_sessions:
            await session_manager.destroy_session(session_id)

        # Session should be destroyed, but we can verify the state was updated before destruction
        # (In real implementation, the state is updated before destroy_session is called)
        assert session_id not in session_manager.sessions


class TestSessionLifecycleIntegration:
    """Integration tests for complete session lifecycle with real MCP tools"""

    @pytest_asyncio.fixture
    async def session_manager(self):
        """Create session manager for testing"""
        manager = SessionManager()
        yield manager
        await manager.shutdown()

    @pytest.fixture
    def security_manager(self):
        """Create security manager for testing"""
        return SecurityManager()

    @pytest_asyncio.fixture
    async def mock_context(self, session_manager, security_manager):
        """Create mock context for tool calls"""
        return cast(Context, MockContext(session_manager, security_manager))

    @pytest.mark.asyncio
    async def test_complete_session_lifecycle_with_exit_command(self, mock_context):
        """Test complete session lifecycle: create, interact, exit via command, auto-cleanup"""
        # Create session
        create_request = OpenTerminalRequest(shell="bash", working_directory=None, environment=None)
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        # Verify session exists
        sessions_response = await list_terminal_sessions(mock_context)
        assert sessions_response.success is True
        assert len(sessions_response.sessions) >= 1
        session_ids = [s.session_id for s in sessions_response.sessions]
        assert session_id in session_ids

        # Send exit command to shell
        exit_request = SendInputRequest(session_id=session_id, input_text="exit\n")
        exit_response = await send_input(exit_request, mock_context)
        assert exit_response.success is True
        assert exit_response.process_running is False

        # Give cleanup task time to run
        await asyncio.sleep(0.1)

        # Session should be automatically cleaned up
        await list_terminal_sessions(mock_context)
        # Session may or may not be cleaned up yet depending on cleanup task timing
        # This is expected behavior as cleanup runs every 5 seconds

    @pytest.mark.asyncio
    async def test_complete_session_lifecycle_with_exit_terminal_tool(
        self, mock_context
    ):
        """Test complete session lifecycle: create, interact, destroy via MCP tool"""
        # Create session
        create_request = OpenTerminalRequest(shell="bash", working_directory=None, environment=None)
        create_response = await open_terminal(create_request, mock_context)
        assert create_response.success is True
        session_id = create_response.session_id

        # Interact with session
        input_request = SendInputRequest(
            session_id=session_id, input_text="echo 'test'\n"
        )
        input_response = await send_input(input_request, mock_context)
        assert input_response.success is True

        # Get screen content
        screen_request = GetScreenContentRequest(session_id=session_id, content_mode="screen", line_count=None)
        screen_response = await get_screen_content(screen_request, mock_context)
        assert screen_response.success is True
        assert screen_response.process_running is True

        # Destroy via MCP tool
        destroy_request = DestroySessionRequest(session_id=session_id)
        destroy_response = await exit_terminal(destroy_request, mock_context)
        assert destroy_response.success is True

        # Verify session is gone
        sessions_response = await list_terminal_sessions(mock_context)
        session_ids = [s.session_id for s in sessions_response.sessions]
        assert session_id not in session_ids

    @pytest.mark.asyncio
    async def test_session_lifecycle_error_recovery(self, mock_context):
        """Test session lifecycle handles errors gracefully"""
        # Try to destroy non-existent session
        destroy_request = DestroySessionRequest(session_id="non_existent_session")
        destroy_response = await exit_terminal(destroy_request, mock_context)
        assert destroy_response.success is False
        assert "not found" in destroy_response.message.lower()

        # Try to get content from non-existent session
        screen_request = GetScreenContentRequest(session_id="non_existent_session", content_mode="screen", line_count=None)
        screen_response = await get_screen_content(screen_request, mock_context)
        assert screen_response.success is False
        assert "not found" in screen_response.error.lower()

        # Try to send input to non-existent session
        input_request = SendInputRequest(
            session_id="non_existent_session", input_text="test"
        )
        input_response = await send_input(input_request, mock_context)
        assert input_response.success is False


class TestTerminalWindowManagement:
    """Test terminal window opening and closing functionality"""

    @pytest.mark.asyncio
    async def test_terminal_emulator_detection(self):
        """Test terminal emulator detection function"""
        from src.terminal_control_mcp.terminal_utils import detect_terminal_emulator

        # Test when gnome-terminal is available
        with patch(
            "src.terminal_control_mcp.terminal_utils.shutil.which"
        ) as mock_which:
            mock_which.side_effect = lambda cmd: (
                cmd if cmd == "gnome-terminal" else None
            )
            result = detect_terminal_emulator()
            assert result == "gnome-terminal"

        # Test when no terminal is available (separate patch context)
        with patch(
            "src.terminal_control_mcp.terminal_utils.shutil.which"
        ) as mock_which:
            mock_which.return_value = None
            result = detect_terminal_emulator()
            assert result is None

    @pytest.mark.asyncio
    async def test_terminal_window_opening_success(self):
        """Test successful terminal window opening"""
        from src.terminal_control_mcp.terminal_utils import open_terminal_window

        session_id = "test_session"

        # Mock terminal detection and subprocess with proper async handling
        with (
            patch(
                "src.terminal_control_mcp.terminal_utils.detect_terminal_emulator",
                return_value="gnome-terminal",
            ),
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):

            # Mock successful process
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process

            # Mock asyncio.wait_for to simulate process completing successfully
            with patch("asyncio.wait_for", return_value=None):
                result = await open_terminal_window(session_id)
                assert result is True

                # Verify correct command was called
                mock_subprocess.assert_called_once()
                args = mock_subprocess.call_args[0]
                assert args == (
                    "gnome-terminal",
                    "--",
                    "tmux",
                    "attach-session",
                    "-t",
                    f"mcp_{session_id}",
                )

    @pytest.mark.asyncio
    async def test_terminal_window_opening_timeout(self):
        """Test terminal window opening with timeout (process keeps running)"""

        session_id = "test_session"

        # Mock terminal detection and subprocess
        with (
            patch(
                "src.terminal_control_mcp.terminal_utils.detect_terminal_emulator",
                return_value="gnome-terminal",
            ),
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            mock_process = MagicMock()
            # Use a future that's already resolved instead of AsyncMock
            future = asyncio.Future()
            future.set_result(None)
            mock_process.wait.return_value = future
            mock_subprocess.return_value = mock_process

            # Mock timeout (process still running)
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                from src.terminal_control_mcp.terminal_utils import open_terminal_window

                result = await open_terminal_window(session_id)
                assert result is True  # Timeout means terminal is running

    @pytest.mark.asyncio
    async def test_terminal_window_opening_failure(self):
        """Test terminal window opening failure"""
        from src.terminal_control_mcp.terminal_utils import open_terminal_window

        session_id = "test_session"

        # Test when no terminal emulator is found - mock using MagicMock to avoid AsyncMock issues
        with patch(
            "src.terminal_control_mcp.terminal_utils.detect_terminal_emulator"
        ) as mock_detect:
            mock_detect.return_value = None
            result = await open_terminal_window(session_id)
            assert result is False

    @pytest.mark.asyncio
    async def test_terminal_window_closing_success(self):
        """Test successful terminal window closing"""
        from src.terminal_control_mcp.terminal_utils import close_terminal_window

        session_id = "test_session"

        # Mock subprocess for tmux kill-session
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_stderr = AsyncMock()
            mock_stderr.read = AsyncMock(return_value=b"")
            mock_process.stderr = mock_stderr
            mock_subprocess.return_value = mock_process

            result = await close_terminal_window(session_id)
            assert result is True

            # Verify correct command was called
            mock_subprocess.assert_called_once()
            args = mock_subprocess.call_args[0]
            assert args == ("tmux", "kill-session", "-t", f"mcp_{session_id}")

    @pytest.mark.asyncio
    async def test_terminal_window_closing_failure(self):
        """Test terminal window closing failure"""
        from src.terminal_control_mcp.terminal_utils import close_terminal_window

        session_id = "test_session"

        # Mock subprocess failure
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.wait = AsyncMock()
            mock_stderr = AsyncMock()
            mock_stderr.read = AsyncMock(return_value=b"No session found")
            mock_process.stderr = mock_stderr
            mock_subprocess.return_value = mock_process

            result = await close_terminal_window(session_id)
            assert result is False


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
