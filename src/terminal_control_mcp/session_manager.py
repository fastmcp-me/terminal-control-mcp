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
        self._cleanup_task = None
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

    async def destroy_session(self, session_id: str) -> bool:
        """Terminate and cleanup a session"""
        if session_id in self.sessions:
            logger.info(f"Destroying session {session_id}")
            session = self.sessions[session_id]
            try:
                await session.terminate()
                logger.info(f"Session {session_id} terminated successfully")
            except Exception as e:
                logger.error(f"Error terminating session {session_id}: {e}")

            # Always cleanup from manager even if termination fails
            del self.sessions[session_id]
            del self.session_metadata[session_id]
            logger.info(f"Session {session_id} removed from manager")
            return True
        logger.warning(f"Cannot destroy session {session_id}: not found")
        return False

    async def list_sessions(self) -> list[SessionMetadata]:
        """List all active sessions"""
        sessions = list(self.session_metadata.values())
        logger.debug(f"Listed {len(sessions)} active sessions")
        return sessions
