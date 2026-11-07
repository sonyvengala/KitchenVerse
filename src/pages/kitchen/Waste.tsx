/**
 * Kitchen Waste Records & Analytics Page — Feature 2.
 * Real period wastage analytics, recipe-based automatic loss calculations,
 * and immutable inventory audit ledger.
 */

import { useState, useEffect } from 'react';
import kitchenApi, {
  Ingredient,
  WasteRecord,
  WasteRecordInput,
  WasteAnalytics,
} from '../../services/kitchenApi';
import {
  Trash2,
  Plus,
  RefreshCw,
  AlertCircle,
  Calendar,
  TrendingUp,
  PieChart as PieChartIcon,
  Package,
  Layers,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from 'recharts';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function KitchenWaste() {
  const [wasteRecords, setWasteRecords] = useState<WasteRecord[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [analytics, setAnalytics] = useState<WasteAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Period Selector: default to October 2026 (matching system date) or current date
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState<number>(now.getFullYear() || 2026);
  const [selectedMonth, setSelectedMonth] = useState<number>(now.getMonth() + 1 || 10);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<WasteRecordInput>({
    ingredient_id: '',
    quantity: 1,
    reason: 'Spoiled',
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [records, ings, anData] = await Promise.all([
        kitchenApi.getWasteRecords(100),
        kitchenApi.getIngredients(),
        kitchenApi.getWasteAnalytics(selectedYear, selectedMonth),
      ]);
      setWasteRecords(records);
      setIngredients(ings);
      setAnalytics(anData);
      if (ings.length > 0 && !formData.ingredient_id) {
        setFormData((prev) => ({ ...prev, ingredient_id: ings[0].id }));
      }
    } catch (err: any) {
      setError(err?.detail || 'Failed to fetch waste records.');
    } finally {
      setLoading(false);
    }
  };

  const reloadAnalytics = async (y: number, m: number) => {
    try {
      setAnalyticsLoading(true);
      const anData = await kitchenApi.getWasteAnalytics(y, m);
      setAnalytics(anData);
    } catch (err) {
      console.error('Failed to reload waste analytics:', err);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handlePrevMonth = () => {
    let newM = selectedMonth - 1;
    let newY = selectedYear;
    if (newM < 1) {
      newM = 12;
      newY -= 1;
    }
    setSelectedMonth(newM);
    setSelectedYear(newY);
    reloadAnalytics(newY, newM);
  };

  const handleNextMonth = () => {
    let newM = selectedMonth + 1;
    let newY = selectedYear;
    if (newM > 12) {
      newM = 1;
      newY += 1;
    }
    setSelectedMonth(newM);
    setSelectedYear(newY);
    reloadAnalytics(newY, newM);
  };

  const handleRecordWaste = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.ingredient_id || formData.quantity <= 0 || !formData.reason.trim()) {
      alert('Please fill out all required waste information.');
      return;
    }
    try {
      const created = await kitchenApi.recordWaste(formData);
      setWasteRecords([created, ...wasteRecords]);
      setIsModalOpen(false);
      setFormData({
        ingredient_id: ingredients[0]?.id || '',
        quantity: 1,
        reason: 'Spoiled',
      });
      // Refresh analytics to reflect new manual waste
      reloadAnalytics(selectedYear, selectedMonth);
    } catch (err: any) {
      alert(err?.detail || 'Failed to record waste.');
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <h1 className="text-2xl font-black text-[#172033] tracking-tight">Wastage & Spoilage Analytics</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Real period wastage tracking, recipe-based automatic loss calculations, and ledger audit.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Period Selector */}
          <div className="flex items-center bg-gray-50 border border-gray-200 rounded-2xl p-1 shadow-xs">
            <button
              onClick={handlePrevMonth}
              className="p-1.5 hover:bg-white rounded-xl text-gray-600 transition"
              title="Previous Month"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <div className="px-3 text-xs font-black text-[#172033] flex items-center gap-1.5 min-w-[120px] justify-center">
              <Calendar className="w-3.5 h-3.5 text-gray-400" />
              <span>{MONTH_NAMES[selectedMonth - 1]} {selectedYear}</span>
            </div>
            <button
              onClick={handleNextMonth}
              className="p-1.5 hover:bg-white rounded-xl text-gray-600 transition"
              title="Next Month"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>Record Waste</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-8 bg-red-50 text-red-700 rounded-3xl border border-red-200 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
          <p className="font-semibold text-sm">{error}</p>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition shadow-xs"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          {/* Period Analytics KPI Cards */}
          {analytics && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs relative overflow-hidden">
                <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <span>Total Wastage Cost</span>
                  <span className="p-2 bg-red-50 text-red-600 rounded-xl">₹</span>
                </div>
                <div className="text-2xl font-black text-gray-900 tracking-tight">
                  ₹{(analytics.total_cost ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <p className="text-[11px] text-gray-400 mt-1">Calculated from actual ingredient unit costs</p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs relative overflow-hidden">
                <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <span>Wasted Orders</span>
                  <div className="p-2 bg-amber-50 text-amber-600 rounded-xl">
                    <Package className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-gray-900 tracking-tight">
                  {analytics.wasted_orders_count ?? 0}
                </div>
                <p className="text-[11px] text-gray-400 mt-1">Cancelled after preparation commenced</p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs relative overflow-hidden">
                <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <span>Wasted Portions</span>
                  <div className="p-2 bg-orange-50 text-orange-600 rounded-xl">
                    <Layers className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-gray-900 tracking-tight">
                  {analytics.total_wasted_portions ?? 0}
                </div>
                <p className="text-[11px] text-gray-400 mt-1">
                  Portions prepared but cancelled
                </p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs relative overflow-hidden">
                <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <span>Wastage Rate</span>
                  <div className="p-2 bg-purple-50 text-purple-600 rounded-xl">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-gray-900 tracking-tight">
                  {(analytics.wastage_rate ?? 0).toFixed(1)}%
                </div>
                <p className="text-[11px] text-gray-400 mt-1">
                  wasted / {analytics.prepared_food_portions ?? 0} prepared portions
                </p>
              </div>
            </div>
          )}

          {/* Wastage Breakdown Grids (by Reason, Menu Item, Ingredient) */}
          {analytics && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* Wastage by Reason */}
              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-3">
                    <h3 className="text-xs font-black text-[#172033] uppercase tracking-wider flex items-center gap-1.5">
                      <PieChartIcon className="w-3.5 h-3.5 text-gray-400" /> Wastage by Reason
                    </h3>
                    <span className="text-[10px] text-gray-400 font-bold">{analytics.by_reason?.length || 0} reasons</span>
                  </div>
                  {!analytics.by_reason || analytics.by_reason.length === 0 ? (
                    <p className="text-xs text-gray-400 py-6 text-center italic">No waste recorded this period.</p>
                  ) : (
                    <>
                      {/* Donut chart */}
                      <div className="flex justify-center mb-3">
                        <ResponsiveContainer width={160} height={160}>
                          <PieChart>
                            <Pie
                              data={analytics.by_reason.map((r, idx) => ({
                                name: r.reason,
                                value: r.count,
                                cost: r.total_cost,
                                cost_available: r.cost_available,
                                quantity: r.total_quantity,
                                fill: ['#c2410c','#b45309','#7c3aed','#0369a1','#166534','#be185d'][idx % 6],
                              }))}
                              cx="50%" cy="50%" innerRadius={42} outerRadius={68}
                              paddingAngle={3} dataKey="value"
                            >
                              {analytics.by_reason.map((_, idx) => (
                                <Cell key={`wr-${idx}`} fill={['#c2410c','#b45309','#7c3aed','#0369a1','#166534','#be185d'][idx % 6]} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                              formatter={(v: any, name: any, entry: any) => {
                                const item = entry?.payload;
                                const costText = item?.cost_available && item?.cost !== null && item?.cost !== undefined && item?.cost > 0
                                  ? `₹${Number(item.cost).toFixed(2)}`
                                  : 'Cost unavailable';
                                return [`${v} incident${v > 1 ? 's' : ''} • Qty: ${(item?.quantity || 0).toFixed(2)} • Cost: ${costText}`, name];
                              }}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="space-y-3">
                        {analytics.by_reason.map((r, idx) => {
                          const hasCost = r.cost_available && r.total_cost !== null && r.total_cost !== undefined && r.total_cost > 0;
                          return (
                            <div key={idx} className="flex items-center justify-between text-xs">
                              <div className="flex items-center space-x-2 max-w-[65%]">
                                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: ['#c2410c','#b45309','#7c3aed','#0369a1','#166534','#be185d'][idx % 6] }} />
                                <div className="space-y-0.5">
                                  <span className="font-bold text-gray-800 block truncate" title={r.reason}>{r.reason}</span>
                                  <span className="text-[10px] text-gray-400">{r.count} incident{r.count > 1 ? 's' : ''} • {r.total_quantity.toFixed(2)} units</span>
                                </div>
                              </div>
                              <div className="text-right font-mono">
                                {hasCost ? (
                                  <span className="font-bold text-red-600 block">₹{Number(r.total_cost).toFixed(2)}</span>
                                ) : (
                                  <span className="text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded font-semibold block">Cost not set</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Wastage by Menu Item */}
              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-3">
                    <h3 className="text-xs font-black text-[#172033] uppercase tracking-wider flex items-center gap-1.5">
                      <Package className="w-3.5 h-3.5 text-gray-400" /> Wastage by Menu Item
                    </h3>
                    <span className="text-[10px] text-gray-400 font-bold">{analytics.by_menu_item?.length || 0} items</span>
                  </div>
                  {!analytics.by_menu_item || analytics.by_menu_item.length === 0 ? (
                    <p className="text-xs text-gray-400 py-6 text-center italic">No order cancellations with prepared items.</p>
                  ) : (
                    <div className="space-y-3">
                      {analytics.by_menu_item.map((item, idx) => {
                        const hasCost = item.cost_available && item.estimated_cost !== null && item.estimated_cost !== undefined && item.estimated_cost > 0;
                        return (
                          <div key={idx} className="flex items-center justify-between text-xs">
                            <div className="space-y-0.5 max-w-[65%]">
                              <span className="font-bold text-gray-800 block truncate">
                                {item.menu_item_name}
                              </span>
                              <span className="text-[10px] text-gray-400">{item.portions_wasted} portion{item.portions_wasted > 1 ? 's' : ''} wasted</span>
                            </div>
                            <div className="text-right font-mono">
                              {hasCost ? (
                                <span className="font-bold text-red-600 block">₹{Number(item.estimated_cost).toFixed(2)}</span>
                              ) : (
                                <span className="text-[10px] text-gray-400 italic font-semibold block">Cost not set</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Wastage by Ingredient */}
              <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-3">
                    <h3 className="text-xs font-black text-[#172033] uppercase tracking-wider flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-gray-400" /> Wastage by Ingredient
                    </h3>
                    <span className="text-[10px] text-gray-400 font-bold">{analytics.by_ingredient?.length || 0} ingredients</span>
                  </div>
                  {!analytics.by_ingredient || analytics.by_ingredient.length === 0 ? (
                    <p className="text-xs text-gray-400 py-6 text-center italic">No ingredient losses recorded.</p>
                  ) : (
                    <div className="space-y-3">
                      {analytics.by_ingredient.map((ing, idx) => {
                        const hasCost = ing.cost_available && ing.estimated_cost !== null && ing.estimated_cost !== undefined && ing.estimated_cost > 0;
                        return (
                          <div key={idx} className="flex items-center justify-between text-xs">
                            <div className="space-y-0.5 max-w-[65%]">
                              <span className="font-bold text-gray-800 block truncate">
                                {ing.ingredient_name}
                              </span>
                              <span className="text-[10px] text-gray-400">
                                {(ing.total_quantity ?? ing.quantity ?? 0).toFixed(2)} {ing.unit}
                              </span>
                            </div>
                            <div className="text-right font-mono">
                              {hasCost ? (
                                <span className="font-bold text-red-600 block">₹{Number(ing.estimated_cost).toFixed(2)}</span>
                              ) : (
                                <div className="text-right">
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                    Cost unavailable
                                  </span>
                                  <span className="text-[9px] text-gray-400 block mt-0.5">Unit cost not configured</span>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 6-Month Wastage Trend */}
          {analytics && analytics.monthly_trend && analytics.monthly_trend.length > 0 && (
            <div className="bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <h3 className="text-xs font-black text-[#172033] uppercase tracking-wider flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-gray-400" /> 6-Month Wastage Trend (Real Records)
                </h3>
                <span className="text-[10px] text-gray-400 font-bold">Historical Audit</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {analytics.monthly_trend.map((m, idx) => {
                  const targetMonthKey = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
                  const isCurrent = m.month === targetMonthKey;
                  return (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-2xl border text-center transition ${
                        isCurrent
                          ? 'bg-red-50/50 border-red-200 ring-2 ring-red-500/20'
                          : 'bg-gray-50/60 border-gray-200/70'
                      }`}
                    >
                      <span className="text-[11px] font-black text-gray-700 block">
                        {m.month_label}
                      </span>
                      <div className="text-sm font-black text-red-600 font-mono mt-1">
                        ₹{m.total_cost.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-gray-500 mt-1 space-y-0.5">
                        <div>{m.count} records</div>
                        <div>{m.portions_wasted} portions wasted</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Detailed Waste Audit Log Table */}
          <div className="bg-white rounded-3xl border border-gray-200/80 shadow-xs overflow-hidden space-y-3 p-5">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="text-sm font-black text-[#172033]">Detailed Waste Log</h3>
                <p className="text-[11px] text-gray-400">All automatic and manually recorded wastage events</p>
              </div>
              <span className="text-xs text-gray-500 font-bold">{wasteRecords.length} records</span>
            </div>

            {wasteRecords.length === 0 ? (
              <div className="p-12 text-center space-y-2">
                <Trash2 className="w-10 h-10 text-gray-300 mx-auto" />
                <h4 className="text-sm font-bold text-gray-700">No waste recorded yet</h4>
                <p className="text-xs text-gray-400">Zero ingredient losses logged in inventory ledger.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-[10px] font-bold uppercase tracking-wider text-gray-400 border-b border-gray-100">
                    <tr>
                      <th className="px-4 py-3">Timestamp</th>
                      <th className="px-4 py-3">Source / Type</th>
                      <th className="px-4 py-3">Ingredient</th>
                      <th className="px-4 py-3">Menu Item / Order</th>
                      <th className="px-4 py-3">Quantity</th>
                      <th className="px-4 py-3">Est. Cost</th>
                      <th className="px-4 py-3">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {wasteRecords.map((w) => {
                      const isAuto = w.source_event === 'ORDER_CANCELLATION' || !!w.order_id;
                      return (
                        <tr key={w.id} className="hover:bg-gray-50/50 transition-colors">
                          <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                            {new Date(w.created_at).toLocaleString()}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {isAuto ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                Auto Cancellation
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 text-gray-700">
                                Manual Loss
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 font-bold text-[#172033]">
                            {w.ingredient_name || 'N/A'}
                          </td>
                          <td className="px-4 py-3 text-gray-600">
                            {w.menu_item_name ? (
                              <div>
                                <span className="font-semibold text-gray-800">{w.menu_item_name}</span>
                                {w.portions_wasted && (
                                  <span className="text-[10px] text-gray-400 block">({w.portions_wasted} portions)</span>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono font-bold text-red-600">
                            -{(w.quantity ?? 0).toFixed(2)} {w.unit || ''}
                          </td>
                          <td className="px-4 py-3 font-mono font-bold text-gray-900">
                            {w.cost_available && w.estimated_cost !== null && w.estimated_cost !== undefined && w.estimated_cost > 0 ? (
                              `₹${Number(w.estimated_cost).toFixed(2)}`
                            ) : (
                              <span className="text-gray-400 text-[11px] font-normal italic">Cost unavailable</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-gray-700 font-medium max-w-xs truncate" title={w.reason}>
                            {w.reason}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Record Waste Modal (Manual Log) */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <form
            onSubmit={handleRecordWaste}
            className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="text-base font-black text-gray-900">Record Ingredient Loss</h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Deducts quantity directly from live inventory and logs an immutable audit transaction to the ledger.
            </p>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Ingredient</label>
              <select
                required
                value={formData.ingredient_id}
                onChange={(e) => setFormData({ ...formData, ingredient_id: e.target.value })}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-xs focus:ring-red-500"
              >
                {ingredients.map((ing) => (
                  <option key={ing.id} value={ing.id}>
                    {ing.name} (Stock: {ing.current_stock.toFixed(2)} {ing.unit})
                  </option>
                ))}
              </select>
            </div>

            {ingredients.find((i) => i.id === formData.ingredient_id) && (
              <div className="bg-red-50 border border-red-200 rounded-2xl p-2.5 text-xs text-red-900 flex justify-between">
                <span>Current Stock: <strong>{ingredients.find((i) => i.id === formData.ingredient_id)!.current_stock.toFixed(2)} {ingredients.find((i) => i.id === formData.ingredient_id)!.unit}</strong></span>
                <span>Remaining: <strong>{Math.max(0, ingredients.find((i) => i.id === formData.ingredient_id)!.current_stock - (formData.quantity || 0)).toFixed(2)} {ingredients.find((i) => i.id === formData.ingredient_id)!.unit}</strong></span>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Quantity Lost</label>
              <input
                type="number"
                step="any"
                min="0.001"
                required
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: parseFloat(e.target.value) || 0 })}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-xs focus:ring-red-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Reason for Waste</label>
              <select
                value={formData.reason}
                onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-xs focus:ring-red-500 mb-2"
              >
                <option value="Spoiled">Spoiled</option>
                <option value="Expired">Expired</option>
                <option value="Spilled">Spilled</option>
                <option value="Preparation error">Preparation error</option>
                <option value="Damaged">Damaged</option>
                <option value="Other">Other</option>
              </select>

              {formData.reason === 'Other' && (
                <input
                  type="text"
                  placeholder="Specify other reason..."
                  required
                  onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-xl text-xs"
                />
              )}
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-xs font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-red-600 text-white rounded-xl text-xs font-bold hover:bg-red-700 transition"
              >
                Confirm Waste Record
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
