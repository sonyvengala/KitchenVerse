/**
 * Kitchen Owner Dashboard
 * Displays real-time operational metrics directly from the live database.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import kitchenApi, { KitchenDashboardStats } from '../../services/kitchenApi';
import {
  ShoppingBag,
  TrendingUp,
  AlertTriangle,
  Clock,
  CheckCircle2,
  UtensilsCrossed,
  Star,
  ArrowRight,
  Power,
  RefreshCw,
} from 'lucide-react';

export default function KitchenDashboard() {
  const [stats, setStats] = useState<KitchenDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await kitchenApi.getDashboard();
      setStats(data);
    } catch (err: any) {
      setError(err?.detail || 'Failed to load kitchen dashboard statistics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleToggleOpen = async () => {
    if (!stats) return;
    try {
      setToggling(true);
      const newStatus = !stats.is_open;
      await kitchenApi.updateSettings({ is_open: newStatus });
      setStats({ ...stats, is_open: newStatus });
    } catch (err: any) {
      alert(err?.detail || 'Failed to update kitchen status');
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center space-y-3">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
          <p className="text-gray-500 font-medium">Loading live kitchen statistics...</p>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center max-w-xl mx-auto my-8">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-red-800 mb-1">Failed to Load Dashboard</h3>
        <p className="text-sm text-red-600 mb-4">{error || 'No kitchen profile associated with this account.'}</p>
        <button
          onClick={fetchStats}
          className="px-4 py-2 bg-[#166534] text-white rounded-xl text-sm font-semibold hover:bg-emerald-800 transition-colors"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header & Status Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl font-black text-[#172033] tracking-tight">{stats.kitchen_name}</h1>
            <span
              className={`px-3 py-0.5 text-xs font-bold rounded-full ${
                stats.is_open
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  : 'bg-red-100 text-red-800 border border-red-300'
              }`}
            >
              {stats.is_open ? 'OPEN FOR ORDERS' : 'KITCHEN CLOSED'}
            </span>
          </div>
          <p className="text-sm text-gray-500">Live operational overview and inventory status.</p>
        </div>

        <button
          onClick={handleToggleOpen}
          disabled={toggling}
          className={`flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all shadow-xs ${
            stats.is_open
              ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
              : 'bg-[#166534] text-white hover:bg-emerald-800'
          }`}
        >
          <Power className="w-4 h-4" />
          <span>{toggling ? 'Updating...' : stats.is_open ? 'Close Kitchen' : 'Open Kitchen'}</span>
        </button>
      </div>

      {/* Low Stock Alert Banner */}
      {stats.low_stock_count > 0 && (
        <div className="bg-amber-50 border border-amber-200/80 rounded-2xl p-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-amber-100 rounded-xl text-amber-700">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-amber-900">
                {stats.low_stock_count} {stats.low_stock_count === 1 ? 'ingredient has' : 'ingredients have'} fallen below the minimum threshold.
              </p>
              <p className="text-xs text-amber-700">Restock soon to avoid order rejection or stockout during peak service.</p>
            </div>
          </div>
          <Link
            to="/kitchen/restocking"
            className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition-colors"
          >
            <span>Restock</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Pending Orders */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Order Queue</span>
            <div className="p-2.5 rounded-xl bg-orange-100 text-[#F97316]">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <p className="text-3xl font-black text-[#172033] tracking-tight">{stats.pending_orders_count}</p>
          <div className="flex items-center justify-between mt-3 text-xs">
            <span className="text-gray-500 font-medium">Awaiting acceptance</span>
            <Link to="/kitchen/orders" className="text-[#F97316] font-bold hover:underline">
              Accept now →
            </Link>
          </div>
        </div>

        {/* Active Orders */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Cooking Now</span>
            <div className="p-2.5 rounded-xl bg-emerald-100 text-[#166534]">
              <ShoppingBag className="w-5 h-5" />
            </div>
          </div>
          <p className="text-3xl font-black text-[#172033] tracking-tight">{stats.active_orders_count}</p>
          <p className="mt-3 text-xs text-gray-500 font-medium">Preparing or ready for pickup</p>
        </div>

        {/* Today's Revenue */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Today's Sales</span>
            <div className="p-2.5 rounded-xl bg-emerald-100 text-emerald-700">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <p className="text-3xl font-black text-[#166534] tracking-tight">₹{stats.revenue_today.toFixed(2)}</p>
          <p className="mt-3 text-xs text-gray-500 font-medium">{stats.completed_orders_today} orders completed today</p>
        </div>

        {/* Rating & Menu */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Customer Rating</span>
            <div className="p-2.5 rounded-xl bg-amber-100 text-amber-600">
              <Star className="w-5 h-5 fill-amber-500 text-amber-500" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <p className="text-3xl font-black text-[#172033] tracking-tight">
            {stats.rating > 0 ? stats.rating.toFixed(1) : '—'}
            </p>
            <span className="text-xs text-gray-400">({stats.rating_count} reviews)</span>
          </div>
          <p className="mt-3 text-xs text-gray-500 font-medium">{stats.total_menu_items} active items on menu</p>
        </div>
      </div>

      {/* Quick Operations Navigation */}
      <div>
        <h2 className="text-lg font-bold text-[#172033] mb-4">Operations Shortcuts</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            to="/kitchen/orders"
            className="p-5 bg-white rounded-2xl border border-gray-200/80 hover:border-[#166534] transition-all group shadow-xs"
          >
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#166534] flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
              <ShoppingBag className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-[#172033] group-hover:text-[#166534]">Order Queue</h3>
            <p className="text-xs text-gray-500 mt-1">Accept, reject, and advance order cooking status.</p>
          </Link>

          <Link
            to="/kitchen/menu"
            className="p-5 bg-white rounded-2xl border border-gray-200/80 hover:border-[#166534] transition-all group shadow-xs"
          >
            <div className="w-10 h-10 rounded-xl bg-orange-50 text-[#F97316] flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
              <UtensilsCrossed className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-[#172033] group-hover:text-[#F97316]">Menu & Recipes</h3>
            <p className="text-xs text-gray-500 mt-1">Configure dishes, pricing, and ingredient quantities.</p>
          </Link>

          <Link
            to="/kitchen/inventory"
            className="p-5 bg-white rounded-2xl border border-gray-200/80 hover:border-[#166534] transition-all group shadow-xs"
          >
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-[#172033] group-hover:text-blue-600">Stock & Ledger</h3>
            <p className="text-xs text-gray-500 mt-1">Check stock levels, restock items, and review logs.</p>
          </Link>

          <Link
            to="/kitchen/forecast"
            className="p-5 bg-white rounded-2xl border border-gray-200/80 hover:border-[#166534] transition-all group shadow-xs"
          >
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
              <TrendingUp className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-[#172033] group-hover:text-purple-600">Demand Forecast</h3>
            <p className="text-xs text-gray-500 mt-1">View ML meal-level and center demand predictions.</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
