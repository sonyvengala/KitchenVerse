/**
 * Admin Dashboard Page
 */

import { useState, useEffect } from 'react';
import { adminApi, DashboardStats } from '../../services/adminApi';
import { StatCard, LoadingState, ErrorState, PageHeader, Card } from '../../components/admin/AdminComponents';
import { formatINR } from '../../utils/currency';

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<'production' | 'test_scenario'>('production');

  const fetchStats = async (selectedScenario: 'production' | 'test_scenario' = scenario) => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getDashboardStats({ scenario: selectedScenario });
      setStats(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats(scenario);
  }, [scenario]);

  const handleScenarioChange = (newScenario: 'production' | 'test_scenario') => {
    setScenario(newScenario);
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => fetchStats(scenario)} />;
  }

  if (!stats) {
    return <ErrorState message="No data available" />;
  }

  const hasData = stats.total_users > 0 || stats.total_orders > 0;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <PageHeader
          title="Dashboard"
          description={
            scenario === 'production'
              ? "Platform overview — live production records only (test fixtures excluded)"
              : "Isolated Test Scenario — audit view of synthetic validation fixtures"
          }
        />

        {/* Scenario Filter Segmented Control */}
        <div className="flex items-center gap-1.5 p-1.5 bg-gray-100 rounded-2xl border border-gray-200 self-start sm:self-auto">
          <button
            onClick={() => handleScenarioChange('production')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              scenario === 'production'
                ? 'bg-[#166534] text-white shadow-xs'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Live Business Data
          </button>
          <button
            onClick={() => handleScenarioChange('test_scenario')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              scenario === 'test_scenario'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Test Scenario Data
          </button>
        </div>
      </div>

      {scenario === 'test_scenario' && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3">
          <span className="text-xl">🧪</span>
          <div className="text-xs text-amber-900">
            <p className="font-bold">Viewing Isolated Test Scenario Data</p>
            <p className="text-amber-800 mt-0.5">
              Displaying synthetic test fixture orders (TEST-*). Live business records and real customer transactions remain strictly isolated.
            </p>
          </div>
        </div>
      )}

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
                subtitle="Customers & Kitchen Owners (excl. Admins)"
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
                subtitle={stats.gross_order_value !== undefined ? `Gross: ${formatINR(stats.gross_order_value)}` : undefined}
              />
              <StatCard
                title="Pending Orders"
                value={stats.pending_orders}
                icon="⏳"
                color="bg-yellow-500"
                subtitle="Awaiting preparation"
              />
              <StatCard
                title="Completed Orders"
                value={stats.completed_orders}
                icon="✅"
                color="bg-green-500"
                subtitle="Delivered to customer"
              />
              <StatCard
                title="Cancelled Orders"
                value={stats.cancelled_orders}
                icon="❌"
                color="bg-red-500"
                subtitle={stats.refunded_amount !== undefined && stats.refunded_amount > 0 ? `Refunded: ${formatINR(stats.refunded_amount)}` : undefined}
              />
            </div>
          </div>

          {/* Financial & Operational */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Financial & Operational</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Revenue"
                value={formatINR(stats.revenue)}
                icon="💰"
                color="bg-emerald-500"
                subtitle="Delivered & paid (net fulfilled)"
              />
              <StatCard
                title="Low Stock Items"
                value={stats.low_stock_items}
                icon="⚠️"
                color="bg-amber-500"
                subtitle="Needs replenishment"
              />
              <StatCard
                title="Reviews"
                value={stats.reviews}
                icon="⭐"
                color="bg-pink-500"
                subtitle="Customer feedback"
              />
              <StatCard
                title="Waste Records"
                value={stats.waste_records}
                icon="🗑️"
                color="bg-gray-500"
                subtitle="Logged inventory waste"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
