/**
 * RealtimeContext — React context for live cross-role events in KitchenVerse.
 * Integrates with useAuth to maintain session-specific subscriptions.
 */
import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { useAuth } from '../hooks/useAuth';
import realtimeService, { RealtimeEvent, ConnectionStatus } from '../services/websocketService';

interface RealtimeContextValue {
  status: ConnectionStatus;
  isConnected: boolean;
  isPolling: boolean;
  lastEvent: RealtimeEvent | null;
  unreadCount: number;
  setUnreadCount: React.Dispatch<React.SetStateAction<number>>;
  subscribe: (eventType: string, handler: (event: RealtimeEvent) => void) => () => void;
  subscribeAll: (handler: (event: RealtimeEvent) => void) => () => void;
  reconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | undefined>(undefined);

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [status, setStatus] = useState<ConnectionStatus>(realtimeService.getStatus());
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);

  // Sync status listener
  useEffect(() => {
    const unsub = realtimeService.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });
    return unsub;
  }, []);

  // Connect when authenticated, disconnect on logout
  useEffect(() => {
    if (isAuthenticated && user) {
      realtimeService.connect();
    } else {
      realtimeService.disconnect();
      setLastEvent(null);
    }
  }, [isAuthenticated, user?.id]);

  // Global listener for notifications & badge updates
  useEffect(() => {
    const unsub = realtimeService.subscribeAll((event) => {
      setLastEvent(event);
      if (event.type === 'NOTIFICATION_NEW' || event.type === 'NOTIFICATION_CREATED') {
        setUnreadCount((prev) => prev + 1);
      }
    });
    return unsub;
  }, []);

  const subscribe = useCallback((eventType: string, handler: (event: RealtimeEvent) => void) => {
    return realtimeService.subscribe(eventType, handler);
  }, []);

  const subscribeAll = useCallback((handler: (event: RealtimeEvent) => void) => {
    return realtimeService.subscribeAll(handler);
  }, []);

  const reconnect = useCallback(() => {
    realtimeService.connect();
  }, []);

  const value: RealtimeContextValue = {
    status,
    isConnected: status === 'CONNECTED',
    isPolling: status === 'FALLBACK_POLLING',
    lastEvent,
    unreadCount,
    setUnreadCount,
    subscribe,
    subscribeAll,
    reconnect,
  };

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime(): RealtimeContextValue {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return context;
}

export default useRealtime;
