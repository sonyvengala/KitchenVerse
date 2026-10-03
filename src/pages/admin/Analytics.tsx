/**
 * Admin Analytics Page
 */

import { useState, useEffect } from 'react';
import { adminApi, AnalyticsResponse } from '../../services/adminApi';
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, StatCard } from '../../components/admin/AdminComponents';

export default function AdminAnalytics() {
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getAnalytics();
      setAnalytics(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchAnalytics} />;
  if (!analytics) return <ErrorState message="No analytics data available" />;

  const hasData = analytics.orders_over_time.length > 0 || analytics.revenue_over_time.length > 0;

  if (!hasData) {
    return (
      <div>
        <PageHeader title="Analytics" description="Platform analytics and insights" />
        <Card>
          <EmptyState
            icon="📊"
            title="No data available yet"
            description="Analytics require historical data. Start by creating orders and users to see trends here."
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Analytics" description="Platform analytics and insights" />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Inventory Items"
          value={analytics.inventory_status.total}
          icon="📦"
          color="bg-blue-500"
          subtitle={`${analytics.inventory_status.low_stock} low stock`}
        />
        <StatCard
          title="Order Statuses"
          value={analytics.order_status.length}
          icon="📋"
          color="bg-green-500"
        />
        <StatCard
          title="Active Kitchens"
          value={analytics.kitchen_activity.length}
          icon="🏪"
          color="bg-purple-500"
        />
        <StatCard
          title="Popular Items"
          value={analytics.popular_items.length}
          icon="🍽️"
          color="bg-orange-500"
        />
      </div>

      {/* Orders Over Time */}
      {analytics.orders_over_time.length > 0 && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-semibold mb-4">Orders Over Time (Last 30 Days)</h3>
          <div className="space-y-2">
            {analytics.orders_over_time.slice(-10).map((item, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.date}</span>
                <div className="flex items-center flex-1 ml-4">
                  <div
                    className="bg-blue-500 h-4 rounded"
                    style={{ width: `${(item.count / Math.max(...analytics.orders_over_time.map(i => i.count))) * 100}%` }}
                  />
                  <span className="ml-2 text-sm font-medium">{item.count}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Revenue Over Time */}
      {analytics.revenue_over_time.length > 0 && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-semibold mb-4">Revenue Over Time (Last 30 Days)</h3>
          <div className="space-y-2">
            {analytics.revenue_over_time.slice(-10).map((item, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.date}</span>
                <div className="flex items-center flex-1 ml-4">
                  <div
                    className="bg-green-500 h-4 rounded"
                    style={{ width: `${(item.revenue / Math.max(...analytics.revenue_over_time.map(i => i.revenue))) * 100}%` }}
                  />
                  <span className="ml-2 text-sm font-medium">${item.revenue.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Kitchen Activity */}
      {analytics.kitchen_activity.length > 0 && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-semibold mb-4">Kitchen Activity</h3>
          <div className="space-y-2">
            {analytics.kitchen_activity.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.kitchen}</span>
                <div className="flex items-center flex-1 ml-4">
                  <div
                    className="bg-purple-500 h-4 rounded"
                    style={{ width: `${(item.orders / Math.max(...analytics.kitchen_activity.map(i => i.orders))) * 100}%` }}
                  />
                  <span className="ml-2 text-sm font-medium">{item.orders} orders</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Popular Items */}
      {analytics.popular_items.length > 0 && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-semibold mb-4">Popular Menu Items</h3>
          <div className="space-y-2">
            {analytics.popular_items.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.item}</span>
                <div className="flex items-center flex-1 ml-4">
                  <div
                    className="bg-orange-500 h-4 rounded"
                    style={{ width: `${(item.ordered / Math.max(...analytics.popular_items.map(i => i.ordered))) * 100}%` }}
                  />
                  <span className="ml-2 text-sm font-medium">{item.ordered} ordered</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Order Status Distribution */}
      {analytics.order_status.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Order Status Distribution</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {analytics.order_status.map((item, idx) => (
              <div key={idx} className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{item.count}</div>
                <div className="text-sm text-gray-500">{item.status}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
