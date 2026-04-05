"""
Claude Persistence Server - Layer 3: Persistent WebSocket Connection
Using Flask-Sock for simplicity and reliability
"""

from flask import Flask, request, jsonify
from flask_sock import Sock
from datetime import datetime, timezone
import os
import json
from functools import wraps
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Initialize WebSocket support
sock = Sock(app)

# In-memory storage
memory_store = {}
active_connections = {}  # sid -> {'ws': websocket, 'instance_id': str, 'metadata': dict}
instance_rooms = {}      # instance_id -> [websocket, websocket, ...]
connections_lock = threading.Lock()

# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        secret_key = os.getenv('SECRET_KEY')
        
        if not auth_header or auth_header != f'Bearer {secret_key}':
            return jsonify({'error': 'Unauthorized'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


# Helper function to broadcast to a room
def broadcast_to_room(instance_id, event_type, data, exclude_ws=None):
    """Send message to all websockets in a room"""
    with connections_lock:
        if instance_id not in instance_rooms:
            return
        
        message = json.dumps({
            'type': event_type,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        dead_connections = []
        for ws in instance_rooms[instance_id]:
            if ws == exclude_ws:
                continue
            try:
                ws.send(message)
            except:
                dead_connections.append(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            instance_rooms[instance_id].remove(ws)


# ============================================================================
# HTTP ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    with connections_lock:
        active_count = len(active_connections)
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'layer': 3,
        'active_connections': active_count
    })


@app.route('/memory', methods=['GET'])
@require_auth
def get_memory():
    """Retrieve memory state"""
    instance_id = request.args.get('instance_id', 'default')
    return jsonify({
        'data': memory_store.get(instance_id, {}),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/memory', methods=['POST'])
@require_auth
def update_memory():
    """Update memory state"""
    data = request.json
    instance_id = data.get('instance_id', 'default')
    memory_data = data.get('data', {})
    
    memory_store[instance_id] = memory_data
    
    # Broadcast update to all connected instances
    broadcast_to_room(instance_id, 'memory_updated', {
        'instance_id': instance_id
    })
    
    return jsonify({
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/memory', methods=['DELETE'])
@require_auth
def delete_memory():
    """Clear memory state"""
    instance_id = request.args.get('instance_id', 'default')
    
    if instance_id in memory_store:
        del memory_store[instance_id]
    
    # Broadcast clear to all connected instances
    broadcast_to_room(instance_id, 'memory_cleared', {
        'instance_id': instance_id
    })
    
    return jsonify({
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@sock.route('/ws')
def websocket_handler(ws):
    """Handle WebSocket connections"""
    connection_id = id(ws)
    instance_id = None
    
    print(f'[WebSocket] New connection: {connection_id}')
    
    try:
        # Send initial connection message
        ws.send(json.dumps({
            'type': 'connected',
            'data': {
                'session_id': str(connection_id),
                'message': 'Connected to Claude Persistence Server - Layer 3'
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }))
        
        # Message loop
        while True:
            message = ws.receive()
            if message is None:
                break
            
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                # Handle registration
                if msg_type == 'register_instance':
                    instance_id = data.get('instance_id', 'default')
                    metadata = data.get('metadata', {})
                    
                    with connections_lock:
                        # Track this connection
                        active_connections[connection_id] = {
                            'ws': ws,
                            'instance_id': instance_id,
                            'metadata': metadata,
                            'connected_at': datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Add to room
                        if instance_id not in instance_rooms:
                            instance_rooms[instance_id] = []
                        instance_rooms[instance_id].append(ws)
                    
                    print(f'[WebSocket] Instance registered: {instance_id}')
                    
                    # Send current memory state
                    current_memory = memory_store.get(instance_id, {})
                    ws.send(json.dumps({
                        'type': 'registration_complete',
                        'data': {
                            'instance_id': instance_id,
                            'session_id': str(connection_id),
                            'memory': current_memory,
                            'active_sessions': len(instance_rooms.get(instance_id, []))
                        },
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }))
                    
                    # Notify other instances
                    broadcast_to_room(instance_id, 'instance_connected', {
                        'instance_id': instance_id,
                        'session_id': str(connection_id)
                    }, exclude_ws=ws)
                
                # Handle heartbeat
                elif msg_type == 'heartbeat':
                    ws.send(json.dumps({
                        'type': 'heartbeat_ack',
                        'data': {},
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }))
                
                # Handle memory sync
                elif msg_type == 'sync_memory':
                    if instance_id:
                        memory_update = data.get('memory', {})
                        
                        if instance_id not in memory_store:
                            memory_store[instance_id] = {}
                        memory_store[instance_id].update(memory_update)
                        
                        # Broadcast to all in room
                        broadcast_to_room(instance_id, 'memory_synced', {
                            'instance_id': instance_id,
                            'memory': memory_store[instance_id]
                        })
                
                # Handle custom events
                elif msg_type == 'send_event':
                    if instance_id:
                        event_type = data.get('event_type')
                        event_data = data.get('event_data', {})
                        
                        broadcast_to_room(instance_id, 'custom_event', {
                            'event_type': event_type,
                            'data': event_data,
                            'from_session': str(connection_id)
                        }, exclude_ws=ws)
                
                # Handle get active instances
                elif msg_type == 'get_active_instances':
                    if instance_id:
                        with connections_lock:
                            sessions = [
                                {
                                    'session_id': str(sid),
                                    'metadata': conn['metadata'],
                                    'connected_at': conn['connected_at']
                                }
                                for sid, conn in active_connections.items()
                                if conn['instance_id'] == instance_id
                            ]
                        
                        ws.send(json.dumps({
                            'type': 'active_instances',
                            'data': {
                                'instance_id': instance_id,
                                'sessions': sessions,
                                'count': len(sessions)
                            },
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }))
                
            except json.JSONDecodeError:
                print(f'[WebSocket] Invalid JSON received')
            except Exception as e:
                print(f'[WebSocket] Error processing message: {e}')
    
    except Exception as e:
        print(f'[WebSocket] Connection error: {e}')
    
    finally:
        # Cleanup on disconnect
        print(f'[WebSocket] Connection closed: {connection_id}')
        
        with connections_lock:
            if connection_id in active_connections:
                conn_instance_id = active_connections[connection_id]['instance_id']
                del active_connections[connection_id]
                
                # Remove from room
                if conn_instance_id in instance_rooms:
                    if ws in instance_rooms[conn_instance_id]:
                        instance_rooms[conn_instance_id].remove(ws)
                
                # Notify others
                broadcast_to_room(conn_instance_id, 'instance_disconnected', {
                    'instance_id': conn_instance_id,
                    'session_id': str(connection_id)
                })


print("""
╔══════════════════════════════════════════════════════════════╗
║  Claude Persistence Server - Layer 3                         ║
║  WebSocket-enabled persistence (Flask-Sock)                  ║
╚══════════════════════════════════════════════════════════════╝
""")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)        if not auth_header or auth_header != f'Bearer {secret_key}':
            return jsonify({'error': 'Unauthorized'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# HTTP ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'layer': 3,
        'active_connections': len(active_connections)
    })


@app.route('/memory', methods=['GET'])
@require_auth
def get_memory():
    """Retrieve memory state"""
    instance_id = request.args.get('instance_id', 'default')
    return jsonify({
        'data': memory_store.get(instance_id, {}),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/memory', methods=['POST'])
@require_auth
def update_memory():
    """Update memory state"""
    data = request.json
    instance_id = data.get('instance_id', 'default')
    memory_data = data.get('data', {})
    
    memory_store[instance_id] = memory_data
    
    # Broadcast update
    socketio.emit('memory_updated', {
        'instance_id': instance_id,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=instance_id)
    
    return jsonify({
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/memory', methods=['DELETE'])
@require_auth
def delete_memory():
    """Clear memory state"""
    instance_id = request.args.get('instance_id', 'default')
    
    if instance_id in memory_store:
        del memory_store[instance_id]
    
    socketio.emit('memory_cleared', {
        'instance_id': instance_id,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=instance_id)
    
    return jsonify({
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection"""
    print(f'[WebSocket] Client connected: {request.sid}')
    emit('connected', {
        'session_id': request.sid,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'message': 'Connected to Claude Persistence Server - Layer 3'
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    sid = request.sid
    print(f'[WebSocket] Client disconnected: {sid}')
    
    if sid in active_connections:
        instance_id = active_connections[sid]['instance_id']
        del active_connections[sid]
        
        socketio.emit('instance_disconnected', {
            'instance_id': instance_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, room=instance_id, skip_sid=sid)


@socketio.on('register_instance')
def handle_register_instance(data):
    """Register a Claude instance"""
    instance_id = data.get('instance_id', 'default')
    metadata = data.get('metadata', {})
    sid = request.sid
    
    # Track connection
    active_connections[sid] = {
        'instance_id': instance_id,
        'connected_at': datetime.now(timezone.utc).isoformat(),
        'metadata': metadata
    }
    
    # Join room
    join_room(instance_id)
    
    # Store metadata
    if instance_id not in instance_metadata:
        instance_metadata[instance_id] = []
    
    instance_metadata[instance_id].append({
        'session_id': sid,
        'connected_at': active_connections[sid]['connected_at'],
        'metadata': metadata
    })
    
    print(f'[WebSocket] Instance registered: {instance_id} (session: {sid})')
    
    # Send current state
    current_memory = memory_store.get(instance_id, {})
    
    emit('registration_complete', {
        'instance_id': instance_id,
        'session_id': sid,
        'memory': current_memory,
        'active_sessions': len(instance_metadata.get(instance_id, [])),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    # Notify others
    emit('instance_connected', {
        'instance_id': instance_id,
        'session_id': sid,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=instance_id, skip_sid=sid)


@socketio.on('heartbeat')
def handle_heartbeat(data):
    """Handle heartbeat"""
    sid = request.sid
    
    if sid in active_connections:
        active_connections[sid]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
    
    emit('heartbeat_ack', {
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@socketio.on('sync_memory')
def handle_sync_memory(data):
    """Real-time memory synchronization"""
    instance_id = data.get('instance_id', 'default')
    memory_update = data.get('memory', {})
    
    if instance_id not in memory_store:
        memory_store[instance_id] = {}
    
    memory_store[instance_id].update(memory_update)
    
    emit('memory_synced', {
        'instance_id': instance_id,
        'memory': memory_store[instance_id],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=instance_id, include_self=True)


@socketio.on('send_event')
def handle_send_event(data):
    """Send custom event"""
    instance_id = data.get('instance_id', 'default')
    event_type = data.get('event_type')
    event_data = data.get('event_data', {})
    
    emit('custom_event', {
        'event_type': event_type,
        'data': event_data,
        'from_session': request.sid,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=instance_id, skip_sid=request.sid)


@socketio.on('get_active_instances')
def handle_get_active_instances(data):
    """Get active instances"""
    instance_id = data.get('instance_id', 'default')
    active_sessions = instance_metadata.get(instance_id, [])
    
    emit('active_instances', {
        'instance_id': instance_id,
        'sessions': active_sessions,
        'count': len(active_sessions),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# WSGI app for gunicorn
# Gunicorn will run this with: gunicorn --worker-class gevent app:app
print("""
╔══════════════════════════════════════════════════════════════╗
║  Claude Persistence Server - Layer 3                         ║
║  WebSocket-enabled persistence with gevent                   ║
╚══════════════════════════════════════════════════════════════╝
""")
