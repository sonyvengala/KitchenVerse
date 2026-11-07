/**
 * Admin Analytics Page
 * Real data visualizations using Recharts.
 * All charts bind to live API data — zero synthetic values.
 */

import { useState, useEffect } from 'react';
import { adminApi, AnalyticsResponse } from '../../services/adminApi';
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, StatCard } from '../../components/admin/AdminComponents';
import { formatINR } from '../../utils/currency';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';

const CHART_COLORS = ['#166534', '#0369a1', '#7c3aed', '#c2410c', '#b45309', '#0f766e', '#be185d', '#6b21a8'];
const INR_FORMATTER = (v: number) => formatINR(v);

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="mb-6 p-6">
      <h3 className="text-base font-black text-[#172033] tracking-tight mb-4">{title}</h3>
      {children}
    </Card>
  );
}

function InsufficientDataState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center space-y-2">
      <span className="text-3xl">📊</span>
      <p className="text-sm font-semibold text-gray-500">Insufficient real data</p>
      <p className="text-xs text-gray-400 max-w-xs">{message}</p>
    </div>
  );
}

export default function AdminAnalytics() {
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<'production' | 'test_scenario'>('production');

  const fetchAnalytics = async (selectedScenario: 'production' | 'test_scenario' = scenario) => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getAnalytics(selectedScenario);
      setAnalytics(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics(scenario);
  }, [scenario]);

  const handleScenarioChange = (newScenario: 'production' | 'test_scenario') => {
    setScenario(newScenario);
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => fetchAnalytics(scenario)} />;
  if (!analytics) return <ErrorState message="No analytics data available" />;

  const hasData = analytics.orders_over_time.length > 0 || analytics.revenue_over_time.length > 0;

  const orderStatusPieData = analytics.order_status.map((item, idx) => ({
    name: item.status.replace(/_/g, ' '),
    value: item.count,
    fill: CHART_COLORS[idx % CHART_COLORS.length],
  }));

  const popularItemsData = [...analytics.popular_items]
    .sort((a, b) => b.ordered - a.ordered)
    .slice(0, 10)
    .map((item) => ({ name: item.item.length > 22 ? item.item.slice(0, 22) + '...' : item.item, ordered: item.ordered }));

  const kitchenData = [...analytics.kitchen_activity]
    .sort((a, b) => b.orders - a.orders)
    .slice(0, 10)
    .map((item) => ({ name: item.kitchen.length > 20 ? item.kitchen.slice(0, 20) + '...' : item.kitchen, orders: item.orders }));

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <PageHeader
          title="Platform Analytics"
          description={
            scenario === 'production'
              ? "Live business performance — production records only (test records strictly excluded)"
              : "Isolated Test Scenario — audit view of generated validation orders and customer activity"
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
            <p className="font-bold">Viewing Isolated Test Scenario Analytics</p>
            <p className="text-amber-800 mt-0.5">
              Displaying validation orders placed by test customer accounts. Normal production analytics remain strictly isolated and unaffected.
            </p>
          </div>
        </div>
      )}

      {!hasData ? (
        <Card>
          <EmptyState
            icon="📊"
            title={`No ${scenario === 'production' ? 'production' : 'test'} order data recorded`}
            description={
              scenario === 'production'
                ? "Live business analytics require historical customer orders. Switch to Test Scenario to view validation runs."
                : "No test scenario orders exist in the database yet. Run the demand test scenario seeder to populate test data."
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard title="Inventory Items" value={analytics.inventory_status.total} icon="📦" color="bg-blue-500"
              subtitle={`${analytics.inventory_status.low_stock} low stock`} />
            <StatCard title="Total Orders" value={analytics.order_status.reduce((sum, s) => sum + s.count, 0)} icon="📋"
              color={scenario === 'production' ? "bg-green-500" : "bg-amber-500"} subtitle={`${analytics.order_status.length} status types`} />
            <StatCard title="Active Kitchens" value={analytics.kitchen_activity.length} icon="🏪" color="bg-purple-500" />
            <StatCard title="Popular Items" value={analytics.popular_items.length} icon="🍽️" color="bg-orange-500" />
          </div>

      <ChartCard title="Orders Over Time (Last 30 Days)">
        {analytics.orders_over_time.length === 0 ? (
          <InsufficientDataState message="No order history available. Orders will appear here as they are placed." />
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={analytics.orders_over_time} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                labelFormatter={(l) => `Date: ${l}`} formatter={(v: any) => [v, 'Orders']} />
              <Line type="monotone" dataKey="count" name="Orders" stroke="#166534" strokeWidth={2.5}
                dot={{ r: 3, fill: '#166534' }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {analytics.revenue_over_time.length > 0 && (
        <ChartCard title="Revenue Over Time (Last 30 Days)">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={analytics.revenue_over_time} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#166534" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#166534" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={INR_FORMATTER} width={80} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                labelFormatter={(l) => `Date: ${l}`} formatter={(v: any) => [INR_FORMATTER(v), 'Revenue']} />
              <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#166534" strokeWidth={2.5} fill="url(#revenueGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="p-6">
          <h3 className="text-base font-black text-[#172033] tracking-tight mb-4">Kitchen Activity (Orders)</h3>
          {kitchenData.length === 0 ? (
            <InsufficientDataState message="No kitchen order data recorded yet." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={kitchenData} margin={{ top: 4, right: 8, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9ca3af' }} angle={-30} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  formatter={(v: any) => [v, 'Orders']} />
                <Bar dataKey="orders" name="Orders" radius={[4, 4, 0, 0]}>
                  {kitchenData.map((_entry, idx) => (
                    <Cell key={`kc-${idx}`} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="p-6">
          <h3 className="text-base font-black text-[#172033] tracking-tight mb-4">Popular Menu Items (Times Ordered)</h3>
          {popularItemsData.length === 0 ? (
            <InsufficientDataState message="No menu item order data available yet." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={popularItemsData} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: '#6b7280' }} width={110} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  formatter={(v: any) => [v, 'Orders']} />
                <Bar dataKey="ordered" name="Times Ordered" fill="#F97316" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {analytics.order_status.length > 0 && (
        <ChartCard title="Order Status Distribution">
          <div className="flex flex-col md:flex-row items-center gap-6">
            <div className="flex-shrink-0">
              <ResponsiveContainer width={220} height={220}>
                <PieChart>
                  <Pie data={orderStatusPieData} cx="50%" cy="50%" innerRadius={55} outerRadius={90}
                    paddingAngle={3} dataKey="value">
                    {orderStatusPieData.map((entry, idx) => (
                      <Cell key={`ps-${idx}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    formatter={(v: any) => [v, 'Orders']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-3">
              {orderStatusPieData.map((item, idx) => (
                <div key={idx} className="bg-gray-50 p-3 rounded-xl border border-gray-200 text-center">
                  <div className="w-3 h-3 rounded-full mx-auto mb-1" style={{ background: item.fill }} />
                  <div className="text-xl font-black text-gray-900">{item.value}</div>
                  <div className="text-[10px] text-gray-500 font-semibold uppercase tracking-wide leading-tight mt-0.5">{item.name}</div>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      )}

      {analytics.customer_growth && analytics.customer_growth.length > 0 && (
        <ChartCard title="Customer Growth Over Time">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={analytics.customer_growth} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="custGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0369a1" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#0369a1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                formatter={(v: any) => [v, 'New Customers']} />
              <Area type="monotone" dataKey="count" name="New Customers" stroke="#0369a1" strokeWidth={2.5} fill="url(#custGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {analytics.waste_trends && analytics.waste_trends.length > 0 && (
        <ChartCard title="Waste Cost Trend">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={analytics.waste_trends} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="wasteGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#c2410c" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#c2410c" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={INR_FORMATTER} width={80} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                formatter={(v: any) => [INR_FORMATTER(v), 'Waste Cost']} />
              <Area type="monotone" dataKey="cost" name="Waste Cost" stroke="#c2410c" strokeWidth={2.5} fill="url(#wasteGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
        </>
      )}
    </div>
  );
}
