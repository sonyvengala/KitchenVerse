/**
 * Kitchen Inventory & Transaction Ledger Page
 * Complete inventory tracking with separated Restock (+ Add Stock) and Waste (Record Waste) workflows,
 * backed by an atomic transactional ledger.
 */

import { useState, useEffect } from 'react';
import kitchenApi, {
  Ingredient,
  InventoryTransaction,
  RestockInput,
  WasteRecordInput,
} from '../../services/kitchenApi';
import {
  Plus,
  RefreshCw,
  ArrowDownLeft,
  ArrowUpRight,
  Trash2,
  Sliders,
  AlertTriangle,
  RotateCcw,
  Truck,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useRealtime } from '../../context/RealtimeContext';

const getUnitOptions = (baseUnit: string = '') => {
  const norm = baseUnit.trim().toLowerCase();
  if (['kg', 'g', 'gram', 'grams', 'kilogram', 'kilograms', 'gm'].includes(norm)) {
    return ['kg', 'g', 'mg'];
  }
  if (['l', 'ml', 'liter', 'liters', 'litre', 'litres', 'ltr'].includes(norm)) {
    return ['l', 'ml'];
  }
  if (['pcs', 'pc', 'piece', 'pieces', 'unit', 'units', 'box', 'pack', 'bottle', 'can'].includes(norm)) {
    return ['pcs', 'box', 'pack', 'bottle', 'can', 'unit'];
  }
  return [baseUnit || 'unit'];
};

const getConversionRatio = (from: string, to: string): number => {
  const f = from.trim().toLowerCase();
  const t = to.trim().toLowerCase();
  if (f === t || !f || !t) return 1.0;
  if (['g', 'gram', 'grams', 'gm'].includes(f) && ['kg', 'kilogram', 'kilograms'].includes(t)) return 0.001;
  if (['kg', 'kilogram', 'kilograms'].includes(f) && ['g', 'gram', 'grams', 'gm'].includes(t)) return 1000;
  if (['mg', 'milligram'].includes(f) && ['kg', 'kilogram'].includes(t)) return 0.000001;
  if (['mg', 'milligram'].includes(f) && ['g', 'gram'].includes(t)) return 0.001;
  if (['ml', 'milliliter', 'millilitre'].includes(f) && ['l', 'liter', 'litre'].includes(t)) return 0.001;
  if (['l', 'liter', 'litre'].includes(f) && ['ml', 'milliliter', 'millilitre'].includes(t)) return 1000;
  return 1.0;
};

