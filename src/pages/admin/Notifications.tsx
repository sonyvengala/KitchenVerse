/**
 * Admin Notification Center & Notification Management System
 * Displays real platform events: kitchen approvals, customer orders,
 * payments, low inventory alerts, and system operational notices.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApi, AdminNotification, AdminNotificationListResponse } from '../../services/adminApi';
import { Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import {
  Bell,
  Check,
  CheckCheck,
  RotateCcw,
  Trash2,
  RefreshCw,
  Store,
  AlertTriangle,
  Info,
  CheckCircle2,
  Package,
  CreditCard,
  XCircle,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';

type TabKey = 'ALL' | 'UNREAD' | 'READ' | 'KITCHEN' | 'ORDERS' | 'PAYMENTS' | 'INVENTORY' | 'SYSTEM';

interface TabConfig {
  key: TabKey;
  label: string;
  countKey: keyof AdminNotificationListResponse['counts_by_tab'];
}

const TABS: TabConfig[] = [
  { key: 'ALL', label: 'All', countKey: 'all' },
  { key: 'UNREAD', label: 'Unread', countKey: 'unread' },
  { key: 'READ', label: 'Read', countKey: 'read' },
  { key: 'KITCHEN', label: 'Kitchen Approvals', countKey: 'kitchen' },
  { key: 'ORDERS', label: 'Orders', countKey: 'orders' },
  { key: 'PAYMENTS', label: 'Payments', countKey: 'payments' },
  { key: 'INVENTORY', label: 'Inventory', countKey: 'inventory' },
  { key: 'SYSTEM', label: 'System', countKey: 'system' },
];

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return 'Just now';
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return 'Just now';
    if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateString;
  }
}

function getDateGroup(dateString: string): 'Today' | 'Yesterday' | 'Older' {
  try {
    const d = new Date(dateString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const itemDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (itemDate.getTime() >= today.getTime()) return 'Today';
    if (itemDate.getTime() >= yesterday.getTime()) return 'Yesterday';
    return 'Older';
  } catch {
    return 'Older';
  }
}

export default function AdminNotifications() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabKey>('ALL');
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [counts, setCounts] = useState<AdminNotificationListResponse['counts_by_tab']>({
    all: 0,
    unread: 0,
    read: 0,
    kitchen: 0,
    orders: 0,
    payments: 0,
    inventory: 0,
    system: 0,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const fetchNotifications = async (tab: TabKey = activeTab, isBackground: boolean = false) => {
    try {
      if (!isBackground) setLoading(true);
      setError(null);
      const res: any = await adminApi.getNotifications({ tab });
      if (res && res.notifications) {
        setNotifications(res.notifications);
        if (res.counts_by_tab) {
          setCounts(res.counts_by_tab);
        }
      } else if (Array.isArray(res)) {
        setNotifications(res);
      }
    } catch (err: any) {
      setError(err?.detail || 'Failed to fetch admin notifications');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchNotifications(activeTab);
  }, [activeTab]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchNotifications(activeTab, true);
  };

  const handleMarkRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      setActionLoadingId(id);
      await adminApi.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setCounts((prev) => ({
        ...prev,
        unread: Math.max(0, prev.unread - 1),
        read: prev.read + 1,
      }));
    } catch (err: any) {
      alert(err?.detail || 'Failed to mark notification as read');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleMarkUnread = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      setActionLoadingId(id);
      await adminApi.markNotificationUnread(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: false } : n))
      );
      setCounts((prev) => ({
        ...prev,
        unread: prev.unread + 1,
        read: Math.max(0, prev.read - 1),
      }));
    } catch (err: any) {
      alert(err?.detail || 'Failed to mark notification as unread');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      setRefreshing(true);
      await adminApi.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setCounts((prev) => ({
        ...prev,
        read: prev.read + prev.unread,
        unread: 0,
      }));
    } catch (err: any) {
      alert(err?.detail || 'Failed to mark all notifications as read');
    } finally {
      setRefreshing(false);
    }
  };

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      setActionLoadingId(id);
      await adminApi.deleteNotification(id);
      const deletedItem = notifications.find((n) => n.id === id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      if (deletedItem) {
        setCounts((prev) => ({
          ...prev,
          all: Math.max(0, prev.all - 1),
          unread: deletedItem.is_read ? prev.unread : Math.max(0, prev.unread - 1),
          read: deletedItem.is_read ? Math.max(0, prev.read - 1) : prev.read,
          [deletedItem.category.toLowerCase()]: Math.max(
            0,
            (prev as any)[deletedItem.category.toLowerCase()] - 1
          ),
        }));
      }
    } catch (err: any) {
      alert(err?.detail || 'Failed to delete notification');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleClearRead = async () => {
    if (counts.read === 0) return;
    const confirmClear = window.confirm(
      `Are you sure you want to clear ${counts.read} read notification${
        counts.read > 1 ? 's' : ''
      }? All unread notifications will be kept safe.`
    );
    if (!confirmClear) return;

    try {
      setRefreshing(true);
      await adminApi.clearReadNotifications();
      setNotifications((prev) => prev.filter((n) => !n.is_read));
      setCounts((prev) => ({
        ...prev,
        all: prev.unread,
        read: 0,
      }));
      // Refetch to refresh category counts cleanly
      await fetchNotifications(activeTab, true);
    } catch (err: any) {
      alert(err?.detail || 'Failed to clear read notifications');
    } finally {
      setRefreshing(false);
    }
  };

  const handleNotificationClick = (item: AdminNotification) => {
    if (!item.is_read) {
      // Auto-mark as read on click
      adminApi.markNotificationRead(item.id).catch(() => {});
      setNotifications((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n))
      );
      setCounts((prev) => ({
        ...prev,
        unread: Math.max(0, prev.unread - 1),
        read: prev.read + 1,
      }));
    }

    if (item.link) {
      navigate(item.link);
    }
  };

  const getNotificationIcon = (item: AdminNotification) => {
    const t = (item.event_type || item.notification_type || '').toUpperCase();
    if (t.includes('KITCHEN_REGISTRATION')) {
      return <Store className="w-5 h-5 text-amber-600" />;
    }
    if (t.includes('KITCHEN_APPROVED')) {
      return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
    }
    if (t.includes('KITCHEN_REJECTED')) {
      return <XCircle className="w-5 h-5 text-rose-600" />;
    }
    if (t.includes('DELIVERED')) {
      return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
    }
    if (t.includes('CANCELLED') || t.includes('REJECTED')) {
      return <XCircle className="w-5 h-5 text-rose-600" />;
    }
    if (t.includes('ORDER')) {
      return <Package className="w-5 h-5 text-blue-600" />;
    }
    if (t.includes('PAYMENT')) {
      return <CreditCard className="w-5 h-5 text-teal-600" />;
    }
    if (t.includes('STOCK') || t.includes('INVENTORY')) {
      return <AlertTriangle className="w-5 h-5 text-amber-600" />;
    }
    if (t.includes('PROMOTION') || t.includes('SYSTEM')) {
      return <ShieldAlert className="w-5 h-5 text-purple-600" />;
    }
    return <Info className="w-5 h-5 text-gray-500" />;
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'KITCHEN':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            Kitchen
          </span>
        );
      case 'ORDERS':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            Order
          </span>
        );
      case 'PAYMENTS':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Payment
          </span>
        );
      case 'INVENTORY':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            Inventory
          </span>
        );
      case 'SYSTEM':
      default:
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-purple-50 text-purple-700 border border-purple-200">
            System
          </span>
        );
    }
  };

  // Group notifications into Today, Yesterday, and Older
  const groupedNotifications: { [key in 'Today' | 'Yesterday' | 'Older']: AdminNotification[] } = {
    Today: [],
    Yesterday: [],
    Older: [],
  };

  notifications.forEach((item) => {
    const group = getDateGroup(item.created_at);
    groupedNotifications[group].push(item);
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200/90 shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-gray-900 tracking-tight">Admin Notification Center</h1>
            {counts.unread > 0 ? (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-orange-600 text-white shadow-xs">
                {counts.unread} Unread
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                All Caught Up
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Real-time platform activity, approvals, order transitions, payments, and inventory health.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center flex-wrap gap-2">
          {counts.unread > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={refreshing}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-orange-50 hover:bg-orange-100 text-orange-700 border border-orange-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
              title="Mark all notifications as read"
            >
              <CheckCheck className="w-4 h-4" />
              <span>Mark All Read</span>
            </button>
          )}

          {counts.read > 0 && (
            <button
              onClick={handleClearRead}
              disabled={refreshing}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-gray-50 hover:bg-rose-50 text-gray-600 hover:text-rose-700 border border-gray-200 hover:border-rose-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
              title="Clear all read notifications. Unread notifications remain untouched."
            >
              <Trash2 className="w-4 h-4" />
              <span>Clear Read ({counts.read})</span>
            </button>
          )}

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center space-x-1.5 px-3.5 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-orange-600' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none border-b border-gray-200">
        {TABS.map((tab) => {
          const count = counts[tab.countKey] || 0;
          const isSelected = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                isSelected
                  ? 'bg-gray-900 text-white shadow-xs'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`px-1.5 py-0.5 rounded-full text-[10px] font-black ${
                  isSelected
                    ? 'bg-white/20 text-white'
                    : count > 0 && tab.key === 'UNREAD'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      {loading && notifications.length === 0 ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={() => fetchNotifications(activeTab)} />
      ) : notifications.length === 0 ? (
        <Card>
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-orange-50 border border-orange-100 flex items-center justify-center mx-auto mb-3 text-orange-500">
              <Bell className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-gray-900">No Notifications</h3>
            <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
              There are no notifications matching the selected tab ({TABS.find((t) => t.key === activeTab)?.label}).
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {(['Today', 'Yesterday', 'Older'] as const).map((groupKey) => {
            const groupItems = groupedNotifications[groupKey];
            if (groupItems.length === 0) return null;

            return (
              <div key={groupKey} className="space-y-2.5">
                <div className="flex items-center space-x-2 px-1">
                  <h3 className="text-xs font-black uppercase tracking-wider text-gray-600">
                    {groupKey}
                  </h3>
                  <div className="h-px bg-gray-200 flex-1" />
                  <span className="text-[11px] font-semibold text-gray-600">
                    {groupItems.length}
                  </span>
                </div>

                <div className="space-y-2">
                  {groupItems.map((item) => {
                    const isUnread = !item.is_read;
                    const isActing = actionLoadingId === item.id;

                    return (
                      <div
                        key={item.id}
                        onClick={() => handleNotificationClick(item)}
                        className={`group relative p-4 rounded-2xl border transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          isUnread
                            ? 'bg-orange-50/40 hover:bg-orange-50/70 border-orange-200/90 shadow-xs'
                            : 'bg-white hover:bg-gray-50/80 border-gray-200/80 text-gray-600'
                        }`}
                      >
                        {/* Unread Accent Pill */}
                        {isUnread && (
                          <div className="absolute left-0 top-3 bottom-3 w-1 bg-orange-600 rounded-r-full" />
                        )}

                        <div className="flex items-start space-x-3.5 min-w-0 pl-1">
                          {/* Icon Box */}
                          <div
                            className={`p-2.5 rounded-xl border shrink-0 mt-0.5 ${
                              isUnread
                                ? 'bg-white border-orange-200 shadow-xs'
                                : 'bg-gray-50 border-gray-200/70'
                            }`}
                          >
                            {getNotificationIcon(item)}
                          </div>

                          {/* Content */}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center flex-wrap gap-2">
                              <h4
                                className={`text-sm tracking-tight truncate ${
                                  isUnread ? 'font-black text-gray-900' : 'font-semibold text-gray-700'
                                }`}
                              >
                                {item.title}
                              </h4>

                              {isUnread && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-black bg-orange-600 text-white tracking-wide uppercase">
                                  New
                                </span>
                              )}

                              {getCategoryBadge(item.category)}
                            </div>

                            <p className="text-xs text-gray-600 mt-1 leading-relaxed break-words">
                              {item.message}
                            </p>

                            <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-600 font-medium">
                              <span>{formatRelativeTime(item.created_at)}</span>
                              <span>•</span>
                              <span>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              {item.link && (
                                <>
                                  <span>•</span>
                                  <span className="inline-flex items-center text-orange-600 font-bold group-hover:underline">
                                    <span>View details</span>
                                    <ChevronRight className="w-3 h-3 ml-0.5" />
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Row Action Buttons */}
                        <div
                          className="flex items-center self-end sm:self-center gap-1.5 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-gray-100 sm:border-transparent w-full sm:w-auto justify-end"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {isUnread ? (
                            <button
                              onClick={(e) => handleMarkRead(item.id, e)}
                              disabled={isActing}
                              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-white hover:bg-emerald-50 text-gray-700 hover:text-emerald-700 border border-gray-200 hover:border-emerald-200 text-xs font-bold transition-colors cursor-pointer"
                              title="Mark as Read"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span className="hidden xs:inline">Mark Read</span>
                            </button>
                          ) : (
                            <button
                              onClick={(e) => handleMarkUnread(item.id, e)}
                              disabled={isActing}
                              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-white hover:bg-orange-50 text-gray-500 hover:text-orange-700 border border-gray-200 hover:border-orange-200 text-xs font-bold transition-colors cursor-pointer"
                              title="Mark as Unread"
                            >
                              <RotateCcw className="w-3.5 h-3.5" />
                              <span className="hidden xs:inline">Mark Unread</span>
                            </button>
                          )}

                          <button
                            onClick={(e) => handleDelete(item.id, e)}
                            disabled={isActing}
                            className="p-1.5 rounded-xl bg-white hover:bg-rose-50 text-gray-400 hover:text-rose-600 border border-gray-200 hover:border-rose-200 transition-colors cursor-pointer"
                            title="Delete Notification"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
