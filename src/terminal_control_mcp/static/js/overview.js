// WebSocket connection for session overview auto-refresh

const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/overview`;
let ws = null;

function connectOverviewWebSocket() {
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('Overview WebSocket connected');
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'session_update') {
                updateSessionList(data.sessions);
            }
        };
        
        ws.onclose = function() {
            console.log('Overview WebSocket connection closed');
            setTimeout(connectOverviewWebSocket, 2000);
        };
        
        ws.onerror = function(error) {
            console.error('Overview WebSocket error:', error);
        };
    } catch (error) {
        console.error('Failed to connect overview WebSocket:', error);
        setTimeout(connectOverviewWebSocket, 2000);
    }
}

function updateSessionList(sessions) {
    const container = document.querySelector('.container');
    
    if (sessions.length === 0) {
        container.innerHTML = `
            <h1>Terminal Control Sessions</h1>
            <p>Active terminal sessions managed by the MCP server:</p>
            <div class="empty-state"><p>No active sessions</p></div>
        `;
    } else {
        const sessionRows = sessions.map(session => `
            <tr>
                <td><code>${session.session_id}</code></td>
                <td><code>${session.command}</code></td>
                <td><span class="status status-${session.state.toLowerCase()}">${session.state}</span></td>
                <td><a href="${session.url}" class="btn btn-primary">View Session</a></td>
            </tr>
        `).join('');
        
        container.innerHTML = `
            <h1>Terminal Control Sessions</h1>
            <p>Active terminal sessions managed by the MCP server:</p>
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
                    ${sessionRows}
                </tbody>
            </table>
        `;
    }
}

// Connect WebSocket on page load
connectOverviewWebSocket();