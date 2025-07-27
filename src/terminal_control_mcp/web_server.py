#!/usr/bin/env python3
"""
Web interface server for terminal sessions
Provides HTTP endpoints for viewing and interacting with terminal sessions
"""

import asyncio
import json
import logging
import os
from asyncio import Task
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .interactive_session import InteractiveSession
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

# Web server configuration
DEFAULT_WEB_PORT = 8080
DEFAULT_WEB_HOST = "0.0.0.0"  # Bind to all interfaces by default for remote access


class WebServer:
    """FastAPI-based web server for terminal session access"""

    def __init__(self, session_manager: SessionManager, port: int = DEFAULT_WEB_PORT):
        self.session_manager = session_manager
        self.port = port
        self.host = DEFAULT_WEB_HOST
        self.app = FastAPI(title="Terminal Control Web Interface")
        # Track active xterm.js terminals
        self.xterm_terminals: dict[str, dict] = {}  # session_id -> {websocket, session}
        # Terminal buffer tracking for MCP tool access
        self.terminal_buffers: dict[str, str] = (
            {}
        )  # session_id -> current_screen_content
        # Input queues for MCP tools
        self.input_queues: dict[str, asyncio.Queue] = {}  # session_id -> input_queue
        # Overview WebSocket connections for auto-refresh
        self.overview_websockets: list[WebSocket] = []

        # Setup templates and static files
        self._setup_templates_and_static()
        self._setup_routes()

    def _setup_templates_and_static(self) -> None:
        """Setup Jinja2 templates and static file serving"""
        try:
            # Try to use importlib.resources for installed package
            from importlib import resources

            try:
                # Check if templates are available via package resources
                template_path = resources.files("terminal_control_mcp") / "templates"
                if template_path.is_dir():
                    templates_dir = template_path
                    logger.info(
                        f"Using package templates directory at: {templates_dir}"
                    )
                    self.templates: Jinja2Templates | None = Jinja2Templates(
                        directory=str(templates_dir)
                    )
                    logger.info("Package templates successfully loaded")
                else:
                    raise FileNotFoundError("Package templates not found")
            except (ImportError, FileNotFoundError):
                # Fall back to development mode (source directory)
                current_dir = Path(__file__).parent
                templates_dir = current_dir / "templates"
                logger.info(
                    f"Falling back to source templates directory at: {templates_dir}"
                )

                if templates_dir.exists():
                    self.templates = Jinja2Templates(directory=str(templates_dir))
                    logger.info("Source templates successfully loaded")
                else:
                    self.templates = None
                    logger.error(f"Templates directory not found at {templates_dir}")
                    raise RuntimeError(
                        "Templates not found in package or source directory"
                    ) from None

            # Setup static files directory
            try:
                static_path = resources.files("terminal_control_mcp") / "static"
                if static_path.is_dir():
                    static_dir = static_path
                    logger.info(f"Using package static directory at: {static_dir}")
                    self.app.mount(
                        "/static", StaticFiles(directory=str(static_dir)), name="static"
                    )
                else:
                    raise FileNotFoundError("Package static files not found")
            except (ImportError, FileNotFoundError):
                # Fall back to development mode
                current_dir = Path(__file__).parent
                static_dir = current_dir / "static"
                if static_dir.exists():
                    logger.info(f"Using source static directory at: {static_dir}")
                    self.app.mount(
                        "/static", StaticFiles(directory=str(static_dir)), name="static"
                    )

        except Exception as e:
            logger.error(f"Error setting up templates and static files: {e}")
            self.templates = None

    def _setup_routes(self) -> None:
        """Setup FastAPI routes"""
        self.app.get("/", response_class=HTMLResponse)(self._index_route)
        self.app.get("/session/{session_id}", response_class=HTMLResponse)(
            self._session_route
        )
        self.app.websocket("/session/{session_id}/pty")(self._pty_websocket_route)
        self.app.websocket("/overview")(self._overview_websocket_route)
        self.app.delete("/session/{session_id}")(self._destroy_session_route)

    async def _index_route(self, request: Request) -> HTMLResponse:
        """Main page with list of sessions"""
        sessions = await self.session_manager.list_sessions()
        session_data = [
            {
                "session_id": session.session_id,
                "command": session.command,
                "state": session.state.value,
                "created_at": session.created_at,
                "url": f"/session/{session.session_id}",
            }
            for session in sessions
        ]
        html_content = self._render_index_template(session_data)
        return HTMLResponse(content=html_content)

    async def _get_session_data(self, session_id: str) -> dict:
        """Get session data for rendering"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        sessions = await self.session_manager.list_sessions()
        session_metadata = next(
            (s for s in sessions if s.session_id == session_id), None
        )
        if not session_metadata:
            raise HTTPException(status_code=404, detail="Session metadata not found")

        try:
            screen_content = await session.get_output()
        except Exception as e:
            logger.warning(f"Failed to get screen content: {e}")
            screen_content = f"Error getting screen content: {e}"

        return {
            "session_id": session_id,
            "command": session_metadata.command,
            "state": session_metadata.state.value,
            "screen_content": screen_content,
            "process_running": session.is_process_alive(),
        }

    async def _session_route(self, request: Request, session_id: str) -> HTMLResponse:
        """Session interface page"""
        session_data = await self._get_session_data(session_id)
        html_content = self._render_session_template(session_data)
        return HTMLResponse(content=html_content)

    async def _pty_websocket_route(self, websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for xterm.js PTY connection using tmux"""
        await websocket.accept()

        session = await self._validate_session_for_websocket(websocket, session_id)
        if not session:
            return

        self._register_terminal_connection(session_id, websocket, session)
        tasks = await self._setup_websocket_tasks(session_id, session, websocket)

        try:
            await self._handle_websocket_messages(session, websocket)
        except WebSocketDisconnect:
            logger.debug(f"PTY WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"PTY WebSocket error for session {session_id}: {e}")
        finally:
            await self._cleanup_websocket_connection(session_id, tasks, websocket)

    async def _validate_session_for_websocket(
        self, websocket: WebSocket, session_id: str
    ) -> Optional["InteractiveSession"]:
        """Validate session exists for WebSocket connection"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            await websocket.send_text("ERROR: Session not found")
            await websocket.close()
            return None
        return session

    def _register_terminal_connection(
        self, session_id: str, websocket: WebSocket, session: "InteractiveSession"
    ) -> None:
        """Register the terminal connection and initialize input queue"""
        self.xterm_terminals[session_id] = {
            "websocket": websocket,
            "session": session,
            "last_update": asyncio.get_event_loop().time(),
        }

        if session_id not in self.input_queues:
            self.input_queues[session_id] = asyncio.Queue()

    async def _setup_websocket_tasks(
        self, session_id: str, session: "InteractiveSession", websocket: WebSocket
    ) -> dict[str, Task[None] | None]:
        """Set up background tasks for WebSocket handling"""
        # Initialize buffer for MCP tools
        initial_content = await session.get_raw_output()
        self.terminal_buffers[session_id] = initial_content

        # No manual content restoration needed - tmux pipe-pane stream will naturally
        # provide all session history through incremental polling
        logger.debug(f"WebSocket established for session {session_id}, starting incremental stream")

        # Start background tasks
        mcp_input_task = asyncio.create_task(
            self._handle_mcp_input(session_id, session)
        )
        output_poll_task = asyncio.create_task(
            self._poll_tmux_output(session_id, session, websocket)
        )

        return {"mcp_input_task": mcp_input_task, "output_poll_task": output_poll_task}


    async def _handle_websocket_messages(
        self, session: "InteractiveSession", websocket: WebSocket
    ) -> None:
        """Handle incoming WebSocket messages"""
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                data = json.loads(message)

                if data["type"] == "input":
                    await session.send_input(data["data"])
                elif data["type"] == "resize":
                    # Ignore resize events - tmux stays at fixed size for clean MCP output
                    pass

            except asyncio.TimeoutError:
                # Keep connection alive
                continue

    async def _cleanup_websocket_connection(
        self,
        session_id: str,
        tasks: dict[str, Task[None] | None],
        websocket: WebSocket,
    ) -> None:
        """Clean up WebSocket connection and associated resources"""
        # Cancel background tasks
        for task in tasks.values():
            if task is not None:
                task.cancel()

        # Clean up tracking dictionaries
        self.xterm_terminals.pop(session_id, None)
        self.terminal_buffers.pop(session_id, None)
        self.input_queues.pop(session_id, None)

        try:
            await websocket.close()
        except Exception:
            pass

    async def _poll_tmux_output(
        self, session_id: str, session: InteractiveSession, websocket: WebSocket
    ) -> None:
        """Poll tmux session for new stream output and send incremental data to websocket"""
        # Each WebSocket connection tracks its own stream position for proper history restoration
        websocket_stream_position = 0
        
        try:
            # First, send all existing content to restore session history
            if session.output_stream_file.exists():
                try:
                    with open(session.output_stream_file, "rb") as f:
                        historical_data = f.read()
                        websocket_stream_position = f.tell()
                    
                    if historical_data:
                        historical_content = historical_data.decode("utf-8", errors="replace")
                        await websocket.send_text(historical_content)
                        logger.debug(f"Restored {len(historical_content)} chars of history for session {session_id}")
                except Exception as e:
                    logger.debug(f"Error restoring historical content: {e}")
            
            # Then poll for incremental updates
            while True:
                await asyncio.sleep(0.05)  # Poll every 50ms for responsiveness

                try:
                    # Get incremental stream output from this WebSocket's position
                    if session.output_stream_file.exists():
                        with open(session.output_stream_file, "rb") as f:
                            f.seek(websocket_stream_position)
                            new_data = f.read()
                            websocket_stream_position = f.tell()
                        
                        if new_data:
                            new_stream_data = new_data.decode("utf-8", errors="replace")
                            # Send incremental stream data directly to xterm.js
                            await websocket.send_text(new_stream_data)

                            # Update buffer for MCP tools - get full content
                            full_content = await session.get_raw_output()
                            self.terminal_buffers[session_id] = full_content

                            # Update for MCP tools
                            if session_id in self.xterm_terminals:
                                self.xterm_terminals[session_id][
                                    "last_update"
                                ] = asyncio.get_event_loop().time()

                        # Check if session process has terminated and auto-destroy
                        await self._check_session_termination(session_id, session)

                except Exception as e:
                    logger.debug(f"Error polling tmux stream output: {e}")

        except asyncio.CancelledError:
            pass

    async def _handle_mcp_input(
        self, session_id: str, session: InteractiveSession
    ) -> None:
        """Background task to handle input from MCP tools"""
        input_queue = self.input_queues[session_id]

        try:
            while True:
                # Wait for input from MCP tools
                input_data = await input_queue.get()

                # Send to the tmux session - no complex output handling needed
                await session.send_input(input_data)

                # tmux output polling will handle sending updates to web interface

        except asyncio.CancelledError:
            pass  # Task was cancelled, clean exit
        except Exception as e:
            logger.error(f"Error in MCP input handler for session {session_id}: {e}")

    async def mcp_send_input(self, session_id: str, input_data: str) -> bool:
        """Send input to terminal via xterm.js (for MCP tools)"""
        if session_id not in self.input_queues:
            return False

        try:
            await self.input_queues[session_id].put(input_data)
            return True
        except Exception as e:
            logger.error(f"Failed to queue input for session {session_id}: {e}")
            return False

    def is_xterm_active(self, session_id: str) -> bool:
        """Check if xterm.js terminal is active for this session"""
        return session_id in self.xterm_terminals

    async def mcp_get_screen_content(self, session_id: str) -> str | None:
        """Get current screen content from tmux session (for MCP tools)"""
        session = await self.session_manager.get_session(session_id)
        if session:
            try:
                return await session.get_raw_output()
            except Exception as e:
                logger.warning(f"Failed to get session output: {e}")
                return None
        return None

    async def _overview_websocket_route(self, websocket: WebSocket) -> None:
        """WebSocket endpoint for session overview auto-refresh"""
        await websocket.accept()
        self.overview_websockets.append(websocket)

        try:
            await self._handle_overview_websocket_loop(websocket)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Overview WebSocket error: {e}")
        finally:
            await self._cleanup_overview_websocket(websocket)

    async def _handle_overview_websocket_loop(self, websocket: WebSocket) -> None:
        """Handle the overview WebSocket update loop"""
        while True:
            await asyncio.sleep(2.0)
            session_data = await self._get_session_data_for_overview()

            try:
                message = json.dumps(
                    {"type": "session_update", "sessions": session_data}
                )
                await websocket.send_text(message)
            except Exception:
                break

    async def _get_session_data_for_overview(self) -> list[dict]:
        """Get session data formatted for overview"""
        sessions = await self.session_manager.list_sessions()
        return [
            {
                "session_id": session.session_id,
                "command": session.command,
                "state": session.state.value,
                "created_at": session.created_at,
                "url": f"/session/{session.session_id}",
            }
            for session in sessions
        ]

    async def _cleanup_overview_websocket(self, websocket: WebSocket) -> None:
        """Clean up overview WebSocket connection"""
        if websocket in self.overview_websockets:
            self.overview_websockets.remove(websocket)
        try:
            await websocket.close()
        except Exception:
            pass

    async def _destroy_session_route(self, session_id: str) -> dict:
        """DELETE endpoint to destroy a session"""
        success = await self.session_manager.destroy_session(session_id)

        if success:
            # Notify overview pages about session destruction
            await self._broadcast_session_update()
            return {"success": True, "message": "Session destroyed"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    async def _broadcast_session_update(self) -> None:
        """Broadcast session updates to all overview WebSocket connections"""
        if not self.overview_websockets:
            return

        sessions = await self.session_manager.list_sessions()
        session_data = [
            {
                "session_id": session.session_id,
                "command": session.command,
                "state": session.state.value,
                "created_at": session.created_at,
                "url": f"/session/{session.session_id}",
            }
            for session in sessions
        ]

        message = json.dumps({"type": "session_update", "sessions": session_data})

        # Send to all connected overview clients
        disconnected = []
        for ws in self.overview_websockets:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.overview_websockets.remove(ws)

    async def _check_session_termination(
        self, session_id: str, session: InteractiveSession
    ) -> None:
        """Check if session process has terminated and auto-destroy if needed"""
        try:
            if not session.is_process_alive():
                logger.info(
                    f"Auto-destroying session {session_id} - process terminated"
                )
                await self.session_manager.destroy_session(session_id)
                await self._broadcast_session_update()
        except Exception as e:
            logger.debug(f"Error checking session termination: {e}")

    def _render_index_template(self, sessions: list[dict]) -> str:
        """Render the index page template"""
        if not self.templates:
            raise RuntimeError(
                "Templates directory not found - external templates are required"
            )

        template_result = self.templates.get_template("index.html").render(
            sessions=sessions
        )
        return str(template_result)

    def _render_session_template(self, session_data: dict) -> str:
        """Render the session interface template"""
        if not self.templates:
            raise RuntimeError(
                "Templates directory not found - external templates are required"
            )

        template_result = self.templates.get_template("session.html").render(
            **session_data
        )
        return str(template_result)

    async def start(self) -> None:
        """Start the web server"""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,  # Reduce noise in logs
        )
        server = uvicorn.Server(config)
        logger.info(f"Starting web server on http://{self.host}:{self.port}")
        await server.serve()

    def get_session_url(self, session_id: str, external_host: str | None = None) -> str:
        """Get the URL for a specific session

        Args:
            session_id: The session ID
            external_host: External hostname/IP for remote access (if different from bind host)
        """
        # Use external host if provided, otherwise use the configured host
        # If host is 0.0.0.0 (bind all), we need to use a more specific host for URLs
        display_host = external_host or self.host
        if display_host == "0.0.0.0":
            # Try to determine a reasonable default
            import socket

            try:
                # Get the local IP address
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    display_host = s.getsockname()[0]
            except Exception:
                display_host = "localhost"

        return f"http://{display_host}:{self.port}/session/{session_id}"


def get_web_port() -> int:
    """Get web server port from environment or use default"""
    try:
        return int(os.environ.get("TERMINAL_CONTROL_WEB_PORT", DEFAULT_WEB_PORT))
    except ValueError:
        return DEFAULT_WEB_PORT


def get_web_host() -> str:
    """Get web server host from environment or use default"""
    return os.environ.get("TERMINAL_CONTROL_WEB_HOST", DEFAULT_WEB_HOST)


def get_external_web_host() -> str | None:
    """Get external web host for URLs (may be different from bind host)"""
    return os.environ.get("TERMINAL_CONTROL_EXTERNAL_HOST")
