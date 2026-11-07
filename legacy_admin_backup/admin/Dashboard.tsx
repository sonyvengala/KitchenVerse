/**
 * Admin Dashboard Page
 */

import { useState, useEffect } from 'react';
import { adminApi, DashboardStats } from '../../services/adminApi';
import { StatCard, LoadingState, ErrorState, PageHeader, Card } from '../../components/admin/AdminComponents';

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getDashboardStats();
      setStats(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchStats} />;
  }

  if (!stats) {
    return <ErrorState message="No data available" />;
  }

  const hasData = stats.total_users > 0 || stats.total_orders > 0;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Platform overview and key metrics"
      />

      {!hasData ? (
        <Card>
          <div className="p-12 text-center">
            <div className="text-6xl mb-4">📊</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No data available yet</h3>
            <p className="text-sm text-gray-500">
              Start by creating users, kitchens, and orders to see statistics here.
            </p>
          </div>
        </Card>
      ) : (
        <>
          {/* User Statistics */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">User Statistics</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Total Users"
                value={stats.total_users}
                icon="👥"
                color="bg-blue-500"
              />
              <StatCard
                title="Customers"
                value={stats.customers}
                icon="🛒"
                color="bg-green-500"
              />
              <StatCard
                title="Kitchen Owners"
                value={stats.kitchen_owners}
                icon="👨‍🍳"
                color="bg-purple-500"
              />
              <StatCard
                title="Kitchens"
                value={stats.kitchens}
                icon="🏪"
                color="bg-indigo-500"
              />
            </div>
          </div>

          {/* Order Statistics */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Order Statistics</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Total Orders"
                value={stats.total_orders}
                icon="📦"
                color="bg-orange-500"
              />
              <StatCard
                title="Pending Orders"
                value={stats.pending_orders}
                icon="⏳"
                color="bg-yellow-500"
              />
              <StatCard
                title="Completed Orders"
                value={stats.completed_orders}
                icon="✅"
                color="bg-green-500"
              />
              <StatCard
                title="Cancelled Orders"
                value={stats.cancelled_orders}
                icon="❌"
                color="bg-red-500"
              />
            </div>
          </div>

          {/* Financial & Operational */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Financial & Operational</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Revenue"
                value={`$${stats.revenue.toFixed(2)}`}
                icon="💰"
                color="bg-emerald-500"
              />
              <StatCard
                title="Low Stock Items"
                value={stats.low_stock_items}
                icon="⚠️"
                color="bg-amber-500"
              />
              <StatCard
                title="Reviews"
                value={stats.reviews}
                icon="⭐"
                color="bg-pink-500"
              />
              <StatCard
                title="Waste Records"
                value={stats.waste_records}
                icon="🗑️"
                color="bg-gray-500"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
