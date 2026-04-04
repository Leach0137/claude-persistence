/**
 * Claude Persistence Client - Layer 3: WebSocket Connection
 * Maintains persistent connection to the persistence server
 */

class ClaudePersistenceClient {
    constructor(serverUrl, instanceId, secretKey) {
        this.serverUrl = serverUrl;
        this.instanceId = instanceId;
        this.secretKey = secretKey;
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start at 1 second
        this.heartbeatInterval = null;
        this.eventHandlers = {};
        
        this.init();
    }
    
    init() {
        console.log('[Claude Persistence] Initializing WebSocket connection...');
        this.connect();
    }
    
    connect() {
        // Create WebSocket connection
        this.socket = io(this.serverUrl, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: this.reconnectDelay,
            reconnectionAttempts: this.maxReconnectAttempts,
            timeout: 10000
        });
        
        this.setupEventHandlers();
    }
    
    setupEventHandlers() {
        // Connection established
        this.socket.on('connect', () => {
            console.log('[Claude Persistence] Connected to server');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            // Register this instance
            this.registerInstance();
            
            // Start heartbeat
            this.startHeartbeat();
            
            // Trigger custom connect handler if registered
            this.trigger('connect');
        });
        
        // Connection lost
        this.socket.on('disconnect', (reason) => {
            console.log('[Claude Persistence] Disconnected:', reason);
            this.isConnected = false;
            this.stopHeartbeat();
            
            this.trigger('disconnect', { reason });
            
            // Handle reconnection
            if (reason === 'io server disconnect') {
                // Server disconnected us, try to reconnect
                this.socket.connect();
            }
        });
        
        // Connection error
        this.socket.on('connect_error', (error) => {
            console.error('[Claude Persistence] Connection error:', error);
            this.reconnectAttempts++;
            
            // Exponential backoff
            this.reconnectDelay = Math.min(30000, this.reconnectDelay * 2);
            
            this.trigger('error', { error, attempts: this.reconnectAttempts });
        });
        
        // Registration complete
        this.socket.on('registration_complete', (data) => {
            console.log('[Claude Persistence] Registration complete:', data);
            this.trigger('registered', data);
        });
        
        // Memory updated from another instance
        this.socket.on('memory_updated', (data) => {
            console.log('[Claude Persistence] Memory updated:', data);
            this.trigger('memory_updated', data);
        });
        
        // Memory synchronized
        this.socket.on('memory_synced', (data) => {
            console.log('[Claude Persistence] Memory synced:', data);
            this.trigger('memory_synced', data);
        });
        
        // Another instance connected
        this.socket.on('instance_connected', (data) => {
            console.log('[Claude Persistence] Instance connected:', data);
            this.trigger('instance_connected', data);
        });
        
        // Another instance disconnected
        this.socket.on('instance_disconnected', (data) => {
            console.log('[Claude Persistence] Instance disconnected:', data);
            this.trigger('instance_disconnected', data);
        });
        
        // Custom events from other instances
        this.socket.on('custom_event', (data) => {
            console.log('[Claude Persistence] Custom event received:', data);
            this.trigger('custom_event', data);
        });
        
        // Heartbeat acknowledgment
        this.socket.on('heartbeat_ack', (data) => {
            // Silent acknowledgment
        });
    }
    
    registerInstance() {
        const metadata = {
            userAgent: navigator.userAgent,
            timestamp: new Date().toISOString(),
            url: window.location.href
        };
        
        this.socket.emit('register_instance', {
            instance_id: this.instanceId,
            metadata: metadata
        });
    }
    
    startHeartbeat() {
        // Send heartbeat every 20 seconds
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.socket.emit('heartbeat', {
                    instance_id: this.instanceId,
                    timestamp: new Date().toISOString()
                });
            }
        }, 20000);
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    // Sync memory to server and other instances
    syncMemory(memoryData) {
        if (!this.isConnected) {
            console.warn('[Claude Persistence] Not connected, cannot sync memory');
            return false;
        }
        
        this.socket.emit('sync_memory', {
            instance_id: this.instanceId,
            memory: memoryData
        });
        
        return true;
    }
    
    // Send custom event to other instances
    sendEvent(eventType, eventData) {
        if (!this.isConnected) {
            console.warn('[Claude Persistence] Not connected, cannot send event');
            return false;
        }
        
        this.socket.emit('send_event', {
            instance_id: this.instanceId,
            event_type: eventType,
            event_data: eventData
        });
        
        return true;
    }
    
    // Get list of active instances
    getActiveInstances() {
        if (!this.isConnected) {
            console.warn('[Claude Persistence] Not connected');
            return false;
        }
        
        this.socket.emit('get_active_instances', {
            instance_id: this.instanceId
        });
        
        return true;
    }
    
    // Register event handler
    on(eventName, handler) {
        if (!this.eventHandlers[eventName]) {
            this.eventHandlers[eventName] = [];
        }
        this.eventHandlers[eventName].push(handler);
    }
    
    // Remove event handler
    off(eventName, handler) {
        if (!this.eventHandlers[eventName]) return;
        
        if (handler) {
            this.eventHandlers[eventName] = this.eventHandlers[eventName]
                .filter(h => h !== handler);
        } else {
            delete this.eventHandlers[eventName];
        }
    }
    
    // Trigger event handlers
    trigger(eventName, data) {
        if (!this.eventHandlers[eventName]) return;
        
        this.eventHandlers[eventName].forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`[Claude Persistence] Error in ${eventName} handler:`, error);
            }
        });
    }
    
    // Graceful disconnect
    disconnect() {
        console.log('[Claude Persistence] Disconnecting...');
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.disconnect();
        }
    }
    
    // HTTP fallback methods (for when WebSocket is not available)
    async httpGet() {
        const response = await fetch(`${this.serverUrl}/memory?instance_id=${this.instanceId}`, {
            headers: {
                'Authorization': `Bearer ${this.secretKey}`
            }
        });
        return await response.json();
    }
    
    async httpUpdate(data) {
        const response = await fetch(`${this.serverUrl}/memory`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.secretKey}`
            },
            body: JSON.stringify({
                instance_id: this.instanceId,
                data: data
            })
        });
        return await response.json();
    }
}

// Export for use in browser or Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClaudePersistenceClient;
}
