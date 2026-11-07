/**
 * Customer Portal - Checkout Page
 * Handles delivery address, contact details, payment selection, backend checkout preview,
 * authoritative promotion discount calculation, order placement, and redirection to order tracking.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useCart } from '../../context/CartContext';
import { useAuth } from '../../hooks/useAuth';
import { customerApi, Address, CheckoutPreviewResponse } from '../../services/customerApi';
import {
  MapPin,
  Phone,
  CreditCard,
  Banknote,
  ShieldCheck,
  ArrowRight,
  ArrowLeft,
  Truck,
  CheckCircle,
  AlertCircle,
  Plus,
  Home,
  Briefcase,
  Tag,
  X,
  Check,
  Edit2,
  Trash2,
  Loader2,
  Star,
} from 'lucide-react';
import CustomerLocationPicker, { CustomerLocation } from '../../components/common/CustomerLocationPicker';
import authService from '../../services/authService';

export default function Checkout() {
  const { items, kitchenId, clearCart, subtotal, appliedPromoCode, setAppliedPromoCode } = useCart();
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string>('');
  const [showNewAddress, setShowNewAddress] = useState(false);
  
  // New address form
  const [newAddressLine1, setNewAddressLine1] = useState('');
  const [newCity, setNewCity] = useState('');
  const [newState, setNewState] = useState('');
  const [newPostalCode, setNewPostalCode] = useState('');
  const [newLabel, setNewLabel] = useState<'Home' | 'Work' | 'Other'>('Home');
  const [newLandmark, setNewLandmark] = useState('');
  const [newLatitude, setNewLatitude] = useState<number | null>(null);
  const [newLongitude, setNewLongitude] = useState<number | null>(null);

  const [contactPhone, setContactPhone] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'CASH_ON_DELIVERY' | 'UPI'>('CASH_ON_DELIVERY');
  const [specialInstructions, setSpecialInstructions] = useState('');
  
  const [preview, setPreview] = useState<CheckoutPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [orderError, setOrderError] = useState('');
  const [orderPlaced, setOrderPlaced] = useState(false);
  const [placedOrderId, setPlacedOrderId] = useState<string | null>(null);

  // Email verification modal in Checkout
  const [showUnverifiedModal, setShowUnverifiedModal] = useState(false);
  const [unverifiedResendStatus, setUnverifiedResendStatus] = useState('');
  const [unverifiedCooldown, setUnverifiedCooldown] = useState(0);
  const [resendingVerification, setResendingVerification] = useState(false);

  // Delivery Location Confirmation modal
  const [showLocationConfirmModal, setShowLocationConfirmModal] = useState(false);
  const [confirmPickerLoc, setConfirmPickerLoc] = useState<CustomerLocation | null>(null);

  // Coupon state in Checkout
  const [promoInput, setPromoInput] = useState(appliedPromoCode || '');
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState('');
  const [promoSuccess, setPromoSuccess] = useState('');

  // Delete address confirmation state
  const [addressToDelete, setAddressToDelete] = useState<Address | null>(null);
  const [isDeletingAddress, setIsDeletingAddress] = useState(false);
  const [deleteAddressError, setDeleteAddressError] = useState<string | null>(null);

  // Edit address state
  const [editingAddress, setEditingAddress] = useState<Address | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editLine1, setEditLine1] = useState('');
  const [editLine2, setEditLine2] = useState('');
  const [editCity, setEditCity] = useState('');
  const [editState, setEditState] = useState('');
  const [editPostalCode, setEditPostalCode] = useState('');
  const [editLandmark, setEditLandmark] = useState('');
  const [editLabel, setEditLabel] = useState<string>('Home');
  const [editLatitude, setEditLatitude] = useState<string>('');
  const [editLongitude, setEditLongitude] = useState<string>('');
  const [editDeliveryInstructions, setEditDeliveryInstructions] = useState('');
  const [editIsDefault, setEditIsDefault] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const handleDeleteAddress = async () => {
    if (!addressToDelete) return;
    setIsDeletingAddress(true);
    setDeleteAddressError(null);
    try {
      const res = await customerApi.deleteAddress(addressToDelete.id);
      const list = await customerApi.getAddresses();
      setAddresses(list || []);
      if (selectedAddressId === addressToDelete.id) {
        if (res.new_default_id) {
          setSelectedAddressId(res.new_default_id);
        } else if (list && list.length > 0) {
          setSelectedAddressId(list[0].id);
        } else {
          setSelectedAddressId('');
          setShowNewAddress(true);
        }
      }
      setAddressToDelete(null);
    } catch (err: any) {
      setDeleteAddressError(err?.detail || 'Failed to delete address.');
    } finally {
      setIsDeletingAddress(false);
    }
  };

  const openEditModal = (addr: Address, e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setEditingAddress(addr);
    setEditLine1(addr.address_line1);
    setEditLine2(addr.address_line2 || '');
    setEditCity(addr.city);
    setEditState(addr.state);
    setEditPostalCode(addr.postal_code);
    setEditLandmark(addr.landmark || '');
    setEditLabel(addr.label || 'Home');
    setEditLatitude(addr.latitude != null ? addr.latitude.toString() : '');
    setEditLongitude(addr.longitude != null ? addr.longitude.toString() : '');
    setEditDeliveryInstructions(addr.delivery_instructions || '');
    setEditIsDefault(addr.is_default);
    setEditError(null);
    setIsEditModalOpen(true);
  };

  const handleSaveEditAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAddress) return;
    setEditError(null);

    let latNum: number | undefined = undefined;
    let lngNum: number | undefined = undefined;
    if (editLatitude.trim() || editLongitude.trim()) {
      latNum = parseFloat(editLatitude.trim());
      lngNum = parseFloat(editLongitude.trim());
      if (isNaN(latNum) || latNum < -90 || latNum > 90) {
        setEditError('Latitude must be between -90 and 90');
        return;
      }
      if (isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
        setEditError('Longitude must be between -180 and 180');
        return;
      }
    }

    setEditLoading(true);
    try {
      const updated = await customerApi.updateAddress(editingAddress.id, {
        address_line1: editLine1.trim(),
        address_line2: editLine2.trim() || undefined,
        city: editCity.trim(),
        state: editState.trim(),
        postal_code: editPostalCode.trim(),
        landmark: editLandmark.trim() || undefined,
        label: editLabel.trim() || 'Home',
        latitude: latNum,
        longitude: lngNum,
        delivery_instructions: editDeliveryInstructions.trim() || undefined,
        is_default: editIsDefault,
      });
      const list = await customerApi.getAddresses();
      setAddresses(list || []);
      setIsEditModalOpen(false);
      setEditingAddress(null);
      if (selectedAddressId === updated.id) {
        runCheckoutPreview();
      }
    } catch (err: any) {
      setEditError(err?.detail || 'Failed to update address.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleSetDefaultAddress = async (addrId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await customerApi.setDefaultAddress(addrId);
      const list = await customerApi.getAddresses();
      setAddresses(list || []);
    } catch (err: any) {
      setOrderError(err?.detail || 'Failed to update default address.');
    }
  };

  useEffect(() => {
    let timer: any;
    if (unverifiedCooldown > 0) {
      timer = setTimeout(() => setUnverifiedCooldown((c) => c - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [unverifiedCooldown]);

  const handleResendUnverified = async () => {
    if (unverifiedCooldown > 0 || resendingVerification) return;
    setResendingVerification(true);
    setUnverifiedResendStatus('');
    try {
      const res = await authService.resendVerification(user?.email);
      setUnverifiedResendStatus(res.message || 'Verification email resent successfully!');
      setUnverifiedCooldown(res.cooldown_seconds || 60);
    } catch (err: any) {
      setUnverifiedResendStatus(err?.detail || 'Failed to resend verification email.');
    } finally {
      setResendingVerification(false);
    }
  };

  const handleSaveConfirmedLocation = async () => {
    if (!confirmPickerLoc || !selectedAddressId) return;
    try {
      const updated = await customerApi.updateAddress(selectedAddressId, {
        latitude: confirmPickerLoc.latitude,
        longitude: confirmPickerLoc.longitude,
      });
      setAddresses((prev) => prev.map((a) => (a.id === selectedAddressId ? updated : a)));
      setShowLocationConfirmModal(false);
      setConfirmPickerLoc(null);
      setOrderError('');
    } catch (err: any) {
      setOrderError(err?.detail || 'Failed to update delivery coordinates.');
    }
  };

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: location } });
      return;
    }

    if (items.length === 0 && !orderPlaced) {
      navigate('/cart');
      return;
    }

    loadAddresses();
  }, [isAuthenticated, items]);

  useEffect(() => {
    if (appliedPromoCode) {
      setPromoInput(appliedPromoCode);
    }
    runCheckoutPreview(appliedPromoCode);
  }, [items, kitchenId, selectedAddressId, appliedPromoCode]);

  const loadAddresses = async () => {
    try {
      const list = await customerApi.getAddresses();
      setAddresses(list || []);
      if (list && list.length > 0) {
        const defaultAddr = list.find((a) => a.is_default) || list[0];
        setSelectedAddressId(defaultAddr.id);
      } else {
        setShowNewAddress(true);
      }
    } catch (err) {
      setShowNewAddress(true);
    }
  };

  const runCheckoutPreview = async (promo?: string | null) => {
    if (!kitchenId || items.length === 0) return;
    try {
      const codeToUse = promo !== undefined ? promo : appliedPromoCode;
      const res = await customerApi.checkoutPreview({
        kitchen_id: kitchenId,
        items: items.map((i) => ({
          menu_item_id: i.menuItem.id,
          quantity: i.quantity,
        })),
        delivery_address_id: selectedAddressId || undefined,
        promotion_code: codeToUse || undefined,
      });
      setPreview(res);
      setPreviewError('');
      if (codeToUse && res.discount_amount > 0) {
        setPromoSuccess(`Promotion ${res.applied_promotion_code || codeToUse} active: -₹${res.discount_amount.toFixed(2)} off`);
        setPromoError('');
      }
    } catch (err: any) {
      setPreviewError(err?.detail || 'Failed to calculate checkout preview');
      if (promo) {
        setPromoError(err?.detail || 'Invalid or inactive promotion coupon code.');
        setAppliedPromoCode(null);
      }
    }
  };

  const handleApplyCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = promoInput.trim().toUpperCase();
    if (!clean) {
      setPromoError('Please enter a promotion code.');
      return;
    }
    if (!kitchenId || items.length === 0) return;

    setPromoLoading(true);
    setPromoError('');
    setPromoSuccess('');

    try {
      const res = await customerApi.checkoutPreview({
        kitchen_id: kitchenId,
        items: items.map((i) => ({
          menu_item_id: i.menuItem.id,
          quantity: i.quantity,
        })),
        delivery_address_id: selectedAddressId || undefined,
        promotion_code: clean,
      });
      setPreview(res);
      setAppliedPromoCode(clean);
      setPromoSuccess(`Promotion ${res.applied_promotion_code || clean} applied: -₹${res.discount_amount.toFixed(2)} savings!`);
      setPromoError('');
    } catch (err: any) {
      setPromoError(err?.detail || 'Invalid or inactive promotion coupon code.');
      setPromoSuccess('');
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemoveCoupon = async () => {
    setAppliedPromoCode(null);
    setPromoInput('');
    setPromoError('');
    setPromoSuccess('');
    await runCheckoutPreview(null);
  };

  const handleLocationPicked = (loc: CustomerLocation | null) => {
    if (!loc) {
      setNewLatitude(null);
      setNewLongitude(null);
      return;
    }
    setNewLatitude(loc.latitude);
    setNewLongitude(loc.longitude);
    if (!newAddressLine1) {
      setNewAddressLine1(loc.address);
    }
  };

  const handleCreateAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAddressLine1.trim() || !newCity.trim() || !newPostalCode.trim()) {
      setOrderError('Please provide address line, city, and postal code.');
      return;
    }
    if (newLatitude == null || newLongitude == null) {
      setOrderError('Please select or confirm your location on the map to set delivery coordinates.');
      return;
    }
    try {
      const created = await customerApi.createAddress({
        address_line1: newAddressLine1.trim(),
        city: newCity.trim(),
        state: newState.trim() || 'State',
        postal_code: newPostalCode.trim(),
        landmark: newLandmark.trim() || undefined,
        label: newLabel,
        latitude: newLatitude,
        longitude: newLongitude,
        is_default: true,
      });
      setAddresses((prev) => [created, ...prev]);
      setSelectedAddressId(created.id);
      setShowNewAddress(false);
      setOrderError('');
    } catch (err: any) {
      setOrderError(err?.detail || 'Failed to save address');
    }
  };

  const handlePlaceOrder = async () => {
    if (!kitchenId) return;

    if (user && !user.is_verified) {
      setShowUnverifiedModal(true);
      return;
    }

    const selectedAddress = addresses.find((a) => a.id === selectedAddressId);
    if (!selectedAddress) {
      setOrderError('Please select or add a delivery address.');
      return;
    }

    if (selectedAddress.latitude == null || selectedAddress.longitude == null) {
      setOrderError('Customer delivery location is not confirmed. Please confirm your delivery pin on the map before placing the order.');
      setShowLocationConfirmModal(true);
      return;
    }

    setOrderError('');
    setLoading(true);

    try {
      const res = await customerApi.placeOrder({
        kitchen_id: kitchenId,
        items: items.map((i) => ({
          menu_item_id: i.menuItem.id,
          quantity: i.quantity,
        })),
        delivery_address_id: selectedAddressId || undefined,
        payment_method: paymentMethod,
        special_instructions: specialInstructions || undefined,
        promotion_code: appliedPromoCode || undefined,
      });

      setOrderPlaced(true);
      setPlacedOrderId(res.id);
      clearCart();
      setAppliedPromoCode(null);
    } catch (err: any) {
      setOrderError(err?.detail || 'Could not place order. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (orderPlaced && placedOrderId) {
    return (
      <div className="max-w-xl mx-auto py-16 px-4 text-center space-y-6">
        <div className="w-20 h-20 bg-emerald-50 rounded-3xl flex items-center justify-center mx-auto text-emerald-600">
          <CheckCircle className="w-10 h-10" />
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-black text-[#172033]">Order Confirmed!</h1>
          <p className="text-sm text-gray-600">
            Your order has been transmitted directly to the kitchen. Track preparation in real time on your Orders page.
          </p>
        </div>
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/orders"
            className="w-full sm:w-auto bg-[#166534] hover:bg-[#15803d] text-white px-6 py-3 rounded-xl font-bold text-sm shadow-md transition"
          >
            Track Order Live
          </Link>
          <Link
            to="/menu"
            className="w-full sm:w-auto bg-gray-100 hover:bg-gray-200 text-gray-800 px-6 py-3 rounded-xl font-bold text-sm transition"
          >
            Back to Menu
          </Link>
        </div>
      </div>
    );
  }

  const billSubtotal = preview ? preview.subtotal : subtotal;
  const billDiscount = preview ? preview.discount_amount : 0;
  const billDelivery = preview ? preview.delivery_fee : 20.0;
  const billTotal = preview ? preview.total_amount : Number((billSubtotal - billDiscount + billDelivery).toFixed(2));

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <Link to="/cart" className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 hover:text-[#166534] mb-2">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Cart
        </Link>
        <h1 className="text-3xl font-black text-[#172033] tracking-tight">Checkout</h1>
        <p className="text-xs text-gray-500">Provide delivery coordinates and complete your KitchenVerse order</p>
      </div>

      {orderError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-2xl text-xs font-bold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{orderError}</span>
        </div>
      )}

      {previewError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-2xl text-xs font-bold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" />
          <span>{previewError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Section: Delivery & Payment Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Address Section */}
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[#172033]">
                <MapPin className="w-5 h-5 text-[#166534]" />
                <h2 className="text-base font-black">Delivery Address</h2>
              </div>
              {!showNewAddress && (
                <button
                  onClick={() => setShowNewAddress(true)}
                  className="text-xs font-bold text-[#166534] hover:underline flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add New Address
                </button>
              )}
            </div>

            {showNewAddress ? (
              <form onSubmit={handleCreateAddress} className="space-y-3 bg-gray-50 p-4 rounded-2xl border border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-gray-700">Enter Delivery Address</h3>
                  <div className="flex items-center gap-1.5">
                    {(['Home', 'Work', 'Other'] as const).map((lbl) => (
                      <button
                        key={lbl}
                        type="button"
                        onClick={() => setNewLabel(lbl)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition ${
                          newLabel === lbl
                            ? 'bg-[#166534] text-white'
                            : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        {lbl === 'Home' && '🏠 '}
                        {lbl === 'Work' && '💼 '}
                        {lbl === 'Other' && '📍 '}
                        {lbl}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Optional Google Places / Current Location Autodetect */}
                <div className="pt-1">
                  <CustomerLocationPicker
                    currentLocation={
                      newLatitude && newLongitude
                        ? { address: newAddressLine1, latitude: newLatitude, longitude: newLongitude }
                        : null
                    }
                    onLocationChange={handleLocationPicked}
                  />
                </div>

                <div>
                  <input
                    type="text"
                    required
                    placeholder="Flat / House No. / Street Address"
                    value={newAddressLine1}
                    onChange={(e) => setNewAddressLine1(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <input
                    type="text"
                    required
                    placeholder="City"
                    value={newCity}
                    onChange={(e) => setNewCity(e.target.value)}
                    className="px-3 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                  <input
                    type="text"
                    required
                    placeholder="State"
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    className="px-3 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                  <input
                    type="text"
                    required
                    placeholder="PIN Code"
                    value={newPostalCode}
                    onChange={(e) => setNewPostalCode(e.target.value)}
                    className="px-3 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div>
                  <input
                    type="text"
                    placeholder="Landmark (e.g. Near HDFC Bank, opposite park)"
                    value={newLandmark}
                    onChange={(e) => setNewLandmark(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  {addresses.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowNewAddress(false)}
                      className="px-3 py-1.5 rounded-xl text-xs font-semibold text-gray-600 hover:bg-gray-200"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="submit"
                    className="bg-[#166534] hover:bg-[#15803d] text-white px-4 py-1.5 rounded-xl text-xs font-bold"
                  >
                    Save Address
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-2">
                {addresses.map((addr) => (
                  <label
                    key={addr.id}
                    className={`flex items-start gap-3 p-3.5 rounded-2xl border cursor-pointer transition ${
                      selectedAddressId === addr.id
                        ? 'border-[#166534] bg-emerald-50/50 ring-1 ring-[#166534]'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="deliveryAddress"
                      checked={selectedAddressId === addr.id}
                      onChange={() => setSelectedAddressId(addr.id)}
                      className="mt-0.5 text-[#166534] focus:ring-[#166534]"
                    />
                    <div className="text-xs space-y-1 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-800">{addr.address_line1}</span>
                          {addr.label && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                              {addr.label}
                            </span>
                          )}
                          {addr.is_default && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-600">
                              Default
                            </span>
                          )}
                        </div>

                        {/* Edit and Delete Actions */}
                        <div className="flex items-center gap-1">
                          {!addr.is_default && (
                            <button
                              type="button"
                              onClick={(e) => handleSetDefaultAddress(addr.id, e)}
                              className="px-2 py-0.5 text-[10px] font-bold text-gray-500 hover:text-[#166534] hover:bg-gray-100 rounded transition"
                              title="Make this my default address"
                            >
                              Set Default
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={(e) => openEditModal(addr, e)}
                            className="p-1 text-gray-400 hover:text-[#166534] hover:bg-gray-100 rounded transition"
                            title="Edit address"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setAddressToDelete(addr);
                              setDeleteAddressError(null);
                            }}
                            className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                            title="Delete address"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-gray-500">
                        {addr.city}, {addr.state} - {addr.postal_code}
                        {addr.landmark ? ` (Landmark: ${addr.landmark})` : ''}
                      </p>
                      {addr.latitude != null && addr.longitude != null ? (
                        <p className="text-[10px] text-emerald-700 font-mono">
                          📍 Coordinates: {addr.latitude.toFixed(4)}, {addr.longitude.toFixed(4)}
                        </p>
                      ) : (
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 mt-1 border-t border-amber-100">
                          <p className="text-[10px] text-amber-800 font-semibold flex items-center gap-1">
                            <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                            Customer delivery location is not confirmed.
                          </p>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setSelectedAddressId(addr.id);
                              setShowLocationConfirmModal(true);
                            }}
                            className="px-2.5 py-1 rounded-lg text-[10px] font-bold bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 transition shrink-0"
                          >
                            Confirm Pin on Map
                          </button>
                        </div>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Payment Method Section */}
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs space-y-4">
            <div className="flex items-center gap-2 text-[#172033]">
              <CreditCard className="w-5 h-5 text-[#166534]" />
              <h2 className="text-base font-black">Payment Mode</h2>
            </div>

            {/* Authoritative Final Payment Display Bar */}
            <div className="p-4 bg-emerald-50/70 rounded-2xl border border-emerald-200 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-emerald-950 block">Amount to Pay</span>
                {billDiscount > 0 ? (
                  <span className="text-[11px] text-emerald-700 font-medium">
                    (Subtotal ₹{billSubtotal.toFixed(2)} − Discount ₹{billDiscount.toFixed(2)})
                  </span>
                ) : (
                  <span className="text-[11px] text-gray-500 font-medium">
                    Authoritative server-calculated bill
                  </span>
                )}
              </div>
              <span className="text-2xl font-black text-[#166534] font-mono">
                ₹{billTotal.toFixed(2)}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                className={`flex items-center gap-3 p-4 rounded-2xl border cursor-pointer transition ${
                  paymentMethod === 'CASH_ON_DELIVERY'
                    ? 'border-[#166534] bg-emerald-50/50 ring-1 ring-[#166534]'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="radio"
                  name="paymentMode"
                  checked={paymentMethod === 'CASH_ON_DELIVERY'}
                  onChange={() => setPaymentMethod('CASH_ON_DELIVERY')}
                  className="text-[#166534] focus:ring-[#166534]"
                />
                <Banknote className="w-5 h-5 text-gray-700" />
                <div>
                  <p className="text-xs font-bold text-gray-800">Cash on Delivery</p>
                  <p className="text-[10px] text-gray-500">Pay cash or scan QR when meal arrives</p>
                </div>
              </label>

              <label
                className={`flex items-center gap-3 p-4 rounded-2xl border cursor-pointer transition ${
                  paymentMethod === 'UPI'
                    ? 'border-[#166534] bg-emerald-50/50 ring-1 ring-[#166534]'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="radio"
                  name="paymentMode"
                  checked={paymentMethod === 'UPI'}
                  onChange={() => setPaymentMethod('UPI')}
                  className="text-[#166534] focus:ring-[#166534]"
                />
                <CreditCard className="w-5 h-5 text-gray-700" />
                <div>
                  <p className="text-xs font-bold text-gray-800">UPI / Online Instant</p>
                  <p className="text-[10px] text-gray-500">Verified mock simulated gateway</p>
                </div>
              </label>
            </div>
          </div>

          {/* Special Instructions */}
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs space-y-2">
            <label className="block text-xs font-bold text-gray-700">
              Kitchen Instructions / Delivery Notes (Optional)
            </label>
            <textarea
              rows={2}
              placeholder="E.g. Extra napkins, leave at door, less spicy..."
              value={specialInstructions}
              onChange={(e) => setSpecialInstructions(e.target.value)}
              className="w-full p-3 bg-gray-50 border border-gray-200 rounded-2xl text-xs outline-none focus:ring-2 focus:ring-[#166534] focus:bg-white"
            />
          </div>
        </div>

        {/* Right Section: Bill & Confirmation */}
        <div className="space-y-4">
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs space-y-5">
            <h2 className="text-lg font-black text-[#172033]">Order Preview</h2>

            {/* Items summary */}
            <div className="space-y-2 divide-y divide-gray-100 max-h-48 overflow-y-auto pr-1">
              {items.map(({ menuItem, quantity }) => (
                <div key={menuItem.id} className="pt-2 first:pt-0 flex justify-between text-xs">
                  <span className="text-gray-700">
                    {quantity} × {menuItem.name}
                  </span>
                  <span className="font-bold text-gray-900">
                    ₹{(menuItem.price * quantity).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>

            {/* Coupon Code Section */}
            <div className="pt-2 border-t border-gray-100">
              {appliedPromoCode ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Tag className="w-4 h-4 text-emerald-600" />
                    <div>
                      <span className="text-xs font-black text-emerald-900 tracking-wide">
                        {appliedPromoCode}
                      </span>
                      <span className="text-[10px] text-emerald-700 block font-semibold">
                        Discount of ₹{billDiscount.toFixed(2)} applied
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveCoupon}
                    className="text-xs font-bold text-red-600 hover:text-red-700 flex items-center gap-0.5 px-2 py-1 rounded-lg hover:bg-red-50 transition"
                  >
                    <X className="w-3.5 h-3.5" /> Remove
                  </button>
                </div>
              ) : (
                <form onSubmit={handleApplyCoupon} className="space-y-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Tag className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        placeholder="Coupon code (WELCOME_20)"
                        value={promoInput}
                        onChange={(e) => setPromoInput(e.target.value)}
                        className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs uppercase font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#166534]"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={promoLoading}
                      className="bg-gray-800 hover:bg-black disabled:opacity-50 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition"
                    >
                      {promoLoading ? 'Verifying...' : 'Apply'}
                    </button>
                  </div>
                  {promoSuccess && (
                    <p className="text-[11px] font-bold text-emerald-600">{promoSuccess}</p>
                  )}
                  {promoError && (
                    <p className="text-[11px] font-bold text-red-600">{promoError}</p>
                  )}
                </form>
              )}
            </div>

            {/* Price lines */}
            <div className="space-y-2.5 text-xs text-gray-600 border-t border-gray-100 pt-3">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span className="font-bold text-gray-800">₹{billSubtotal.toFixed(2)}</span>
              </div>

              {billDiscount > 0 && (
                <>
                  <div className="flex justify-between text-emerald-800">
                    <span>Promotion</span>
                    <span className="font-black tracking-wider uppercase bg-emerald-100 px-2 py-0.5 rounded text-[11px]">
                      {preview?.applied_promotion_code || appliedPromoCode}
                    </span>
                  </div>
                  <div className="flex justify-between text-emerald-600 font-bold">
                    <span>Discount</span>
                    <span>-₹{billDiscount.toFixed(2)}</span>
                  </div>
                </>
              )}

              {/* Dynamic Delivery Fee Section */}
              <div className="space-y-1.5 pt-1 border-t border-gray-100">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-medium text-gray-700">Delivery Partner Fee</span>
                    {preview?.distance_km != null && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        preview.is_estimate 
                          ? 'bg-amber-100 text-amber-800 border border-amber-200' 
                          : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      }`}>
                        {preview.distance_km} km {preview.is_estimate ? '(Est. Straight-Line)' : '(Road Route)'}
                      </span>
                    )}
                  </div>
                  <span className="font-bold text-gray-900">
                    ₹{billDelivery.toFixed(2)}
                  </span>
                </div>

                {preview?.formula_display && (
                  <p className="text-[10px] text-gray-500 font-mono bg-gray-50 p-1.5 rounded-lg border border-gray-100">
                    💡 {preview.formula_display}
                  </p>
                )}

                {preview?.is_estimate && (
                  <p className="text-[10px] text-amber-700 font-medium">
                    Road network route unavailable; distance calculated using direct coordinates estimate.
                  </p>
                )}

                {preview?.requires_location && (
                  <p className="text-[10px] text-amber-700 font-medium">
                    Base fee shown. Please confirm your delivery address pin on the map for exact road distance.
                  </p>
                )}

                {preview?.out_of_range && (
                  <p className="text-[11px] text-red-600 font-bold bg-red-50 p-1.5 rounded border border-red-200">
                    ⚠️ Delivery address exceeds the platform maximum delivery radius of {preview.max_delivery_radius_km || 15} km.
                  </p>
                )}
              </div>

              {(preview?.platform_fee || 0) > 0 && (
                <div className="flex justify-between">
                  <span>Platform Convenience Fee</span>
                  <span className="font-bold text-gray-800">₹{preview?.platform_fee?.toFixed(2)}</span>
                </div>
              )}

              <div className="flex justify-between text-gray-500 text-[11px]">
                <span>Taxes & Kitchen Packaging</span>
                <span className="font-bold text-gray-700">
                  {(preview?.tax || 0) > 0 ? `₹${preview?.tax.toFixed(2)}` : 'Inclusive'}
                </span>
              </div>

              <div className="border-t border-gray-100 pt-3 flex justify-between text-base font-black text-[#172033]">
                <span>Final Total</span>
                <span>₹{billTotal.toFixed(2)}</span>
              </div>
            </div>

            {/* Submit */}
            <button
              onClick={handlePlaceOrder}
              disabled={loading || items.length === 0}
              className="w-full bg-[#166534] hover:bg-[#15803d] text-white py-3.5 px-4 rounded-xl font-bold text-sm tracking-wide transition shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? 'Transmitting Order...' : `Pay ₹${billTotal.toFixed(2)} & Place Order`} <ArrowRight className="w-4 h-4" />
            </button>

            <div className="flex items-center justify-center gap-1.5 text-[11px] text-gray-400 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Authenticated KitchenVerse Transaction
            </div>
          </div>
        </div>
      </div>

      {/* Unverified Email Protection Modal */}
      {showUnverifiedModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 space-y-4 text-center">
            <div className="w-14 h-14 bg-amber-100 text-amber-700 rounded-3xl flex items-center justify-center mx-auto">
              <AlertCircle className="w-7 h-7" />
            </div>

            <div className="space-y-2">
              <h3 className="text-xl font-black text-gray-900">
                Please verify your email first.
              </h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                Verification link was sent to:<br />
                <strong className="text-gray-900 text-sm font-bold">{user?.email}</strong>
              </p>
              <p className="text-[11px] text-gray-500">
                Your cart is saved. Please verify your email address to complete and track your order.
              </p>
            </div>

            {unverifiedResendStatus && (
              <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl">
                {unverifiedResendStatus}
              </p>
            )}

            <div className="flex flex-col sm:flex-row gap-2.5 pt-2">
              <button
                type="button"
                onClick={handleResendUnverified}
                disabled={resendingVerification || unverifiedCooldown > 0}
                className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-800 py-2.5 px-3 rounded-xl text-xs font-bold transition disabled:opacity-50"
              >
                {unverifiedCooldown > 0 ? `Resend (${unverifiedCooldown}s)` : 'Resend Verification Email'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowUnverifiedModal(false);
                  navigate('/verify-email');
                }}
                className="flex-1 bg-[#166534] hover:bg-[#15803d] text-white py-2.5 px-3 rounded-xl text-xs font-bold transition shadow-sm"
              >
                I'll Verify My Email
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delivery Location Confirmation Modal */}
      {showLocationConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-100 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-gray-900">
                  Confirm Delivery Location on Map
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Set or adjust your doorstep delivery pin so our kitchen and courier can find you.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowLocationConfirmModal(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <CustomerLocationPicker
              currentLocation={
                confirmPickerLoc ||
                (() => {
                  const s = addresses.find((a) => a.id === selectedAddressId);
                  return s && s.latitude != null && s.longitude != null
                    ? { address: s.address_line1, latitude: s.latitude, longitude: s.longitude }
                    : null;
                })()
              }
              onLocationChange={(loc) => setConfirmPickerLoc(loc)}
            />

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setShowLocationConfirmModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!confirmPickerLoc}
                onClick={handleSaveConfirmedLocation}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-[#166534] hover:bg-[#15803d] disabled:opacity-50 text-white transition shadow-sm"
              >
                Confirm Location
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Address Confirmation Modal */}
      {addressToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
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
              Are you sure you want to delete this delivery address?{' '}
              <strong className="text-gray-800">
                Historical orders referencing this address will preserve all delivery records and snapshots.
              </strong>{' '}
              {addressToDelete.is_default && (
                <span className="text-[#166534] font-medium">
                  Another saved address will automatically be selected as default.
                </span>
              )}
            </p>

            {deleteAddressError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{deleteAddressError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={isDeletingAddress}
                onClick={() => setAddressToDelete(null)}
                className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeletingAddress}
                onClick={handleDeleteAddress}
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
              >
                {isDeletingAddress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Delete Address
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Address Modal */}
      {isEditModalOpen && editingAddress && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <MapPin className="w-5 h-5 text-[#166534]" />
                <h3 className="text-base font-black text-[#172033]">Edit Saved Address</h3>
              </div>
              <button
                onClick={() => {
                  setIsEditModalOpen(false);
                  setEditingAddress(null);
                }}
                className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {editError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSaveEditAddress} className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Label
                </label>
                <div className="flex items-center gap-2">
                  {(['Home', 'Work', 'Other'] as const).map((lbl) => (
                    <button
                      key={lbl}
                      type="button"
                      onClick={() => setEditLabel(lbl)}
                      className={`flex-1 py-1.5 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                        editLabel === lbl
                          ? 'bg-[#166534] text-white shadow-xs'
                          : 'bg-gray-50 border border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {lbl === 'Home' && <Home className="w-3.5 h-3.5" />}
                      {lbl === 'Work' && <Briefcase className="w-3.5 h-3.5" />}
                      {lbl === 'Other' && <Tag className="w-3.5 h-3.5" />}
                      {lbl}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Line 1 *
                </label>
                <input
                  type="text"
                  required
                  value={editLine1}
                  onChange={(e) => setEditLine1(e.target.value)}
                  placeholder="Flat, House No., Street Address"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Address Line 2 (Optional)
                </label>
                <input
                  type="text"
                  value={editLine2}
                  onChange={(e) => setEditLine2(e.target.value)}
                  placeholder="Area / Colony"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Landmark (Optional)
                </label>
                <input
                  type="text"
                  value={editLandmark}
                  onChange={(e) => setEditLandmark(e.target.value)}
                  placeholder="Near Water Tank / College Gate"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">City *</label>
                  <input
                    type="text"
                    required
                    value={editCity}
                    onChange={(e) => setEditCity(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">State *</label>
                  <input
                    type="text"
                    required
                    value={editState}
                    onChange={(e) => setEditState(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">PIN Code *</label>
                  <input
                    type="text"
                    required
                    value={editPostalCode}
                    onChange={(e) => setEditPostalCode(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Latitude</label>
                  <input
                    type="text"
                    value={editLatitude}
                    onChange={(e) => setEditLatitude(e.target.value)}
                    placeholder="e.g. 18.0123"
                    className="w-full px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Longitude</label>
                  <input
                    type="text"
                    value={editLongitude}
                    onChange={(e) => setEditLongitude(e.target.value)}
                    placeholder="e.g. 79.5432"
                    className="w-full px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-gray-700 mb-1">
                  Delivery Instructions (Optional)
                </label>
                <input
                  type="text"
                  value={editDeliveryInstructions}
                  onChange={(e) => setEditDeliveryInstructions(e.target.value)}
                  placeholder="e.g. Leave with security guard"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-[#166534] outline-none"
                />
              </div>

              <label className="flex items-center gap-2 pt-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={editIsDefault}
                  onChange={(e) => setEditIsDefault(e.target.checked)}
                  className="rounded text-[#166534] focus:ring-[#166534]"
                />
                <span className="text-xs font-bold text-gray-700">
                  Set as my primary default delivery address
                </span>
              </label>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => {
                    setIsEditModalOpen(false);
                    setEditingAddress(null);
                  }}
                  className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="px-5 py-2 bg-[#166534] hover:bg-[#15803d] text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
                >
                  {editLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
