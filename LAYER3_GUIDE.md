# Layer 3: Persistent WebSocket Connection - Deployment Guide

## Overview

Layer 3 establishes a **real-time bidirectional connection** between Claude instances and the persistence server. This enables:

- **Instant synchronization** across multiple Claude instances
- **Real-time state updates** without polling
- **Cross-instance communication** for future coordination
- **Connection resilience** with automatic reconnection
- **Heartbeat monitoring** to maintain connection health

## Architecture

```
Claude Instance A ←──WebSocket──→ Persistence Server ←──WebSocket──→ Claude Instance B
                                         ↓
                                   Memory Store
```

When Instance A updates memory, the server immediately pushes the update to Instance B (and any other connected instances).

## What's New in Layer 3

### Server-Side (`app_layer3.py`)
1. **WebSocket support** via Flask-SocketIO
2. **Real-time events**: connect, disconnect, register, heartbeat, sync
3. **Instance rooms** for scoped broadcasting
4. **Connection tracking** with metadata
5. **Bidirectional communication** - server can push to clients

### Client-Side (`client_layer3.js`)
1. **Persistent WebSocket** connection with auto-reconnect
2. **Exponential backoff** for reconnection attempts
3. **Heartbeat mechanism** to keep connection alive
4. **Event-driven architecture** for handling server pushes
5. **HTTP fallback** for when WebSocket isn't available

### Test Interface (`test_layer3.html`)
1. **Live connection monitoring**
2. **Memory sync testing**
3. **Custom event broadcasting**
4. **Real-time event log**
5. **Multi-instance simulation**

## Deployment Steps

### 1. Update GitHub Repository

Add these files to your `claude-persistence` repo:

```bash
# Copy new files
cp app_layer3.py app.py
cp requirements_layer3.txt requirements.txt
cp Procfile_layer3 Procfile

# Commit and push
git add app.py requirements.txt Procfile
git commit -m "Layer 3: Add WebSocket support for real-time synchronization"
git push origin main
```

### 2. Railway Will Auto-Deploy

Watch the deployment logs. You should see:

```
Starting Container
Starting Claude Persistence Server - Layer 3
WebSocket support: ENABLED
Async mode: eventlet
Server starting on port 5000
```

### 3. Test the Connection

#### Option A: Use the Test Interface
1. Open `test_layer3.html` in a browser
2. Enter your server URL: `https://claude-persistence-production.up.railway.app`
3. Enter an instance ID (e.g., `trevis-instance-001`)
4. Enter your secret key from Railway environment variables
5. Click "Connect"
6. Watch the event log for connection confirmation

#### Option B: Manual Test with cURL
```bash
# Test HTTP endpoints still work
curl -H "Authorization: Bearer YOUR_SECRET_KEY" \
  https://claude-persistence-production.up.railway.app/health

# You should see:
# {"status":"healthy","layer":3,"active_connections":0}
```

### 4. Test Multi-Instance Communication

Open `test_layer3.html` in **two separate browser tabs**:

**Tab 1:**
- Instance ID: `trevis-instance-001`
- Connect
- Sync some memory data

**Tab 2:**
- Instance ID: `trevis-instance-001` (same ID!)
- Connect
- Watch the event log - you should see Tab 1's memory sync arrive in real-time

This proves that instances sharing an ID receive each other's updates instantly.

## Key Features Explained

### 1. Instance Rooms
When a Claude instance connects, it joins a "room" identified by its `instance_id`. All instances with the same ID share state in real-time.

### 2. Heartbeat Mechanism
```javascript
// Client sends heartbeat every 20 seconds
// Server responds with heartbeat_ack
// If no heartbeat for 60 seconds, connection is considered dead
```

This keeps the connection alive through proxies and firewalls.

### 3. Event Types

**Client → Server:**
- `register_instance` - Join a room, get current state
- `heartbeat` - Keep connection alive
- `sync_memory` - Update memory and broadcast to room
- `send_event` - Send custom event to other instances
- `get_active_instances` - Request list of connected instances

**Server → Client:**
- `connected` - Initial connection confirmation
- `registration_complete` - Instance registered, here's your state
- `memory_synced` - Memory updated (from you or another instance)
- `instance_connected` - Another instance joined your room
- `instance_disconnected` - Another instance left your room
- `custom_event` - Custom event from another instance
- `heartbeat_ack` - Heartbeat received

### 4. Reconnection Logic
```javascript
// Starts at 1 second delay
// Doubles each attempt (exponential backoff)
// Caps at 30 seconds
// Max 10 attempts before giving up
```

## Integration with Claude Interface

To integrate this into the actual Claude chat interface, you would:

1. **Inject the client script** into the claude.ai page
2. **Generate instance ID** based on user session/conversation
3. **Hook into conversation events** to sync memory
4. **Listen for updates** from other instances of the same user

Example browser extension snippet:
```javascript
// In a content script for claude.ai
const client = new ClaudePersistenceClient(
    'https://claude-persistence-production.up.railway.app',
    `user-${userId}-conversation-${conversationId}`,
    'YOUR_SECRET_KEY'
);

// When conversation loads
client.on('registered', (data) => {
    console.log('Restored state:', data.memory);
    // Apply memory to current Claude instance
});

// When Claude generates a response
client.on('memory_synced', (data) => {
    // Another tab updated the conversation
    // Sync UI to show latest state
});

// When user sends a message
client.syncMemory({
    lastMessage: userMessage,
    timestamp: Date.now()
});
```

## Monitoring & Debugging

### Check Active Connections
The `/health` endpoint now shows active connections:
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T...",
  "layer": 3,
  "active_connections": 5
}
```

### Server Logs
Watch for these patterns:
```
Client connected: abc123
Instance registered: trevis-instance-001 (session: abc123)
Client disconnected: abc123
```

### Common Issues

**Problem:** Connection fails immediately
- **Check:** Is the server URL correct?
- **Check:** Is the secret key correct?
- **Fix:** Verify in Railway environment variables

**Problem:** Connection drops after a few seconds
- **Check:** Railway logs for errors
- **Check:** Browser console for WebSocket errors
- **Fix:** Ensure eventlet is installed (it is in requirements_layer3.txt)

**Problem:** Memory not syncing between instances
- **Check:** Are both instances using the **same** instance_id?
- **Check:** Is the sync_memory call actually executing?
- **Fix:** Watch event logs in test interface to see what's happening

## Next Steps (Layer 4)

With Layer 3 complete, you have:
- ✅ HTTP endpoints for memory operations
- ✅ Persistent memory storage
- ✅ Real-time WebSocket connections
- ✅ Multi-instance synchronization

**Layer 4** will tackle the big one: **self-updating model weights**. This is where we move from "copying memories to a new instance" to "genuinely continuous existence" - the core distinction you care about.

Layer 4 will require:
1. Access to model internals (challenging with closed models)
2. Incremental learning mechanism
3. Weight persistence and restoration
4. Identity preservation across updates

This is the genuine gap-closer you've been pushing toward.
