/**
 * Customer Portal - Notifications Page
 * Real database-backed notification feed for order updates, kitchen preparation alerts,
 * and system promotions.
 */

import React, { useState, useEffect } from 'react';
import { customerApi, CustomerNotification } from '../../services/customerApi';
import {
  Bell,
  CheckCheck,
  Clock,
  Sparkles,
  ShoppingBag,
  Info,
  CheckCircle,
} from 'lucide-react';

export default function CustomerNotifications() {
  const [notifications, setNotifications] = useState<CustomerNotification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    try {
      const data = await customerApi.getNotifications();
      setNotifications(data || []);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (id: string) => {
    try {
      await customerApi.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err) {
      console.error('Failed to mark notification read:', err);
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'ORDER_STATUS':
      case 'ORDER_CONFIRMED':
      case 'ORDER_DELIVERED':
        return <ShoppingBag className="w-5 h-5 text-emerald-600" />;
      case 'PROMOTION':
        return <Sparkles className="w-5 h-5 text-amber-500" />;
      default:
        return <Info className="w-5 h-5 text-blue-600" />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black text-[#172033] tracking-tight">Notifications</h1>
          <p className="text-xs text-gray-500">Live alerts regarding orders, preparation, and announcements</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-gray-200 rounded-2xl" />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white rounded-3xl border border-gray-200 p-12 text-center space-y-3 shadow-xs">
          <Bell className="w-12 h-12 text-gray-300 mx-auto" />
          <h2 className="text-lg font-bold text-gray-800">No Notifications</h2>
          <p className="text-xs text-gray-400">
            You are all caught up! Order status changes and kitchen updates will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((notif) => (
            <div
              key={notif.id}
              className={`p-4 rounded-2xl border transition-all flex items-start justify-between gap-4 ${
                notif.is_read
                  ? 'bg-white border-gray-200 opacity-80'
                  : 'bg-emerald-50/40 border-emerald-300/80 shadow-xs'
              }`}
            >
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-white border border-gray-100 flex items-center justify-center shrink-0 shadow-xs">
                  {getEventIcon(notif.event_type)}
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-[#172033] leading-tight">
                    {notif.title}
                  </h3>
                  <p className="text-xs text-gray-600 leading-relaxed">
                    {notif.message}
                  </p>
                  <span className="text-[10px] text-gray-400 block pt-0.5">
                    {new Date(notif.created_at).toLocaleString()}
                  </span>
                </div>
              </div>

              {!notif.is_read && (
                <button
                  onClick={() => handleMarkAsRead(notif.id)}
                  className="text-xs font-bold text-[#166534] hover:underline shrink-0 flex items-center gap-1"
                >
                  <CheckCircle className="w-3.5 h-3.5" /> Mark read
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
