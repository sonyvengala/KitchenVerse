/**
 * Kitchen Owner Portal Layout
 * Features sidebar navigation, kitchen status indicator, alerts count, and profile/logout.
 */

import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { normalizeRole, getRoleDashboardPath } from '../../utils/roleUtils';
import kitchenApi, { KitchenDashboardStats } from '../../services/kitchenApi';
import {
  LayoutDashboard,
  ShoppingBag,
  UtensilsCrossed,
  Layers,
  Package,
  RefreshCw,
  Trash2,
  TrendingUp,
  Bell,
  Settings,
  LogOut,
  Menu,
  X,
  Store,
} from 'lucide-react';

import { useRealtime } from '../../context/RealtimeContext';

export default function KitchenLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState<KitchenDashboardStats | null>(null);
  const [license, setLicense] = useState<any | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { subscribe } = useRealtime();

  const fetchLayoutData = () => {
    kitchenApi.getDashboard()
      .then(setStats)
      .catch(() => {});

    kitchenApi.getLicense()
      .then(setLicense)
      .catch(() => {});

    kitchenApi.getNotifications()
      .then((notes) => {
        const unread = notes ? notes.filter((n) => !n.is_read).length : 0;
        setUnreadCount(unread);
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    fetchLayoutData();

    // Listen for live updates
    const unsubNotif = subscribe('NOTIFICATION_NEW', fetchLayoutData);
    const unsubOrder = subscribe('ORDER_CREATED', fetchLayoutData);
    const unsubApproval = subscribe('KITCHEN_APPROVAL_UPDATED', fetchLayoutData);
    const unsubLic = subscribe('LICENSE_STATUS_UPDATED', fetchLayoutData);

    return () => {
      unsubNotif();
      unsubOrder();
      unsubApproval();
      unsubLic();
    };
  }, [location.pathname, isAuthenticated, isLoading, subscribe]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600"></div>
          <span className="text-sm font-semibold text-gray-600">Loading KitchenVerse...</span>
        </div>
      </div>
    );
  }

  if (isAuthenticated && user) {
    const role = normalizeRole(user.role);
    if (role !== 'KITCHEN_OWNER') {
      return <Navigate to={getRoleDashboardPath(role)} replace />;
    }
  }

  const navItems = [
    { name: 'Dashboard', href: '/kitchen/dashboard', icon: LayoutDashboard },
    { name: 'Orders', href: '/kitchen/orders', icon: ShoppingBag, badge: stats?.pending_orders_count || 0 },
    { name: 'Menu', href: '/kitchen/menu', icon: UtensilsCrossed },
    { name: 'Ingredients', href: '/kitchen/ingredients', icon: Layers },
    { name: 'Inventory & Ledger', href: '/kitchen/inventory', icon: Package },
    { name: 'Restocking', href: '/kitchen/restocking', icon: RefreshCw, badge: stats?.low_stock_count || 0 },
    { name: 'Waste Records', href: '/kitchen/waste', icon: Trash2 },
    { name: 'Demand Forecast', href: '/kitchen/forecast', icon: TrendingUp },
    { name: 'Notifications', href: '/kitchen/notifications', icon: Bell, badge: unreadCount || 0 },
    { name: 'Settings', href: '/kitchen/settings', icon: Settings },
  ];

  const isActive = (href: string) => location.pathname === href;

  return (
    <div className="min-h-screen bg-[#FFFDF8] text-[#172033]">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden backdrop-blur-xs"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#166534] text-white flex flex-col justify-between transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          {/* Brand & Kitchen Info */}
          <div className="p-6 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-[#F97316] flex items-center justify-center font-bold text-white shadow-md">
                <Store className="w-6 h-6" />
              </div>
              <div className="min-w-0">
                <h1 className="font-bold text-lg tracking-tight leading-none text-white">KitchenVerse</h1>
                <p className="text-[10px] text-emerald-200/80 font-medium tracking-tight mt-0.5 truncate">
                  Multiple Kitchens. One Destination.
                </p>
                <p className="text-[11px] text-amber-300 font-semibold truncate mt-1">
                  {stats?.kitchen_name || (user ? `${user.first_name} ${user.last_name}`.trim() : 'Kitchen Owner')}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden text-emerald-200 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Kitchen Status pill */}
          {stats && (
            <div className="px-6 py-3 bg-emerald-900/40 border-b border-white/5 flex items-center justify-between text-xs">
              <span className="text-emerald-200">Status</span>
              <span className={`px-2 py-0.5 rounded-full font-medium ${stats.is_open ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'}`}>
                {stats.is_open ? 'OPEN' : 'CLOSED'}
              </span>
            </div>
          )}

          {/* Navigation Links */}
          <nav className="p-4 space-y-1 overflow-y-auto max-h-[calc(100vh-220px)]">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    active
                      ? 'bg-white text-[#166534] shadow-sm font-semibold'
                      : 'text-emerald-100 hover:bg-emerald-800 hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon className={`w-4 h-4 ${active ? 'text-[#166534]' : 'text-emerald-300'}`} />
                    <span>{item.name}</span>
                  </div>
                  {item.badge ? (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                        active
                          ? 'bg-[#F97316] text-white'
                          : 'bg-emerald-700 text-emerald-100'
                      }`}
                    >
                      {item.badge}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Card & Logout */}
        <div className="p-4 border-t border-white/10 bg-emerald-900/30">
          <div className="flex items-center justify-between">
            <div className="truncate mr-2">
              <p className="text-sm font-semibold text-white truncate">
                {user ? `${user.first_name} ${user.last_name}`.trim() : 'Chef'}
              </p>
              <p className="text-xs text-emerald-300 truncate">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              title="Logout"
              className="p-2 rounded-lg bg-emerald-800/80 hover:bg-red-600 text-emerald-100 hover:text-white transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="lg:pl-64 flex flex-col min-h-screen">
        {/* Top Navbar */}
        <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-gray-200 px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-lg font-bold text-[#172033]">
              {navItems.find((item) => isActive(item.href))?.name || 'Kitchen Portal'}
            </h2>
          </div>

          <div className="flex items-center space-x-4">
            <Link
              to="/kitchen/notifications"
              className="relative p-2 rounded-full hover:bg-gray-100 text-gray-600 transition-colors"
              title="Notifications"
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 ? (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-[#F97316] text-white text-[10px] font-black rounded-full flex items-center justify-center ring-2 ring-white">
                  {unreadCount}
                </span>
              ) : null}
            </Link>
            <div className="hidden sm:flex items-center space-x-2 text-sm text-gray-500">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Live System Connected</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto space-y-6">
          {license && license.status !== 'VERIFIED' && (
            <div
              className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-xs ${
                license.status === 'CORRECTION_REQUIRED'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : license.status === 'REJECTED' || license.status === 'EXPIRED'
                  ? 'bg-rose-50 border-rose-200 text-rose-900'
                  : 'bg-blue-50 border-blue-200 text-blue-900'
              }`}
            >
              <div className="space-y-1">
                <div className="font-bold text-sm flex items-center gap-2">
                  <span>
                    {license.status === 'CORRECTION_REQUIRED'
                      ? '⚠️ FSSAI Food License: Correction Requested'
                      : license.status === 'REJECTED'
                      ? '⛔ FSSAI Food License: Submission Rejected'
                      : license.status === 'EXPIRED'
                      ? '⏰ FSSAI Food License: Expired'
                      : '⏳ FSSAI Food License: Pending Admin Verification'}
                  </span>
                </div>
                <p className="opacity-90">
                  {license.status === 'CORRECTION_REQUIRED'
                    ? `Admin requested changes: "${license.correction_reason || 'Please review and re-upload'}"`
                    : license.status === 'REJECTED'
                    ? `Reason: "${license.rejection_reason || 'Non-compliant submission'}". Kitchen operations paused.`
                    : license.status === 'EXPIRED'
                    ? 'Your food safety license has expired. Kitchen is closed until renewal is verified.'
                    : 'Customer orders and kitchen opening are disabled until official verification is approved.'}
                </p>
              </div>
              <Link
                to="/kitchen/settings"
                className="shrink-0 px-4 py-2 bg-white text-gray-800 font-bold rounded-xl border border-gray-200 hover:border-gray-300 transition shadow-xs text-center"
              >
                Manage License →
              </Link>
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
