/**
 * Admin Promotions Management Page
 * Supports:
 * - Real promotions fetched from backend DB
 * - Search by code, title, description
 * - Filter by active / inactive
 * - Create new promotion modal with validation
 * - Edit existing promotion modal
 * - Toggle Active / Inactive
 * - Delete promotion (with safe historical soft-archive on backend)
 * - Explicit "Send Campaign" button to dispatch promotional emails to real active customers
 * - Exact currency formatting (₹)
 */

import { useState, useEffect } from 'react';
import { adminApi, Promotion } from '../../services/adminApi';
import {
  Badge,
  Pagination,
  FilterSelect,
  PageHeader,
  Card,
  LoadingState,
  ErrorState,
} from '../../components/admin/AdminComponents';

export default function AdminPromotions() {
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(25);
  const [activeFilter, setActiveFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingPromo, setEditingPromo] = useState<Promotion | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [campaignDispatching, setCampaignDispatching] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    code: '',
    title: '',
    description: '',
    discount_type: 'PERCENTAGE', // PERCENTAGE or FIXED
    discount_value: 10,
    min_order_amount: 0,
    max_discount_amount: 100,
    usage_limit: 100,
    per_user_limit: 1,
    is_active: true,
    valid_from: '',
    valid_until: '',
  });

  const fetchPromotions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getPromotions({
        skip,
        limit,
        active: activeFilter === 'active' ? true : activeFilter === 'inactive' ? false : undefined,
        search: searchQuery.trim() || undefined,
      });
      setPromotions(data.promotions);
      setTotal(data.total);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.detail || 'Failed to load promotions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPromotions();
  }, [skip, activeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSkip(0);
    fetchPromotions();
  };

  const openCreateModal = () => {
    setEditingPromo(null);
    setFormData({
      code: '',
      title: '',
      description: '',
      discount_type: 'PERCENTAGE',
      discount_value: 20,
      min_order_amount: 0,
      max_discount_amount: 100,
      usage_limit: 50,
      per_user_limit: 1,
      is_active: true,
      valid_from: new Date().toISOString().split('T')[0],
      valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    });
    setIsCreateOpen(true);
  };

  const openEditModal = (p: Promotion) => {
    setEditingPromo(p);
    const isPct = p.promotion_type === 'PERCENTAGE' || (p.discount_percent && p.discount_percent > 0);
    setFormData({
      code: p.code,
      title: p.title || p.code,
      description: p.description || '',
      discount_type: isPct ? 'PERCENTAGE' : 'FIXED',
      discount_value: isPct ? (p.discount_percent || p.discount_value) : (p.discount_amount || p.discount_value),
      min_order_amount: p.min_order_amount || 0,
      max_discount_amount: p.max_discount_amount || 0,
      usage_limit: p.usage_limit || 0,
      per_user_limit: p.per_user_limit || 1,
      is_active: p.is_active,
      valid_from: p.starts_at ? p.starts_at.split('T')[0] : '',
      valid_until: p.expires_at ? p.expires_at.split('T')[0] : '',
    });
    setIsCreateOpen(true);
  };

  const handleSavePromotion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.code.trim()) {
      alert('Promotion code is required');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      const isPct = formData.discount_type === 'PERCENTAGE';
      const payload: any = {
        title: formData.title.trim() || formData.code.trim().toUpperCase(),
        description: formData.description.trim(),
        discount_percent: isPct ? Number(formData.discount_value) : 0,
        discount_amount: !isPct ? Number(formData.discount_value) : 0,
        min_order_amount: Number(formData.min_order_amount) || 0,
        max_discount_amount: isPct && Number(formData.max_discount_amount) > 0 ? Number(formData.max_discount_amount) : undefined,
        usage_limit: Number(formData.usage_limit) > 0 ? Number(formData.usage_limit) : undefined,
        per_user_limit: Number(formData.per_user_limit) > 0 ? Number(formData.per_user_limit) : 1,
        is_active: formData.is_active,
        valid_from: formData.valid_from ? new Date(formData.valid_from).toISOString() : undefined,
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : undefined,
      };

      if (editingPromo) {
        await adminApi.updatePromotion(editingPromo.id, payload);
        setActionSuccess(`Promotion '${editingPromo.code}' updated successfully.`);
      } else {
        payload.code = formData.code.trim().toUpperCase();
        await adminApi.createPromotion(payload);
        setActionSuccess(`Promotion '${payload.code}' created successfully.`);
      }

      setIsCreateOpen(false);
      fetchPromotions();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.detail || 'Failed to save promotion');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggle = async (p: Promotion) => {
    try {
      setError(null);
      const res = await adminApi.togglePromotionStatus(p.id);
      setActionSuccess(res.message || `Promotion '${p.code}' status updated.`);
      fetchPromotions();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.detail || 'Failed to toggle status');
    }
  };

  const handleDelete = async (p: Promotion) => {
    if (!window.confirm(`Are you sure you want to delete/archive promotion '${p.code}'?`)) {
      return;
    }
    try {
      setError(null);
      const res = await adminApi.deletePromotion(p.id);
      setActionSuccess(res.message || `Promotion '${p.code}' deleted.`);
      fetchPromotions();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.detail || 'Failed to delete promotion');
    }
  };

  const handleSendCampaign = async (p: Promotion) => {
    if (!p.is_active) {
      alert('Cannot send campaign for an inactive promotion. Please activate it first.');
      return;
    }
    if (!window.confirm(`Dispatch promotional campaign email for code '${p.code}' to all active real customers?`)) {
      return;
    }

    try {
      setCampaignDispatching(p.id);
      setError(null);
      const res = await adminApi.sendPromotionCampaign(p.id);
      setActionSuccess(res.message || `Campaign sent to ${res.dispatched_count} customers.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.detail || 'Failed to dispatch promotional campaign');
    } finally {
      setCampaignDispatching(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader title="Promotions & Coupons" description="Create, configure, monitor, and dispatch real promotional campaigns" />
        <button
          onClick={openCreateModal}
          className="inline-flex items-center justify-center px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg shadow-sm transition-colors"
        >
          <span className="mr-2 text-lg leading-none">+</span> Create Promotion
        </button>
      </div>

      {actionSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>✅</span>
            <p className="text-sm font-medium">{actionSuccess}</p>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-green-600 hover:text-green-800 text-sm font-bold">
            ✕
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <p className="text-sm font-medium">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800 text-sm font-bold">
            ✕
          </button>
        </div>
      )}

      <Card>
        {/* Filters and Search Bar */}
        <div className="p-4 sm:p-6 border-b border-gray-200 flex flex-col md:flex-row items-center justify-between gap-4">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 w-full md:w-80">
            <input
              type="text"
              placeholder="Search code, title..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            <button
              type="submit"
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              Search
            </button>
          </form>

          <div className="flex items-center gap-3 w-full md:w-auto">
            <FilterSelect
              value={activeFilter}
              onChange={setActiveFilter}
              options={[
                { value: 'active', label: 'Active Only' },
                { value: 'inactive', label: 'Inactive Only' },
              ]}
              placeholder="All Statuses"
            />
          </div>
        </div>

        {/* Content Table */}
        {loading && promotions.length === 0 ? (
          <LoadingState />
        ) : promotions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-5xl mb-3">🏷️</div>
            <h3 className="text-base font-semibold text-gray-900">No Promotions Found</h3>
            <p className="text-sm text-gray-500 mt-1">There are no promotions matching your current filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase tracking-wider text-xs font-semibold">
                <tr>
                  <th className="px-6 py-3">Code / Title</th>
                  <th className="px-6 py-3">Discount</th>
                  <th className="px-6 py-3">Min Order</th>
                  <th className="px-6 py-3">Usage</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Validity</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {promotions.map((p) => {
                  const isPct = p.promotion_type === 'PERCENTAGE' || (p.discount_percent && p.discount_percent > 0);
                  const discountDisplay = isPct
                    ? `${p.discount_percent || p.discount_value}% OFF`
                    : `₹${(p.discount_amount || p.discount_value).toFixed(2)} OFF`;

                  return (
                    <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-mono font-bold text-gray-900 text-base">{p.code}</div>
                        {p.title && p.title !== p.code && (
                          <div className="text-xs text-gray-500 font-sans mt-0.5">{p.title}</div>
                        )}
                        {p.description && (
                          <div className="text-xs text-gray-400 mt-0.5 max-w-xs truncate">{p.description}</div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-semibold text-orange-600">{discountDisplay}</span>
                        {p.max_discount_amount ? (
                          <div className="text-xs text-gray-500">Max ₹{p.max_discount_amount}</div>
                        ) : null}
                      </td>
                      <td className="px-6 py-4 text-gray-700">
                        {p.min_order_amount && p.min_order_amount > 0 ? `₹${p.min_order_amount.toFixed(2)}` : 'None'}
                      </td>
                      <td className="px-6 py-4 text-gray-700">
                        <div className="font-medium">
                          {p.usage_count} {p.usage_limit ? `/ ${p.usage_limit}` : 'used'}
                        </div>
                        <div className="text-xs text-gray-400">Limit: {p.per_user_limit || 1}/user</div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={p.is_active ? 'success' : 'default'}>
                          {p.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-600">
                        <div>Till: {new Date(p.expires_at).toLocaleDateString()}</div>
                        {new Date(p.expires_at) < new Date() && (
                          <span className="text-red-500 font-semibold">(Expired)</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                        <button
                          onClick={() => handleSendCampaign(p)}
                          disabled={!p.is_active || campaignDispatching === p.id}
                          className="px-2.5 py-1 text-xs font-medium rounded bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-40 transition-colors"
                          title="Dispatch email to eligible customers"
                        >
                          {campaignDispatching === p.id ? 'Sending...' : '📧 Send'}
                        </button>
                        <button
                          onClick={() => handleToggle(p)}
                          className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                            p.is_active
                              ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                              : 'bg-green-50 text-green-700 hover:bg-green-100'
                          }`}
                        >
                          {p.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          onClick={() => openEditModal(p)}
                          className="px-2.5 py-1 text-xs font-medium rounded bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(p)}
                          className="px-2.5 py-1 text-xs font-medium rounded bg-red-50 text-red-700 hover:bg-red-100 transition-colors"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>

      {/* CREATE / EDIT PROMOTION MODAL */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-lg font-bold text-gray-900">
                {editingPromo ? `Edit Promotion: ${editingPromo.code}` : 'Create New Promotion'}
              </h3>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSavePromotion} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Coupon Code *</label>
                  <input
                    type="text"
                    required
                    disabled={!!editingPromo}
                    placeholder="e.g. WELCOME_20"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-lg text-sm font-mono uppercase focus:ring-2 focus:ring-orange-500 disabled:bg-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Display Title</label>
                  <input
                    type="text"
                    placeholder="e.g. Welcome Discount"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Offer details for customers"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Discount Type</label>
                  <select
                    value={formData.discount_type}
                    onChange={(e) => setFormData({ ...formData, discount_type: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  >
                    <option value="PERCENTAGE">Percentage (%)</option>
                    <option value="FIXED">Fixed Amount (₹)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    {formData.discount_type === 'PERCENTAGE' ? 'Discount Percentage (%)' : 'Discount Amount (₹)'}
                  </label>
                  <input
                    type="number"
                    min="0"
                    max={formData.discount_type === 'PERCENTAGE' ? 100 : undefined}
                    step="0.01"
                    required
                    value={formData.discount_value}
                    onChange={(e) => setFormData({ ...formData, discount_value: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Minimum Order (₹)</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={formData.min_order_amount}
                    onChange={(e) => setFormData({ ...formData, min_order_amount: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Max Discount Cap (₹)</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    placeholder="Optional"
                    value={formData.max_discount_amount || ''}
                    onChange={(e) => setFormData({ ...formData, max_discount_amount: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Total Usage Limit</label>
                  <input
                    type="number"
                    min="1"
                    placeholder="Unlimited if empty"
                    value={formData.usage_limit || ''}
                    onChange={(e) => setFormData({ ...formData, usage_limit: parseInt(e.target.value, 10) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Per User Limit</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.per_user_limit}
                    onChange={(e) => setFormData({ ...formData, per_user_limit: parseInt(e.target.value, 10) || 1 })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Valid From</label>
                  <input
                    type="date"
                    value={formData.valid_from}
                    onChange={(e) => setFormData({ ...formData, valid_from: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Valid Until</label>
                  <input
                    type="date"
                    value={formData.valid_until}
                    onChange={(e) => setFormData({ ...formData, valid_until: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="promo_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded text-orange-600 focus:ring-orange-500"
                />
                <label htmlFor="promo_active" className="text-sm font-medium text-gray-800">
                  Promotion is Active
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving...' : editingPromo ? 'Update Promotion' : 'Create Promotion'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
