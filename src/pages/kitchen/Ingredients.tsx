/**
 * Kitchen Ingredients Configuration Page
 * Kitchen owners define their raw ingredients, measurement units, and reorder thresholds.
 */

import { useState, useEffect } from 'react';
import kitchenApi, { Ingredient, IngredientCreateInput } from '../../services/kitchenApi';
import {
  Layers,
  Plus,
  Edit2,
  Trash2,
  AlertTriangle,
  RefreshCw,
  Search,
  CheckCircle,
} from 'lucide-react';

export default function KitchenIngredients() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingIngredient, setEditingIngredient] = useState<Ingredient | null>(null);
  const [formData, setFormData] = useState<{
    name: string;
    unit: string;
    initial_stock: number;
    minimum_stock_threshold: number;
    reorder_quantity: number;
    unit_cost: string;
    initial_cost?: number;
    supplier_name?: string;
  }>({
    name: '',
    unit: 'kg',
    initial_stock: 10,
    minimum_stock_threshold: 2,
    reorder_quantity: 10,
    unit_cost: '',
  });

  const fetchIngredients = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await kitchenApi.getIngredients();
      setIngredients(data);
    } catch (err: any) {
      setError(err?.detail || 'Failed to load ingredients.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIngredients();
  }, []);

  const handleOpenCreate = () => {
    setEditingIngredient(null);
    setFormData({
      name: '',
      unit: 'kg',
      initial_stock: 10,
      minimum_stock_threshold: 2,
      reorder_quantity: 10,
      unit_cost: '',
      initial_cost: undefined,
      supplier_name: '',
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (ing: Ingredient) => {
    setEditingIngredient(ing);
    setFormData({
      name: ing.name,
      unit: ing.unit,
      minimum_stock_threshold: ing.minimum_stock_threshold,
      reorder_quantity: ing.reorder_quantity,
      initial_stock: ing.current_stock,
      unit_cost: ing.unit_cost !== null && ing.unit_cost !== undefined ? String(ing.unit_cost) : '',
    });
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let parsedUnitCost: number | null = null;
      if (formData.unit_cost !== '' && formData.unit_cost !== undefined && formData.unit_cost !== null) {
        const num = parseFloat(String(formData.unit_cost).trim());
        if (isNaN(num)) {
          alert('Unit cost must be a valid number.');
          return;
        }
        if (num < 0) {
          alert('Unit cost cannot be negative.');
          return;
        }
        parsedUnitCost = num;
      }

      if (editingIngredient) {
        const updated = await kitchenApi.updateIngredient(editingIngredient.id, {
          name: formData.name,
          unit: formData.unit,
          minimum_stock_threshold: formData.minimum_stock_threshold,
          reorder_quantity: formData.reorder_quantity,
          unit_cost: parsedUnitCost,
        });
        setIngredients(ingredients.map((i) => (i.id === updated.id ? updated : i)));
      } else {
        const created = await kitchenApi.createIngredient({
          name: formData.name,
          unit: formData.unit,
          initial_stock: formData.initial_stock,
          minimum_stock_threshold: formData.minimum_stock_threshold,
          reorder_quantity: formData.reorder_quantity,
          unit_cost: parsedUnitCost,
          initial_cost: formData.initial_cost,
          supplier_name: formData.supplier_name,
        });
        setIngredients([...ingredients, created]);
      }
      setIsModalOpen(false);
    } catch (err: any) {
      alert(err?.detail || 'Failed to save ingredient.');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this ingredient? It must not be part of any active recipe.')) return;
    try {
      await kitchenApi.deleteIngredient(id);
      setIngredients(ingredients.filter((i) => i.id !== id));
    } catch (err: any) {
      alert(err?.detail || 'Failed to delete ingredient.');
    }
  };

  const filtered = ingredients.filter((i) =>
    i.name.toLowerCase().includes(search.toLowerCase()) ||
    i.unit.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <h1 className="text-2xl font-black text-[#172033] tracking-tight">Ingredient Master</h1>
          <p className="text-sm text-gray-500">
            Define kitchen ingredients, units of measurement, and automated reorder alerts.
          </p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="flex items-center space-x-2 px-5 py-2.5 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-sm font-bold transition-colors shadow-xs"
        >
          <Plus className="w-4 h-4" />
          <span>Add Ingredient</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="w-5 h-5 text-gray-400 absolute left-4 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search ingredients by name or unit..."
          className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200/80 rounded-2xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center">
          <p>{error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
          <Layers className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-700">No ingredients configured</h3>
          <p className="text-sm text-gray-400 mt-1">Add your kitchen's ingredients using the button above.</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50/80 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-400">
                <tr>
                  <th className="px-6 py-4">Ingredient</th>
                  <th className="px-6 py-4">Unit</th>
                  <th className="px-6 py-4">Current Stock</th>
                  <th className="px-6 py-4">Unit Cost</th>
                  <th className="px-6 py-4">Stock Value</th>
                  <th className="px-6 py-4">Min. Threshold</th>
                  <th className="px-6 py-4">Reorder Qty</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-4 font-bold text-[#172033]">{item.name}</td>
                    <td className="px-6 py-4 text-gray-500 font-mono text-xs uppercase">{item.unit}</td>
                    <td className="px-6 py-4 font-bold text-gray-900">
                      {item.current_stock.toFixed(2)} {item.unit}
                    </td>
                    <td className="px-6 py-4">
                      {item.cost_available && item.unit_cost !== null && item.unit_cost !== undefined ? (
                        <span className="font-semibold text-gray-900">₹{item.unit_cost.toFixed(2)} <span className="text-xs text-gray-500 font-normal">/{item.unit}</span></span>
                      ) : (
                        <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">Cost not set</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {item.cost_available && item.stock_value !== null && item.stock_value !== undefined ? (
                        <span className="font-bold text-emerald-800">₹{item.stock_value.toFixed(2)}</span>
                      ) : (
                        <span className="text-xs text-gray-400 italic font-medium">Cost not set</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {item.minimum_stock_threshold.toFixed(2)} {item.unit}
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {item.reorder_quantity.toFixed(2)} {item.unit}
                    </td>
                    <td className="px-6 py-4">
                      {item.is_low_stock ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>LOW STOCK</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-[#166534]">
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Adequate</span>
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-1">
                      <button
                        onClick={() => handleOpenEdit(item)}
                        className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Edit Thresholds"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete Ingredient"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <form
            onSubmit={handleSave}
            className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4"
          >
            <h3 className="text-lg font-bold text-[#172033]">
              {editingIngredient ? 'Edit Ingredient' : 'New Ingredient'}
            </h3>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Ingredient Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g. Basmati Rice, Paneer, Chicken"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Unit of Measure</label>
              <select
                required
                value={formData.unit}
                onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
              >
                <option value="kg">kg (Kilograms)</option>
                <option value="g">g (Grams)</option>
                <option value="l">l (Liters)</option>
                <option value="ml">ml (Milliliters)</option>
                <option value="pcs">pcs (Pieces / Eggs / Buns)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                Unit Cost (₹) <span className="text-gray-400 font-normal lowercase">(per {formData.unit}, optional)</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 font-bold text-sm">₹</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.unit_cost}
                  onChange={(e) => setFormData({ ...formData, unit_cost: e.target.value })}
                  placeholder={`e.g. 220 per ${formData.unit} (leave blank if cost not set)`}
                  className="w-full pl-8 pr-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />
              </div>
              <p className="text-[11px] text-gray-400 mt-1">
                Purchase cost per 1 {formData.unit}. If unknown, leave blank and &ldquo;Cost not set&rdquo; will be displayed.
              </p>
              {formData.unit_cost !== '' && !isNaN(parseFloat(formData.unit_cost)) && parseFloat(formData.unit_cost) >= 0 && (
                <div className="mt-2 bg-emerald-50/80 border border-emerald-200/80 rounded-xl px-3 py-2 text-xs flex justify-between items-center text-emerald-900">
                  <span className="font-medium">
                    Calculated Stock Value ({editingIngredient ? `${editingIngredient.current_stock.toFixed(2)} ${formData.unit}` : `${formData.initial_stock} ${formData.unit}`}):
                  </span>
                  <span className="font-bold font-mono">
                    ₹{(Math.max(0, (editingIngredient ? editingIngredient.current_stock : formData.initial_stock) || 0) * parseFloat(formData.unit_cost)).toFixed(2)}
                  </span>
                </div>
              )}
            </div>

            {!editingIngredient && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Initial Opening Stock</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      required
                      value={formData.initial_stock}
                      onChange={(e) => setFormData({ ...formData, initial_stock: parseFloat(e.target.value) || 0 })}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                      Total Cost (₹) <span className="text-gray-400 font-normal lowercase">(optional)</span>
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={formData.initial_cost !== undefined ? formData.initial_cost : ''}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          initial_cost: e.target.value === '' ? undefined : parseFloat(e.target.value),
                        })
                      }
                      placeholder="e.g. 500"
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                    Supplier Name <span className="text-gray-400 font-normal lowercase">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={formData.supplier_name || ''}
                    onChange={(e) => setFormData({ ...formData, supplier_name: e.target.value })}
                    placeholder="e.g. Metro Cash & Carry, Local Mandi"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                  />
                </div>
              </>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Low-Stock Alert Level</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  required
                  value={formData.minimum_stock_threshold}
                  onChange={(e) => setFormData({ ...formData, minimum_stock_threshold: parseFloat(e.target.value) || 0 })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Reorder Quantity</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  required
                  value={formData.reorder_quantity}
                  onChange={(e) => setFormData({ ...formData, reorder_quantity: parseFloat(e.target.value) || 0 })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-[#166534] text-white rounded-xl text-sm font-bold hover:bg-emerald-800 transition-colors"
              >
                Save Ingredient
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
