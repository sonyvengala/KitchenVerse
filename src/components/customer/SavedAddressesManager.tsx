/**
 * SavedAddressesManager Component
 * Full-featured customer saved delivery address management:
 * - View saved addresses with Home/Work/Other labels and Default badge
 * - Add new addresses with validation and coordinates
 * - Edit existing address details, landmark, and pin
 * - Quick 1-click Set as Default
 * - Safe Delete with clear confirmation modal identifying address
 * - Preserves historical order address integrity
 */

import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Plus,
  Home,
  Building,
  Bookmark,
  Star,
  Trash2,
  Edit2,
  Check,
  AlertCircle,
  Loader2,
  X,
  Compass,
} from 'lucide-react';
import { customerApi, Address, AddressCreateInput } from '../../services/customerApi';

interface SavedAddressesManagerProps {
  onAddressUpdated?: (addresses: Address[]) => void;
  selectedAddressId?: string;
  onSelectAddress?: (addr: Address) => void;
  selectable?: boolean;
}

export default function SavedAddressesManager({
  onAddressUpdated,
  selectedAddressId,
  onSelectAddress,
  selectable = false,
}: SavedAddressesManagerProps) {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Add / Edit Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<Address | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Form fields
  const [addressLine1, setAddressLine1] = useState('');
  const [addressLine2, setAddressLine2] = useState('');
  const [city, setCity] = useState('');
  const [stateName, setStateName] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [landmark, setLandmark] = useState('');
  const [label, setLabel] = useState<string>('Home');
  const [latitude, setLatitude] = useState<string>('');
  const [longitude, setLongitude] = useState<string>('');
  const [deliveryInstructions, setDeliveryInstructions] = useState('');
  const [isDefault, setIsDefault] = useState(false);

  // Delete confirmation modal state
  const [addressToDelete, setAddressToDelete] = useState<Address | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Quick action loading state (setting default)
  const [settingDefaultId, setSettingDefaultId] = useState<string | null>(null);

  useEffect(() => {
    loadAddresses();
  }, []);

  const loadAddresses = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await customerApi.getAddresses();
      setAddresses(list || []);
      if (onAddressUpdated) {
        onAddressUpdated(list || []);
      }
    } catch (err: any) {
      setError(err?.detail || 'Failed to load saved addresses. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const openAddModal = () => {
    setEditingAddress(null);
    setAddressLine1('');
    setAddressLine2('');
    setCity('');
    setStateName('Telangana');
    setPostalCode('');
    setLandmark('');
    setLabel('Home');
    setLatitude('');
    setLongitude('');
    setDeliveryInstructions('');
    setIsDefault(addresses.length === 0);
    setModalError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (addr: Address) => {
    setEditingAddress(addr);
    setAddressLine1(addr.address_line1);
    setAddressLine2(addr.address_line2 || '');
    setCity(addr.city);
    setStateName(addr.state);
    setPostalCode(addr.postal_code);
    setLandmark(addr.landmark || '');
    setLabel(addr.label || 'Home');
    setLatitude(addr.latitude != null ? addr.latitude.toString() : '');
    setLongitude(addr.longitude != null ? addr.longitude.toString() : '');
    setDeliveryInstructions(addr.delivery_instructions || '');
    setIsDefault(addr.is_default);
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDetectCoordinates = () => {
    if (!navigator.geolocation) {
      setModalError('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setLatitude(lat.toFixed(6));
        setLongitude(lng.toFixed(6));
        try {
          const rev = await customerApi.reverseGeocode(lat, lng);
          if (rev.city && !city) setCity(rev.city);
          if (rev.formatted_address && !addressLine1) {
            setAddressLine1(rev.formatted_address.split(',')[0]);
          }
        } catch {
          // ignore reverse geocoding failure
        }
      },
      (err) => {
        setModalError(`Unable to retrieve GPS coordinates: ${err.message}`);
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  const handleSaveAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);

    if (!addressLine1.trim()) {
      setModalError('Address line 1 is required.');
      return;
    }
    if (!city.trim()) {
      setModalError('City is required.');
      return;
    }
    if (!stateName.trim()) {
      setModalError('State is required.');
      return;
    }
    if (!postalCode.trim()) {
      setModalError('Postal code is required.');
      return;
    }

    let latNum: number | undefined = undefined;
    let lngNum: number | undefined = undefined;
    if (latitude.trim() || longitude.trim()) {
      latNum = parseFloat(latitude.trim());
      lngNum = parseFloat(longitude.trim());
      if (isNaN(latNum) || latNum < -90 || latNum > 90) {
        setModalError('Latitude must be a valid number between -90 and 90.');
        return;
      }
      if (isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
        setModalError('Longitude must be a valid number between -180 and 180.');
        return;
      }
    }

    setModalLoading(true);
    try {
      const payload: AddressCreateInput = {
        address_line1: addressLine1.trim(),
        address_line2: addressLine2.trim() || undefined,
        city: city.trim(),
        state: stateName.trim(),
        postal_code: postalCode.trim(),
        landmark: landmark.trim() || undefined,
        latitude: latNum,
        longitude: lngNum,
        label: label.trim() || 'Home',
        delivery_instructions: deliveryInstructions.trim() || undefined,
        is_default: isDefault,
      };

      if (editingAddress) {
        await customerApi.updateAddress(editingAddress.id, payload);
        setActionSuccess('Address updated successfully!');
      } else {
        await customerApi.createAddress(payload);
        setActionSuccess('Address saved successfully!');
      }

      setIsModalOpen(false);
      await loadAddresses();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setModalError(err?.detail || 'Failed to save address. Please check entered fields.');
    } finally {
      setModalLoading(false);
    }
  };

  const handleSetDefault = async (addr: Address, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (addr.is_default) return;

    setSettingDefaultId(addr.id);
    try {
      await customerApi.setDefaultAddress(addr.id);
      setActionSuccess(`Default address set to "${addr.label || 'Saved Address'}"`);
      await loadAddresses();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.detail || 'Failed to update default address.');
    } finally {
      setSettingDefaultId(null);
    }
  };

  const confirmDeleteAddress = async () => {
    if (!addressToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      await customerApi.deleteAddress(addressToDelete.id);
      setAddressToDelete(null);
      setActionSuccess('Address deleted successfully!');
      await loadAddresses();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setDeleteError(err?.detail || 'Failed to delete address. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Add Button */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-gray-100">
        <div>
          <h3 className="text-base font-black text-[#172033] flex items-center gap-2">
            <MapPin className="w-5 h-5 text-[#166534]" />
            Saved Delivery Addresses
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Manage your doorstep delivery locations for faster, location-aware checkout
          </p>
        </div>
        <button
          onClick={openAddModal}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-[#166534] hover:bg-[#15803d] text-white rounded-xl text-xs font-bold transition shadow-xs"
        >
          <Plus className="w-4 h-4" /> Add New Address
        </button>
      </div>

      {/* Notifications */}
      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-bold flex items-center gap-2 animate-fade-in">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-bold flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadAddresses}
            className="text-xs underline hover:text-red-900 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Addresses Grid / List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : addresses.length === 0 ? (
        <div className="p-8 text-center bg-gray-50 rounded-2xl border border-dashed border-gray-200 space-y-3">
          <MapPin className="w-10 h-10 text-gray-300 mx-auto" />
          <p className="text-xs font-bold text-gray-600">No saved delivery addresses yet.</p>
          <p className="text-[11px] text-gray-400 max-w-sm mx-auto">
            Add your home, office, or frequently used addresses to quickly discover nearby cloud kitchens.
          </p>
          <button
            onClick={openAddModal}
            className="px-4 py-2 bg-[#166534] text-white rounded-xl text-xs font-bold hover:bg-[#15803d] transition"
          >
            + Add First Address
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {addresses.map((addr) => {
            const isSelected = selectedAddressId === addr.id;
            return (
              <div
                key={addr.id}
                onClick={() => selectable && onSelectAddress && onSelectAddress(addr)}
                className={`relative p-4 rounded-2xl border transition-all flex flex-col justify-between ${
                  selectable ? 'cursor-pointer' : ''
                } ${
                  isSelected
                    ? 'border-[#166534] bg-emerald-50/40 ring-2 ring-[#166534]'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div className="space-y-2">
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 text-gray-700">
                        {addr.label === 'Home' && <Home className="w-3 h-3 text-[#166534]" />}
                        {addr.label === 'Work' && <Building className="w-3 h-3 text-blue-600" />}
                        {addr.label === 'Other' && <Bookmark className="w-3 h-3 text-amber-600" />}
                        {addr.label || 'Address'}
                      </span>

                      {addr.is_default && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                          <Star className="w-3 h-3 fill-amber-500 text-amber-500" /> Default
                        </span>
                      )}
                    </div>

                    {/* Coordinates check */}
                    {addr.latitude != null && addr.longitude != null ? (
                      <span className="text-[10px] text-emerald-700 font-mono font-medium">
                        📍 {addr.latitude.toFixed(3)}, {addr.longitude.toFixed(3)}
                      </span>
                    ) : (
                      <span className="text-[10px] text-amber-700 font-medium">
                        ⚠️ No Pin
                      </span>
                    )}
                  </div>

                  {/* Address Body */}
                  <div>
                    <h4 className="text-xs font-black text-[#172033] line-clamp-1">
                      {addr.address_line1}
                    </h4>
                    {addr.address_line2 && (
                      <p className="text-xs text-gray-600 line-clamp-1">{addr.address_line2}</p>
                    )}
                    <p className="text-xs text-gray-500 mt-0.5">
                      {addr.city}, {addr.state} - {addr.postal_code}
                    </p>
                    {addr.landmark && (
                      <p className="text-[11px] text-gray-500 italic mt-0.5">
                        Landmark: {addr.landmark}
                      </p>
                    )}
                    {addr.delivery_instructions && (
                      <p className="text-[10px] text-gray-400 mt-1 line-clamp-1 bg-gray-50 p-1 rounded-md">
                        Note: {addr.delivery_instructions}
                      </p>
                    )}
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="pt-3 mt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                  {!addr.is_default ? (
                    <button
                      type="button"
                      disabled={settingDefaultId === addr.id}
                      onClick={(e) => handleSetDefault(addr, e)}
                      className="text-[11px] font-bold text-gray-600 hover:text-[#166534] transition flex items-center gap-1"
                    >
                      {settingDefaultId === addr.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Star className="w-3 h-3" />
                      )}
                      Set as Default
                    </button>
                  ) : (
                    <span className="text-[11px] font-bold text-emerald-700 flex items-center gap-1">
                      <Check className="w-3 h-3" /> Default Address
                    </span>
                  )}

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openEditModal(addr);
                      }}
                      className="p-1.5 text-gray-500 hover:text-[#166534] hover:bg-emerald-50 rounded-lg transition text-xs font-bold flex items-center gap-1"
                      title="Edit address"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Edit</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setAddressToDelete(addr);
                        setDeleteError(null);
                      }}
                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition text-xs font-bold flex items-center gap-1"
                      title="Delete address"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Delete</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add / Edit Address Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <MapPin className="w-5 h-5 text-[#166534]" />
                <h3 className="text-base font-black text-[#172033]">
                  {editingAddress ? 'Edit Saved Address' : 'Add New Delivery Address'}
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleSaveAddress} className="space-y-3">
              {/* Label Selector */}
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Label
                </label>
                <div className="flex items-center gap-2">
                  {(['Home', 'Work', 'Other'] as const).map((lbl) => (
                    <button
                      key={lbl}
                      type="button"
                      onClick={() => setLabel(lbl)}
                      className={`flex-1 py-1.5 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                        label === lbl
                          ? 'bg-[#166534] text-white shadow-xs'
                          : 'bg-gray-50 border border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {lbl === 'Home' && <Home className="w-3.5 h-3.5" />}
                      {lbl === 'Work' && <Building className="w-3.5 h-3.5" />}
                      {lbl === 'Other' && <Bookmark className="w-3.5 h-3.5" />}
                      {lbl}
                    </button>
                  ))}
                </div>
              </div>

              {/* Address Line 1 */}
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Line 1 (Flat, House No., Building, Street) *
                </label>
                <input
                  type="text"
                  required
                  value={addressLine1}
                  onChange={(e) => setAddressLine1(e.target.value)}
                  placeholder="e.g. Flat 302, Sai Residency, Hasanparthy"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              {/* Address Line 2 */}
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Line 2 (Area, Sector, Colony - Optional)
                </label>
                <input
                  type="text"
                  value={addressLine2}
                  onChange={(e) => setAddressLine2(e.target.value)}
                  placeholder="e.g. Near KITS Campus"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              {/* Landmark */}
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Landmark (Optional)
                </label>
                <input
                  type="text"
                  value={landmark}
                  onChange={(e) => setLandmark(e.target.value)}
                  placeholder="e.g. Opposite Water Tank"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              {/* City, State, Postal Code */}
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">City *</label>
                  <input
                    type="text"
                    required
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Warangal"
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">State *</label>
                  <input
                    type="text"
                    required
                    value={stateName}
                    onChange={(e) => setStateName(e.target.value)}
                    placeholder="Telangana"
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">PIN Code *</label>
                  <input
                    type="text"
                    required
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                    placeholder="506015"
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
              </div>

              {/* Coordinates & GPS Detection */}
              <div className="p-3 bg-gray-50 rounded-2xl border border-gray-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-700 flex items-center gap-1">
                    <Compass className="w-3.5 h-3.5 text-[#166534]" /> Coordinates (Delivery Pin)
                  </span>
                  <button
                    type="button"
                    onClick={handleDetectCoordinates}
                    className="text-[10px] font-bold text-[#166534] hover:underline flex items-center gap-1"
                  >
                    📍 Use Device GPS
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Latitude (e.g. 18.0123)"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono outline-none"
                  />
                  <input
                    type="text"
                    placeholder="Longitude (e.g. 79.5432)"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono outline-none"
                  />
                </div>
                <p className="text-[10px] text-gray-400">
                  Accurate coordinates enable verified road-distance delivery calculations and real-time kitchen discovery.
                </p>
              </div>

              {/* Delivery instructions */}
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Delivery Instructions (Optional)
                </label>
                <input
                  type="text"
                  value={deliveryInstructions}
                  onChange={(e) => setDeliveryInstructions(e.target.value)}
                  placeholder="e.g. Ring the bell twice, leave with security"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              {/* Default Address Checkbox */}
              <label className="flex items-center gap-2 pt-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="rounded text-[#166534] focus:ring-[#166534]"
                />
                <span className="text-xs font-bold text-gray-700">
                  Set as my primary default delivery address
                </span>
              </label>

              {/* Modal Buttons */}
              <div className="pt-3 flex items-center justify-end gap-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="px-5 py-2 bg-[#166534] hover:bg-[#15803d] text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
                >
                  {modalLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {editingAddress ? 'Update Address' : 'Save Address'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Address Confirmation Dialog */}
      {addressToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-10 h-10 rounded-2xl bg-red-50 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <h3 className="text-base font-black text-[#172033]">Delete Saved Address?</h3>
                <p className="text-xs text-gray-500">Please confirm address removal</p>
              </div>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-2xl border border-gray-200 text-xs space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-200 text-gray-700">
                  {addressToDelete.label || 'Address'}
                </span>
                {addressToDelete.is_default && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                    Default Address
                  </span>
                )}
              </div>
              <p className="font-bold text-gray-800">{addressToDelete.address_line1}</p>
              <p className="text-gray-500">
                {addressToDelete.city}, {addressToDelete.state} - {addressToDelete.postal_code}
              </p>
            </div>

            <p className="text-xs text-gray-600 leading-relaxed">
              Are you sure you want to delete this address?{' '}
              <strong className="text-gray-800">
                Historical orders placed with this address will preserve their full delivery address details.
              </strong>{' '}
              {addressToDelete.is_default && (
                <span className="text-[#166534] font-medium">
                  Another saved address will automatically be selected as your default.
                </span>
              )}
            </p>

            {deleteError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{deleteError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setAddressToDelete(null)}
                className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={confirmDeleteAddress}
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
              >
                {isDeleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Delete Address
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
