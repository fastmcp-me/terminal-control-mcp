// Keyboard shortcuts functionality for session page

// Initialize keyboard shortcut elements
const modifierBtns = document.querySelectorAll('.modifier-btn');
const keyInput = document.getElementById('key-input');
const sendKeyBtn = document.getElementById('send-key');
const clearModifiersBtn = document.getElementById('clear-modifiers');
const quickBtns = document.querySelectorAll('.quick-btn');

let activeModifiers = new Set();

// Toggle modifier buttons
modifierBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const modifier = btn.dataset.modifier;
        if (activeModifiers.has(modifier)) {
            activeModifiers.delete(modifier);
            btn.classList.remove('active');
        } else {
            activeModifiers.add(modifier);
            btn.classList.add('active');
        }
    });
});

// Clear modifiers button
clearModifiersBtn.addEventListener('click', () => {
    if (activeModifiers.size === 0) {
        return; // No modifiers to send
    }
    
    // Send just the modifier keys if no regular key is pressed
    let sequence = '';
    if (activeModifiers.has('ctrl') && activeModifiers.has('alt')) {
        // Ctrl+Alt combinations are complex, skip for now
    } else if (activeModifiers.has('ctrl')) {
        // Just send escape for lone modifier
        sequence = '\x1b';
    } else if (activeModifiers.has('alt')) {
        sequence = '\x1b';
    }
    
    if (sequence && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'input',
            data: sequence
        }));
    }
    
    // Clear all modifiers
    activeModifiers.clear();
    modifierBtns.forEach(btn => btn.classList.remove('active'));
});

// Send key combination
function sendKeyCombination(key) {
    let sequence = '';
    
    if (activeModifiers.size === 0) {
        // No modifiers, send key as-is
        sequence = key;
    } else {
        // Generate escape sequence based on modifiers and key
        sequence = generateEscapeSequence(key, activeModifiers);
    }
    
    if (sequence && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'input',
            data: sequence
        }));
    }
    
    // Clear modifiers after sending
    activeModifiers.clear();
    modifierBtns.forEach(btn => btn.classList.remove('active'));
    keyInput.value = '';
}

// Generate escape sequence for key + modifiers
function generateEscapeSequence(key, modifiers) {
    // Convert key to ASCII code
    const keyCode = key.charCodeAt(0);
    
    // Handle Ctrl combinations
    if (modifiers.has('ctrl')) {
        // Convert to control character (A=1, B=2, etc.)
        if (key >= 'a' && key <= 'z') {
            return String.fromCharCode(key.charCodeAt(0) - 96); // a=1, b=2, etc.
        }
        if (key >= 'A' && key <= 'Z') {
            return String.fromCharCode(key.charCodeAt(0) - 64); // A=1, B=2, etc.
        }
        // Special Ctrl combinations
        switch(key) {
            case '[': return '\x1b';  // Ctrl+[
            case ']': return '\x1d';  // Ctrl+]
            case '\\': return '\x1c'; // Ctrl+\
            case '/': return '\x1f';  // Ctrl+/
            case ' ': return '\x00';  // Ctrl+Space
            default: return '\x03';   // Default to Ctrl+C
        }
    }
    
    // Handle Alt combinations (ESC + key)
    if (modifiers.has('alt')) {
        return '\x1b' + key;
    }
    
    // Handle other combinations...
    if (modifiers.has('shift')) {
        return key.toUpperCase();
    }
    
    return key;
}

// Send key button
sendKeyBtn.addEventListener('click', () => {
    const key = keyInput.value;
    if (key) {
        sendKeyCombination(key);
    }
});

// Enter key in input field
keyInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const key = keyInput.value;
        if (key) {
            sendKeyCombination(key);
        }
    }
    // Auto-populate with the actual key pressed
    if (e.key.length === 1) {
        e.preventDefault();
        keyInput.value = e.key;
    }
});

// Quick shortcut buttons
quickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const sequence = btn.dataset.sequence;
        if (sequence && ws && ws.readyState === WebSocket.OPEN) {
            // Convert escape sequence string to actual bytes
            const actualSequence = sequence.replace(/\\x([0-9a-fA-F]{2})/g, (match, hex) => {
                return String.fromCharCode(parseInt(hex, 16));
            });
            
            ws.send(JSON.stringify({
                type: 'input',
                data: actualSequence
            }));
        }
    });
});

// Destroy session button functionality
const destroyBtn = document.getElementById('destroy-session-btn');
if (destroyBtn) {
    destroyBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to destroy this session? This action cannot be undone.')) {
            try {
                const response = await fetch(`/session/${sessionId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    // Show success message and redirect
                    alert('Session destroyed successfully.');
                    window.location.href = '/';
                } else {
                    alert('Failed to destroy session. Please try again.');
                }
            } catch (error) {
                console.error('Error destroying session:', error);
                alert('Error occurred while destroying session.');
            }
        }
    });
}