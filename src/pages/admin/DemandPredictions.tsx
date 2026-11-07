/**
 * Admin Demand Forecasting & Demand Center Page
 *
 * Tab 1: Demand Center (Geographic Distribution)
 *  - Real geographic customer order distribution, delivery area concentration,
 *    kitchen-level order volume, nearest kitchen distance, and coverage gap analysis.
 *
 * Tab 2: Reference Model (Official 456K Dataset)
 *  - Official fulfillment dataset benchmark model (456,548 records, RandomForestRegressor active model),
 *    evaluation metrics, aggregated multi-week forecasts, center-level drill-down, and category benchmarks.
 */

import { useState, useEffect } from 'react';
import apiClient from '../../lib/api';
import {
  Compass,
  Brain,
  Store,
  MapPin,
  RefreshCw,
  Info,
  AlertTriangle,
  Target,
  Zap,
  BarChart3,
  Server,
  Layers,
  UtensilsCrossed,
  Award,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Scale,
} from 'lucide-react';
import DemandCenterMap, { KitchenLocation, DemandArea } from '../../components/common/DemandCenterMap';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts';

// --- Demand Center Interfaces ---
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

// --- Reference Model Interfaces ---
interface ModelMeta {
  model_type: string;
  target: string;
  train_weeks: string;
  val_weeks: string;
  train_samples: number;
  val_samples: number;
  feature_count: number;
  features?: string[];
  metrics: { mae: number; rmse: number; r2: number; mape_pct: number };
  validation_strategy: string;
  dataset_source: string;
  trained_at: string;
}

interface ForecastPrediction {
  week: number;
  week_label: string;
  predicted_orders: number;
  centers_sampled: number;
  meals_sampled: number;
}

interface AggForecast {
  model_info: { type: string; mae: number; rmse: number; r2: number; mape_pct: number };
  weeks_forecasted: number;
  baseline_week: number;
  predictions: ForecastPrediction[];
}

interface CenterInfo {
  center_id: number;
  city_code: number;
  region_code: number;
  center_type: string;
  op_area: number;
}

interface ReferenceCategoryForecast {
  category: string;
  weekly_predictions: Array<{ week: number; predicted_orders: number }>;
  avg_predicted_weekly: number;
}

interface ReferenceModelResponse {
  mode: string;
  label: string;
  disclaimer: string;
  model_name: string;
  model_metrics: { mae: number; rmse: number; r2: number; mape_pct: number };
  weeks_forecasted: number;
  validation_strategy: string;
  total_dataset_records: string;
  category_demand_forecast: ReferenceCategoryForecast[];
  available_categories: string[];
  available_cuisines: string[];
}

// --- Algorithm Comparison Interfaces ---
interface AlgorithmMetrics {
  mae: number;
  rmse: number;
  r2: number;
  mape_pct: number;
  training_time_sec: number;
}

interface AlgorithmModelData {
  algorithm: string;
  family: string;
  hyperparameters: Record<string, any>;
  metrics: AlgorithmMetrics;
  top_features?: Record<string, number>;
  description: string;
}

interface AlgorithmComparisonResponse {
  dataset_metadata: {
    dataset_name: string;
    source_files: string[];
    total_records: number;
    train_records: number;
    test_records: number;
    total_weeks: number;
    train_weeks: string;
    test_weeks: string;
    unique_centers: number;
    unique_meals: number;
    target_variable: string;
    is_customer_data: boolean;
    data_distinction_note: string;
  };
  validation_protocol: {
    strategy: string;
    leakage_prevention: string[];
    metrics_defined: Record<string, string>;
  };
  models: Record<string, AlgorithmModelData>;
  ranking: Array<{
    algorithm: string;
    mae: number;
    rmse: number;
    r2: number;
    mape_pct: number;
    training_time_sec: number;
  }>;
  best_model: {
    algorithm: string;
    selection_rationale: string;
  };
  limitations: string[];
  generated_at: string;
}

