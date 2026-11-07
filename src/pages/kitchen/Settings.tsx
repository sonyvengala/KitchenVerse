/**
 * Kitchen Settings Page
 * Manage kitchen business profile, contact details, operating hours, and geo-location map.
 */

import { useState, useEffect } from 'react';
import kitchenApi, { KitchenSettingsInput } from '../../services/kitchenApi';
import GoogleMapLocationPicker from '../../components/common/GoogleMapLocationPicker';
import {
  Store,
  Save,
  RefreshCw,
  Power,
  CheckCircle,
  MapPin,
  Clock,
  UtensilsCrossed,
  ShieldCheck,
} from 'lucide-react';
import { FssaiManagementTab } from '../../components/license/FssaiManagementTab';
import { KitchenLicense } from '../../types';
import { useRealtime } from '../../context/RealtimeContext';

export default function KitchenSettings() {
  const [activeTab, setActiveTab] = useState<'profile' | 'license'>('profile');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [license, setLicense] = useState<KitchenLicense | null>(null);
  const [formData, setFormData] = useState<KitchenSettingsInput>({
    kitchen_name: '',
    description: '',
    address: '',
    city: '',
    state: '',
    postal_code: '',
    phone: '',
    operating_hours: '10:00 AM - 11:00 PM',
    cuisine: '',
    latitude: null,
    longitude: null,
    is_open: true,
  });

  const fetchLicense = async () => {
    try {
      const lic = await kitchenApi.getLicense();
      setLicense(lic);
    } catch {
      // License might not exist yet
    }
  };

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await kitchenApi.getSettings();
      setFormData({
        kitchen_name: data.kitchen_name || '',
        description: data.description || '',
        address: data.address || '',
        city: data.city || '',
        state: data.state || '',
        postal_code: data.postal_code || '',
        phone: data.phone || '',
        operating_hours: data.operating_hours || '10:00 AM - 11:00 PM',
        cuisine: data.cuisine || '',
        latitude: typeof data.latitude === 'number' ? data.latitude : null,
        longitude: typeof data.longitude === 'number' ? data.longitude : null,
        is_open: data.is_open ?? true,
      });
      await fetchLicense();
    } catch {
      try {
        const stats = await kitchenApi.getDashboard();
        setFormData((prev) => ({
          ...prev,
          kitchen_name: stats.kitchen_name,
          is_open: stats.is_open,
        }));
        await fetchLicense();
      } catch {
        // Fallback
      }
    } finally {
      setLoading(false);
    }
  };

  const { subscribe } = useRealtime();

  useEffect(() => {
    fetchProfile();

    const unsubApproval = subscribe('KITCHEN_APPROVAL_UPDATED', () => {
      fetchProfile();
      fetchLicense();
    });
    const unsubLicense = subscribe('LICENSE_STATUS_UPDATED', () => {
      fetchProfile();
      fetchLicense();
    });

    return () => {
      unsubApproval();
      unsubLicense();
    };
  }, [subscribe]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setSuccess(false);
      await kitchenApi.updateSettings(formData);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      alert(err?.detail || 'Failed to update kitchen settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs">
        <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-gray-100">
          <div className="p-3 bg-emerald-50 text-[#166534] rounded-xl">
            <Store className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#172033]">Kitchen Settings & Location</h1>
            <p className="text-xs text-gray-500">Configure operating profile, service availability, and real GPS kitchen location.</p>
          </div>
        </div>

        {success && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 text-[#166534] rounded-xl text-sm font-semibold flex items-center space-x-2">
            <CheckCircle className="w-4 h-4" />
            <span>Kitchen settings saved successfully!</span>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center space-x-2 border-b border-gray-100 mb-6">
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`pb-3 px-3 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'profile'
                ? 'border-[#166534] text-[#166534]'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            <Store className="w-4 h-4" />
            <span>Profile & Location</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('license')}
            className={`pb-3 px-3 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'license'
                ? 'border-[#166534] text-[#166534]'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>FSSAI Food License</span>
            {license?.status && (
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                  license.status === 'VERIFIED'
                    ? 'bg-emerald-100 text-emerald-800'
                    : license.status === 'CORRECTION_REQUIRED'
                    ? 'bg-amber-100 text-amber-800'
                    : license.status === 'REJECTED' || license.status === 'EXPIRED'
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-blue-100 text-blue-800'
                }`}
              >
                {license.status}
              </span>
            )}
          </button>
        </div>

        {activeTab === 'license' ? (
          <FssaiManagementTab
            license={license}
            onLicenseUpdated={fetchLicense}
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
          {/* Operating Status Toggle */}
          <div className="p-4 bg-gray-50 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-sm font-bold text-[#172033]">Live Kitchen Status</p>
              <p className="text-xs text-gray-500">
                When closed, customers cannot place new orders to your kitchen.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, is_open: !formData.is_open })}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5 ${
                formData.is_open
                  ? 'bg-[#166534] text-white hover:bg-emerald-800'
                  : 'bg-red-600 text-white hover:bg-red-700'
              }`}
            >
              <Power className="w-3.5 h-3.5" />
              <span>{formData.is_open ? 'OPEN FOR ORDERS' : 'CLOSED'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Kitchen Name</label>
              <input
                type="text"
                required
                value={formData.kitchen_name}
                onChange={(e) => setFormData({ ...formData, kitchen_name: e.target.value })}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Cuisine / Specialties</label>
              <div className="relative">
                <input
                  type="text"
                  value={formData.cuisine || ''}
                  onChange={(e) => setFormData({ ...formData, cuisine: e.target.value })}
                  placeholder="e.g. Hyderabadi, North Indian, Biryani"
                  className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                />
                <UtensilsCrossed className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
            <textarea
              rows={2}
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="e.g. Authentic regional cloud kitchen specialising in slow-cooked dum biryanis and starters."
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Contact Phone</label>
              <input
                type="text"
                value={formData.phone || ''}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+91 98765 43210"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Operating Hours</label>
              <div className="relative">
                <input
                  type="text"
                  value={formData.operating_hours || ''}
                  onChange={(e) => setFormData({ ...formData, operating_hours: e.target.value })}
                  placeholder="10:00 AM - 11:00 PM"
                  className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                />
                <Clock className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
              </div>
            </div>
          </div>

          {/* Address Information */}
          <div className="pt-2 border-t border-gray-100">
            <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-[#166534]" />
              Address & Postal Details
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Street Address</label>
                <input
                  type="text"
                  value={formData.address || ''}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  placeholder="Plot 42, Hitec City Main Road, Cyber Towers Area"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-gray-500 mb-1">City</label>
                  <input
                    type="text"
                    value={formData.city || ''}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    placeholder="Hyderabad"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-gray-500 mb-1">State</label>
                  <input
                    type="text"
                    value={formData.state || ''}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                    placeholder="Telangana"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Postal Code</label>
                  <input
                    type="text"
                    value={formData.postal_code || ''}
                    onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
                    placeholder="500081"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-[#166534]"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Google Maps Geo-Location & Place Search */}
          <div className="pt-2 border-t border-gray-100">
            <h3 className="text-sm font-bold text-gray-900 mb-1 flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-[#166534]" />
              Kitchen Location & Real GPS Coordinates
            </h3>
            <p className="text-xs text-gray-500 mb-3">
              Search your address using Google Places, pinpoint with GPS, or adjust the marker. Customers discover your kitchen based on real geographic proximity.
            </p>

            <GoogleMapLocationPicker
              label="Kitchen Address & Place"
              initialAddress={formData.address}
              initialLatitude={formData.latitude}
              initialLongitude={formData.longitude}
              height="350px"
              onLocationSelect={(loc) => {
                setFormData((prev) => ({
                  ...prev,
                  address: loc.address || prev.address,
                  latitude: loc.latitude,
                  longitude: loc.longitude,
                }));
              }}
            />
          </div>

          <div className="pt-4 flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-2 px-6 py-2.5 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-sm font-bold transition-colors shadow-xs"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Settings'}</span>
            </button>
          </div>
        </form>
        )}
      </div>
    </div>
  );
}
