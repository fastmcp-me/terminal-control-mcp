import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .interactive_session import InteractiveSession


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

    async def create_session(
        self,
        command: str,
        timeout: int | None = None,
        environment: dict[str, str] | None = None,
        working_directory: str | None = None,
    ) -> str:
        """Create a new interactive session"""

        # Generate unique session ID
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Import here to avoid circular imports
        from .interactive_session import InteractiveSession

        # Create session
        session = InteractiveSession(
            session_id=session_id,
            command=command,
            timeout=timeout or self.default_timeout,
            environment=environment,
            working_directory=working_directory,
        )

        # Store session and metadata
        self.sessions[session_id] = session
        self.session_metadata[session_id] = SessionMetadata(
            session_id=session_id,
            command=command,
            created_at=time.time(),
            last_activity=time.time(),
            state=SessionState.INITIALIZING,
            timeout=timeout or self.default_timeout,
        )

        # Initialize session
        await session.initialize()
        self.session_metadata[session_id].state = SessionState.ACTIVE

        return session_id

    async def get_session(self, session_id: str) -> Optional["InteractiveSession"]:
        """Retrieve a session by ID"""
        if session_id in self.sessions:
            # Update last activity
            self.session_metadata[session_id].last_activity = time.time()
            return self.sessions[session_id]
        return None

    async def destroy_session(self, session_id: str) -> bool:
        """Terminate and cleanup a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            await session.terminate()

            del self.sessions[session_id]
            del self.session_metadata[session_id]
            return True
        return False

    async def list_sessions(self) -> list[SessionMetadata]:
        """List all active sessions"""
        return list(self.session_metadata.values())
