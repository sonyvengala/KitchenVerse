/**
 * Kitchen Demand Forecast & Demand Center Page
 * 
 * Architecture & Real Data Principles:
 *  - Order History: Chronological daily actual orders + progressive forecast with 10% safety buffer
 *  - Menu Demand: Demand tracking per real menu item (zero benchmark meal IDs)
 *  - Preparation & Stock: Portions × recipe ingredients vs real inventory stock
 *  - Demand Center: Real customer order geographic distribution, privacy-preserving postal/city clusters,
 *    and opportunity recommendations strictly when evidence threshold is met (5+ orders from 3+ customers).
 */

import { useState, useEffect } from 'react';
import apiClient from '../../lib/api';
import {
  TrendingUp,
  RefreshCw,
  AlertCircle,
  BarChart3,
  UtensilsCrossed,
  Calendar,
  Info,
  MapPin,
  Compass,
  AlertTriangle,
  Store,
  ShieldCheck,
  CheckCircle2,
  Package,
  Layers,
  ArrowRight,
} from 'lucide-react';
import DemandCenterMap, { KitchenLocation, DemandArea } from '../../components/common/DemandCenterMap';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line,
} from 'recharts';

interface DailyHistoryItem {
  date: string;
  day_name: string;
  actual_orders: number;
  real_orders?: number;
  test_orders?: number;
  data_type?: string;
  is_actual: boolean;
}

interface DailyForecastItem {
  day_offset: number;
  day_name: string;
  predicted_demand: number;
  safety_buffer_pct: number;
  recommended_capacity: number;
  confidence: string;
}

interface MenuItemDemandItem {
  id?: string;
  menu_item_id?: string;
  name: string;
  category: string;
  cuisine?: string;
  price: number;
  historical_units_sold: number;
  daily_order_rate: number;
  predicted_daily_portions?: number;
  weekly_predicted_demand?: number;
}

interface IngredientReadinessItem {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  required_amount: number;
  expected_usage?: number;
  available_stock: number;
  current_stock?: number;
  projected_stock?: number;
  minimum_threshold?: number;
  status: 'OK' | 'SHORTAGE' | 'RESTOCK_REQUIRED' | string;
  forecast_status?: string;
  shortage_amount: number;
  restock_needed?: number;
  restock_recommendation: string;
}

interface OperationalForecastResponse {
  mode: string;
  status: 'insufficient_data' | 'operational';
  confidence: 'NONE' | 'INSUFFICIENT_FOR_PROJECTION' | 'LOW' | 'MEDIUM' | 'HIGH';
  kitchen_id: string;
  kitchen_name: string;
  actual_orders_available?: number;
  actual_orders_analyzed?: number;
  total_real_orders?: number;
  total_test_orders?: number;
  distinct_operating_days?: number;
  history_available_days?: number;
  history_period_days?: number;
  min_required_orders?: number;
  min_required_days?: number;
  message: string;
  daily_history: DailyHistoryItem[];
  daily_forecast: DailyForecastItem[];
  safety_buffer_rule?: string;
  menu_item_demand: MenuItemDemandItem[];
  preparation_plan_status: 'available' | 'unavailable';
  preparation_plan_message?: string;
  ingredient_readiness: IngredientReadinessItem[];
  data_freshness?: {
    calculated_at: string;
    orders_from: string | null;
    orders_to: string | null;
  };
}

export interface KitchenDemandItem {
  kitchen_id: string;
  kitchen_name: string;
  city: string;
  address?: string;
  order_count: number;
  unique_customers: number;
  revenue: number;
  demand_intensity: 'HIGH' | 'MEDIUM' | 'LOW';
  is_open?: boolean;
  is_approved?: boolean;
  rating?: number;
  total_reviews?: number;
  is_my_kitchen?: boolean;
}

interface DemandCenterResponse {
  mode: string;
  status: 'insufficient_data' | 'operational';
  period_days: number;
  total_orders: number;
  total_revenue: number;
  message: string;
  threshold_rule?: string;
  definitions?: {
    kitchen_demand: string;
    geographic_demand: string;
  };
  kitchen_demand?: KitchenDemandItem[];
  demand_areas: DemandArea[];
  top_demand_areas: DemandArea[];
  recommended_areas: DemandArea[];
  cloudkitchen_kitchens: KitchenLocation[];
  data_freshness?: {
    calculated_at: string;
    period_days: number;
    earliest_order: string | null;
    latest_order: string | null;
  };
}

const CATEGORY_COLORS = [
  '#166534', '#0369a1', '#7c3aed', '#c2410c', '#b45309',
  '#0f766e', '#be185d', '#6b21a8', '#0c4a6e', '#14532d',
];

