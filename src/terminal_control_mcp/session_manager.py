import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .interactive_session import InteractiveSession

logger = logging.getLogger(__name__)


class SessionState(Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    WAITING = "waiting"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class SessionMetadata:
    session_id: str
    command: str
    created_at: float
    last_activity: float
    state: SessionState
    timeout: int
    user_data: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages interactive terminal sessions with lifecycle tracking"""

    def __init__(self, max_sessions: int = 50, default_timeout: int = 3600):
        self.sessions: dict[str, InteractiveSession] = {}
        self.session_metadata: dict[str, SessionMetadata] = {}
        self.max_sessions = max_sessions
        self.default_timeout = default_timeout
        self._cleanup_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._cleanup_task_started = False
        logger.info(
            f"SessionManager initialized with max_sessions={max_sessions}, default_timeout={default_timeout}"
        )

    async def create_session(
        self,
        command: str,
        timeout: int | None = None,
        environment: dict[str, str] | None = None,
        working_directory: str | None = None,
    ) -> str:
        """Create a new interactive session"""
        # Ensure cleanup task is running now that we have an event loop
        self._ensure_cleanup_task_running()

        self._validate_session_creation()
        session_id = self._generate_session_id(command)
        session = self._create_session_object(
            session_id, command, timeout, environment, working_directory
        )
        self._store_session_data(session_id, session, command, timeout)

        try:
            await self._initialize_session(session_id, session)
        except Exception as e:
            self._cleanup_failed_session(session_id, e)
            raise

        return session_id

    def _validate_session_creation(self) -> None:
        """Validate if a new session can be created"""
        if len(self.sessions) >= self.max_sessions:
            logger.warning(
                f"Maximum sessions ({self.max_sessions}) reached, cannot create new session"
            )
            raise RuntimeError(f"Maximum sessions ({self.max_sessions}) reached")

    def _generate_session_id(self, command: str) -> str:
        """Generate a unique session ID"""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating session {session_id} for command: {command}")
        return session_id

    def _create_session_object(
        self,
        session_id: str,
        command: str,
        timeout: int | None,
        environment: dict[str, str] | None,
        working_directory: str | None,
    ) -> "InteractiveSession":
        """Create the InteractiveSession object"""
        # Import here to avoid circular imports
        from .interactive_session import InteractiveSession

        return InteractiveSession(
            session_id=session_id,
            command=command,
            timeout=timeout or self.default_timeout,
            environment=environment,
            working_directory=working_directory,
        )

    def _store_session_data(
        self,
        session_id: str,
        session: "InteractiveSession",
        command: str,
        timeout: int | None,
    ) -> None:
        """Store session and metadata"""
        self.sessions[session_id] = session
        self.session_metadata[session_id] = SessionMetadata(
            session_id=session_id,
            command=command,
            created_at=time.time(),
            last_activity=time.time(),
            state=SessionState.INITIALIZING,
            timeout=timeout or self.default_timeout,
        )

    async def _initialize_session(
        self, session_id: str, session: "InteractiveSession"
    ) -> None:
        """Initialize the session"""
        await session.initialize()
        self.session_metadata[session_id].state = SessionState.ACTIVE
        logger.info(f"Session {session_id} successfully initialized and active")

    def _cleanup_failed_session(self, session_id: str, error: Exception) -> None:
        """Clean up a failed session"""
        logger.error(f"Failed to initialize session {session_id}: {error}")
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]

    async def get_session(self, session_id: str) -> Optional["InteractiveSession"]:
        """Retrieve a session by ID"""
        if session_id in self.sessions:
            # Update last activity
            self.session_metadata[session_id].last_activity = time.time()
            logger.debug(f"Retrieved session {session_id}, updated last activity")
            return self.sessions[session_id]
        logger.debug(f"Session {session_id} not found")
        return None

    async def _close_terminal_window_if_needed(
        self, session_id: str, close_terminal_window: bool
    ) -> None:
        """Close terminal window if web is disabled and requested"""
        if not close_terminal_window:
            return

        try:
            from .config import ServerConfig
            from .terminal_utils import close_terminal_window as close_window_func

            config = ServerConfig.from_config_and_environment()
            if not config.web_enabled:
                await close_window_func(session_id)
        except Exception as e:
            logger.warning(
                f"Error closing terminal window for session {session_id}: {e}"
            )

    async def _terminate_session_process(
        self, session_id: str, session: "InteractiveSession"
    ) -> None:
        """Terminate the session process"""
        try:
            await session.terminate()
            logger.info(f"Session {session_id} terminated successfully")
        except Exception as e:
            logger.error(f"Error terminating session {session_id}: {e}")

    def _cleanup_session_from_manager(self, session_id: str) -> None:
        """Remove session from manager storage"""
        del self.sessions[session_id]
        del self.session_metadata[session_id]
        logger.info(f"Session {session_id} removed from manager")

    async def destroy_session(
        self, session_id: str, close_terminal_window: bool = True
    ) -> bool:
        """Terminate and cleanup a session"""
        if session_id not in self.sessions:
            logger.warning(f"Cannot destroy session {session_id}: not found")
            return False

        logger.info(f"Destroying session {session_id}")
        session = self.sessions[session_id]

        await self._close_terminal_window_if_needed(session_id, close_terminal_window)
        await self._terminate_session_process(session_id, session)
        self._cleanup_session_from_manager(session_id)
        return True

    async def list_sessions(self) -> list[SessionMetadata]:
        """List all active sessions"""
        sessions = list(self.session_metadata.values())
        logger.debug(f"Listed {len(sessions)} active sessions")
        return sessions

    def _ensure_cleanup_task_running(self) -> None:
        """Ensure the background cleanup task is running (lazy initialization)"""
        if self._cleanup_task_started:
            return

        try:
            # Initialize shutdown event if not already done
            if self._shutdown_event is None:
                self._shutdown_event = asyncio.Event()

            # Start cleanup task if not already running
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_dead_sessions())
                self._cleanup_task_started = True
                logger.info("Background cleanup task started")
        except RuntimeError:
            # No event loop running - will start when one becomes available
            logger.debug("No event loop available yet - cleanup task will start later")

    def _check_session_health(
        self, session_id: str, session: "InteractiveSession"
    ) -> bool:
        """Check if a session is alive, returning False if dead or error"""
        try:
            return session.is_process_alive()
        except Exception as e:
            logger.error(f"Error checking session {session_id} health: {e}")
            return False

    def _mark_session_as_terminated(self, session_id: str) -> None:
        """Mark session metadata as terminated"""
        if session_id in self.session_metadata:
            self.session_metadata[session_id].state = SessionState.TERMINATED

    def _find_dead_sessions(self) -> list[str]:
        """Find all dead sessions that need cleanup"""
        dead_sessions = []
        for session_id, session in list(self.sessions.items()):
            if not self._check_session_health(session_id, session):
                logger.info(f"Detected dead session {session_id}")
                dead_sessions.append(session_id)
                self._mark_session_as_terminated(session_id)
        return dead_sessions

    async def _cleanup_dead_sessions(self) -> None:
        """Background task to monitor and cleanup dead sessions"""
        # Ensure shutdown event is initialized
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(5)  # Check for dead sessions every 5 seconds

                dead_sessions = self._find_dead_sessions()
                for session_id in dead_sessions:
                    logger.info(f"Auto-cleaning up dead session {session_id}")
                    await self.destroy_session(session_id)

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                # Continue running despite errors

    async def shutdown(self) -> None:
        """Shutdown the session manager and cleanup resources"""
        logger.info("Shutting down SessionManager")

        # Initialize shutdown event if not already done
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        self._shutdown_event.set()

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Destroy all remaining sessions
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.destroy_session(session_id)

        logger.info("SessionManager shutdown complete")