export default function KitchenInventory() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState<'STOCK' | 'LEDGER'>('STOCK');

  // Restock Modal
  const [isRestockOpen, setIsRestockOpen] = useState(false);
  const [restockData, setRestockData] = useState<RestockInput>({
    ingredient_id: '',
    quantity: 10,
    purchase_unit: '',
    movement_type: 'PURCHASE',
    supplier_name: '',
    total_price: undefined,
    unit_cost: undefined,
    purchase_date: new Date().toISOString().split('T')[0],
    batch_number: '',
    expiry_date: '',
    notes: '',
  });

  // Waste Modal
  const [isWasteOpen, setIsWasteOpen] = useState(false);
  const [wasteData, setWasteData] = useState<WasteRecordInput>({
    ingredient_id: '',
    quantity: 1,
    reason: 'Spoiled',
    notes: '',
  });
  const [wasteError, setWasteError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [ings, txns] = await Promise.all([
        kitchenApi.getIngredients(),
        kitchenApi.getTransactions(),
      ]);
      setIngredients(ings);
      setTransactions(txns);
      if (ings.length > 0) {
        if (!restockData.ingredient_id) {
          setRestockData((prev) => ({ ...prev, ingredient_id: ings[0].id }));
        }
        if (!wasteData.ingredient_id) {
          setWasteData((prev) => ({ ...prev, ingredient_id: ings[0].id }));
        }
      }
    } catch (err: any) {
      setError(err?.detail || 'Failed to load inventory data.');
    } finally {
      setLoading(false);
    }
  };

  const { subscribe } = useRealtime();

  useEffect(() => {
    fetchData();

    const unsubInv = subscribe('INVENTORY_UPDATED', () => {
      fetchData();
    });
    const unsubWaste = subscribe('WASTE_RECORD_CREATED', () => {
      fetchData();
    });

    return () => {
      unsubInv();
      unsubWaste();
    };
  }, [subscribe]);

  const selectedRestockIngredient = ingredients.find(
    (i) => i.id === restockData.ingredient_id
  );
  const selectedWasteIngredient = ingredients.find(
    (i) => i.id === wasteData.ingredient_id
  );

  const openRestockModal = (ing?: Ingredient) => {
    const target = ing || ingredients[0];
    if (target) {
      setRestockData({
        ingredient_id: target.id,
        quantity: 10,
        purchase_unit: target.unit,
        movement_type: 'PURCHASE',
        supplier_name: '',
        total_price: undefined,
        unit_cost: undefined,
        purchase_date: new Date().toISOString().split('T')[0],
        batch_number: '',
        expiry_date: '',
        notes: '',
      });
    }
    setIsRestockOpen(true);
  };

  const openWasteModal = (ing?: Ingredient) => {
    const target = ing || ingredients[0];
    if (target) {
      setWasteData({
        ingredient_id: target.id,
        quantity: 1,
        reason: 'Spoiled',
        notes: '',
      });
    }
    setWasteError(null);
    setIsWasteOpen(true);
  };

  const handleRestockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!restockData.ingredient_id || restockData.quantity <= 0) {
      alert('Restock quantity must be greater than 0.');
      return;
    }
    try {
      const pUnit = restockData.purchase_unit || selectedRestockIngredient?.unit;
      await kitchenApi.restockIngredient({
        ingredient_id: restockData.ingredient_id,
        quantity: Number(restockData.quantity),
        purchase_unit: pUnit,
        movement_type: restockData.movement_type || 'PURCHASE',
        supplier_name: restockData.supplier_name?.trim() || undefined,
        total_price: restockData.total_price !== undefined && !isNaN(Number(restockData.total_price))
          ? Number(restockData.total_price)
          : undefined,
        unit_cost: restockData.unit_cost !== undefined && !isNaN(Number(restockData.unit_cost))
          ? Number(restockData.unit_cost)
          : undefined,
        purchase_date: restockData.purchase_date ? new Date(restockData.purchase_date).toISOString() : undefined,
        batch_number: restockData.batch_number?.trim() || undefined,
        expiry_date: restockData.expiry_date ? new Date(restockData.expiry_date).toISOString() : undefined,
        notes: restockData.notes?.trim() || undefined,
      });
      setIsRestockOpen(false);
      setActionSuccess(
        `Successfully added ${restockData.quantity} ${pUnit || 'units'} to ${selectedRestockIngredient?.name || 'stock'}.`
      );
      setTimeout(() => setActionSuccess(null), 4000);
      await fetchData();
    } catch (err: any) {
      alert(err?.detail || 'Failed to record restock.');
    }
  };

  const handleWasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wasteData.ingredient_id || wasteData.quantity <= 0) {
      setWasteError('Waste quantity must be greater than 0.');
      return;
    }
    if (selectedWasteIngredient && wasteData.quantity > selectedWasteIngredient.current_stock) {
      setWasteError(
        `Cannot waste more than available stock (${selectedWasteIngredient.current_stock.toFixed(2)} ${selectedWasteIngredient.unit}).`
      );
      return;
    }

    try {
      await kitchenApi.recordWaste({
        ingredient_id: wasteData.ingredient_id,
        quantity: Number(wasteData.quantity),
        reason: wasteData.reason,
        notes: wasteData.notes?.trim() || undefined,
      });
      setIsWasteOpen(false);
      setActionSuccess(
        `Recorded waste of ${wasteData.quantity} ${selectedWasteIngredient?.unit || 'units'} for ${selectedWasteIngredient?.name || 'ingredient'}.`
      );
      setTimeout(() => setActionSuccess(null), 4000);
      await fetchData();
    } catch (err: any) {
      setWasteError(err?.detail || 'Failed to record waste.');
    }
  };

  const getTransactionBadge = (type: string, reason?: string | null) => {
    const upperType = (type || '').toUpperCase();
    const upperReason = (reason || '').toUpperCase();

    if (upperType === 'INWARD') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-[#166534]">
          <ArrowDownLeft className="w-3.5 h-3.5" />
          <span>RESTOCK / PURCHASE</span>
        </span>
      );
    }
    if (upperType === 'RETURN') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-800">
          <RotateCcw className="w-3.5 h-3.5" />
          <span>RETURN</span>
        </span>
      );
    }
    if (upperType === 'TRANSFER_IN') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-100 text-sky-800">
          <Truck className="w-3.5 h-3.5" />
          <span>TRANSFER IN</span>
        </span>
      );
    }
    if (upperType === 'WASTE') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800">
          <Trash2 className="w-3.5 h-3.5" />
          <span>WASTE</span>
        </span>
      );
    }
    if (upperType === 'OUTWARD_ORDER' || upperType === 'CONSUMPTION') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
          <ArrowUpRight className="w-3.5 h-3.5" />
          <span>ORDER CONSUMPTION</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-800">
        <Sliders className="w-3.5 h-3.5" />
        <span>ADJUSTMENT</span>
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header with two clearly separated actions: [+ Add Stock] and [Record Waste] */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-3xl border border-gray-200/80 shadow-xs">
        <div>
          <h1 className="text-2xl font-black text-[#172033] tracking-tight">Inventory & Ledger</h1>
          <p className="text-xs text-gray-500 mt-1">
            Real-time stock ledger with separate Add Stock (restock) and Record Waste workflows.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => openRestockModal()}
            className="flex items-center space-x-2 px-4 py-2.5 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>+ Add Stock</span>
          </button>

          <button
            onClick={() => openWasteModal()}
            className="flex items-center space-x-2 px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
          >
            <Trash2 className="w-4 h-4" />
            <span>Record Waste</span>
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center space-x-3 text-emerald-800 text-sm font-semibold animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('STOCK')}
          className={`px-4 py-2.5 text-sm font-bold rounded-t-xl transition-colors border-b-2 ${
            activeTab === 'STOCK'
              ? 'border-[#166534] text-[#166534] bg-emerald-50/50'
              : 'border-transparent text-gray-500 hover:text-gray-800'
          }`}
        >
          Current Stock Levels ({ingredients.length})
        </button>
        <button
          onClick={() => setActiveTab('LEDGER')}
          className={`px-4 py-2.5 text-sm font-bold rounded-t-xl transition-colors border-b-2 ${
            activeTab === 'LEDGER'
              ? 'border-[#166534] text-[#166534] bg-emerald-50/50'
              : 'border-transparent text-gray-500 hover:text-gray-800'
          }`}
        >
          Transaction Ledger ({transactions.length})
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center">
          <p>{error}</p>
        </div>
      ) : activeTab === 'STOCK' ? (
        /* Stock Overview Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {ingredients.map((ing) => (
            <div
              key={ing.id}
              className={`p-5 rounded-3xl border bg-white shadow-xs flex flex-col justify-between ${
                ing.is_low_stock ? 'border-amber-300 ring-2 ring-amber-100' : 'border-gray-200/80'
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <h3 className="font-bold text-base text-[#172033]">{ing.name}</h3>
                  {ing.is_low_stock ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      <span>LOW STOCK</span>
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      SUFFICIENT
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-baseline space-x-1">
                  <span className="text-3xl font-black text-[#172033]">{ing.current_stock.toFixed(2)}</span>
                  <span className="text-sm font-semibold text-gray-500 uppercase">{ing.unit}</span>
                </div>

                {/* Stock level visual bar */}
                {ing.minimum_stock_threshold > 0 && (
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-[10px] text-gray-400 font-semibold mb-1">
                      <span>Stock level</span>
                      <span>
                        {Math.round(
                          (ing.current_stock /
                            Math.max(ing.minimum_stock_threshold * 2, ing.current_stock, 1)) *
                            100
                        )}
                        %
                      </span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-1.5 rounded-full transition-all ${
                          ing.current_stock <= ing.minimum_stock_threshold
                            ? 'bg-red-500'
                            : ing.current_stock <= ing.minimum_stock_threshold * 1.5
                            ? 'bg-amber-400'
                            : 'bg-[#166534]'
                        }`}
                        style={{
                          width: `${Math.min(
                            100,
                            (ing.current_stock /
                              Math.max(ing.minimum_stock_threshold * 2, 1)) *
                              100
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="text-[10px] text-gray-400 mt-1">
                      Min threshold: {ing.minimum_stock_threshold} {ing.unit}
                    </p>
                  </div>
                )}

                <div className="mt-4 pt-3 border-t border-gray-100 grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-gray-400">Min. Alert</span>
                    <span className="font-semibold text-gray-700">{ing.minimum_stock_threshold} {ing.unit}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-gray-400">Reorder Size</span>
                    <span className="font-semibold text-gray-700">{ing.reorder_quantity} {ing.unit}</span>
                  </div>
                </div>

                <div className="mt-2 pt-2 border-t border-gray-100 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-gray-400">Unit Cost</span>
                    <span className="font-semibold text-gray-900">
                      {ing.cost_available && ing.unit_cost !== null && ing.unit_cost !== undefined ? (
                        `₹${Number(ing.unit_cost).toFixed(2)} / ${ing.unit}`
                      ) : (
                        <span className="text-gray-400 font-normal italic">Cost not set</span>
                      )}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-gray-400">Stock Value</span>
                    <span className="font-bold text-emerald-800">
                      {ing.cost_available && ing.stock_value !== null && ing.stock_value !== undefined ? (
                        `₹${Number(ing.stock_value).toFixed(2)}`
                      ) : (
                        <span className="text-gray-400 font-normal italic">Cost not set</span>
                      )}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons for this ingredient */}
              <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-gray-100">
                <button
                  onClick={() => openRestockModal(ing)}
                  className="py-2 px-3 bg-emerald-50 hover:bg-emerald-100 text-[#166534] rounded-xl text-xs font-bold transition-colors flex items-center justify-center space-x-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>+ Add Stock</span>
                </button>
                <button
                  onClick={() => openWasteModal(ing)}
                  className="py-2 px-3 bg-red-50 hover:bg-red-100 text-red-700 rounded-xl text-xs font-bold transition-colors flex items-center justify-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Record Waste</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Transaction Ledger Table */
        <div className="bg-white rounded-3xl border border-gray-200/80 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50/80 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-400">
                <tr>
                  <th className="px-6 py-4">Timestamp</th>
                  <th className="px-6 py-4">Ingredient</th>
                  <th className="px-6 py-4">Action / Movement</th>
                  <th className="px-6 py-4">Qty Changed</th>
                  <th className="px-6 py-4">Balance After</th>
                  <th className="px-6 py-4">Audit Reason / Ref</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-400">
                      No inventory transactions recorded yet.
                    </td>
                  </tr>
                ) : (
                  transactions.map((t) => {
                    const isPositive = t.quantity > 0;
                    return (
                      <tr key={t.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-4 text-xs text-gray-400 whitespace-nowrap">
                          {new Date(t.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 font-bold text-[#172033]">{t.ingredient_name || 'N/A'}</td>
                        <td className="px-6 py-4">{getTransactionBadge(t.transaction_type, t.reason)}</td>
                        <td className={`px-6 py-4 font-mono font-bold ${isPositive ? 'text-[#166534]' : 'text-red-600'}`}>
                          {isPositive ? `+${t.quantity.toFixed(2)}` : t.quantity.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 font-mono font-semibold text-gray-900">
                          {t.balance_after.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 text-xs text-gray-500">
                          {t.reason || (t.reference_order_id ? `Order #${t.reference_order_id.slice(-6)}` : 'Standard operation')}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PART 1 — RESTOCK / ADD STOCK MODAL */}
      {isRestockOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <form
            onSubmit={handleRestockSubmit}
            className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-xl space-y-4"
          >
            <div>
              <h3 className="text-lg font-black text-[#172033]">+ Add Stock / Restock</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Increases inventory and creates an atomic RESTOCK / PURCHASE ledger entry.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Ingredient</label>
              <select
                required
                value={restockData.ingredient_id}
                onChange={(e) => {
                  const newId = e.target.value;
                  const ing = ingredients.find((i) => i.id === newId);
                  setRestockData({
                    ...restockData,
                    ingredient_id: newId,
                    purchase_unit: ing ? ing.unit : restockData.purchase_unit,
                  });
                }}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
              >
                {ingredients.map((ing) => (
                  <option key={ing.id} value={ing.id}>
                    {ing.name} ({ing.unit}) — Current Stock: {ing.current_stock.toFixed(2)} {ing.unit}
                  </option>
                ))}
              </select>
            </div>

            {(() => {
              const baseUnit = selectedRestockIngredient?.unit || 'unit';
              const pUnit = restockData.purchase_unit || baseUnit;
              const ratio = getConversionRatio(pUnit, baseUnit);
              const qtyNum = Number(restockData.quantity) || 0;
              const convertedStockQty = qtyNum * ratio;
              const effectiveTotal =
                restockData.total_price !== undefined && !isNaN(Number(restockData.total_price))
                  ? Number(restockData.total_price)
                  : restockData.unit_cost !== undefined && !isNaN(Number(restockData.unit_cost))
                  ? Number(restockData.unit_cost) * qtyNum
                  : undefined;
              const effectiveBaseUnitCost =
                effectiveTotal !== undefined && convertedStockQty > 0
                  ? effectiveTotal / convertedStockQty
                  : undefined;

              return (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Purchase Qty
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="0.001"
                        required
                        value={restockData.quantity}
                        onChange={(e) =>
                          setRestockData({ ...restockData, quantity: parseFloat(e.target.value) || 0 })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-mono focus:ring-[#166534]"
                        placeholder="e.g. 10.00"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Purchase Unit
                      </label>
                      <select
                        value={pUnit}
                        onChange={(e) =>
                          setRestockData({ ...restockData, purchase_unit: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-white border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      >
                        {getUnitOptions(baseUnit).map((u) => (
                          <option key={u} value={u}>
                            {u} {u === baseUnit ? '(Base)' : ''}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Movement Type
                      </label>
                      <select
                        value={restockData.movement_type || 'PURCHASE'}
                        onChange={(e) => setRestockData({ ...restockData, movement_type: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      >
                        <option value="PURCHASE">Purchase / Restock</option>
                        <option value="RETURN">Return</option>
                        <option value="TRANSFER_IN">Transfer In</option>
                        <option value="ADJUSTMENT">Adjustment</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Total Purchase Price (₹)
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="0"
                        value={restockData.total_price !== undefined ? restockData.total_price : ''}
                        onChange={(e) => {
                          const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
                          setRestockData({
                            ...restockData,
                            total_price: val,
                            unit_cost:
                              val !== undefined && qtyNum > 0
                                ? Number((val / qtyNum).toFixed(2))
                                : restockData.unit_cost,
                          });
                        }}
                        placeholder="e.g. 500.00"
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-mono focus:ring-[#166534]"
                      />
                      <span className="text-[10px] text-gray-400 mt-0.5 block">
                        Total amount paid to supplier
                      </span>
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Unit Cost (₹/{pUnit})
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="0"
                        value={restockData.unit_cost !== undefined ? restockData.unit_cost : ''}
                        onChange={(e) => {
                          const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
                          setRestockData({
                            ...restockData,
                            unit_cost: val,
                            total_price:
                              val !== undefined && qtyNum > 0
                                ? Number((val * qtyNum).toFixed(2))
                                : restockData.total_price,
                          });
                        }}
                        placeholder="e.g. 50.00"
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-mono focus:ring-[#166534]"
                      />
                      <span className="text-[10px] text-gray-400 mt-0.5 block">
                        Per {pUnit} cost
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Supplier (Optional)
                      </label>
                      <input
                        type="text"
                        value={restockData.supplier_name || ''}
                        onChange={(e) => setRestockData({ ...restockData, supplier_name: e.target.value })}
                        placeholder="e.g. Metro Wholesale"
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Purchase Date
                      </label>
                      <input
                        type="date"
                        value={restockData.purchase_date || ''}
                        onChange={(e) => setRestockData({ ...restockData, purchase_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Batch Number (Optional)
                      </label>
                      <input
                        type="text"
                        value={restockData.batch_number || ''}
                        onChange={(e) => setRestockData({ ...restockData, batch_number: e.target.value })}
                        placeholder="e.g. BATCH-2026-A"
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                        Expiry Date (Optional)
                      </label>
                      <input
                        type="date"
                        value={restockData.expiry_date || ''}
                        onChange={(e) => setRestockData({ ...restockData, expiry_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                      Notes / Invoice Reference (Optional)
                    </label>
                    <input
                      type="text"
                      value={restockData.notes || ''}
                      onChange={(e) => setRestockData({ ...restockData, notes: e.target.value })}
                      placeholder="e.g. Weekly bulk restock, Inv #INV-9821"
                      className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                    />
                  </div>

                  {/* Dynamic Cost & Valuation Preview */}
                  <div className="p-3.5 bg-emerald-50/80 border border-emerald-200 rounded-2xl text-xs space-y-1.5">
                    <div className="flex justify-between items-center text-emerald-950 font-semibold">
                      <span>Inventory Increase:</span>
                      <span className="font-mono font-bold text-sm text-[#166534]">
                        +{convertedStockQty.toFixed(2)} {baseUnit}
                        {pUnit !== baseUnit && (
                          <span className="text-xs text-gray-500 font-normal"> ({qtyNum} {pUnit})</span>
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-emerald-950">
                      <span>Effective Unit Cost:</span>
                      <span className="font-mono font-bold">
                        {effectiveBaseUnitCost !== undefined ? (
                          `₹${effectiveBaseUnitCost.toFixed(2)} / ${baseUnit}`
                        ) : (
                          <span className="text-gray-400 font-normal italic">Cost not set</span>
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-emerald-950">
                      <span>Total Purchase Cost:</span>
                      <span className="font-mono font-bold">
                        {effectiveTotal !== undefined ? (
                          `₹${effectiveTotal.toFixed(2)}`
                        ) : (
                          <span className="text-gray-400 font-normal italic">Not recorded</span>
                        )}
                      </span>
                    </div>
                    <div className="pt-1.5 border-t border-emerald-200/70 text-[10px] text-emerald-800">
                      Inventory valuation method: <strong>Weighted-Average Cost (WAC)</strong>. Unit costs are recorded in the permanent ledger.
                    </div>
                  </div>
                </>
              );
            })()}

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsRestockOpen(false)}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-xs font-bold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2.5 bg-[#166534] text-white rounded-xl text-xs font-bold hover:bg-emerald-800 transition-colors shadow-xs"
              >
                Confirm Restock
              </button>
            </div>
          </form>
        </div>
      )}

      {/* PART 2 — RECORD WASTE MODAL */}
      {isWasteOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <form
            onSubmit={handleWasteSubmit}
            className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-xl space-y-4"
          >
            <div>
              <h3 className="text-lg font-black text-red-600">Record Ingredient Waste</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Deducts from inventory and logs a WASTE transaction in the ledger.
              </p>
            </div>

            {wasteError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-2xl flex items-center space-x-2 text-red-700 text-xs font-semibold">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{wasteError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Ingredient</label>
              <select
                required
                value={wasteData.ingredient_id}
                onChange={(e) => {
                  setWasteData({ ...wasteData, ingredient_id: e.target.value });
                  setWasteError(null);
                }}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-sm focus:ring-red-500"
              >
                {ingredients.map((ing) => (
                  <option key={ing.id} value={ing.id}>
                    {ing.name} ({ing.unit}) — Available: {ing.current_stock.toFixed(2)} {ing.unit}
                  </option>
                ))}
              </select>
            </div>

            {selectedWasteIngredient && (
              <div className="bg-red-50/70 border border-red-200/80 rounded-2xl p-3 text-xs flex items-center justify-between text-red-900">
                <span>
                  Current Stock: <strong className="font-mono text-sm">{selectedWasteIngredient.current_stock.toFixed(2)} {selectedWasteIngredient.unit}</strong>
                </span>
                <span>
                  Balance After Waste: <strong className="font-mono text-sm">
                    {Math.max(0, selectedWasteIngredient.current_stock - (Number(wasteData.quantity) || 0)).toFixed(2)} {selectedWasteIngredient.unit}
                  </strong>
                </span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                  Quantity to Waste ({selectedWasteIngredient?.unit || 'unit'})
                </label>
                <input
                  type="number"
                  step="any"
                  min="0.001"
                  max={selectedWasteIngredient?.current_stock || undefined}
                  required
                  value={wasteData.quantity}
                  onChange={(e) => {
                    setWasteData({ ...wasteData, quantity: parseFloat(e.target.value) || 0 });
                    setWasteError(null);
                  }}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm font-mono focus:ring-red-500"
                  placeholder="e.g. 1.00 or 0.25"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Wastage Reason</label>
                <select
                  required
                  value={wasteData.reason}
                  onChange={(e) => setWasteData({ ...wasteData, reason: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-sm focus:ring-red-500"
                >
                  <option value="Spoiled">Spoiled</option>
                  <option value="Damaged">Damaged</option>
                  <option value="Expired">Expired</option>
                  <option value="Preparation Error">Preparation Error</option>
                  <option value="Spilled">Spilled</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Notes (Optional)</label>
              <input
                type="text"
                value={wasteData.notes || ''}
                onChange={(e) => setWasteData({ ...wasteData, notes: e.target.value })}
                placeholder="e.g. Fridge temperature fluctuation"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-red-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsWasteOpen(false)}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-xs font-bold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2.5 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-700 transition-colors shadow-xs"
              >
                Confirm Waste
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