export default function AdminDemandPredictions() {
  // Exactly Two Main Tabs as required:
  // Tab 1: 'demand_center' ("Geographic Demand Center")
  // Tab 2: 'reference_model' ("Reference Model")
  const [activeTab, setActiveTab] = useState<'demand_center' | 'reference_model'>('demand_center');
  const [referenceView, setReferenceView] = useState<'projections' | 'benchmarks'>('projections');

  // --- Demand Center State ---
  const [demandCenterData, setDemandCenterData] = useState<DemandCenterResponse | null>(null);
  const [demandCenterLoading, setDemandCenterLoading] = useState<boolean>(true);
  const [demandCenterLookback, setDemandCenterLookback] = useState<number>(30);
  const [demandCenterError, setDemandCenterError] = useState<string | null>(null);

  // --- Reference Model State ---
  const [meta, setMeta] = useState<ModelMeta | null>(null);
  const [forecast, setForecast] = useState<AggForecast | null>(null);
  const [centers, setCenters] = useState<CenterInfo[]>([]);
  const [referenceData, setReferenceData] = useState<ReferenceModelResponse | null>(null);
  const [refLoading, setRefLoading] = useState<boolean>(false);
  const [refError, setRefError] = useState<string | null>(null);
  const [weeksAhead, setWeeksAhead] = useState<number>(4);
  const [selectedCenter, setSelectedCenter] = useState<number | null>(null);
  const [centerForecast, setCenterForecast] = useState<any | null>(null);
  const [centerLoading, setCenterLoading] = useState<boolean>(false);

  // --- Algorithm Comparison State ---
  const [comparisonData, setComparisonData] = useState<AlgorithmComparisonResponse | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState<boolean>(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  // Fetch Demand Center Data
  const fetchDemandCenter = async () => {
    try {
      setDemandCenterLoading(true);
      setDemandCenterError(null);
      const res = await apiClient.get<DemandCenterResponse>(
        `/api/v1/ml/demand-center?days=${demandCenterLookback}`
      );
      setDemandCenterData(res);
    } catch (err: any) {
      setDemandCenterError(err?.detail || 'Failed to load demand center intelligence.');
    } finally {
      setDemandCenterLoading(false);
    }
  };

  // Fetch Reference Model Data
  const fetchReferenceModel = async () => {
    try {
      setRefLoading(true);
      setRefError(null);
      const [metaRes, forecastRes, centersRes, refRes] = await Promise.all([
        apiClient.get<ModelMeta>('/api/v1/ml/info'),
        apiClient.get<AggForecast>(`/api/v1/ml/forecast?weeks_ahead=${weeksAhead}`),
        apiClient.get<CenterInfo[]>('/api/v1/ml/centers'),
        apiClient.get<ReferenceModelResponse>(`/api/v1/ml/reference-model?weeks_ahead=${weeksAhead}`),
      ]);
      setMeta(metaRes);
      setForecast(forecastRes);
      setCenters(centersRes);
      setReferenceData(refRes);
    } catch (err: any) {
      setRefError(err?.detail || 'Failed to load reference model predictions.');
    } finally {
      setRefLoading(false);
    }
  };

  // Center-level drill-down
  const fetchCenterForecast = async (centerId: number) => {
    try {
      setCenterLoading(true);
      const data = await apiClient.get(
        `/api/v1/ml/forecast/center/${centerId}?weeks_ahead=${weeksAhead}`
      );
      setCenterForecast(data);
    } catch (err: any) {
      console.warn('Failed to load center forecast:', err);
    } finally {
      setCenterLoading(false);
    }
  };

  // Initial load: Demand Center by default
  useEffect(() => {
    fetchDemandCenter();
  }, [demandCenterLookback]);

  // Load Reference Model when user switches to tab 2 or changes weeks ahead
  useEffect(() => {
    if (activeTab === 'reference_model') {
      fetchReferenceModel();
    }
  }, [activeTab, weeksAhead]);

  useEffect(() => {
    if (selectedCenter !== null && activeTab === 'reference_model') {
      fetchCenterForecast(selectedCenter);
    }
  }, [selectedCenter, weeksAhead, activeTab]);

  // Fetch Algorithm Comparison Data
  const fetchAlgorithmComparison = async () => {
    try {
      setComparisonLoading(true);
      setComparisonError(null);
      const res = await apiClient.get<AlgorithmComparisonResponse>('/api/v1/ml/algorithm-comparison');
      setComparisonData(res);
    } catch (err: any) {
      setComparisonError(err?.detail || 'Failed to load algorithm comparison benchmarks.');
    } finally {
      setComparisonLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'reference_model' && referenceView === 'benchmarks') {
      fetchAlgorithmComparison();
    }
  }, [activeTab, referenceView]);

  return (
    <div className="space-y-6">
      {/* Page Header & Tab Navigation */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <h1 className="text-2xl font-black text-[#172033] tracking-tight">
                Demand Forecasting & Demand Center
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-[#166534] tracking-wider uppercase">
                Admin Intelligence
              </span>
            </div>
            <p className="text-sm text-gray-500">
              Geographic customer demand concentration, kitchen hub volume, and official 456K historical fulfillment dataset benchmark model.
            </p>
          </div>

          {/* Exactly Two Tabs */}
          <div className="flex items-center gap-1.5 p-1.5 bg-gray-100 rounded-2xl border border-gray-200/80 self-start md:self-auto">
            <button
              id="admin-tab-demand-center"
              onClick={() => setActiveTab('demand_center')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === 'demand_center'
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Geographic Demand Center</span>
            </button>

            <button
              id="admin-tab-reference-model"
              onClick={() => setActiveTab('reference_model')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === 'reference_model'
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Brain className="w-3.5 h-3.5" />
              <span>Reference Model (Official 456K Dataset)</span>
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: DEMAND CENTER (GEOGRAPHIC DISTRIBUTION)                            */}
      {/* ========================================================================= */}
      {activeTab === 'demand_center' && (
        <div className="space-y-6">
          {/* Action Bar */}
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
                Visualizes where customer orders originate, delivery density, and nearest kitchen coverage gaps.
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

          {/* Interactive Geographic Map */}
          <DemandCenterMap
            kitchens={demandCenterData?.cloudkitchen_kitchens || []}
            demandAreas={demandCenterData?.demand_areas || []}
          />

          {demandCenterLoading ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
              <RefreshCw className="w-8 h-8 text-[#166534] animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-gray-700">Loading geographic demand data...</p>
            </div>
          ) : demandCenterError ? (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-800 text-sm">
              {demandCenterError}
            </div>
          ) : demandCenterData?.status === 'insufficient_data' && (!demandCenterData.kitchen_demand || demandCenterData.kitchen_demand.length === 0) ? (
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
              {demandCenterData?.threshold_rule && (
                <div className="p-4 bg-blue-50/80 rounded-xl border border-blue-200 text-xs text-blue-900 flex items-start space-x-3">
                  <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-blue-950 mb-0.5">Location Recommendation Threshold Rule</p>
                    <p className="text-blue-800 leading-relaxed">
                      {demandCenterData.threshold_rule}
                    </p>
                  </div>
                </div>
              )}

              {/* FEATURE 1: KITCHEN DEMAND TABLE + CHART */}
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
                        data={demandCenterData.kitchen_demand.map((k) => ({
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
                        <Tooltip
                          contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                          formatter={(v: any) => [v, 'Real Orders']}
                        />
                        <Bar dataKey="orders" name="Real Orders" radius={[0, 4, 4, 0]}>
                          {demandCenterData.kitchen_demand.map((_k, idx) => (
                            <Cell key={`kd-${idx}`} fill="#166534" />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
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
                          <tr key={k.kitchen_id} className="hover:bg-gray-50/60 transition">
                            <td className="px-6 py-4">
                              <div className="font-bold text-gray-900">{k.kitchen_name}</div>
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

              {/* FEATURE 2: GEOGRAPHIC DEMAND AREAS TABLE */}
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

      {/* ========================================================================= */}
      {/* TAB 2: REFERENCE MODEL (OFFICIAL 456K DATASET)                            */}
      {/* ========================================================================= */}
      {activeTab === 'reference_model' && (
        <div className="space-y-6">
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <h2 className="text-lg font-bold text-gray-900">
                  Official Dataset Reference Model (456,548 Records)
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 uppercase">
                  {meta?.model_type ? `${meta.model_type} (Active)` : 'Random Forest (Active)'}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Official fulfillment center research benchmark model · Held-out validation weeks {meta?.val_weeks || '117–145'} (zero future leakage).
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center bg-gray-100 p-1 rounded-xl border border-gray-200">
                <button
                  id="ref-subtab-projections"
                  onClick={() => setReferenceView('projections')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1.5 ${
                    referenceView === 'projections'
                      ? 'bg-white text-gray-900 shadow-xs'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}
                >
                  <Brain className="w-3.5 h-3.5" />
                  <span>Projections & Centers</span>
                </button>
                <button
                  id="ref-subtab-benchmarks"
                  onClick={() => {
                    setReferenceView('benchmarks');
                    if (!comparisonData && !comparisonLoading) {
                      fetchAlgorithmComparison();
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1.5 ${
                    referenceView === 'benchmarks'
                      ? 'bg-white text-gray-900 shadow-xs'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}
                >
                  <Scale className="w-3.5 h-3.5" />
                  <span>Algorithm Benchmark</span>
                </button>
              </div>

              {referenceView === 'projections' && (
                <>
                  <select
                    value={weeksAhead}
                    onChange={(e) => setWeeksAhead(Number(e.target.value))}
                    className="px-3 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 bg-white"
                  >
                    {[2, 4, 6, 8, 12].map((w) => (
                      <option key={w} value={w}>
                        {w} Weeks Ahead
                      </option>
                    ))}
                  </select>

                  <button
                    onClick={fetchReferenceModel}
                    disabled={refLoading}
                    className="flex items-center space-x-1.5 px-3.5 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${refLoading ? 'animate-spin' : ''}`} />
                    <span>Refresh</span>
                  </button>
                </>
              )}

              {referenceView === 'benchmarks' && (
                <button
                  onClick={fetchAlgorithmComparison}
                  disabled={comparisonLoading}
                  className="flex items-center space-x-1.5 px-3.5 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${comparisonLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh Benchmarks</span>
                </button>
              )}
            </div>
          </div>

          {referenceView === 'projections' && (
            refLoading ? (
              <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
                <RefreshCw className="w-8 h-8 text-[#166534] animate-spin mx-auto mb-3" />
                <p className="text-sm font-semibold text-gray-700">Loading reference model predictions...</p>
              </div>
          ) : refError ? (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-800 text-sm">
              {refError}
            </div>
          ) : meta && forecast ? (
            <div className="space-y-6">
              {/* Benchmark Disclaimer Banner */}
              <div className="p-4 bg-purple-50/80 rounded-2xl border border-purple-200 text-xs text-purple-900 flex items-start space-x-3 shadow-2xs">
                <Brain className="w-5 h-5 text-purple-700 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-purple-950 mb-0.5">Official Research Benchmark Notice</p>
                  <p className="text-purple-800 leading-relaxed">
                    {referenceData?.disclaimer ||
                      'This model is trained on 456,548 historical fulfillment records and serves as an official reference benchmark for multi-week demand projection patterns.'}
                  </p>
                </div>
              </div>

              {/* Model Quality Evaluation Metrics */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3 flex items-center space-x-1.5">
                  <Target className="w-4 h-4 text-gray-400" />
                  <span>Model Evaluation Metrics (Held-out weeks {meta.val_weeks} — zero future leakage)</span>
                </h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { label: 'MAE', value: `${meta.metrics.mae.toFixed(1)}`, unit: 'orders', color: 'text-emerald-700', bg: 'bg-emerald-50/50' },
                    { label: 'RMSE', value: `${meta.metrics.rmse.toFixed(1)}`, unit: 'orders', color: 'text-blue-700', bg: 'bg-blue-50/50' },
                    { label: 'R² Score', value: meta.metrics.r2.toFixed(3), unit: '', color: 'text-purple-700', bg: 'bg-purple-50/50' },
                    { label: 'MAPE', value: `${meta.metrics.mape_pct.toFixed(1)}%`, unit: '', color: 'text-orange-700', bg: 'bg-orange-50/50' },
                  ].map((m) => (
                    <div key={m.label} className={`p-5 bg-white rounded-2xl border border-gray-200/80 shadow-xs ${m.bg}`}>
                      <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1">{m.label}</p>
                      <p className={`text-3xl font-black ${m.color}`}>
                        {m.value}
                        {m.unit && <span className="text-sm font-semibold text-gray-400 ml-1">{m.unit}</span>}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Aggregated Platform Forecast Chart */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-5">
                  <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                    <BarChart3 className="w-5 h-5 text-[#166534]" />
                    <span>Aggregated Platform Demand Forecast — Next {weeksAhead} Weeks</span>
                  </h3>
                  <span className="text-xs text-gray-400">
                    Baseline Week {forecast.baseline_week} · Sampled {forecast.predictions[0]?.centers_sampled} Centers × {forecast.predictions[0]?.meals_sampled} Meals
                  </span>
                </div>

                <div className="space-y-3">
                  {(() => {
                    const maxPred = Math.max(...forecast.predictions.map((p) => p.predicted_orders), 1);
                    return forecast.predictions.map((pred) => (
                      <div key={pred.week} className="flex items-center gap-4">
                        <span className="text-xs font-semibold text-gray-500 w-20 shrink-0">
                          Week {pred.week}
                        </span>
                        <div className="flex-1 flex items-center gap-3">
                          <div
                            className="h-7 rounded-lg bg-gradient-to-r from-[#166534] to-emerald-400 transition-all shadow-2xs"
                            style={{
                              width: `${(pred.predicted_orders / maxPred) * 100}%`,
                            }}
                          />
                          <span className="text-sm font-bold text-[#172033] shrink-0 font-mono">
                            {Math.round(pred.predicted_orders).toLocaleString()} orders
                          </span>
                        </div>
                      </div>
                    ));
                  })()}
                </div>
              </div>

              {/* Center-Level Forecast Drill-Down */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
                  <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                    <Server className="w-5 h-5 text-blue-600" />
                    <span>Fulfillment Center Forecast Drill-Down</span>
                  </h3>
                  <div className="flex items-center space-x-2">
                    <select
                      value={selectedCenter ?? ''}
                      onChange={(e) => setSelectedCenter(e.target.value ? Number(e.target.value) : null)}
                      className="px-3 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 bg-white"
                    >
                      <option value="">Select a fulfillment center...</option>
                      {centers.map((c) => (
                        <option key={c.center_id} value={c.center_id}>
                          Center #{c.center_id} — {c.center_type} (City #{c.city_code}, {c.op_area} km²)
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {centerLoading && (
                  <div className="flex items-center justify-center py-8">
                    <RefreshCw className="w-6 h-6 animate-spin text-[#166534]" />
                  </div>
                )}

                {centerForecast && !centerLoading && (
                  <div className="space-y-3 pt-2 border-t border-gray-100">
                    <div className="text-xs text-gray-500 font-semibold mb-2">
                      Fulfillment Center #{centerForecast.center?.center_id} · Type: {centerForecast.center?.center_type} · City Code: #{centerForecast.center?.city_code} · Operating Area: {centerForecast.center?.op_area} km²
                    </div>
                    {(() => {
                      const maxCenterOrders = Math.max(
                        ...centerForecast.predictions.map((p: any) => p.predicted_orders),
                        1
                      );
                      return centerForecast.predictions.map((p: any) => (
                        <div key={p.week} className="flex items-center gap-4">
                          <span className="text-xs font-semibold text-gray-500 w-20 shrink-0">
                            Week {p.week}
                          </span>
                          <div className="flex-1 flex items-center gap-3">
                            <div
                              className="h-6 rounded-lg bg-blue-500/80"
                              style={{
                                width: `${(p.predicted_orders / maxCenterOrders) * 100}%`,
                              }}
                            />
                            <span className="text-sm font-bold text-[#172033] shrink-0 font-mono">
                              {Math.round(p.predicted_orders).toLocaleString()} orders
                            </span>
                          </div>
                        </div>
                      ));
                    })()}
                  </div>
                )}

                {!selectedCenter && (
                  <p className="text-xs text-gray-400 italic">
                    Select any of the 77 official fulfillment centers above to inspect center-level projected orders.
                  </p>
                )}
              </div>

              {/* Category Demand Forecast Table */}
              {referenceData?.category_demand_forecast && referenceData.category_demand_forecast.length > 0 && (
                <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                  <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                        <UtensilsCrossed className="w-4 h-4 text-amber-600" />
                        <span>Benchmark Category Demand Projections</span>
                      </h3>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Predicted demand distribution across culinary categories from the official 456K fulfillment training dataset.
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-gray-500">
                      {referenceData.category_demand_forecast.length} Categories
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                        <tr>
                          <th className="px-6 py-3">Category</th>
                          <th className="px-6 py-3">Avg Weekly Demand</th>
                          <th className="px-6 py-3">Weekly Breakdown</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {referenceData.category_demand_forecast.map((cat) => (
                          <tr key={cat.category} className="hover:bg-gray-50/60 transition">
                            <td className="px-6 py-4 font-bold text-gray-900">{cat.category}</td>
                            <td className="px-6 py-4 font-mono font-bold text-emerald-800">
                              {cat.avg_predicted_weekly.toLocaleString()} orders/wk
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2 flex-wrap">
                                {cat.weekly_predictions.map((w) => (
                                  <span
                                    key={w.week}
                                    className="px-2 py-0.5 rounded-lg bg-gray-100 text-gray-700 text-[11px] font-mono"
                                  >
                                    W{w.week}: {Math.round(w.predicted_orders)}
                                  </span>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Model Technical Details Card */}
              <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
                <div className="flex items-start space-x-3">
                  <Zap className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
                  <div className="text-xs text-gray-600 space-y-1.5 leading-relaxed">
                    <p>
                      <strong className="text-gray-900">Algorithm:</strong> {meta.model_type}
                    </p>
                    <p>
                      <strong className="text-gray-900">Training Samples:</strong>{' '}
                      {meta.train_samples.toLocaleString()} samples · Weeks {meta.train_weeks}
                    </p>
                    <p>
                      <strong className="text-gray-900">Validation Samples:</strong>{' '}
                      {meta.val_samples.toLocaleString()} samples · Weeks {meta.val_weeks} (Zero future leakage)
                    </p>
                    <p>
                      <strong className="text-gray-900">Feature Count ({meta.feature_count}):</strong>{' '}
                      {meta.features?.join(', ') || 'week, center_id, meal_id, checkout_price, base_price, category_enc, cuisine_enc, center_type_enc, etc.'}
                    </p>
                    <p>
                      <strong className="text-gray-900">Trained At:</strong>{' '}
                      {new Date(meta.trained_at).toLocaleString()}
                    </p>
                    <p>
                      <strong className="text-gray-900">Dataset Source:</strong> {meta.dataset_source}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null)}

          {/* ========================================================================= */}
          {/* REFERENCE MODEL: ALGORITHM COMPARISON BENCHMARK SUB-VIEW                  */}
          {/* ========================================================================= */}
          {referenceView === 'benchmarks' && (
            <div className="space-y-6">
          {/* Action & Info Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <h2 className="text-lg font-bold text-gray-900">
                  Demand Forecasting Algorithm Comparison
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800">
                  OFFICIAL 456K BENCHMARK
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Rigorous, leakage-free empirical comparison across 5 forecasting paradigms on 456,548 historical fulfillment records.
              </p>
            </div>

            <button
              onClick={fetchAlgorithmComparison}
              disabled={comparisonLoading}
              className="px-4 py-2 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-xl text-xs font-bold transition flex items-center space-x-2 shadow-2xs self-start sm:self-auto"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${comparisonLoading ? 'animate-spin' : ''}`} />
              <span>Re-run Comparison</span>
            </button>
          </div>

          {comparisonLoading ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
              <RefreshCw className="w-8 h-8 text-[#166534] animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-gray-700">Loading algorithm comparison benchmarks...</p>
            </div>
          ) : comparisonError ? (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-800 text-sm">
              {comparisonError}
            </div>
          ) : comparisonData ? (
            <div className="space-y-6">
              {/* Dataset Distinction Notice */}
              <div className="p-4 bg-amber-50/90 rounded-2xl border border-amber-200 text-xs text-amber-900 flex items-start space-x-3 shadow-2xs">
                <ShieldCheck className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-amber-950 mb-0.5">Official Reference Dataset — Research Benchmark Only</p>
                  <p className="text-amber-800 leading-relaxed">
                    {comparisonData.dataset_metadata.data_distinction_note} All models were trained strictly on weeks 1–116 ({comparisonData.dataset_metadata.train_records.toLocaleString()} rows) and tested on held-out weeks 117–145 ({comparisonData.dataset_metadata.test_records.toLocaleString()} rows) to guarantee zero future data leakage.
                  </p>
                </div>
              </div>

              {/* Best Model Winner Banner */}
              <div className="p-6 bg-gradient-to-r from-emerald-900 to-[#166534] rounded-2xl text-white shadow-md relative overflow-hidden">
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center space-x-2">
                      <Award className="w-6 h-6 text-amber-300" />
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-200">
                        Top-Performing Model Selection
                      </span>
                    </div>
                    <h3 className="text-2xl font-black tracking-tight text-white">
                      {comparisonData.best_model.algorithm}
                    </h3>
                    <p className="text-xs text-emerald-100 max-w-2xl leading-relaxed">
                      {comparisonData.best_model.selection_rationale}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-white/10 p-3 rounded-xl backdrop-blur-xs text-center shrink-0">
                    <div className="px-3 py-1">
                      <p className="text-[10px] uppercase font-bold text-emerald-200">Best MAE</p>
                      <p className="text-lg font-black text-white">{comparisonData.models[comparisonData.best_model.algorithm]?.metrics.mae}</p>
                    </div>
                    <div className="px-3 py-1">
                      <p className="text-[10px] uppercase font-bold text-emerald-200">Best RMSE</p>
                      <p className="text-lg font-black text-white">{comparisonData.models[comparisonData.best_model.algorithm]?.metrics.rmse}</p>
                    </div>
                    <div className="px-3 py-1">
                      <p className="text-[10px] uppercase font-bold text-emerald-200">Top R²</p>
                      <p className="text-lg font-black text-white">{comparisonData.models[comparisonData.best_model.algorithm]?.metrics.r2}</p>
                    </div>
                    <div className="px-3 py-1">
                      <p className="text-[10px] uppercase font-bold text-emerald-200">MAPE</p>
                      <p className="text-lg font-black text-white">{comparisonData.models[comparisonData.best_model.algorithm]?.metrics.mape_pct}%</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* High-level Highlights Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Lowest MAE Error</span>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                  <p className="text-2xl font-black text-gray-900">
                    {comparisonData.ranking[0].mae} <span className="text-xs font-normal text-gray-400">orders</span>
                  </p>
                  <p className="text-xs text-emerald-700 font-semibold mt-1">
                    {comparisonData.ranking[0].algorithm}
                  </p>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Lowest RMSE Penalty</span>
                    <Target className="w-4 h-4 text-blue-600" />
                  </div>
                  <p className="text-2xl font-black text-gray-900">
                    {comparisonData.ranking[0].rmse} <span className="text-xs font-normal text-gray-400">orders</span>
                  </p>
                  <p className="text-xs text-blue-700 font-semibold mt-1">
                    {comparisonData.ranking[0].algorithm}
                  </p>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Fastest Non-Linear Tree</span>
                    <Clock className="w-4 h-4 text-purple-600" />
                  </div>
                  <p className="text-2xl font-black text-gray-900">
                    {comparisonData.models['XGBoost Regressor']?.metrics.training_time_sec}s
                  </p>
                  <p className="text-xs text-purple-700 font-semibold mt-1">
                    XGBoost (Hist Tree Method, R² = 0.7262)
                  </p>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Time-Series Baseline</span>
                    <Layers className="w-4 h-4 text-orange-600" />
                  </div>
                  <p className="text-2xl font-black text-gray-900">
                    {comparisonData.models['Time-Series Baseline']?.metrics.mae} <span className="text-xs font-normal text-gray-400">MAE</span>
                  </p>
                  <p className="text-xs text-orange-700 font-semibold mt-1">
                    Rolling 4-Week Moving Average
                  </p>
                </div>
              </div>

              {/* Comprehensive Leaderboard Table */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
                <div className="p-5 border-b border-gray-200/80 bg-gray-50/60 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                      <BarChart3 className="w-4 h-4 text-[#166534]" />
                      <span>Empirical Benchmark Results (Test Weeks 117–145, N=95,200)</span>
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Evaluated on identical chronological holdout with no lookahead. All metrics computed from un-shuffled real reference records.
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    5 Approaches Compared
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-bold uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3.5">Rank</th>
                        <th className="px-6 py-3.5">Algorithm</th>
                        <th className="px-6 py-3.5">Model Family</th>
                        <th className="px-6 py-3.5">MAE (Orders)</th>
                        <th className="px-6 py-3.5">RMSE</th>
                        <th className="px-6 py-3.5">R² Score</th>
                        <th className="px-6 py-3.5">MAPE (%)</th>
                        <th className="px-6 py-3.5">Train Time</th>
                        <th className="px-6 py-3.5">Evaluation Assessment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {comparisonData.ranking.map((item, idx) => {
                        const mData = comparisonData.models[item.algorithm];
                        const isWinner = item.algorithm === comparisonData.best_model.algorithm;
                        return (
                          <tr
                            key={item.algorithm}
                            className={`transition ${isWinner ? 'bg-emerald-50/40 hover:bg-emerald-50/70 font-semibold' : 'hover:bg-gray-50/60'}`}
                          >
                            <td className="px-6 py-4 font-mono font-bold">
                              {isWinner ? (
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-400 text-amber-950 font-black text-[11px] shadow-2xs">
                                  1
                                </span>
                              ) : (
                                <span className="text-gray-400 font-semibold">{idx + 1}</span>
                              )}
                            </td>
                            <td className="px-6 py-4">
                              <span className={`font-bold ${isWinner ? 'text-emerald-950 text-sm' : 'text-gray-900'}`}>
                                {item.algorithm}
                              </span>
                              {isWinner && (
                                <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-200 text-emerald-900 uppercase tracking-wider">
                                  BEST OVERALL
                                </span>
                              )}
                            </td>
                            <td className="px-6 py-4 text-gray-500">{mData?.family || 'Baseline'}</td>
                            <td className="px-6 py-4 font-mono font-bold text-gray-900">{item.mae.toFixed(3)}</td>
                            <td className="px-6 py-4 font-mono font-semibold text-gray-700">{item.rmse.toFixed(3)}</td>
                            <td className="px-6 py-4 font-mono font-bold text-purple-700">{item.r2.toFixed(4)}</td>
                            <td className="px-6 py-4 font-mono text-gray-700">{item.mape_pct.toFixed(2)}%</td>
                            <td className="px-6 py-4 font-mono text-gray-500">{item.training_time_sec.toFixed(2)}s</td>
                            <td className="px-6 py-4 text-gray-600 max-w-xs leading-normal">
                              {item.algorithm.includes('Random Forest') && 'Top balanced precision: lowest MAE & RMSE, robust against variance spikes.'}
                              {item.algorithm.includes('XGBoost') && 'Fastest non-linear tree (6.1s), tied top R² (0.7262), higher percentage error on tail items.'}
                              {item.algorithm.includes('Gradient Boosting') && 'Production reference baseline with Huber loss; best MAPE (65.37%), solid MAE (90.398).'}
                              {item.algorithm.includes('Time-Series') && 'Outperforms Linear Regression without exogenous features, but lags during promo surges.'}
                              {item.algorithm.includes('Linear') && 'Struggles with non-linear interaction between discounts, center types, and cuisines.'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Comparative Visual Chart */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
                  <div>
                    <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                      <BarChart3 className="w-5 h-5 text-[#166534]" />
                      <span>Visual Metric Comparison Across Models</span>
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Direct side-by-side comparison of Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and Mean Absolute Percentage Error (MAPE). Lower is better.
                    </p>
                  </div>
                </div>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={comparisonData.ranking.map((r) => ({
                        name: r.algorithm.replace(' Regressor', '').replace(' (Reference)', '').replace(' Baseline', ''),
                        MAE: r.mae,
                        RMSE: r.rmse,
                        'MAPE (%)': r.mape_pct,
                      }))}
                      margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6B7280' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#6B7280' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#FFFFFF',
                          borderColor: '#E5E7EB',
                          borderRadius: '12px',
                          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                          fontSize: '12px',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                      <Bar dataKey="MAE" fill="#166534" radius={[4, 4, 0, 0]} name="MAE (Orders, Lower=Better)" />
                      <Bar dataKey="RMSE" fill="#3B82F6" radius={[4, 4, 0, 0]} name="RMSE (Lower=Better)" />
                      <Bar dataKey="MAPE (%)" fill="#F59E0B" radius={[4, 4, 0, 0]} name="MAPE (%) (Lower=Better)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Data Leakage Prevention & Methodology Card */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs space-y-4">
                  <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                    <ShieldCheck className="w-5 h-5 text-emerald-700" />
                    <span>Rigorous Data Leakage Prevention Guarantees</span>
                  </h3>
                  <ul className="text-xs text-gray-600 space-y-2.5">
                    {comparisonData.validation_protocol.leakage_prevention.map((rule, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{rule}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs space-y-4">
                  <h3 className="text-sm font-black text-gray-900 flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <span>Operational Limitations & Scientific Boundaries</span>
                  </h3>
                  <ul className="text-xs text-gray-600 space-y-2.5">
                    {comparisonData.limitations.map((lim, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0 mt-1.5" />
                        <span className="leading-relaxed">{lim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
        </div>
      )}
    </div>
  );
}
