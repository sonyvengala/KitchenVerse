/**
 * Kitchen Notifications Page
 * Displays alerts, order notices, and low-stock warnings with mark-as-read capability.
 */

import { useState, useEffect } from 'react';
import kitchenApi, { KitchenNotification } from '../../services/kitchenApi';
import {
  Bell,
  Check,
  RefreshCw,
  AlertTriangle,
  Info,
  ShoppingBag,
} from 'lucide-react';

export default function KitchenNotifications() {
  const [notifications, setNotifications] = useState<KitchenNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await kitchenApi.getNotifications();
      setNotifications(data);
    } catch (err: any) {
      setError(err?.detail || 'Failed to fetch notifications.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkRead = async (id: string) => {
    try {
      await kitchenApi.markNotificationRead(id);
      setNotifications(
        notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err: any) {
      alert(err?.detail || 'Failed to mark notification as read.');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await kitchenApi.markAllNotificationsRead();
      setNotifications(notifications.map((n) => ({ ...n, is_read: true })));
    } catch (err: any) {
      alert(err?.detail || 'Failed to mark all notifications as read.');
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const getIcon = (type: string) => {
    if (type.includes('STOCK')) {
      return <AlertTriangle className="w-5 h-5 text-amber-600" />;
    }
    if (type.includes('ORDER')) {
      return <ShoppingBag className="w-5 h-5 text-[#166534]" />;
    }
    return <Info className="w-5 h-5 text-blue-600" />;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-[#172033] tracking-tight">Kitchen Notifications</h1>
            {unreadCount > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F97316] text-white">
                {unreadCount} Unread
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500">Live operational alerts, low-stock warnings, and order updates.</p>
        </div>

        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-50 hover:bg-emerald-100 text-[#166534] border border-emerald-200 rounded-xl text-sm font-semibold transition-colors"
            >
              <Check className="w-4 h-4" />
              <span>Mark All Read</span>
            </button>
          )}

          <button
            onClick={fetchNotifications}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center">
          <p>{error}</p>
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
          <Bell className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-700">No notifications</h3>
          <p className="text-sm text-gray-400 mt-1">Your kitchen alert log is currently clear.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`p-4 rounded-2xl border transition-all flex items-start justify-between gap-4 ${
                n.is_read
                  ? 'bg-white border-gray-200/80 text-gray-600'
                  : 'bg-emerald-50/40 border-emerald-200 text-gray-900 shadow-xs'
              }`}
            >
              <div className="flex items-start space-x-3.5">
                <div className="p-2.5 bg-white rounded-xl shadow-xs border border-gray-100 mt-0.5">
                  {getIcon(n.notification_type)}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h4 className="font-bold text-sm text-[#172033]">{n.title}</h4>
                    {!n.is_read && (
                      <span className="w-2 h-2 rounded-full bg-[#F97316]" />
                    )}
                  </div>
                  <p className="text-xs text-gray-600 mt-0.5">{n.message}</p>
                  <p className="text-[10px] text-gray-400 mt-2 font-medium">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
              </div>

              {!n.is_read && (
                <button
                  onClick={() => handleMarkRead(n.id)}
                  className="px-3 py-1 bg-white hover:bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:text-gray-900 transition-colors flex items-center space-x-1"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Mark Read</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
