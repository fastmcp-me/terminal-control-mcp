#!/usr/bin/env python3
"""
Web interface server for terminal sessions
Provides HTTP endpoints for viewing and interacting with terminal sessions
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .interactive_session import InteractiveSession
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

# Web server configuration
DEFAULT_WEB_PORT = 8080
DEFAULT_WEB_HOST = "0.0.0.0"  # Bind to all interfaces by default for remote access


class SendInputRequest(BaseModel):
    """Request model for sending input to a session"""

    input_text: str


class WebServer:
    """FastAPI-based web server for terminal session access"""

    def __init__(self, session_manager: SessionManager, port: int = DEFAULT_WEB_PORT):
        self.session_manager = session_manager
        self.port = port
        self.host = DEFAULT_WEB_HOST
        self.app = FastAPI(title="Terminal Control Web Interface")
        self.active_websockets: dict[str, set[WebSocket]] = {}
        # Track xterm.js terminals as source of truth
        self.xterm_terminals: dict[str, dict] = {}  # session_id -> {websocket, buffer, input_queue}
        # Terminal buffer tracking for MCP tool access
        self.terminal_buffers: dict[str, str] = {}  # session_id -> current_screen_content
        self.input_queues: dict[str, asyncio.Queue] = {}  # session_id -> input_queue for MCP tools

        # Setup templates and static files
        self._setup_templates_and_static()
        self._setup_routes()

    def _setup_templates_and_static(self) -> None:
        """Setup Jinja2 templates and static file serving"""
        # Get the directory of this file
        current_dir = Path(__file__).parent

        # Setup templates directory
        templates_dir = current_dir / "templates"
        if templates_dir.exists():
            self.templates: Jinja2Templates | None = Jinja2Templates(directory=str(templates_dir))
        else:
            # Create templates in memory if directory doesn't exist
            self.templates = None
            logger.warning("Templates directory not found, using inline templates")

        # Setup static files directory
        static_dir = current_dir / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _setup_routes(self) -> None:
        """Setup FastAPI routes"""
        self.app.get("/", response_class=HTMLResponse)(self._index_route)
        self.app.get("/session/{session_id}", response_class=HTMLResponse)(self._session_route)
        self.app.post("/session/{session_id}/input")(self._send_input_route)
        self.app.websocket("/session/{session_id}/ws")(self._websocket_route)
        self.app.websocket("/session/{session_id}/pty")(self._pty_websocket_route)

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

    async def _notify_websockets(self, session_id: str, content: str) -> None:
        """Notify all connected websockets for a session"""
        if session_id not in self.active_websockets:
            return

        disconnected = set()
        for websocket in self.active_websockets[session_id]:
            try:
                await websocket.send_text(content)
            except Exception:
                disconnected.add(websocket)

        for ws in disconnected:
            self.active_websockets[session_id].discard(ws)

    async def _send_input_route(self, session_id: str, request: SendInputRequest) -> dict:
        """Send input to a session"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        try:
            await session.send_input(request.input_text)
            await asyncio.sleep(0.1)  # Wait for output to update
            screen_content = await session.get_output()
            await self._notify_websockets(session_id, screen_content)
            return {"success": True, "message": "Input sent successfully"}
        except Exception as e:
            logger.error(f"Failed to send input to session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def _websocket_route(self, websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time session updates"""
        await self._setup_websocket_connection(websocket, session_id)
        try:
            await self._handle_websocket_session(websocket, session_id)
        except WebSocketDisconnect:
            pass
        finally:
            self._cleanup_websocket_connection(websocket, session_id)

    async def _setup_websocket_connection(self, websocket: WebSocket, session_id: str) -> None:
        """Setup websocket connection"""
        await websocket.accept()
        if session_id not in self.active_websockets:
            self.active_websockets[session_id] = set()
        self.active_websockets[session_id].add(websocket)

    def _cleanup_websocket_connection(self, websocket: WebSocket, session_id: str) -> None:
        """Clean up websocket connection"""
        if session_id in self.active_websockets:
            self.active_websockets[session_id].discard(websocket)
            if not self.active_websockets[session_id]:
                del self.active_websockets[session_id]

    async def _handle_websocket_session(self, websocket: WebSocket, session_id: str) -> None:
        """Handle websocket session communication"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            await websocket.send_text("ERROR: Session not found")
            return

        await self._send_initial_content(websocket, session)
        await self._websocket_update_loop(websocket, session)

    async def _send_initial_content(self, websocket: WebSocket, session: InteractiveSession) -> None:
        """Send initial screen content to websocket"""
        try:
            screen_content = await session.get_output()
            await websocket.send_text(screen_content)
        except Exception as e:
            await websocket.send_text(f"Error getting screen content: {e}")

    async def _websocket_update_loop(self, websocket: WebSocket, session: InteractiveSession) -> None:
        """Main websocket update loop"""
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                try:
                    current_content = await session.get_output()
                    await websocket.send_text(current_content)
                except Exception as e:
                    logger.warning(f"Failed to get screen content: {e}")
                    break
            except WebSocketDisconnect:
                break

    async def _pty_websocket_route(self, websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for xterm.js PTY connection - xterm.js as source of truth"""
        await websocket.accept()
        
        session = await self.session_manager.get_session(session_id)
        if not session:
            await websocket.send_text("ERROR: Session not found")
            await websocket.close()
            return

        # Register this terminal as the source of truth
        self.xterm_terminals[session_id] = {
            "websocket": websocket,
            "session": session,
            "buffer": "",
            "last_update": asyncio.get_event_loop().time()
        }
        
        # Initialize input queue for MCP tools
        if session_id not in self.input_queues:
            self.input_queues[session_id] = asyncio.Queue()
        
        # Initialize terminal buffer
        self.terminal_buffers[session_id] = ""

        try:
            # Send initial raw screen content to xterm.js (with ANSI sequences)
            initial_content = await session.get_raw_output()
            if initial_content:
                await websocket.send_text(initial_content)
                self.terminal_buffers[session_id] = initial_content
                self.xterm_terminals[session_id]["buffer"] = initial_content
            
            # Start background task to handle MCP tool input
            mcp_input_task = asyncio.create_task(self._handle_mcp_input(session_id, session))
            
            while True:
                try:
                    # Receive messages from xterm.js or handle timeouts for polling
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    data = json.loads(message)
                    
                    if data["type"] == "input":
                        # Send input to terminal session
                        input_data = data["data"]
                        await session.send_input(input_data)
                        
                        # Get and send back the raw output (with ANSI sequences)
                        await asyncio.sleep(0.1)  # Brief delay for output
                        output = await session.get_raw_output()
                        if output:
                            await websocket.send_text(output)
                            # Update buffer for MCP tools
                            self.terminal_buffers[session_id] = output
                            self.xterm_terminals[session_id]["buffer"] = output
                            self.xterm_terminals[session_id]["last_update"] = asyncio.get_event_loop().time()
                    
                    elif data["type"] == "resize":
                        # Handle terminal resize (future enhancement)
                        cols = data.get("cols", 80)
                        rows = data.get("rows", 24)
                        logger.debug(f"Terminal resize requested: {cols}x{rows}")
                    
                    elif data["type"] == "get_screen":
                        # MCP tool requesting current screen content
                        current_buffer = self.terminal_buffers.get(session_id, "")
                        await websocket.send_text(json.dumps({
                            "type": "screen_content",
                            "data": current_buffer
                        }))
                        
                except asyncio.TimeoutError:
                    # Periodically check for new output and send to xterm.js
                    current_content = await session.get_raw_output()
                    if current_content and current_content != self.terminal_buffers.get(session_id, ""):
                        await websocket.send_text(current_content)
                        # Update buffer for MCP tools
                        self.terminal_buffers[session_id] = current_content
                        self.xterm_terminals[session_id]["buffer"] = current_content
                        self.xterm_terminals[session_id]["last_update"] = asyncio.get_event_loop().time()
                        
        except WebSocketDisconnect:
            logger.debug(f"PTY WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"PTY WebSocket error for session {session_id}: {e}")
        finally:
            # Clean up tracking
            mcp_input_task.cancel()
            if session_id in self.xterm_terminals:
                del self.xterm_terminals[session_id]
            if session_id in self.terminal_buffers:
                del self.terminal_buffers[session_id]
            if session_id in self.input_queues:
                del self.input_queues[session_id]
            try:
                await websocket.close()
            except Exception:
                pass

    def _render_index_template(self, sessions: list[dict]) -> str:
        """Render the index page template"""
        if self.templates:
            # Use Jinja2 template if available
            try:
                template_result = self.templates.get_template("index.html").render(sessions=sessions)
                return str(template_result)
            except Exception:
                pass

        # Fallback to inline template
        session_rows = ""
        for session in sessions:
            session_rows += f"""
            <tr>
                <td><code>{session['session_id']}</code></td>
                <td><code>{session['command']}</code></td>
                <td><span class="status status-{session['state'].lower()}">{session['state']}</span></td>
                <td><a href="{session['url']}" class="btn btn-primary">View Session</a></td>
            </tr>
            """

        # Create content based on whether sessions exist
        if not sessions:
            content = '<div class="empty-state"><p>No active sessions</p></div>'
        else:
            content = f"""
                <table>
                    <thead>
                        <tr>
                            <th>Session ID</th>
                            <th>Command</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {session_rows}
                    </tbody>
                </table>
                """

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Terminal Control - Sessions</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; font-weight: 600; }}
                .btn {{ display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 14px; }}
                .btn:hover {{ background: #0056b3; }}
                .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .status-active {{ background: #d4edda; color: #155724; }}
                .status-waiting {{ background: #fff3cd; color: #856404; }}
                .status-error {{ background: #f8d7da; color: #721c24; }}
                .status-terminated {{ background: #d1ecf1; color: #0c5460; }}
                code {{ background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: 'Monaco', 'Consolas', monospace; }}
                .empty-state {{ text-align: center; padding: 40px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Terminal Control Sessions</h1>
                <p>Active terminal sessions managed by the MCP server:</p>

                {content}
            </div>
        </body>
        </html>
        """

    def _render_session_template(self, session_data: dict) -> str:
        """Render the session interface template"""
        if self.templates:
            # Use Jinja2 template if available
            try:
                template_result = self.templates.get_template("session.html").render(**session_data)
                return str(template_result)
            except Exception:
                pass

        # Fallback to inline template
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Session {session_data['session_id']} - Terminal Control</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; }}
                .session-info {{ flex: 1; }}
                .session-info h1 {{ margin: 0; color: #333; }}
                .session-info p {{ margin: 5px 0; color: #666; }}
                .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .status-active {{ background: #d4edda; color: #155724; }}
                .status-waiting {{ background: #fff3cd; color: #856404; }}
                .status-error {{ background: #f8d7da; color: #721c24; }}
                .status-terminated {{ background: #d1ecf1; color: #0c5460; }}
                .btn {{ display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 14px; border: none; cursor: pointer; }}
                .btn:hover {{ background: #0056b3; }}
                .btn-secondary {{ background: #6c757d; }}
                .btn-secondary:hover {{ background: #545b62; }}
                .terminal-container {{ border: 1px solid #ddd; border-radius: 4px; background: #000; height: 600px; }}
                #terminal {{ width: 100%; height: 100%; }}
                code {{ background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: 'Monaco', 'Consolas', monospace; color: #333; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="session-info">
                        <h1>Session {session_data['session_id']}</h1>
                        <p><strong>Command:</strong> <code>{session_data['command']}</code></p>
                        <p><strong>Status:</strong> <span class="status status-{session_data['state'].lower()}">{session_data['state']}</span></p>
                        <p><strong>Process Running:</strong> {'Yes' if session_data['process_running'] else 'No'}</p>
                    </div>
                    <div>
                        <a href="/" class="btn btn-secondary">← Back to Sessions</a>
                    </div>
                </div>

                <div class="terminal-container">
                    <div id="terminal"></div>
                </div>
            </div>

            <!-- Load xterm.js -->
            <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
            <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
            
            <script>
                const sessionId = '{session_data['session_id']}';
                
                // Initialize xterm.js terminal
                const terminal = new Terminal({{
                    cursorBlink: true,
                    fontSize: 14,
                    fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                    theme: {{
                        background: '#000000',
                        foreground: '#ffffff'
                    }}
                }});
                
                const fitAddon = new FitAddon.FitAddon();
                terminal.loadAddon(fitAddon);
                
                // Open terminal in the container
                terminal.open(document.getElementById('terminal'));
                fitAddon.fit();
                
                // WebSocket connection for terminal I/O
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${{protocol}}//${{window.location.host}}/session/${{sessionId}}/pty`;
                let ws = null;
                
                function connectWebSocket() {{
                    try {{
                        ws = new WebSocket(wsUrl);
                        
                        ws.onopen = function() {{
                            console.log('Terminal WebSocket connected');
                            // Send initial terminal size
                            ws.send(JSON.stringify({{
                                type: 'resize',
                                cols: terminal.cols,
                                rows: terminal.rows
                            }}));
                        }};
                        
                        ws.onmessage = function(event) {{
                            // Write data directly to terminal
                            terminal.write(event.data);
                        }};
                        
                        ws.onclose = function() {{
                            console.log('Terminal WebSocket connection closed');
                            setTimeout(connectWebSocket, 2000);
                        }};
                        
                        ws.onerror = function(error) {{
                            console.error('Terminal WebSocket error:', error);
                        }};
                    }} catch (error) {{
                        console.error('Failed to connect terminal WebSocket:', error);
                        setTimeout(connectWebSocket, 2000);
                    }}
                }}
                
                // Handle terminal input
                terminal.onData(function(data) {{
                    if (ws && ws.readyState === WebSocket.OPEN) {{
                        ws.send(JSON.stringify({{
                            type: 'input',
                            data: data
                        }}));
                    }}
                }});
                
                // Handle terminal resize
                terminal.onResize(function(size) {{
                    if (ws && ws.readyState === WebSocket.OPEN) {{
                        ws.send(JSON.stringify({{
                            type: 'resize',
                            cols: size.cols,
                            rows: size.rows
                        }}));
                    }}
                }});
                
                // Resize terminal when window resizes
                window.addEventListener('resize', function() {{
                    fitAddon.fit();
                }});
                
                // Connect WebSocket on page load
                connectWebSocket();
                
                // Focus terminal
                terminal.focus();
            </script>
        </body>
        </html>
        """

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


    async def _handle_mcp_input(self, session_id: str, session: InteractiveSession) -> None:\n        \"\"\"Background task to handle input from MCP tools\"\"\"\n        input_queue = self.input_queues[session_id]\n        \n        try:\n            while True:\n                # Wait for input from MCP tools\n                input_data = await input_queue.get()\n                \n                # Send to the underlying terminal session\n                await session.send_input(input_data)\n                \n                # Get output and update buffer\n                await asyncio.sleep(0.1)  # Brief delay for output\n                output = await session.get_raw_output()\n                if output:\n                    # Update buffer for MCP tools\n                    self.terminal_buffers[session_id] = output\n                    if session_id in self.xterm_terminals:\n                        self.xterm_terminals[session_id][\"buffer\"] = output\n                        self.xterm_terminals[session_id][\"last_update\"] = asyncio.get_event_loop().time()\n                        \n                        # Send to xterm.js if websocket is active\n                        try:\n                            websocket = self.xterm_terminals[session_id][\"websocket\"]\n                            await websocket.send_text(output)\n                        except Exception as e:\n                            logger.debug(f\"Failed to send output to xterm.js: {e}\")\n                            \n        except asyncio.CancelledError:\n            pass  # Task was cancelled, clean exit\n        except Exception as e:\n            logger.error(f\"Error in MCP input handler for session {session_id}: {e}\")\n\n    async def mcp_send_input(self, session_id: str, input_data: str) -> bool:\n        \"\"\"Send input to terminal via xterm.js (for MCP tools)\"\"\"\n        if session_id not in self.input_queues:\n            return False\n            \n        try:\n            await self.input_queues[session_id].put(input_data)\n            return True\n        except Exception as e:\n            logger.error(f\"Failed to queue input for session {session_id}: {e}\")\n            return False\n\n    async def mcp_get_screen_content(self, session_id: str) -> str | None:\n        \"\"\"Get current screen content from xterm.js buffer (for MCP tools)\"\"\"\n        # First try to get from xterm.js buffer (most up-to-date)\n        if session_id in self.terminal_buffers:\n            return self.terminal_buffers[session_id]\n        \n        # Fallback to session if no xterm.js terminal is active\n        session = await self.session_manager.get_session(session_id)\n        if session:\n            try:\n                return await session.get_raw_output()\n            except Exception as e:\n                logger.warning(f\"Failed to get session output: {e}\")\n                return None\n        \n        return None\n\n    def is_xterm_active(self, session_id: str) -> bool:\n        \"\"\"Check if xterm.js terminal is active for this session\"\"\"\n        return session_id in self.xterm_terminals\n\n\ndef get_web_port() -> int:
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
