/**
 * Customer Portal - Orders History & Live Tracking
 * Real-time order pipeline tracking (PENDING -> CONFIRMED -> PREPARING -> READY -> OUT_FOR_DELIVERY -> DELIVERED),
 * itemized details, and post-delivery review submission.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { customerApi, OrderDetail } from '../../services/customerApi';
import {
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Truck,
  ChefHat,
  PackageCheck,
  Star,
  ArrowRight,
  Store,
  ChevronDown,
  ChevronUp,
  X,
  MapPin,
  Ban,
} from 'lucide-react';
import CustomerLocationPicker, { CustomerLocation } from '../../components/common/CustomerLocationPicker';

import { useRealtime } from '../../context/RealtimeContext';

const STATUS_STEPS = [
  { key: 'PENDING', label: 'Placed', icon: Clock },
  { key: 'CONFIRMED', label: 'Accepted', icon: CheckCircle2 },
  { key: 'PREPARING', label: 'Preparing', icon: ChefHat },
  { key: 'READY', label: 'Ready', icon: PackageCheck },
  { key: 'OUT_FOR_DELIVERY', label: 'On Way', icon: Truck },
  { key: 'DELIVERED', label: 'Delivered', icon: CheckCircle2 },
];

export default function Orders() {
  const { subscribe } = useRealtime();
  const [orders, setOrders] = useState<OrderDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Review modal state
  const [reviewOrder, setReviewOrder] = useState<OrderDetail | null>(null);
  const [rating, setRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  // Cancellation modal state
  const [cancelModalOrder, setCancelModalOrder] = useState<OrderDetail | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  // Request Cancellation modal state (for READY orders)
  const [requestCancelOrder, setRequestCancelOrder] = useState<OrderDetail | null>(null);
  const [requestReason, setRequestReason] = useState('Changed my mind');
  const [requestCustomerNote, setRequestCustomerNote] = useState('');
  const [requestSubmitting, setRequestSubmitting] = useState(false);
  const [requestSuccessMsg, setRequestSuccessMsg] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

  // Order Delivery Location Confirmation state
  const [locationConfirmOrder, setLocationConfirmOrder] = useState<OrderDetail | null>(null);
  const [confirmLoc, setConfirmLoc] = useState<CustomerLocation | null>(null);
  const [locationSaving, setLocationSaving] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  useEffect(() => {
    loadOrders();

    // Instant real-time updates for customer orders
    const unsubStatus = subscribe('ORDER_STATUS_CHANGED', () => {
      loadOrders();
    });
    const unsubCreated = subscribe('ORDER_CREATED', () => {
      loadOrders();
    });

    const interval = setInterval(loadOrders, 30000); // Fallback poll interval
    return () => {
      unsubStatus();
      unsubCreated();
      clearInterval(interval);
    };
  }, [subscribe]);

  const loadOrders = async () => {
    try {
      const data = await customerApi.getOrders();
      setOrders(data || []);
      if (!expandedId && data && data.length > 0) {
        setExpandedId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load customer orders:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStepIndex = (status: string) => {
    switch (status) {
      case 'ORDER_PLACED':
      case 'PENDING':
        return 0;
      case 'PAYMENT_CONFIRMED':
      case 'KITCHEN_ACCEPTED':
      case 'CONFIRMED':
        return 1;
      case 'PREPARING':
        return 2;
      case 'READY':
        return 3;
      case 'OUT_FOR_DELIVERY':
        return 4;
      case 'DELIVERED':
        return 5;
      default:
        return -1;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ORDER_PLACED':
      case 'PENDING':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'PAYMENT_CONFIRMED':
      case 'KITCHEN_ACCEPTED':
      case 'CONFIRMED':
        return 'bg-blue-50 text-blue-800 border-blue-200';
      case 'PREPARING':
        return 'bg-purple-50 text-purple-800 border-purple-200';
      case 'READY':
        return 'bg-indigo-50 text-indigo-800 border-indigo-200';
      case 'OUT_FOR_DELIVERY':
        return 'bg-orange-50 text-orange-800 border-orange-200';
      case 'DELIVERED':
        return 'bg-emerald-50 text-emerald-800 border-emerald-200';
      case 'CANCELLED':
      case 'REJECTED':
      case 'PAYMENT_FAILED':
        return 'bg-red-50 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleOpenReview = (order: OrderDetail) => {
    setReviewOrder(order);
    setRating(5);
    setReviewComment('');
    setReviewSuccess(false);
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewOrder) return;
    setReviewSubmitting(true);
    try {
      await customerApi.submitReview({
        order_id: reviewOrder.id,
        rating,
        comment: reviewComment,
      });
      setReviewSuccess(true);
      setTimeout(() => {
        setReviewOrder(null);
        setReviewSuccess(false);
      }, 1500);
    } catch (err) {
      console.error('Failed to submit review:', err);
    } finally {
      setReviewSubmitting(false);
    }
  };

  const handleOpenCancel = (order: OrderDetail) => {
    setCancelModalOrder(order);
    setCancelReason('');
    setCancelError(null);
  };

  const handleConfirmCancel = async () => {
    if (!cancelModalOrder) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await customerApi.cancelOrder(cancelModalOrder.id, cancelReason.trim() || undefined);
      setCancelModalOrder(null);
      await loadOrders();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to cancel order.';
      setCancelError(msg);
    } finally {
      setCancelling(false);
    }
  };

  const handleOpenRequestCancel = (order: OrderDetail) => {
    setRequestCancelOrder(order);
    setRequestReason('Changed my mind');
    setRequestCustomerNote('');
    setRequestSuccessMsg(null);
    setRequestError(null);
  };

  const handleConfirmRequestCancel = async () => {
    if (!requestCancelOrder) return;
    setRequestSubmitting(true);
    setRequestError(null);
    try {
      const cr = await customerApi.requestCancellation(requestCancelOrder.id, {
        reason: requestReason,
        customer_note: requestReason === 'Other' ? requestCustomerNote.trim() : (requestCustomerNote.trim() || undefined),
      });
      setRequestSuccessMsg('Cancellation request sent to Admin.');
      setOrders((prev) =>
        prev.map((o) => (o.id === requestCancelOrder.id ? { ...o, cancellation_request: cr } : o))
      );
      setTimeout(() => {
        setRequestCancelOrder(null);
        setRequestSuccessMsg(null);
      }, 1500);
      await loadOrders();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.detail || err.message || 'Failed to submit cancellation request.';
      setRequestError(msg);
    } finally {
      setRequestSubmitting(false);
    }
  };

  const handleSaveOrderLocation = async () => {
    if (!locationConfirmOrder || !confirmLoc) return;
    setLocationSaving(true);
    setLocationError(null);
    try {
      const updated = await customerApi.updateOrderDeliveryLocation(locationConfirmOrder.id, {
        latitude: confirmLoc.latitude,
        longitude: confirmLoc.longitude,
      });
      setOrders((prev) =>
        prev.map((o) =>
          o.id === locationConfirmOrder.id
            ? {
                ...o,
                delivery_latitude: updated.delivery_latitude,
                delivery_longitude: updated.delivery_longitude,
                delivery_address_snapshot: updated.delivery_address_snapshot,
              }
            : o
        )
      );
      setLocationConfirmOrder(null);
      setConfirmLoc(null);
    } catch (err: any) {
      setLocationError(err?.detail || err?.message || 'Failed to update delivery coordinates.');
    } finally {
      setLocationSaving(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black text-[#172033] tracking-tight">Your Orders</h1>
        <p className="text-xs text-gray-500">Track preparation, dispatch, and review past KitchenVerse meals</p>
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 bg-gray-200 rounded-3xl" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <div className="bg-white rounded-3xl border border-gray-200 p-12 text-center space-y-4 shadow-xs">
          <Clock className="w-12 h-12 text-gray-400 mx-auto" />
          <h2 className="text-xl font-bold text-gray-800">No Orders Placed Yet</h2>
          <p className="text-xs text-gray-500 max-w-sm mx-auto">
            You haven't placed any orders with KitchenVerse yet. Browse delicious dishes and place your first order!
          </p>
          <Link
            to="/menu"
            className="inline-flex items-center gap-2 bg-[#166534] hover:bg-[#15803d] text-white px-5 py-2.5 rounded-xl font-bold text-xs transition"
          >
            Explore Menu <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {orders.map((order) => {
            const isExpanded = expandedId === order.id;
            const currentStep = getStepIndex(order.status);
            const isDelivered = order.status === 'DELIVERED';
            const isCancelled = order.status === 'CANCELLED';

            return (
              <div
                key={order.id}
                className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs hover:shadow-md transition-all space-y-6"
              >
                {/* Top Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-black text-[#172033]">
                        #{order.order_number || order.id.slice(0, 8).toUpperCase()}
                      </span>
                      <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${getStatusBadge(order.status)}`}>
                        {order.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">
                      Placed on {new Date(order.created_at).toLocaleString()}
                    </p>
                    {(order.delivery_address_text || order.delivery_address) && (
                      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 pt-0.5">
                        <div className="flex items-center gap-1.5 truncate max-w-md">
                          <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span className="truncate">
                            <span className="font-semibold text-gray-600">Delivery: </span>
                            {order.delivery_address_text || (order.delivery_address ? `${order.delivery_address.address_line1}, ${order.delivery_address.city}` : 'Standard Delivery')}
                          </span>
                        </div>
                        {order.delivery_latitude != null && order.delivery_longitude != null ? (
                          <span className="font-mono text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md font-semibold">
                            📍 {order.delivery_latitude.toFixed(4)}, {order.delivery_longitude.toFixed(4)}
                          </span>
                        ) : !['DELIVERED', 'CANCELLED'].includes(order.status) ? (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md flex items-center gap-1">
                              <AlertCircle className="w-3 h-3 text-amber-600" />
                              Customer delivery location is not confirmed.
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setLocationConfirmOrder(order);
                                setConfirmLoc(null);
                              }}
                              className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 transition"
                            >
                              Confirm Pin on Map
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className="text-[10px] text-gray-400 block font-medium">Total Amount</span>
                      <span className="text-base font-black text-[#172033]">
                        ₹{order.total_amount.toFixed(2)}
                      </span>
                    </div>

                    <button
                      onClick={() => setExpandedId(isExpanded ? null : order.id)}
                      className="p-2 rounded-xl bg-gray-50 hover:bg-gray-100 text-gray-600 transition"
                      title={isExpanded ? 'Collapse' : 'Expand'}
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Tracking Progress Pipeline */}
                {!isCancelled && (
                  <div className="py-2">
                    <div className="grid grid-cols-6 gap-2">
                      {STATUS_STEPS.map((step, idx) => {
                        const Icon = step.icon;
                        const isDone = currentStep >= idx;
                        const isCurrent = currentStep === idx;
                        return (
                          <div key={step.key} className="flex flex-col items-center text-center space-y-1.5">
                            <div
                              className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                                isDone
                                  ? 'bg-[#166534] text-white shadow-xs'
                                  : 'bg-gray-100 text-gray-400'
                              } ${isCurrent ? 'ring-4 ring-emerald-500/20' : ''}`}
                            >
                              <Icon className="w-4 h-4" />
                            </div>
                            <span
                              className={`text-[10px] font-bold leading-tight ${
                                isDone ? 'text-gray-800' : 'text-gray-400'
                              }`}
                            >
                              {step.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {isCancelled && (
                  <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-2xl text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>This order was cancelled. {order.cancellation_reason || order.rejection_reason || ''}</span>
                  </div>
                )}

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="pt-4 border-t border-gray-100 space-y-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                      Itemized Order Details
                    </h3>

                    <div className="divide-y divide-gray-100 bg-gray-50 rounded-2xl p-4">
                      {order.items.map((item) => (
                        <div key={item.id} className="py-2.5 first:pt-0 last:pb-0 flex justify-between text-xs">
                          <div className="space-y-0.5">
                            <span className="font-bold text-gray-800">
                              {item.quantity} × {item.item_name}
                            </span>
                            {item.special_requests && (
                              <p className="text-[10px] text-gray-500 italic">
                                Note: {item.special_requests}
                              </p>
                            )}
                          </div>
                          <span className="font-mono font-bold text-gray-800">
                            ₹{item.subtotal.toFixed(2)}
                          </span>
                        </div>
                      ))}

                      <div className="pt-3 mt-3 border-t border-gray-200 space-y-1.5 text-xs text-gray-600">
                        <div className="flex justify-between">
                          <span>Subtotal</span>
                          <span>₹{order.subtotal.toFixed(2)}</span>
                        </div>
                        {order.discount_amount && order.discount_amount > 0 ? (
                          <div className="flex justify-between text-emerald-600 font-bold">
                            <span>Promotion Discount ({order.promotion_code || 'COUPON'})</span>
                            <span>-₹{order.discount_amount.toFixed(2)}</span>
                          </div>
                        ) : null}
                        <div className="flex justify-between">
                          <span>Delivery Fee</span>
                          <span>{order.delivery_fee === 0 ? <span className="text-emerald-600 font-bold">FREE</span> : `₹${order.delivery_fee.toFixed(2)}`}</span>
                        </div>
                        <div className="flex justify-between font-black text-gray-900 text-sm pt-1 border-t border-gray-200">
                          <span>Final Total</span>
                          <span>₹{order.total_amount.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Action Bar: Cancellation & Reviews */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-gray-100">
                      <div>
                        {/* Status for READY order cancellation requests */}
                        {order.status === 'READY' && order.cancellation_request && (
                          order.cancellation_request.status === 'PENDING' ? (
                            <div className="bg-amber-50 border border-amber-200 text-amber-900 px-3.5 py-1.5 rounded-xl text-xs space-y-0.5">
                              <div className="flex items-center gap-1.5 font-bold">
                                <Clock className="w-3.5 h-3.5 text-amber-600 animate-spin" />
                                <span>Cancellation Request</span>
                              </div>
                              <p className="text-[11px] text-amber-700">Status: Pending Admin Review</p>
                            </div>
                          ) : order.cancellation_request.status === 'REJECTED' ? (
                            <div className="bg-red-50 border border-red-200 text-red-900 px-3.5 py-1.5 rounded-xl text-xs space-y-0.5">
                              <div className="flex items-center gap-1.5 font-bold text-red-700">
                                <AlertCircle className="w-3.5 h-3.5 text-red-600" />
                                <span>Cancellation Rejected</span>
                              </div>
                              <p className="text-[11px] text-red-800">Order remains READY</p>
                              {order.cancellation_request.admin_note && (
                                <p className="text-[11px] text-red-700 italic">Reason: {order.cancellation_request.admin_note}</p>
                              )}
                            </div>
                          ) : order.cancellation_request.status === 'APPROVED' ? (
                            <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 px-3.5 py-1.5 rounded-xl text-xs space-y-0.5">
                              <div className="flex items-center gap-1.5 font-bold text-emerald-700">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Cancellation Approved</span>
                              </div>
                              <p className="text-[11px] text-emerald-800">Order: CANCELLED</p>
                            </div>
                          ) : null
                        )}

                        {order.status === 'OUT_FOR_DELIVERY' && (
                          <span className="text-[11px] text-gray-500 italic bg-amber-50 border border-amber-200/60 px-3 py-1.5 rounded-xl inline-flex items-center gap-1.5">
                            <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                            Cancellation is no longer available at this stage (Out for delivery).
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        {/* Cancel Button - direct cancellation before READY only */}
                        {['ORDER_PLACED', 'PENDING', 'PAYMENT_CONFIRMED', 'KITCHEN_ACCEPTED', 'CONFIRMED', 'PREPARING'].includes(order.status) && !isCancelled && !isDelivered && (
                          <button
                            onClick={() => handleOpenCancel(order)}
                            className="bg-white hover:bg-red-50 text-red-600 border border-red-200 hover:border-red-300 px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                          >
                            <Ban className="w-3.5 h-3.5" /> Cancel Order
                          </button>
                        )}

                        {/* Request Cancellation Button for READY orders (hidden when request is PENDING) */}
                        {order.status === 'READY' && order.cancellation_request?.status !== 'PENDING' && !isCancelled && !isDelivered && (
                          <button
                            onClick={() => handleOpenRequestCancel(order)}
                            className="bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 hover:border-amber-400 px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                          >
                            <AlertCircle className="w-3.5 h-3.5 text-amber-600" /> Request Cancellation
                          </button>
                        )}

                        {/* Review Button for Delivered Orders */}
                        {isDelivered && (
                          <button
                            onClick={() => handleOpenReview(order)}
                            className="bg-[#F97316] hover:bg-[#ea580c] text-white px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                          >
                            <Star className="w-3.5 h-3.5 fill-current" /> Rate & Review Order
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Cancellation Modal */}
      {cancelModalOrder && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <Ban className="w-5 h-5 text-red-600" />
                <h3 className="text-base font-black text-[#172033]">
                  Cancel Order #{cancelModalOrder.order_number || cancelModalOrder.id.slice(0, 8)}
                </h3>
              </div>
              <button
                onClick={() => setCancelModalOrder(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
                disabled={cancelling}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* PREPARING Warning Alert */}
            {cancelModalOrder.status === 'PREPARING' && (
              <div className="bg-amber-50 border border-amber-300 text-amber-900 p-4 rounded-2xl text-xs space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-amber-800 text-sm">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  Food Preparation In Progress
                </div>
                <p className="leading-relaxed font-semibold">
                  Your food may already be prepared. Cancelling now may result in food wastage.
                </p>
              </div>
            )}

            {cancelError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{cancelError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="block text-xs font-bold text-gray-700">
                Reason for cancellation <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Let us know why you are cancelling..."
                className="w-full text-xs p-3 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-red-500/20 focus:border-red-500 resize-none h-20"
                disabled={cancelling}
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setCancelModalOrder(null)}
                className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-gray-800 rounded-xl hover:bg-gray-100 transition"
                disabled={cancelling}
              >
                Keep Order
              </button>
              <button
                type="button"
                onClick={handleConfirmCancel}
                disabled={cancelling}
                className="px-5 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl transition shadow-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                {cancelling
                  ? 'Cancelling...'
                  : cancelModalOrder.status === 'PREPARING'
                  ? 'Yes, Cancel Order'
                  : 'Cancel Order'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Admin-Assisted Cancellation Request Modal for READY orders */}
      {requestCancelOrder && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-600" />
                <h3 className="text-base font-black text-[#172033]">
                  Request order cancellation
                </h3>
              </div>
              <button
                onClick={() => setRequestCancelOrder(null)}
                className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {requestSuccessMsg ? (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-2xl text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span className="font-bold">{requestSuccessMsg}</span>
              </div>
            ) : (
              <>
                <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3.5 rounded-2xl text-xs space-y-1">
                  <p className="font-bold">Your order is already prepared.</p>
                  <p className="text-amber-700">Cancellation requires Admin approval and may result in food wastage.</p>
                </div>

                {requestError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{requestError}</span>
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-700">Reason</label>
                  <select
                    value={requestReason}
                    onChange={(e) => setRequestReason(e.target.value)}
                    className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white"
                  >
                    <option value="Changed my mind">Changed my mind</option>
                    <option value="Ordered by mistake">Ordered by mistake</option>
                    <option value="Cannot receive the order">Cannot receive the order</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                {requestReason === 'Other' && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-gray-700">Short Explanation</label>
                    <textarea
                      value={requestCustomerNote}
                      onChange={(e) => setRequestCustomerNote(e.target.value)}
                      placeholder="Please explain why you need to cancel..."
                      rows={2}
                      maxLength={500}
                      className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
                    />
                  </div>
                )}

                <div className="flex gap-2 pt-2 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => setRequestCancelOrder(null)}
                    className="flex-1 py-2.5 rounded-xl border border-gray-200 text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
                  >
                    Keep Order
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmRequestCancel}
                    disabled={requestSubmitting}
                    className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition disabled:opacity-50"
                  >
                    {requestSubmitting ? 'Submitting...' : 'Request Cancellation'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Review Modal */}
      {reviewOrder && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="text-base font-black text-[#172033]">
                Rate Your KitchenVerse Meal
              </h3>
              <button
                onClick={() => setReviewOrder(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {reviewSuccess ? (
              <div className="text-center py-6 space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto" />
                <p className="text-sm font-bold text-gray-800">Thank you for your feedback!</p>
                <p className="text-xs text-gray-500">Your review helps maintain kitchen culinary quality.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmitReview} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-600 mb-2">Rating</label>
                  <div className="flex items-center gap-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onClick={() => setRating(star)}
                        className="p-1 hover:scale-110 transition"
                      >
                        <Star
                          className={`w-7 h-7 ${
                            rating >= star
                              ? 'text-amber-400 fill-amber-400'
                              : 'text-gray-200'
                          }`}
                        />
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-600 mb-1.5">
                    Your Review & Comments
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Tell us about the taste, packaging, and presentation..."
                    value={reviewComment}
                    onChange={(e) => setReviewComment(e.target.value)}
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-[#166534]"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setReviewOrder(null)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reviewSubmitting}
                    className="bg-[#166534] hover:bg-[#15803d] text-white px-5 py-2 rounded-xl text-xs font-bold transition shadow-xs disabled:opacity-50"
                  >
                    {reviewSubmitting ? 'Submitting...' : 'Submit Review'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Order Location Confirmation Modal */}
      {locationConfirmOrder && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-black text-gray-900">
                  Confirm Delivery Location
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Set or adjust your doorstep delivery pin for Order #{locationConfirmOrder.order_number || locationConfirmOrder.id.slice(0, 8)}.
                </p>
              </div>
              <button
                onClick={() => setLocationConfirmOrder(null)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {locationError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{locationError}</span>
              </div>
            )}

            <CustomerLocationPicker
              currentLocation={
                confirmLoc ||
                (locationConfirmOrder.delivery_latitude != null && locationConfirmOrder.delivery_longitude != null
                  ? {
                      address: locationConfirmOrder.delivery_address_text || '',
                      latitude: locationConfirmOrder.delivery_latitude,
                      longitude: locationConfirmOrder.delivery_longitude,
                    }
                  : null)
              }
              onLocationChange={(loc) => setConfirmLoc(loc)}
            />

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setLocationConfirmOrder(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!confirmLoc || locationSaving}
                onClick={handleSaveOrderLocation}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-[#166534] hover:bg-[#15803d] disabled:opacity-50 text-white transition shadow-sm"
              >
                {locationSaving ? 'Saving...' : 'Confirm Location'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