export default function KitchenDemandForecast() {
  const [activeTab, setActiveTab] = useState<'operational' | 'demand_center'>('operational');

  // Operational State
  const [operationalData, setOperationalData] = useState<OperationalForecastResponse | null>(null);
  const [operationalLoading, setOperationalLoading] = useState<boolean>(true);
  const [operationalError, setOperationalError] = useState<string | null>(null);

  // Demand Center State
  const [demandCenterData, setDemandCenterData] = useState<DemandCenterResponse | null>(null);
  const [demandCenterLoading, setDemandCenterLoading] = useState<boolean>(false);
  const [demandCenterLookback, setDemandCenterLookback] = useState<number>(30);

  const fetchOperationalForecast = async () => {
    try {
      setOperationalLoading(true);
      setOperationalError(null);
      const res = await apiClient.get<OperationalForecastResponse>('/api/v1/ml/operational-forecast');
      setOperationalData(res);
    } catch (err: any) {
      setOperationalError(err?.detail || 'Failed to load operational kitchen forecast.');
    } finally {
      setOperationalLoading(false);
    }
  };

  const fetchDemandCenter = async () => {
    try {
      setDemandCenterLoading(true);
      const res = await apiClient.get<DemandCenterResponse>(`/api/v1/ml/demand-center?days=${demandCenterLookback}`);
      setDemandCenterData(res);
    } catch (err: any) {
      console.warn('Failed to load demand center:', err);
    } finally {
      setDemandCenterLoading(false);
    }
  };

  useEffect(() => {
    fetchOperationalForecast();
  }, []);

  useEffect(() => {
    if (activeTab === 'demand_center') {
      fetchDemandCenter();
    }
  }, [activeTab, demandCenterLookback]);

  return (
    <div className="space-y-6">
      {/* Top Header & Tab Navigation */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <h1 className="text-2xl font-black text-[#172033] tracking-tight">
                Demand Forecasting & Demand Center
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-[#166534] tracking-wider uppercase">
                Real Data Only
              </span>
            </div>
            <p className="text-sm text-gray-500">
              Kitchen-level operational planning, ingredient readiness, and geographic customer demand intelligence.
            </p>
          </div>

          <div className="flex items-center gap-1.5 p-1.5 bg-gray-100 rounded-2xl border border-gray-200/80 self-start md:self-auto">
            <button
              onClick={() => setActiveTab('operational')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === 'operational'
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <UtensilsCrossed className="w-3.5 h-3.5" />
              <span>Demand Forecast</span>
            </button>

            <button
              onClick={() => setActiveTab('demand_center')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === 'demand_center'
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Demand Center</span>
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: OPERATIONAL DEMAND FORECAST & PREPARATION PLAN (MY KITCHEN)        */}
      {/* ========================================================================= */}
      {activeTab === 'operational' && (
        <div className="space-y-6">
          {/* Action & Status Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <h2 className="text-lg font-bold text-gray-900">
                  {operationalData?.kitchen_name || 'My Kitchen'} — Daily Operations & Prep Planning
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800">
                  AUTHENTICATED KITCHEN SCOPE
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Data pipeline: Real Orders → Actual Item History → Progressive Portions → Recipe Ingredients vs Inventory.
              </p>
            </div>

            <button
              onClick={fetchOperationalForecast}
              disabled={operationalLoading}
              className="flex items-center space-x-1.5 px-3.5 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition self-start sm:self-auto"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${operationalLoading ? 'animate-spin' : ''}`} />
              <span>Refresh Forecast</span>
            </button>
          </div>

          {operationalLoading ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
              <RefreshCw className="w-8 h-8 text-[#166534] animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-gray-700">Analyzing authenticated kitchen order history...</p>
            </div>
          ) : !operationalData ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center text-gray-500">
              Operational forecasting data currently unavailable.
            </div>
          ) : operationalData.status === 'insufficient_data' ? (
            /* Insufficient / Progressive Learning State */
            <div className="space-y-6">
              <div className="bg-white rounded-2xl border border-amber-200/90 shadow-xs p-8">
                <div className="max-w-2xl mx-auto text-center space-y-4">
                  <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto border border-amber-200">
                    <BarChart3 className="w-8 h-8" />
                  </div>

                  <div>
                    <h3 className="text-xl font-black text-gray-900 tracking-tight">
                      Insufficient Real Order History
                    </h3>
                    <p className="text-sm text-gray-600 mt-1 leading-relaxed">
                      {operationalData.message}
                    </p>
                  </div>

                  {/* Operational Metrics vs Thresholds */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-left pt-2">
                    <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">
                        Actual Orders
                      </span>
                      <p className="text-2xl font-black text-gray-900">
                        {operationalData.actual_orders_available ?? 0}
                      </p>
                    </div>

                    <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">
                        History Available
                      </span>
                      <p className="text-2xl font-black text-gray-900">
                        {operationalData.history_available_days ?? 0}{' '}
                        <span className="text-xs font-semibold text-gray-400">days</span>
                      </p>
                    </div>

                    <div className="p-3.5 bg-amber-50/70 rounded-xl border border-amber-200">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 block mb-1">
                        Min. For Projections
                      </span>
                      <p className="text-2xl font-black text-amber-900">
                        {operationalData.min_required_orders ?? 5}{' '}
                        <span className="text-xs font-semibold text-amber-700">orders</span>
                      </p>
                    </div>

                    <div className="p-3.5 bg-amber-50/70 rounded-xl border border-amber-200">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 block mb-1">
                        Confidence State
                      </span>
                      <p className="text-sm font-black text-amber-900 mt-1">
                        {operationalData.confidence}
                      </p>
                    </div>
                  </div>

                  {/* Platform Data Guarantee Banner */}
                  <div className="p-4 bg-emerald-50/80 rounded-xl border border-emerald-200 text-left text-xs text-emerald-900 flex items-start space-x-3">
                    <ShieldCheck className="w-5 h-5 text-[#166534] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-[#166534] mb-0.5">Zero Synthetic Forecasts Guarantee</p>
                      <p className="text-emerald-800/90 leading-relaxed">
                        Predictions are never invented or borrowed from other kitchens. As your kitchen receives and fulfills customer orders, daily actual order trends will accumulate below and automatically transition into portion projections.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Order History: Show Chronological Actual Orders if Any Exist */}
              {operationalData.daily_history && operationalData.daily_history.length > 0 && (
                <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                  <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-gray-900">
                        Order History
                      </h4>
                      <p className="text-xs text-gray-500">
                        Shows actual recorded order history and operating days.
                      </p>
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                      {operationalData.daily_history.length} Operating Day(s)
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                        <tr>
                          <th className="px-6 py-3">Date</th>
                          <th className="px-6 py-3">Day</th>
                          <th className="px-6 py-3">Orders</th>
                          <th className="px-6 py-3 text-right">Data Type</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {operationalData.daily_history.map((day) => (
                          <tr key={day.date} className="hover:bg-gray-50/60 transition">
                            <td className="px-6 py-4 font-mono font-bold text-gray-900">{day.date}</td>
                            <td className="px-6 py-4 font-semibold text-gray-700">{day.day_name}</td>
                            <td className="px-6 py-4 font-mono font-black text-[#166534] text-sm">
                              {day.actual_orders} orders
                            </td>
                            <td className="px-6 py-4 text-right">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                day.data_type === 'TEST DATA'
                                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                  : day.data_type === 'REAL & TEST'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-emerald-100 text-[#166534]'
                              }`}>
                                {day.data_type || 'REAL DATA'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Menu Demand: Real Menu Items (Catalog Ready) */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-gray-900">
                      Menu Demand
                    </h4>
                    <p className="text-xs text-gray-500">
                      Shows demand for this kitchen's actual menu items.
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-gray-200 text-gray-800">
                    {operationalData.menu_item_demand.length} Items
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Menu Item</th>
                        <th className="px-6 py-3">Category</th>
                        <th className="px-6 py-3">Unit Price</th>
                        <th className="px-6 py-3">Historical Sold</th>
                        <th className="px-6 py-3 text-right">Portion Forecast</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {operationalData.menu_item_demand.map((item) => (
                        <tr key={item.id || item.name} className="hover:bg-gray-50/60 transition">
                          <td className="px-6 py-4 font-bold text-gray-900">{item.name}</td>
                          <td className="px-6 py-4 text-gray-600">{item.category}</td>
                          <td className="px-6 py-4 font-mono font-bold text-gray-900">₹{item.price.toFixed(2)}</td>
                          <td className="px-6 py-4 font-mono text-gray-700">{item.historical_units_sold} portions</td>
                          <td className="px-6 py-4 text-right">
                            <span className="text-[11px] text-amber-700 italic">
                              Pending order history
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Preparation & Stock: Unavailable State */}
              <div className="bg-gray-50 rounded-2xl border border-gray-200/80 p-6 text-center space-y-2">
                <Package className="w-6 h-6 text-gray-400 mx-auto" />
                <h4 className="text-sm font-bold text-gray-800">Preparation & Stock</h4>
                <p className="text-xs text-gray-500 max-w-md mx-auto">
                  {operationalData.preparation_plan_message || 'Shows preparation recommendations, required ingredients, available stock, and restock status.'}
                </p>
              </div>
            </div>
          ) : (
            /* ============================================================= */
            /* OPERATIONAL FORECAST READY (ACTIVE REAL DATA)                 */
            /* ============================================================= */
            <div className="space-y-6">
              {/* Order History Chart + Table */}
              {operationalData.daily_history && operationalData.daily_history.length > 0 && (
                <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                  <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-gray-900">Order History</h4>
                      <p className="text-xs text-gray-500">Actual recorded orders per operating day.</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                        {operationalData.daily_history.length} Day(s)
                      </span>
                      {operationalData.total_real_orders != null && (
                        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-[#166534]">
                          {operationalData.total_real_orders} Real
                        </span>
                      )}
                      {operationalData.total_test_orders != null && operationalData.total_test_orders > 0 && (
                        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800">
                          {operationalData.total_test_orders} Test
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Line Chart */}
                  <div className="px-5 pt-4 pb-2">
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart
                        data={operationalData.daily_history.map(d => ({ date: d.date.slice(5), orders: d.actual_orders, type: d.data_type }))}
                        margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                        <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                          formatter={(v: any) => [v, 'Orders']}
                        />
                        <Line type="monotone" dataKey="orders" name="Orders" stroke="#166534" strokeWidth={2.5}
                          dot={{ r: 3, fill: '#166534' }} activeDot={{ r: 5 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                        <tr>
                          <th className="px-6 py-3">Date</th>
                          <th className="px-6 py-3">Day</th>
                          <th className="px-6 py-3">Orders</th>
                          <th className="px-6 py-3 text-right">Data Type</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {operationalData.daily_history.map((day) => (
                          <tr key={day.date} className="hover:bg-gray-50/60 transition">
                            <td className="px-6 py-4 font-mono font-bold text-gray-900">{day.date}</td>
                            <td className="px-6 py-4 font-semibold text-gray-700">{day.day_name}</td>
                            <td className="px-6 py-4 font-mono font-black text-[#166534] text-sm">
                              {day.actual_orders} orders
                            </td>
                            <td className="px-6 py-4 text-right">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                day.data_type === 'TEST DATA'
                                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                  : day.data_type === 'REAL & TEST'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-emerald-100 text-[#166534]'
                              }`}>
                                {day.data_type || 'REAL DATA'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Order Forecast & Recommended Capacity */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-gray-100 pb-4">
                  <div>
                    <h3 className="text-base font-black text-gray-900 flex items-center space-x-2">
                      <TrendingUp className="w-5 h-5 text-[#166534]" />
                      <span>Order Forecast & Recommended Capacity</span>
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Progressive forecast incorporating a 10% safety buffer over base demand to protect against stockouts and food waste.
                    </p>
                  </div>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                    operationalData.confidence === 'HIGH' ? 'bg-emerald-100 text-[#166534]' :
                    operationalData.confidence === 'MEDIUM' ? 'bg-blue-100 text-blue-800' : 'bg-amber-100 text-amber-800'
                  }`}>
                    {operationalData.confidence} STATISTICAL CONFIDENCE
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                  {operationalData.daily_forecast.map((day) => (
                    <div key={day.day_offset} className="p-3.5 bg-gray-50/80 rounded-xl border border-gray-200/70 text-center">
                      <span className="text-[10px] font-bold text-gray-500 uppercase block mb-1">
                        {day.day_name}
                      </span>
                      <p className="text-xs text-gray-400">Demand</p>
                      <p className="text-lg font-black text-gray-800 font-mono">
                        {day.predicted_demand}
                      </p>
                      <div className="mt-1 pt-1.5 border-t border-gray-200">
                        <p className="text-[10px] font-bold text-[#166534]">Capacity (+10%)</p>
                        <p className="text-sm font-black text-[#166534] font-mono">
                          {day.recommended_capacity} orders
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <p className="text-[11px] text-gray-500 bg-gray-50 p-2.5 rounded-xl border border-gray-200/60 leading-relaxed">
                  <strong>Safety Buffer Explanation:</strong> {operationalData.safety_buffer_rule}
                </p>
              </div>

              {/* Menu Demand */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">Menu Demand</h3>
                    <p className="text-xs text-gray-500">Orders received per menu item (historical units sold).</p>
                  </div>
                  <span className="text-xs font-semibold text-gray-500">
                    {operationalData.menu_item_demand.length} Active Items
                  </span>
                </div>

                {/* Horizontal bar chart for menu demand */}
                {operationalData.menu_item_demand.length > 0 && (
                  <div className="px-5 pt-4 pb-2">
                    <ResponsiveContainer width="100%" height={Math.max(120, operationalData.menu_item_demand.length * 34)}>
                      <BarChart
                        data={operationalData.menu_item_demand.map(item => ({
                          name: item.name.length > 24 ? item.name.slice(0, 24) + '...' : item.name,
                          sold: item.historical_units_sold,
                        }))}
                        layout="vertical"
                        margin={{ top: 4, right: 32, left: 8, bottom: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 10, fill: '#9ca3af' }} allowDecimals={false} />
                        <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: '#6b7280' }} width={130} />
                        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                          formatter={(v: any) => [v, 'Units Sold']} />
                        <Bar dataKey="sold" name="Units Sold" fill="#166534" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Menu Item</th>
                        <th className="px-6 py-3">Category</th>
                        <th className="px-6 py-3">Historical Sold</th>
                        <th className="px-6 py-3">Daily Velocity</th>
                        <th className="px-6 py-3 text-right">Predicted Daily Portions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {operationalData.menu_item_demand.map((item) => (
                        <tr key={item.menu_item_id || item.name} className="hover:bg-gray-50/60 transition">
                          <td className="px-6 py-4 font-bold text-gray-900">{item.name}</td>
                          <td className="px-6 py-4 text-gray-600">{item.category}</td>
                          <td className="px-6 py-4 font-mono font-semibold text-gray-700">{item.historical_units_sold} sold</td>
                          <td className="px-6 py-4 font-mono text-gray-600">{item.daily_order_rate} / day</td>
                          <td className="px-6 py-4 text-right">
                            <span className="font-mono font-black text-sm text-[#166534] bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                              ~{item.predicted_daily_portions || 0} portions
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Preparation & Stock */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">
                      Preparation & Stock
                    </h3>
                    <p className="text-xs text-gray-500">
                      Shows preparation recommendations, required ingredients, available stock, and restock status.
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-[#166534] text-white">
                    Recipe-Linked
                  </span>
                </div>

                {/* Expected Orders & Recommended Capacity Summary */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-5 bg-gray-50/70 border-b border-gray-100">
                  <div className="p-3.5 bg-white rounded-xl border border-gray-200 shadow-2xs">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">
                      Expected Daily Orders
                    </span>
                    <p className="text-xl font-black text-gray-900 font-mono">
                      ~{operationalData.daily_forecast[0]?.predicted_demand || 0} orders
                    </p>
                  </div>
                  <div className="p-3.5 bg-white rounded-xl border border-gray-200 shadow-2xs">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#166534] block mb-0.5">
                      Recommended Prep Capacity
                    </span>
                    <p className="text-xl font-black text-[#166534] font-mono">
                      {operationalData.daily_forecast[0]?.recommended_capacity || 0} orders <span className="text-xs font-semibold text-gray-400">(+10% buffer)</span>
                    </p>
                  </div>
                  <div className="p-3.5 bg-white rounded-xl border border-gray-200 shadow-2xs">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">
                      Ingredient Readiness
                    </span>
                    <div className="text-sm font-black text-gray-900 mt-1">
                      {operationalData.ingredient_readiness && operationalData.ingredient_readiness.some(i => i.status === 'SHORTAGE' || i.status === 'RESTOCK_REQUIRED' || i.forecast_status === 'RESTOCK REQUIRED') ? (
                        <span className="text-amber-600 flex items-center"><AlertTriangle className="w-4 h-4 mr-1 text-amber-500" /> Restock Needed</span>
                      ) : (
                        <span className="text-[#166534] flex items-center"><ShieldCheck className="w-4 h-4 mr-1" /> All Ingredients Sufficient</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Ingredient</th>
                        <th className="px-6 py-3">Unit</th>
                        <th className="px-6 py-3">Required for Prep</th>
                        <th className="px-6 py-3">Current Stock</th>
                        <th className="px-6 py-3">Projected Stock</th>
                        <th className="px-6 py-3">Status</th>
                        <th className="px-6 py-3 text-right">Restock Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {operationalData.ingredient_readiness && operationalData.ingredient_readiness.length > 0 ? (
                        operationalData.ingredient_readiness.map((ing) => {
                          const isOk = ing.status === 'OK' || ing.forecast_status === 'SUFFICIENT';
                          const isRestock = ing.status === 'RESTOCK_REQUIRED' || ing.forecast_status === 'RESTOCK REQUIRED';
                          const isShortage = ing.status === 'SHORTAGE' || ing.forecast_status === 'SHORTAGE';

                          return (
                            <tr key={ing.ingredient_id} className="hover:bg-gray-50/60 transition">
                              <td className="px-6 py-4 font-bold text-gray-900">{ing.ingredient_name}</td>
                              <td className="px-6 py-4 font-semibold text-gray-500">{ing.unit}</td>
                              <td className="px-6 py-4 font-mono font-bold text-gray-800">
                                {ing.required_amount} {ing.unit}
                              </td>
                              <td className="px-6 py-4 font-mono text-gray-700">
                                {ing.available_stock} {ing.unit}
                              </td>
                              <td className="px-6 py-4 font-mono font-bold text-gray-800">
                                {ing.projected_stock !== undefined ? `${ing.projected_stock} ${ing.unit}` : `${(ing.available_stock - ing.required_amount).toFixed(2)} ${ing.unit}`}
                              </td>
                              <td className="px-6 py-4">
                                <span
                                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                    isOk
                                      ? 'bg-emerald-100 text-[#166534]'
                                      : isRestock
                                      ? 'bg-amber-100 text-amber-800'
                                      : 'bg-red-100 text-red-800'
                                  }`}
                                >
                                  {ing.forecast_status || (isOk ? 'Sufficient' : isRestock ? 'Restock Required' : 'Shortage')}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-right">
                                <span
                                  className={`font-semibold text-xs ${
                                    isShortage ? 'text-red-700 font-bold' : isRestock ? 'text-amber-700 font-bold' : 'text-gray-500'
                                  }`}
                                >
                                  {ing.restock_recommendation}
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-6 py-8 text-center text-gray-400">
                            No recipe ingredients linked to menu items yet. Configure recipes under Menu Management to enable automatic prep stock calculations.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: DEMAND CENTER & LOCATION INTELLIGENCE                             */}
      {/* ========================================================================= */}
      {activeTab === 'demand_center' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <h2 className="text-lg font-bold text-gray-900">
                  Demand Center & Geographic Concentration
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-[#166534]">
                  REAL GEO DEMAND
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Visualizes where customer orders originate and identifies genuine underserved geographic clusters.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <select
                value={demandCenterLookback}
                onChange={(e) => setDemandCenterLookback(Number(e.target.value))}
                className="px-3 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 bg-white"
              >
                <option value={7}>Last 7 Days</option>
                <option value={14}>Last 14 Days</option>
                <option value={30}>Last 30 Days</option>
                <option value={90}>Last 90 Days</option>
              </select>
              <button
                onClick={fetchDemandCenter}
                disabled={demandCenterLoading}
                className="flex items-center space-x-1.5 px-3.5 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${demandCenterLoading ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Explanatory Definitions Banner */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-emerald-50/70 border border-emerald-200/90 rounded-2xl flex items-start space-x-3 shadow-2xs">
              <div className="p-2 bg-emerald-100 text-[#166534] rounded-xl flex-shrink-0">
                <Store className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center space-x-2 mb-0.5">
                  <h4 className="text-xs font-black uppercase tracking-wider text-[#166534]">
                    Kitchen Demand
                  </h4>
                  <span className="text-[10px] font-bold bg-emerald-200/70 text-[#166534] px-1.5 py-0.2 rounded">
                    Hub Orders
                  </span>
                </div>
                <p className="text-xs text-gray-700 leading-relaxed">
                  <strong>Kitchen Demand = orders received by KitchenVerse kitchens.</strong> Answers which KitchenVerse kitchen hub has the most real order volume, unique customers, and fulfilled revenue.
                </p>
              </div>
            </div>

            <div className="p-4 bg-blue-50/70 border border-blue-200/90 rounded-2xl flex items-start space-x-3 shadow-2xs">
              <div className="p-2 bg-blue-100 text-blue-700 rounded-xl flex-shrink-0">
                <MapPin className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center space-x-2 mb-0.5">
                  <h4 className="text-xs font-black uppercase tracking-wider text-blue-900">
                    Geographic Demand
                  </h4>
                  <span className="text-[10px] font-bold bg-blue-200/70 text-blue-800 px-1.5 py-0.2 rounded">
                    Delivery Areas
                  </span>
                </div>
                <p className="text-xs text-gray-700 leading-relaxed">
                  <strong>Geographic Demand = customer delivery locations.</strong> Answers where customers are ordering from geographically, delivery density, and nearest kitchen coverage gaps.
                </p>
              </div>
            </div>
          </div>

          {/* Interactive Map */}
          <DemandCenterMap
            kitchens={demandCenterData?.cloudkitchen_kitchens || []}
            demandAreas={demandCenterData?.demand_areas || []}
          />

          {demandCenterData?.status === 'insufficient_data' && (!demandCenterData.kitchen_demand || demandCenterData.kitchen_demand.length === 0) ? (
            <div className="bg-white rounded-2xl border border-amber-200/80 p-8 text-center space-y-3">
              <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto border border-amber-200">
                <MapPin className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-gray-900">Insufficient Geographic Order Data</h3>
              <p className="text-xs text-gray-500 max-w-md mx-auto leading-relaxed">
                {demandCenterData.message} Demand hotspots and new kitchen recommendations require verified customer orders. Zero synthetic locations or fake heatmaps are generated.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Threshold Rule Banner */}
              <div className="p-4 bg-blue-50/80 rounded-xl border border-blue-200 text-xs text-blue-900 flex items-start space-x-3">
                <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-blue-950 mb-0.5">Location Recommendation Threshold Rule</p>
                  <p className="text-blue-800 leading-relaxed">
                    {demandCenterData?.threshold_rule}
                  </p>
                </div>
              </div>

              {/* ========================================================================= */}
              {/* FEATURE 1: KITCHEN DEMAND TABLE + CHART                                  */}
              {/* Answers: "Which CloudKitchen kitchen has the most REAL orders?"            */}
              {/* ========================================================================= */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <div className="flex items-center space-x-2">
                      <Store className="w-4 h-4 text-[#166534]" />
                      <h3 className="text-sm font-black text-gray-900">
                        Kitchen Demand (Orders Received by KitchenVerse Kitchens)
                      </h3>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-[#166534]">
                        KITCHEN-LEVEL
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      <strong>Kitchen Demand = orders received by KitchenVerse kitchens.</strong> Answers which kitchen has the most real orders, customer reach, and demand intensity.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-500">
                      {demandCenterData?.kitchen_demand?.length || 0} Kitchen Hubs
                    </span>
                  </div>
                </div>

                {/* Kitchen Demand Horizontal Bar Chart */}
                {demandCenterData?.kitchen_demand && demandCenterData.kitchen_demand.length > 0 && (
                  <div className="px-5 pt-4 pb-2">
                    <ResponsiveContainer width="100%" height={Math.max(80, demandCenterData.kitchen_demand.length * 44)}>
                      <BarChart
                        data={demandCenterData.kitchen_demand.map(k => ({
                          name: k.kitchen_name.length > 22 ? k.kitchen_name.slice(0, 22) + '...' : k.kitchen_name,
                          orders: k.order_count,
                          isMine: k.is_my_kitchen,
                        }))}
                        layout="vertical"
                        margin={{ top: 4, right: 48, left: 8, bottom: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 10, fill: '#9ca3af' }} allowDecimals={false} />
                        <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: '#6b7280' }} width={140} />
                        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                          formatter={(v: any) => [v, 'Real Orders']} />
                        <Bar dataKey="orders" name="Real Orders" radius={[0, 4, 4, 0]}>
                          {demandCenterData.kitchen_demand.map((k, idx) => (
                            <Cell key={`kd-${idx}`} fill={k.is_my_kitchen ? '#166534' : '#0369a1'} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <p className="text-[10px] text-gray-400 mt-1 pl-1">
                      <span className="inline-block w-2.5 h-2.5 rounded-sm bg-[#166534] mr-1 align-middle" />Your kitchen
                      <span className="inline-block w-2.5 h-2.5 rounded-sm bg-[#0369a1] ml-3 mr-1 align-middle" />Other kitchens
                    </p>
                  </div>
                )}

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Kitchen</th>
                        <th className="px-6 py-3">Orders</th>
                        <th className="px-6 py-3">Customers</th>
                        <th className="px-6 py-3">Revenue</th>
                        <th className="px-6 py-3">Demand Intensity</th>
                        <th className="px-6 py-3 text-right">Status &amp; Rating</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {demandCenterData?.kitchen_demand && demandCenterData.kitchen_demand.length > 0 ? (
                        demandCenterData.kitchen_demand.map((k) => (
                          <tr
                            key={k.kitchen_id}
                            className={`hover:bg-gray-50/60 transition ${k.is_my_kitchen ? 'bg-emerald-50/30' : ''}`}
                          >
                            <td className="px-6 py-4">
                              <div className="flex items-center space-x-2">
                                <span className="font-bold text-gray-900">{k.kitchen_name}</span>
                                {k.is_my_kitchen && (
                                  <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-[#166534] border border-emerald-200">
                                    YOUR KITCHEN
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-gray-400">
                                {k.city} {k.address ? `· ${k.address}` : ''}
                              </div>
                            </td>
                            <td className="px-6 py-4 font-mono font-bold text-gray-900">
                              {k.order_count}
                            </td>
                            <td className="px-6 py-4 font-mono text-gray-600">
                              {k.unique_customers}
                            </td>
                            <td className="px-6 py-4 font-mono text-gray-700 font-semibold">
                              ₹{k.revenue.toLocaleString()}
                            </td>
                            <td className="px-6 py-4">
                              <span
                                className={`px-2.5 py-0.5 rounded-full text-[10px] font-black ${
                                  k.demand_intensity === 'HIGH'
                                    ? 'bg-red-100 text-red-800'
                                    : k.demand_intensity === 'MEDIUM'
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-blue-100 text-blue-800'
                                }`}
                              >
                                {k.demand_intensity}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-right">
                              <div className="flex items-center justify-end space-x-2">
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                    k.is_open ? 'bg-emerald-100 text-[#166534]' : 'bg-gray-100 text-gray-600'
                                  }`}
                                >
                                  {k.is_open ? 'OPEN' : 'CLOSED'}
                                </span>
                                <span className="text-gray-500 font-bold text-[11px]">
                                  ★ {k.rating?.toFixed(1) || '5.0'}
                                </span>
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="px-6 py-6 text-center text-gray-400">
                            No approved KitchenVerse kitchens found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* ========================================================================= */}
              {/* FEATURE 2: GEOGRAPHIC DEMAND AREAS TABLE                                  */}
              {/* Answers: "Where are customers ordering from?"                             */}
              {/* ========================================================================= */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <div className="flex items-center space-x-2">
                      <MapPin className="w-4 h-4 text-blue-600" />
                      <h4 className="text-sm font-black text-gray-900">
                        Geographic Demand Areas (Aggregated from Customer Deliveries)
                      </h4>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800">
                        CUSTOMER-LEVEL
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      <strong>Geographic Demand = customer delivery locations.</strong> Shows where customers are ordering from, delivery density, and nearest kitchen coverage.
                    </p>
                  </div>
                  <span className="text-xs font-semibold text-gray-500">
                    {demandCenterData?.demand_areas?.length || 0} Areas
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Area Name</th>
                        <th className="px-6 py-3">Orders</th>
                        <th className="px-6 py-3">Unique Customers</th>
                        <th className="px-6 py-3">Revenue</th>
                        <th className="px-6 py-3">Intensity</th>
                        <th className="px-6 py-3">Nearest Kitchen</th>
                        <th className="px-6 py-3">Coverage Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {demandCenterData?.demand_areas && demandCenterData.demand_areas.length > 0 ? (
                        demandCenterData.demand_areas.map((area) => (
                          <tr key={area.area_name} className="hover:bg-gray-50/60 transition">
                            <td className="px-6 py-4">
                              <div className="font-bold text-gray-900">{area.area_name}</div>
                              <div className="text-[10px] text-gray-400">{area.city}</div>
                            </td>
                            <td className="px-6 py-4 font-mono font-bold text-gray-900">{area.order_count}</td>
                            <td className="px-6 py-4 font-mono text-gray-600">{(area as any).unique_customers ?? 1}</td>
                            <td className="px-6 py-4 font-mono text-gray-700">₹{area.revenue.toLocaleString()}</td>
                            <td className="px-6 py-4">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  area.demand_intensity === 'HIGH'
                                    ? 'bg-red-100 text-red-800'
                                    : area.demand_intensity === 'MEDIUM'
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-blue-100 text-blue-800'
                                }`}
                              >
                                {area.demand_intensity}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-gray-700">
                              <div className="font-semibold">{area.nearest_kitchen_name || 'None'}</div>
                              <div className="text-[10px] text-gray-400">
                                {area.nearest_kitchen_distance_km != null ? `${area.nearest_kitchen_distance_km} km` : 'N/A'} · {area.kitchens_within_3km} within 3km
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  area.coverage_gap
                                    ? 'bg-amber-100 text-amber-900 border border-amber-200'
                                    : 'bg-gray-100 text-gray-700'
                                }`}
                              >
                                {(area as any).recommendation_note || (area.coverage_gap ? 'Coverage Gap' : 'Covered')}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-6 py-6 text-center text-gray-400">
                            No customer delivery areas recorded in this timeframe.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recommended Underserved Kitchen Opportunities */}
              {demandCenterData?.recommended_areas && demandCenterData.recommended_areas.length > 0 && (
                <div className="bg-amber-50/60 rounded-2xl border border-amber-200 p-6 space-y-3">
                  <div className="flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <h4 className="text-sm font-bold text-gray-900">
                      Verified Opportunity Areas (Coverage Analysis)
                    </h4>
                  </div>
                  <p className="text-xs text-gray-600">
                    High concentration of customer orders with fewer than 2 KitchenVerse hubs within a 3 km radius:
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                    {demandCenterData.recommended_areas.map((rec) => (
                      <div key={rec.area_name} className="p-4 bg-white rounded-xl border border-amber-200 shadow-xs">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-gray-900">{rec.area_name}</span>
                          <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                            Score: {rec.opportunity_score}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {rec.order_count} real orders · Nearest kitchen {rec.nearest_kitchen_distance_km} km away ({rec.kitchens_within_3km} within 3 km)
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
