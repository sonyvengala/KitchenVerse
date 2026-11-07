import React, { useState, useEffect } from 'react';
import { adminApi, PlatformSettings } from '../../services/adminApi';

export default function AdminSettings() {
  const [settings, setSettings] = useState<PlatformSettings>({
    platform_name: 'KitchenVerse',
    support_email: 'support@kitchenverse.com',
    order_cancellation_window_minutes: 5,
    max_delivery_radius_km: 15.0,
    platform_commission_percent: 10.0,
    maintenance_mode: false,
    auto_approve_kitchens: false,
    min_order_amount: 50.0,
    delivery_base_fee: 20.0,
    delivery_per_km_fee: 8.0,
    surge_pricing_enabled: false,
    surge_multiplier: 1.0,
    platform_fee: 0.0,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getSettings();
      setSettings(data);
    } catch (err: any) {
      console.error('Failed to load settings:', err);
      setError(err?.response?.data?.detail || 'Failed to load platform settings');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setSettings((prev: PlatformSettings) => ({
      ...prev,
      [name]:
        type === 'checkbox'
          ? checked
          : type === 'number'
          ? parseFloat(value) || 0
          : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      const updated = await adminApi.updateSettings(settings);
      setSettings(updated);
      setSuccess('Platform settings saved successfully.');
    } catch (err: any) {
      console.error('Failed to update settings:', err);
      setError(err?.response?.data?.detail || 'Failed to save platform settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Platform Settings</h1>
          <p className="text-sm text-gray-500">Configure global parameters and platform-wide rules.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 text-red-700 text-sm rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border-l-4 border-green-400 p-4 text-green-700 text-sm rounded">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">Platform Name</label>
            <input
              type="text"
              name="platform_name"
              value={settings.platform_name}
              onChange={handleChange}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Support Email</label>
            <input
              type="email"
              name="support_email"
              value={settings.support_email}
              onChange={handleChange}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Cancellation Window (Minutes)
            </label>
            <input
              type="number"
              name="order_cancellation_window_minutes"
              value={settings.order_cancellation_window_minutes}
              onChange={handleChange}
              min={1}
              max={60}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Max Delivery Radius (km)
            </label>
            <input
              type="number"
              step="0.5"
              name="max_delivery_radius_km"
              value={settings.max_delivery_radius_km}
              onChange={handleChange}
              min={1}
              max={100}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Platform Commission (%)
            </label>
            <input
              type="number"
              step="0.1"
              name="platform_commission_percent"
              value={settings.platform_commission_percent}
              onChange={handleChange}
              min={0}
              max={100}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Minimum Order Amount (₹)
            </label>
            <input
              type="number"
              step="1"
              name="min_order_amount"
              value={settings.min_order_amount}
              onChange={handleChange}
              min={0}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
            />
          </div>
        </div>

        {/* Dynamic Delivery Pricing Policy */}
        <div className="pt-6 border-t border-gray-200 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Delivery Pricing & Logistics Policy</h2>
            <p className="text-xs text-gray-500">
              Configure transparent delivery partner fees based on real driving-route distance. Authoritative calculations occur on the backend.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Base Delivery Fee (₹)
              </label>
              <input
                type="number"
                step="0.5"
                name="delivery_base_fee"
                value={settings.delivery_base_fee ?? 20.0}
                onChange={handleChange}
                min={0}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
              />
              <p className="mt-1 text-xs text-gray-500">Standard initial base pickup/drop fee.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Distance Fee (₹ per km)
              </label>
              <input
                type="number"
                step="0.5"
                name="delivery_per_km_fee"
                value={settings.delivery_per_km_fee ?? 8.0}
                onChange={handleChange}
                min={0}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
              />
              <p className="mt-1 text-xs text-gray-500">Charged per kilometer of actual driving route.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Platform Convenience Fee (₹)
              </label>
              <input
                type="number"
                step="0.5"
                name="platform_fee"
                value={settings.platform_fee ?? 0.0}
                onChange={handleChange}
                min={0}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 sm:text-sm px-3 py-2 border"
              />
              <p className="mt-1 text-xs text-gray-500">Optional flat technology fee (default ₹0.00).</p>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-md p-4 space-y-3">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="surge_pricing_enabled"
                name="surge_pricing_enabled"
                checked={settings.surge_pricing_enabled ?? false}
                onChange={handleChange}
                className="h-4 w-4 text-amber-600 focus:ring-amber-500 border-gray-300 rounded"
              />
              <label htmlFor="surge_pricing_enabled" className="ml-2 block text-sm font-medium text-amber-900">
                Enable Demand Surge Pricing
              </label>
            </div>
            <p className="text-xs text-amber-700">
              Surge pricing is disabled by default to protect consumer trust. Only enable when sustained extreme weather or driver shortage policies apply.
            </p>
            {settings.surge_pricing_enabled && (
              <div className="w-48">
                <label className="block text-xs font-medium text-amber-900">Surge Multiplier</label>
                <input
                  type="number"
                  step="0.1"
                  min="1.0"
                  max="3.0"
                  name="surge_multiplier"
                  value={settings.surge_multiplier ?? 1.0}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-amber-300 shadow-sm focus:border-amber-500 focus:ring-amber-500 text-sm px-3 py-1.5 border bg-white"
                />
              </div>
            )}
          </div>
        </div>

        <div className="pt-4 border-t border-gray-200 space-y-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              id="auto_approve_kitchens"
              name="auto_approve_kitchens"
              checked={settings.auto_approve_kitchens}
              onChange={handleChange}
              className="h-4 w-4 text-orange-600 focus:ring-orange-500 border-gray-300 rounded"
            />
            <label htmlFor="auto_approve_kitchens" className="ml-2 block text-sm text-gray-900">
              Auto-approve new kitchen owner registrations
            </label>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="maintenance_mode"
              name="maintenance_mode"
              checked={settings.maintenance_mode}
              onChange={handleChange}
              className="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded"
            />
            <label htmlFor="maintenance_mode" className="ml-2 block text-sm text-red-700 font-medium">
              Maintenance Mode (temporarily disable ordering platform-wide)
            </label>
          </div>
        </div>

        <div className="flex justify-end pt-4">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex justify-center py-2 px-6 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
}
