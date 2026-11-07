/**
 * Customer Portal - Shopping Cart Page
 * Manage cart items, adjust quantities, apply promotions, calculate subtotals,
 * and proceed to checkout.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../../context/CartContext';
import { customerApi, CheckoutPreviewResponse } from '../../services/customerApi';
import {
  ShoppingBag,
  Trash2,
  Plus,
  Minus,
  ArrowRight,
  ArrowLeft,
  Tag,
  ShieldCheck,
  Store,
  X,
  Check,
} from 'lucide-react';

export default function Cart() {
  const {
    items,
    updateQuantity,
    removeFromCart,
    clearCart,
    subtotal,
    kitchenId,
    appliedPromoCode,
    setAppliedPromoCode,
  } = useCart();
  const [promoInput, setPromoInput] = useState(appliedPromoCode || '');
  const [promoError, setPromoError] = useState('');
  const [promoSuccess, setPromoSuccess] = useState('');
  const [preview, setPreview] = useState<CheckoutPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    if (appliedPromoCode) {
      setPromoInput(appliedPromoCode);
    }
  }, [appliedPromoCode]);

  useEffect(() => {
    if (!kitchenId || items.length === 0) {
      setPreview(null);
      return;
    }
    loadPreview(appliedPromoCode);
  }, [items, kitchenId, appliedPromoCode]);

  const loadPreview = async (promo?: string | null) => {
    if (!kitchenId || items.length === 0) return;
    try {
      setPreviewLoading(true);
      const res = await customerApi.checkoutPreview({
        kitchen_id: kitchenId,
        items: items.map((i) => ({
          menu_item_id: i.menuItem.id,
          quantity: i.quantity,
        })),
        promotion_code: promo || undefined,
      });
      setPreview(res);
      if (promo && res.discount_amount > 0) {
        setPromoSuccess(`Promotion ${res.applied_promotion_code || promo} applied: -₹${res.discount_amount.toFixed(2)} savings!`);
        setPromoError('');
      }
    } catch (err: any) {
      if (promo) {
        setPromoError(err?.detail || 'Invalid or inactive coupon code.');
        setPromoSuccess('');
        setAppliedPromoCode(null);
      }
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleApplyPromo = async (e: React.FormEvent) => {
    e.preventDefault();
    setPromoError('');
    setPromoSuccess('');

    const code = promoInput.trim().toUpperCase();
    if (!code) {
      setPromoError('Please enter a promotion code.');
      return;
    }

    if (!kitchenId || items.length === 0) return;

    try {
      setPreviewLoading(true);
      const res = await customerApi.checkoutPreview({
        kitchen_id: kitchenId,
        items: items.map((i) => ({
          menu_item_id: i.menuItem.id,
          quantity: i.quantity,
        })),
        promotion_code: code,
      });
      setPreview(res);
      setAppliedPromoCode(code);
      setPromoSuccess(`Promotion ${res.applied_promotion_code || code} applied: -₹${res.discount_amount.toFixed(2)} savings!`);
      setPromoError('');
    } catch (err: any) {
      setPromoError(err?.detail || 'Invalid or inactive promotion coupon code.');
      setPromoSuccess('');
      setAppliedPromoCode(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRemovePromo = () => {
    setAppliedPromoCode(null);
    setPromoInput('');
    setPromoSuccess('');
    setPromoError('');
    loadPreview(null);
  };

  const billSubtotal = preview ? preview.subtotal : subtotal;
  const billDiscount = preview ? preview.discount_amount : 0;
  const billDelivery = preview ? preview.delivery_fee : (subtotal === 0 ? 0 : 20.0);
  const billTotal = preview ? preview.total_amount : Number((billSubtotal - billDiscount + billDelivery).toFixed(2));

  if (items.length === 0) {
    return (
      <div className="max-w-xl mx-auto py-16 px-4 text-center space-y-6">
        <div className="w-20 h-20 bg-amber-50 rounded-3xl flex items-center justify-center mx-auto text-[#166534]">
          <ShoppingBag className="w-10 h-10" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-black text-[#172033]">Your Cart is Empty</h2>
          <p className="text-sm text-gray-500">
            Looks like you haven't added any dishes yet. Discover delicious KitchenVerse meals and add your favorites!
          </p>
        </div>
        <div>
          <Link
            to="/menu"
            className="inline-flex items-center gap-2 bg-[#166534] hover:bg-[#15803d] text-white px-6 py-3 rounded-xl font-bold text-sm shadow-md hover:shadow-lg transition-all"
          >
            Explore Menu <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black text-[#172033] tracking-tight">Your Order Cart</h1>
          <p className="text-xs text-gray-500 mt-1">Review items before proceeding to checkout</p>
        </div>
        <button
          onClick={clearCart}
          className="text-xs font-bold text-red-600 hover:text-red-700 hover:underline flex items-center gap-1.5"
        >
          <Trash2 className="w-3.5 h-3.5" /> Clear Cart
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Cart Items List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs divide-y divide-gray-100">
            {items.map(({ menuItem, quantity }) => (
              <div key={menuItem.id} className="py-4 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center justify-center w-3.5 h-3.5 rounded border text-[8px] font-black ${
                        menuItem.is_veg
                          ? 'border-emerald-600 text-emerald-600 bg-emerald-50'
                          : 'border-red-600 text-red-600 bg-red-50'
                      }`}
                    >
                      ●
                    </span>
                    <h3 className="font-bold text-sm text-[#172033] leading-tight">
                      {menuItem.name}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-400">
                    ₹{menuItem.price.toFixed(2)} each
                  </p>
                </div>

                {/* Quantity Controls */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center border border-gray-200 rounded-xl bg-gray-50 overflow-hidden">
                    <button
                      onClick={() => updateQuantity(menuItem.id, quantity - 1)}
                      className="p-1.5 hover:bg-gray-200 text-gray-600 transition"
                      title="Decrease"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                    <span className="w-8 text-center text-xs font-bold text-gray-800">
                      {quantity}
                    </span>
                    <button
                      onClick={() => updateQuantity(menuItem.id, quantity + 1)}
                      className="p-1.5 hover:bg-gray-200 text-gray-600 transition"
                      title="Increase"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <span className="w-20 text-right text-sm font-black text-[#172033]">
                    ₹{(menuItem.price * quantity).toFixed(2)}
                  </span>

                  <button
                    onClick={() => removeFromCart(menuItem.id)}
                    className="p-1 text-gray-400 hover:text-red-600 transition"
                    title="Remove item"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-gray-500 px-2">
            <Link to="/menu" className="font-bold text-[#166534] hover:underline flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" /> Add more items from menu
            </Link>
            <span>Prices inclusive of standard kitchen prep</span>
          </div>
        </div>

        {/* Order Summary & Checkout Card */}
        <div className="space-y-4">
          <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs space-y-6">
            <h2 className="text-lg font-black text-[#172033]">Order Summary</h2>

            {/* Promo Code Form */}
            {appliedPromoCode ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4 text-emerald-600" />
                  <div>
                    <span className="text-xs font-black text-emerald-900 tracking-wide">
                      {appliedPromoCode}
                    </span>
                    <span className="text-[11px] text-emerald-700 block">
                      Promotion applied (-₹{billDiscount.toFixed(2)})
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleRemovePromo}
                  className="text-xs font-bold text-red-600 hover:text-red-700 flex items-center gap-0.5 px-2 py-1 rounded-lg hover:bg-red-50 transition"
                >
                  <X className="w-3.5 h-3.5" /> Remove
                </button>
              </div>
            ) : (
              <form onSubmit={handleApplyPromo} className="space-y-2">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Tag className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="Coupon code (e.g. WELCOME_20)"
                      value={promoInput}
                      onChange={(e) => setPromoInput(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs uppercase font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#166534]"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={previewLoading}
                    className="bg-gray-800 hover:bg-black disabled:opacity-50 text-white px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1"
                  >
                    {previewLoading ? 'Verifying...' : 'Apply'}
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

            {/* Breakdown */}
            <div className="space-y-2.5 text-xs text-gray-600 border-t border-gray-100 pt-4">
              <div className="flex justify-between">
                <span>Subtotal ({items.reduce((s, i) => s + i.quantity, 0)} items)</span>
                <span className="font-bold text-gray-800">₹{billSubtotal.toFixed(2)}</span>
              </div>

              {billDiscount > 0 && (
                <div className="flex justify-between text-emerald-600 font-semibold">
                  <span>Promotion ({preview?.applied_promotion_code || appliedPromoCode})</span>
                  <span className="font-bold">-₹{billDiscount.toFixed(2)}</span>
                </div>
              )}

              <div className="flex justify-between items-center">
                <div className="flex items-center gap-1.5">
                  <span>Delivery Partner Fee</span>
                  {preview?.distance_km != null && (
                    <span className="text-[10px] font-semibold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                      {preview.distance_km} km
                    </span>
                  )}
                </div>
                <span className="font-bold text-gray-800">
                  {billDelivery === 0 ? <span className="text-emerald-600 font-bold">FREE</span> : `₹${billDelivery.toFixed(2)}`}
                </span>
              </div>

              <div className="border-t border-gray-100 pt-3 flex justify-between text-base font-black text-[#172033]">
                <span>To Pay</span>
                <span>₹{billTotal.toFixed(2)}</span>
              </div>
            </div>

            {/* Checkout CTA */}
            <button
              onClick={() => navigate('/checkout')}
              className="w-full bg-[#F97316] hover:bg-[#ea580c] text-white py-3.5 px-4 rounded-xl font-bold text-sm tracking-wide transition shadow-md hover:shadow-lg flex items-center justify-center gap-2"
            >
              Proceed to Checkout <ArrowRight className="w-4 h-4" />
            </button>

            <div className="flex items-center justify-center gap-1.5 text-[11px] text-gray-400 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Secure KitchenVerse Checkout
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
