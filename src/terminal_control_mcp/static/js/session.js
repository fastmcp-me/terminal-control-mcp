// Session page JavaScript functionality

// Get session ID from global variable (set by template)
// const sessionId is expected to be defined by the template

// Initialize xterm.js terminal with responsive dimensions
function getTerminalDimensions() {
    const isMobile = window.innerWidth <= 768;
    const isSmallMobile = window.innerWidth <= 600;
    
    if (isSmallMobile) {
        return { cols: 80, rows: 25, fontSize: 12 };
    } else if (isMobile) {
        return { cols: 100, rows: 28, fontSize: 13 };
    } else {
        return { cols: 120, rows: 30, fontSize: 14 };
    }
}

const terminalDims = getTerminalDimensions();
const terminal = new Terminal({
    cursorBlink: true,
    fontSize: terminalDims.fontSize,
    fontFamily: 'Monaco, Consolas, "Courier New", monospace',
    cols: terminalDims.cols,
    rows: terminalDims.rows,
    theme: {
        background: '#000000',
        foreground: '#ffffff'
    }
});

// Open terminal in the container
terminal.open(document.getElementById('terminal'));

// WebSocket connection for terminal I/O
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/session/${sessionId}/pty`;
let ws = null;

function connectWebSocket() {
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('Terminal WebSocket connected');
        };
        
        ws.onmessage = function(event) {
            // Write incremental stream data directly to terminal
            terminal.write(event.data);
        };
        
        ws.onclose = function() {
            console.log('Terminal WebSocket connection closed');
            setTimeout(connectWebSocket, 2000);
        };
        
        ws.onerror = function(error) {
            console.error('Terminal WebSocket error:', error);
        };
    } catch (error) {
        console.error('Failed to connect terminal WebSocket:', error);
        setTimeout(connectWebSocket, 2000);
    }
}

// Handle terminal input
terminal.onData(function(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'input',
            data: data
        }));
    }
});

// Connect WebSocket on page load
connectWebSocket();

// Focus terminal
terminal.focus();

// Session monitoring WebSocket for destroyed notifications
const monitorWsUrl = `${protocol}//${window.location.host}/overview`;
let monitorWs = null;

function connectSessionMonitor() {
    try {
        monitorWs = new WebSocket(monitorWsUrl);
        
        monitorWs.onopen = function() {
            console.log('Session monitor WebSocket connected');
        };
        
        monitorWs.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'session_update') {
                // Check if our session still exists
                const currentSession = data.sessions.find(s => s.session_id === sessionId);
                if (!currentSession) {
                    // Session has been destroyed, show notification
                    showSessionDestroyedNotification();
                }
            }
        };
        
        monitorWs.onclose = function() {
            console.log('Session monitor WebSocket connection closed');
            setTimeout(connectSessionMonitor, 2000);
        };
        
        monitorWs.onerror = function(error) {
            console.error('Session monitor WebSocket error:', error);
        };
    } catch (error) {
        console.error('Failed to connect session monitor WebSocket:', error);
        setTimeout(connectSessionMonitor, 2000);
    }
}

function showSessionDestroyedNotification() {
    // Create overlay notification
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        background: white;
        padding: 30px;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        text-align: center;
        max-width: 400px;
    `;
    
    notification.innerHTML = `
        <h2 style="color: #dc3545; margin: 0 0 15px 0;">Session Destroyed</h2>
        <p style="margin: 0 0 20px 0; color: #666;">This terminal session has been destroyed and is no longer available.</p>
        <button onclick="window.location.href='/'" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Return to Sessions</button>
    `;
    
    overlay.appendChild(notification);
    document.body.appendChild(overlay);
}

// Start session monitoring
connectSessionMonitor();