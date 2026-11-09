/**
 * Real-Time WebSocket & Fallback Polling Service.
 * KitchenVerse Platform.
 *
 * Provides resilient, authenticated real-time updates across Admin, Kitchen Owner,
 * and Customer portals. Features heartbeat keepalives, exponential reconnect backoff,
 * automatic cache invalidation, and seamless HTTP long-polling fallback.
 */
import apiClient from '../lib/api';

export interface RealtimeEvent<T = any> {
  id: string;
  type: string;
  timestamp: number;
  data: T;
}

export type ConnectionStatus =
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'FALLBACK_POLLING';

type EventHandler = (event: RealtimeEvent) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private status: ConnectionStatus = 'DISCONNECTED';
  private listeners: Map<string, Set<EventHandler>> = new Map();
  private globalListeners: Set<EventHandler> = new Set();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();

  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimeout: any = null;
  private pingInterval: any = null;
  private pollingInterval: any = null;

  private lastEventTimestamp: number = Date.now() / 1000;
  private activeToken: string | null = null;
  private intentionalDisconnect = false;

  constructor() {
    // Track window visibility to refresh when coming back online
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        if (this.status === 'DISCONNECTED' || this.status === 'FALLBACK_POLLING') {
          this.reconnect();
        }
      });
    }
  }

  /**
   * Current connection status.
   */
  getStatus(): ConnectionStatus {
    return this.status;
  }

  private setStatus(newStatus: ConnectionStatus) {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((cb) => {
        try {
          cb(newStatus);
        } catch (e) {
          console.warn('[Realtime] Status listener error:', e);
        }
      });
    }
  }

  /**
   * Subscribe to connection status changes.
   */
  onStatusChange(callback: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  /**
   * Connect to backend WebSocket endpoint.
   */
  connect(token?: string): void {
    this.intentionalDisconnect = false;
    const resolvedToken = token || apiClient.getAccessToken();
    this.activeToken = resolvedToken;

    if (!resolvedToken) {
      this.setStatus('DISCONNECTED');
      return;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.setStatus(this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING');

    try {
      let wsBase: string;
      const apiBase = apiClient.getBaseUrl();
      if (apiBase && (apiBase.startsWith('http://') || apiBase.startsWith('https://'))) {
        const parsed = new URL(apiBase);
        const wsProto = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        wsBase = `${wsProto}//${parsed.host}`;
      } else {
        const hostname = window.location.hostname;
        const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
        if (isLocal) {
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          wsBase = `${protocol}//${window.location.host}`;
        } else {
          // Vercel HTTP rewrites do not proxy WebSocket upgrades; connect directly to backend WS
          wsBase = 'wss://kitchenverse.onrender.com';
        }
      }
      const wsUrl = `${wsBase}/api/v1/ws?token=${encodeURIComponent(resolvedToken)}`;

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus('CONNECTED');
        this.stopPollingFallback();
        this.startHeartbeat();

        // If reconnecting, invalidate caches so views fetch authoritative data
        apiClient.clearCache();
        this.emitSyntheticEvent({
          id: 'reconnect-sync',
          type: 'RECONNECTED',
          timestamp: Date.now() / 1000,
          data: { reconnected_at: new Date().toISOString() },
        });
      };

      this.socket.onmessage = (messageEvent) => {
        try {
          const raw = JSON.parse(messageEvent.data);
          if (raw.type === 'PONG') {
            return;
          }
          if (raw.timestamp) {
            this.lastEventTimestamp = Math.max(this.lastEventTimestamp, raw.timestamp);
          }
          this.handleIncomingEvent(raw as RealtimeEvent);
        } catch (err) {
          console.warn('[Realtime] Message parse error:', err);
        }
      };

      this.socket.onerror = (err) => {
        console.warn('[Realtime] WebSocket encountered error:', err);
      };

      this.socket.onclose = (closeEvent) => {
        this.stopHeartbeat();
        this.socket = null;

        if (this.intentionalDisconnect) {
          this.setStatus('DISCONNECTED');
          return;
        }

        // Check if policy violation (auth expired)
        if (closeEvent.code === 4401 || closeEvent.code === 1008) {
          this.setStatus('DISCONNECTED');
          return;
        }

        this.scheduleReconnect();
      };
    } catch (err) {
      console.warn('[Realtime] Failed opening WebSocket:', err);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect cleanly (e.g. on user logout).
   */
  disconnect(): void {
    this.intentionalDisconnect = true;
    this.stopHeartbeat();
    this.stopPollingFallback();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.setStatus('DISCONNECTED');
  }

  /**
   * Reconnect attempt with exponential backoff.
   */
  private scheduleReconnect(): void {
    if (this.intentionalDisconnect) return;

    this.reconnectAttempts++;
    if (this.reconnectAttempts > this.maxReconnectAttempts) {
      // Fallback to HTTP long polling
      console.warn('[Realtime] Max WebSocket reconnect attempts reached. Switching to polling fallback.');
      this.startPollingFallback();
      return;
    }

    this.setStatus('RECONNECTING');
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
    this.reconnectTimeout = setTimeout(() => {
      this.connect(this.activeToken || undefined);
    }, delay);
  }

  private reconnect(): void {
    this.reconnectAttempts = 0;
    this.connect(this.activeToken || undefined);
  }

  /**
   * Heartbeat ping to keep socket alive and detect network drops.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        try {
          this.socket.send(JSON.stringify({ type: 'PING', data: Date.now() }));
        } catch {
          // Socket write failed
        }
      }
    }, 25000);
  }

  private stopHeartbeat(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * HTTP event polling fallback when WebSockets are unavailable.
   */
  private startPollingFallback(): void {
    this.setStatus('FALLBACK_POLLING');
    if (this.pollingInterval) return;

    const poll = async () => {
      if (this.status !== 'FALLBACK_POLLING') return;
      try {
        const res = await apiClient.get<{ status: string; events: RealtimeEvent[]; server_time: number }>(
          `/api/v1/events/poll?since=${this.lastEventTimestamp}`,
          true,
          false // Don't use cache for event polling
        );
        if (res && res.events && Array.isArray(res.events)) {
          for (const ev of res.events) {
            this.lastEventTimestamp = Math.max(this.lastEventTimestamp, ev.timestamp || 0);
            this.handleIncomingEvent(ev);
          }
        }
      } catch (err) {
        // Polling error (e.g. offline)
      }
    };

    poll();
    this.pollingInterval = setInterval(poll, 6000); // Poll every 6 seconds
  }

  private stopPollingFallback(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  /**
   * Process incoming real-time event and invalidate affected frontend caches.
   */
  private handleIncomingEvent(event: RealtimeEvent): void {
    const type = (event.type || '').toUpperCase();

    // 1. Invalidate caches based on event domain to ensure fresh DB records
    if (type.includes('ORDER')) {
      apiClient.clearCache('/orders');
      apiClient.clearCache('/kitchen/orders');
      apiClient.clearCache('/admin/orders');
      apiClient.clearCache('/kitchen/dashboard');
      apiClient.clearCache('/admin/dashboard');
    }
    if (type.includes('INVENTORY') || type.includes('STOCK') || type.includes('WASTE')) {
      apiClient.clearCache('/kitchen/inventory');
      apiClient.clearCache('/kitchen/ingredients');
      apiClient.clearCache('/kitchen/waste');
      apiClient.clearCache('/kitchen/restocking');
      apiClient.clearCache('/admin/inventory');
      apiClient.clearCache('/admin/waste');
    }
    if (type.includes('KITCHEN') || type.includes('LICENSE')) {
      apiClient.clearCache('/kitchen/license');
      apiClient.clearCache('/kitchen/settings');
      apiClient.clearCache('/kitchen/profile');
      apiClient.clearCache('/admin/kitchens');
      apiClient.clearCache('/admin/kitchen-owners');
      apiClient.clearCache('/admin/licenses');
    }
    if (type.includes('NOTIFICATION')) {
      apiClient.clearCache('/notifications');
      apiClient.clearCache('/kitchen/notifications');
      apiClient.clearCache('/admin/notifications');
    }
    if (type.includes('PAYMENT')) {
      apiClient.clearCache('/admin/payments');
      apiClient.clearCache('/orders');
    }

    // 2. Dispatch to specific event listeners
    const specificSet = this.listeners.get(type);
    if (specificSet) {
      specificSet.forEach((cb) => {
        try {
          cb(event);
        } catch (e) {
          console.warn(`[Realtime] Listener error on ${type}:`, e);
        }
      });
    }

    // 3. Dispatch to global listeners
    this.globalListeners.forEach((cb) => {
      try {
        cb(event);
      } catch (e) {
        console.warn('[Realtime] Global listener error:', e);
      }
    });
  }

  private emitSyntheticEvent(event: RealtimeEvent): void {
    this.handleIncomingEvent(event);
  }

  /**
   * Subscribe to specific event types (e.g. 'ORDER_CREATED', 'ORDER_STATUS_CHANGED').
   */
  subscribe(eventType: string, handler: EventHandler): () => void {
    const norm = eventType.toUpperCase();
    if (!this.listeners.has(norm)) {
      this.listeners.set(norm, new Set());
    }
    this.listeners.get(norm)!.add(handler);

    return () => {
      const set = this.listeners.get(norm);
      if (set) {
        set.delete(handler);
        if (set.size === 0) {
          this.listeners.delete(norm);
        }
      }
    };
  }

  /**
   * Subscribe to all real-time events.
   */
  subscribeAll(handler: EventHandler): () => void {
    this.globalListeners.add(handler);
    return () => {
      this.globalListeners.delete(handler);
    };
  }
}

export const realtimeService = new WebSocketService();
export default realtimeService;
