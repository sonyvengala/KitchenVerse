/**
 * Restocking Recommendations Page
 * Forecast-Aware Inventory Replenishment Engine
 * 
 * Flow:
 * Forecasted Menu Demand -> Recipe Ingredient Requirement -> Current Inventory
 * -> Projected Stock After Forecast -> Compare with Minimum Threshold -> Restock / Sufficient
 */

import { useState, useEffect } from 'react';
import kitchenApi, { RestockingRecommendation } from '../../services/kitchenApi';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  PackagePlus,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Layers,
  ArrowRight,
} from 'lucide-react';

export default function KitchenRestocking() {
  const [recommendations, setRecommendations] = useState<RestockingRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restockingId, setRestockingId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'RESTOCK_REQUIRED' | 'SHORTAGE' | 'SUFFICIENT'>('ALL');

  const fetchRecommendations = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await kitchenApi.getRecommendations();
      setRecommendations(data);
    } catch (err: any) {
      setError(err?.detail || 'Failed to fetch restocking recommendations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const formatQty = (val?: number | null) => {
    if (val === null || val === undefined || isNaN(val)) return '0';
    return Number.isInteger(val) ? val.toString() : Number(val.toFixed(2)).toString();
  };

  const handleQuickRestock = async (rec: RestockingRecommendation) => {
    const qty = (rec.recommended_reorder_qty && rec.recommended_reorder_qty > 0)
      ? rec.recommended_reorder_qty
      : (rec.restock_needed ?? 0);
    try {
      setRestockingId(rec.ingredient_id);
      await kitchenApi.restockIngredient({
        ingredient_id: rec.ingredient_id,
        quantity: qty,
        supplier_name: 'Forecast-Driven Inward',
      });
      // Refresh list
      await fetchRecommendations();
    } catch (err: any) {
      alert(err?.detail || 'Failed to apply quick restock.');
    } finally {
      setRestockingId(null);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'SHORTAGE':
        return (
          <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-xs font-black tracking-wide flex items-center space-x-1.5 border border-red-200">
            <AlertCircle className="w-3.5 h-3.5 text-red-600" />
            <span>SHORTAGE</span>
          </span>
        );
      case 'RESTOCK REQUIRED':
        return (
          <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-black tracking-wide flex items-center space-x-1.5 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>RESTOCK REQUIRED</span>
          </span>
        );
      case 'SUFFICIENT':
      default:
        return (
          <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-black tracking-wide flex items-center space-x-1.5 border border-emerald-200">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>SUFFICIENT</span>
          </span>
        );
    }
  };

  const shortageCount = recommendations.filter((r) => r.forecast_status === 'SHORTAGE').length;
  const restockReqCount = recommendations.filter((r) => r.forecast_status === 'RESTOCK REQUIRED').length;
  const sufficientCount = recommendations.filter((r) => r.forecast_status === 'SUFFICIENT').length;

  const filteredRecommendations = recommendations.filter((r) => {
    if (activeFilter === 'SHORTAGE') return r.forecast_status === 'SHORTAGE';
    if (activeFilter === 'RESTOCK_REQUIRED') return r.forecast_status === 'RESTOCK REQUIRED';
    if (activeFilter === 'SUFFICIENT') return r.forecast_status === 'SUFFICIENT';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <Layers className="w-6 h-6 text-[#166534]" />
            <h1 className="text-2xl font-black text-[#172033] tracking-tight">Restocking Engine</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Forecast-aware inventory planning: evaluates incoming menu demand, recipe requirements, current inventory, and projected stock against safety thresholds.
          </p>
        </div>

        <button
          onClick={fetchRecommendations}
          className="flex items-center space-x-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors shadow-2xs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Analysis</span>
        </button>
      </div>

      {/* Logic Workflow Banner */}
      <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-green-50 border border-emerald-200/80 rounded-2xl p-4 text-xs text-emerald-900 shadow-2xs">
        <div className="flex items-center space-x-2 font-bold mb-1.5 text-emerald-950">
          <TrendingUp className="w-4 h-4 text-[#166534]" />
          <span>Replenishment Workflow</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 font-medium text-emerald-800">
          <span className="bg-white/80 px-2 py-0.5 rounded border border-emerald-200">Forecasted Demand</span>
          <ArrowRight className="w-3.5 h-3.5 text-emerald-600" />
          <span className="bg-white/80 px-2 py-0.5 rounded border border-emerald-200">Recipe Ingredient Usage</span>
          <ArrowRight className="w-3.5 h-3.5 text-emerald-600" />
          <span className="bg-white/80 px-2 py-0.5 rounded border border-emerald-200">Projected Stock = Current Stock − Expected Usage</span>
          <ArrowRight className="w-3.5 h-3.5 text-emerald-600" />
          <span className="bg-white/80 px-2 py-0.5 rounded border border-emerald-200">Compare with Minimum Required</span>
        </div>
      </div>

      {/* Summary KPI Badges & Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveFilter('ALL')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeFilter === 'ALL'
                ? 'bg-[#172033] text-white shadow-xs'
                : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
            }`}
          >
            All Items ({recommendations.length})
          </button>
          <button
            onClick={() => setActiveFilter('RESTOCK_REQUIRED')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeFilter === 'RESTOCK_REQUIRED'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-white text-amber-700 border border-amber-200 hover:bg-amber-50'
            }`}
          >
            Restock Required ({restockReqCount})
          </button>
          <button
            onClick={() => setActiveFilter('SHORTAGE')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeFilter === 'SHORTAGE'
                ? 'bg-red-600 text-white shadow-xs'
                : 'bg-white text-red-700 border border-red-200 hover:bg-red-50'
            }`}
          >
            Shortage ({shortageCount})
          </button>
          <button
            onClick={() => setActiveFilter('SUFFICIENT')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeFilter === 'SUFFICIENT'
                ? 'bg-[#166534] text-white shadow-xs'
                : 'bg-white text-emerald-700 border border-emerald-200 hover:bg-emerald-50'
            }`}
          >
            Sufficient ({sufficientCount})
          </button>
        </div>

        <div className="text-xs text-gray-400 font-semibold">
          Actual inventory deduction only occurs upon real order acceptance
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16 bg-white rounded-2xl border border-gray-200/80">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center">
          <p>{error}</p>
        </div>
      ) : filteredRecommendations.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-gray-800">
            {activeFilter === 'ALL'
              ? 'No Ingredients Tracked'
              : `No Ingredients with Status: ${activeFilter.replace('_', ' ')}`}
          </h3>
          <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
            {activeFilter === 'ALL'
              ? 'Add ingredients and recipe links to enable automatic restock forecasting.'
              : 'All filtered items are within safe stock thresholds.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredRecommendations.map((rec) => {
            const currentStock = rec.current_stock ?? 0;
            const expectedUsage = rec.expected_usage ?? 0;
            const projectedStock = rec.projected_stock ?? (currentStock - expectedUsage);
            const minimumRequired = rec.minimum_threshold ?? rec.minimum_stock_threshold ?? 0;
            const status = rec.forecast_status || 'SUFFICIENT';
            const isCritical = status === 'SHORTAGE';
            const isRestock = status === 'RESTOCK REQUIRED';
            const restockQty = (rec.recommended_reorder_qty && rec.recommended_reorder_qty > 0)
              ? rec.recommended_reorder_qty
              : (rec.restock_needed ?? Math.max(0, minimumRequired - projectedStock));
            const needsRestock = isCritical || isRestock || restockQty > 0;

            return (
              <div
                key={rec.ingredient_id}
                className={`p-5 bg-white rounded-2xl border transition-all shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-5 ${
                  isCritical
                    ? 'border-red-300 bg-red-50/15'
                    : isRestock
                    ? 'border-amber-200 bg-amber-50/10'
                    : 'border-gray-200/80'
                }`}
              >
                {/* Left: Ingredient Name, Status, Current | Expected | Projected, Minimum Required */}
                <div className="space-y-3 flex-1">
                  {/* Ingredient Name + Status */}
                  <div className="flex items-center space-x-2.5 flex-wrap gap-y-1">
                    <h3 className="font-bold text-lg text-[#172033]">{rec.ingredient_name}</h3>
                    <span className="text-gray-400 font-medium">—</span>
                    {getStatusBadge(status)}
                  </div>

                  {/* Current Stock | Expected Usage | Projected Stock */}
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs sm:text-sm font-semibold">
                    <div className="bg-gray-50 px-3 py-1.5 rounded-xl border border-gray-200/80 text-gray-700">
                      <span className="text-gray-500 font-normal">Current Stock: </span>
                      <span className="font-bold text-gray-900 font-mono">{formatQty(currentStock)} {rec.unit}</span>
                    </div>

                    <span className="text-gray-300 hidden sm:inline">|</span>

                    <div className="bg-blue-50/60 px-3 py-1.5 rounded-xl border border-blue-100 text-blue-900">
                      <span className="text-blue-600 font-normal">Expected Usage: </span>
                      <span className="font-bold font-mono">{formatQty(expectedUsage)} {rec.unit}</span>
                    </div>

                    <span className="text-gray-300 hidden sm:inline">|</span>

                    <div
                      className={`px-3 py-1.5 rounded-xl border font-mono ${
                        projectedStock < 0
                          ? 'bg-red-50 border-red-200 text-red-900'
                          : projectedStock < minimumRequired
                          ? 'bg-amber-50 border-amber-200 text-amber-900'
                          : 'bg-emerald-50 border-emerald-200 text-emerald-900'
                      }`}
                    >
                      <span className="font-normal opacity-80">Projected Stock: </span>
                      <span className="font-bold">{formatQty(projectedStock)} {rec.unit}</span>
                    </div>
                  </div>

                  {/* Minimum Required */}
                  <div className="text-xs text-gray-600">
                    <span className="text-gray-500 font-medium">Minimum Required: </span>
                    <span className="font-bold text-gray-800 font-mono">{formatQty(minimumRequired)} {rec.unit}</span>
                  </div>
                </div>

                {/* Right: Restock Needed + Action OR Sufficient */}
                <div className="flex flex-col items-start md:items-end justify-center gap-2 pt-3 md:pt-0 border-t md:border-t-0 border-gray-100 min-w-[180px]">
                  {needsRestock ? (
                    <div className="flex flex-col items-start md:items-end gap-2 w-full md:w-auto">
                      <div className="text-xs font-semibold text-gray-700">
                        Restock Needed: <span className="text-sm font-extrabold text-amber-900 font-mono">{formatQty(restockQty)} {rec.unit}</span>
                      </div>
                      <div className="text-[11px] text-gray-500 font-mono">
                        {rec.cost_available && rec.estimated_cost !== null && rec.estimated_cost !== undefined ? (
                          <span>Est. Reorder Cost: <strong className="text-emerald-800 font-bold">₹{Number(rec.estimated_cost).toFixed(2)}</strong> <span className="text-gray-400 font-normal">(@ ₹{Number(rec.unit_cost).toFixed(2)}/{rec.unit})</span></span>
                        ) : (
                          <span className="text-gray-400 italic">Cost not set</span>
                        )}
                      </div>

                      <button
                        onClick={() => handleQuickRestock(rec)}
                        disabled={restockingId === rec.ingredient_id}
                        className={`flex items-center justify-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs w-full md:w-auto ${
                          isCritical
                            ? 'bg-red-600 hover:bg-red-700 text-white'
                            : 'bg-amber-600 hover:bg-amber-700 text-white'
                        }`}
                      >
                        <PackagePlus className="w-3.5 h-3.5" />
                        <span>
                          {restockingId === rec.ingredient_id
                            ? 'Recording Restock...'
                            : `Reorder ${formatQty(restockQty)} ${rec.unit}`}
                        </span>
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3.5 py-2 rounded-xl">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      <span>SUFFICIENT</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
